"""Classes for magnetic fields."""

import warnings
from abc import ABC, abstractmethod

import numpy as np
import scipy.linalg
from netCDF4 import Dataset

from desc.backend import jit, jnp, odeint
from desc.derivatives import Derivative
from desc.geometry.utils import rpz2xyz_vec, xyz2rpz
from desc.grid import Grid
from desc.interpolate import _approx_df, interp2d, interp3d
from desc.io import IOAble


# TODO: vectorize this over multiple coils
def biot_savart(eval_pts, coil_pts, current):
    """Biot-Savart law following [1].

    Parameters
    ----------
    eval_pts : array-like shape(n,3)
        evaluation points in cartesian coordinates
    coil_pts : array-like shape(m,3)
        points in cartesian space defining coil, should be closed curve
    current : float
        current through the coil

    Returns
    -------
    B : ndarray, shape(n,3)
        magnetic field in cartesian components at specified points

    [1] Hanson & Hirshman, "Compact expressions for the Biot-Savart
    fields of a filamentary segment" (2002)
    """
    dvec = jnp.diff(coil_pts, axis=0)
    L = jnp.linalg.norm(dvec, axis=-1)

    Ri_vec = eval_pts[jnp.newaxis, :] - coil_pts[:-1, jnp.newaxis, :]
    Ri = jnp.linalg.norm(Ri_vec, axis=-1)
    Rf = jnp.linalg.norm(
        eval_pts[jnp.newaxis, :] - coil_pts[1:, jnp.newaxis, :], axis=-1
    )
    Ri_p_Rf = Ri + Rf

    # 1.0e-7 == mu_0/(4 pi)
    Bmag = (
        1.0e-7
        * current
        * 2.0
        * Ri_p_Rf
        / (Ri * Rf * (Ri_p_Rf * Ri_p_Rf - (L * L)[:, jnp.newaxis]))
    )

    # cross product of L*hat(eps)==dvec with Ri_vec, scaled by Bmag
    vec = jnp.cross(dvec[:, jnp.newaxis, :], Ri_vec, axis=-1)
    B = jnp.sum(Bmag[:, :, jnp.newaxis] * vec, axis=0)
    return B


class MagneticField(IOAble, ABC):
    """Base class for all magnetic fields.

    Subclasses must implement the "compute_magnetic_field" method

    """

    _io_attrs_ = []

    def __mul__(self, x):
        if np.isscalar(x):
            return ScaledMagneticField(x, self)
        else:
            return NotImplemented

    def __rmul__(self, x):
        return self.__mul__(x)

    def __add__(self, x):
        if isinstance(x, MagneticField):
            return SumMagneticField(self, x)
        else:
            return NotImplemented

    def __neg__(self):
        return ScaledMagneticField(-1, self)

    def __sub__(self, x):
        return self.__add__(-x)

    @abstractmethod
    def compute_magnetic_field(self, coords, params={}, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : dict, optional
            parameters to pass to scalar potential function
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            magnetic field at specified points

        """

    def __call__(self, coords, params={}, basis="rpz"):
        """Compute magnetic field at a set of points."""
        return self.compute_magnetic_field(coords, params, basis)


class ScaledMagneticField(MagneticField):
    """Magnetic field scaled by a scalar value.

    ie B_new = scalar * B_old

    Parameters
    ----------
    scalar : float, int
        scaling factor for magnetic field
    field : MagneticField
        base field to be scaled

    """

    _io_attrs = MagneticField._io_attrs_ + ["_field", "_scalar"]

    def __init__(self, scalar, field):
        assert np.isscalar(scalar), "scalar must actually be a scalar value"
        assert isinstance(
            field, MagneticField
        ), "field should be a subclass of MagneticField, got type {}".format(
            type(field)
        )
        self._scalar = scalar
        self._field = field

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : tuple, optional
            parameters to pass to underlying field
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            scaled magnetic field at specified points
        """
        return self._scalar * self._field.compute_magnetic_field(coords, params, basis)


class SumMagneticField(MagneticField):
    """Sum of two or more magnetic field sources.

    Parameters
    ----------
    fields : MagneticField
        two or more MagneticFields to add together
    """

    _io_attrs = MagneticField._io_attrs_ + ["_fields"]

    def __init__(self, *fields):
        assert all(
            [isinstance(field, MagneticField) for field in fields]
        ), "fields should each be a subclass of MagneticField, got {}".format(
            [type(field) for field in fields]
        )
        self._fields = fields

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : list or tuple of dict, optional
            parameters to pass to underlying fields. If None,
            uses the default parameters for each field. If a list or tuple, should have
            one entry for each component field.
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            scaled magnetic field at specified points
        """
        if params is None:
            params = [None] * len(self._fields)
        if isinstance(params, dict):
            params = [params]
        B = 0
        for i, field in enumerate(self._fields):
            B += field.compute_magnetic_field(coords, params[i % len(params)], basis)
        return B


class ToroidalMagneticField(MagneticField):
    """Magnetic field purely in the toroidal (phi) direction.

    Magnitude is B0*R0/R where R0 is the major radius of the axis and B0
    is the field strength on axis

    Parameters
    ----------
    B0 : float
        field strength on axis
    R0 : major radius of axis

    """

    _io_attrs_ = MagneticField._io_attrs_ + ["_B0", "_R0"]

    def __init__(self, B0, R0):
        assert np.isscalar(B0), "B0 must be a scalar"
        assert np.isscalar(R0), "R0 must be a scalar"
        self._B0 = B0
        self._R0 = R0

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : tuple, optional
            unused by this method
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            magnetic field at specified points

        """
        assert basis.lower() in ["rpz", "xyz"]
        if isinstance(coords, Grid):
            coords = coords.nodes
        coords = jnp.atleast_2d(coords)
        if basis == "xyz":
            coords = xyz2rpz(coords)
        bp = self._B0 * self._R0 / coords[:, 0]
        brz = jnp.zeros_like(bp)
        B = jnp.array([brz, bp, brz]).T
        if basis == "xyz":
            B = rpz2xyz_vec(B, phi=coords[:, 1])

        return B


class VerticalMagneticField(MagneticField):
    """Uniform magnetic field purely in the vertical (Z) direction.

    Parameters
    ----------
    B0 : float
        field strength

    """

    _io_attrs_ = MagneticField._io_attrs_ + ["_B0"]

    def __init__(self, B0):
        assert np.isscalar(B0), "B0 must be a scalar"
        self._B0 = B0

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : tuple, optional
            unused by this method
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            magnetic field at specified points

        """
        assert basis.lower() in ["rpz", "xyz"]
        if isinstance(coords, Grid):
            coords = coords.nodes
        coords = jnp.atleast_2d(coords)
        if basis == "xyz":
            coords = xyz2rpz(coords)
        bz = self._B0 * jnp.ones_like(coords[:, 2])
        brp = jnp.zeros_like(bz)
        B = jnp.array([brp, brp, bz]).T
        if basis == "xyz":
            B = rpz2xyz_vec(B, phi=coords[:, 1])

        return B


class PoloidalMagneticField(MagneticField):
    """Pure poloidal magnetic field (ie in theta direction).

    Field strength is B0*iota*r/R0 where B0 is the toroidal field on axis,
    R0 is the major radius of the axis, iota is the desired rotational transform,
    and r is the minor radius centered on the magnetic axis.

    Combined with a toroidal field with the same B0 and R0, creates an
    axisymmetric field with rotational transform iota

    Note that the divergence of such a field is proportional to Z/R so is generally
    nonzero except on the midplane, but still serves as a useful test case

    Parameters
    ----------
    B0 : float
        field strength on axis
    R0 : float
        major radius of magnetic axis
    iota : float
        desired rotational transform

    """

    _io_attrs_ = MagneticField._io_attrs_ + ["_B0", "_R0", "_iota"]

    def __init__(self, B0, R0, iota):
        assert np.isscalar(B0), "B0 must be a scalar"
        assert np.isscalar(R0), "R0 must be a scalar"
        assert np.isscalar(iota), "iota must be a scalar"
        self._B0 = B0
        self._R0 = R0
        self._iota = iota

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : tuple, optional
            unused by this method
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            magnetic field at specified points, in cylindrical form [BR, Bphi,BZ]

        """
        assert basis.lower() in ["rpz", "xyz"]
        if isinstance(coords, Grid):
            coords = coords.nodes
        coords = jnp.atleast_2d(coords)
        if basis == "xyz":
            coords = xyz2rpz(coords)

        R, phi, Z = coords.T
        r = jnp.sqrt((R - self._R0) ** 2 + Z**2)
        theta = jnp.arctan2(Z, R - self._R0)
        br = -r * jnp.sin(theta)
        bp = jnp.zeros_like(br)
        bz = r * jnp.cos(theta)
        bmag = self._B0 * self._iota / self._R0
        B = bmag * jnp.array([br, bp, bz]).T
        if basis == "xyz":
            B = rpz2xyz_vec(B, phi=coords[:, 1])

        return B


class SplineMagneticField(MagneticField):
    """Magnetic field from precomputed values on a grid.

    Parameters
    ----------
    R : array-like, size(NR)
        R coordinates where field is specified
    phi : array-like, size(Nphi)
        phi coordinates where field is specified
    Z : array-like, size(NZ)
        Z coordinates where field is specified
    BR : array-like, shape(NR,Nphi,NZ)
        radial magnetic field on grid
    Bphi : array-like, shape(NR,Nphi,NZ)
        toroidal magnetic field on grid
    BZ : array-like, shape(NR,Nphi,NZ)
        vertical magnetic field on grid
    method : str
        interpolation method
    extrap : bool
        whether to extrapolate beyond the domain of known field values or return nan
    period : float
        period in the toroidal direction (usually 2pi/NFP)

    """

    _io_attrs_ = [
        "_R",
        "_phi",
        "_Z",
        "_BR",
        "_Bphi",
        "_BZ",
        "_method",
        "_extrap",
        "_period",
        "_derivs",
        "_axisym",
    ]

    def __init__(self, R, phi, Z, BR, Bphi, BZ, method="cubic", extrap=False, period=0):

        R, phi, Z = np.atleast_1d(R), np.atleast_1d(phi), np.atleast_1d(Z)
        assert R.ndim == 1
        assert phi.ndim == 1
        assert Z.ndim == 1
        BR, Bphi, BZ = np.atleast_3d(BR), np.atleast_3d(Bphi), np.atleast_3d(BZ)
        assert BR.shape == Bphi.shape == BZ.shape == (R.size, phi.size, Z.size)

        self._R = R
        self._phi = phi
        if len(phi) == 1:
            self._axisym = True
        else:
            self._axisym = False
        self._Z = Z
        self._BR = BR
        self._Bphi = Bphi
        self._BZ = BZ

        self._method = method
        self._extrap = extrap
        self._period = period

        self._derivs = {}
        self._derivs["BR"] = self._approx_derivs(self._BR)
        self._derivs["Bphi"] = self._approx_derivs(self._Bphi)
        self._derivs["BZ"] = self._approx_derivs(self._BZ)

    def _approx_derivs(self, Bi):
        tempdict = {}
        tempdict["fx"] = _approx_df(self._R, Bi, self._method, 0)
        tempdict["fz"] = _approx_df(self._Z, Bi, self._method, 2)
        tempdict["fxz"] = _approx_df(self._Z, tempdict["fx"], self._method, 2)
        if self._axisym:
            tempdict["fy"] = jnp.zeros_like(tempdict["fx"])
            tempdict["fxy"] = jnp.zeros_like(tempdict["fx"])
            tempdict["fyz"] = jnp.zeros_like(tempdict["fx"])
            tempdict["fxyz"] = jnp.zeros_like(tempdict["fx"])
        else:
            tempdict["fy"] = _approx_df(self._phi, Bi, self._method, 1)
            tempdict["fxy"] = _approx_df(self._phi, tempdict["fx"], self._method, 1)
            tempdict["fyz"] = _approx_df(self._Z, tempdict["fy"], self._method, 2)
            tempdict["fxyz"] = _approx_df(self._Z, tempdict["fxy"], self._method, 2)
        if self._axisym:
            for key, val in tempdict.items():
                tempdict[key] = val[:, 0, :]
        return tempdict

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : tuple, optional
            unused by this method
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            magnetic field at specified points, in cylindrical form [BR, Bphi,BZ]

        """
        assert basis.lower() in ["rpz", "xyz"]
        if isinstance(coords, Grid):
            coords = coords.nodes
        coords = jnp.atleast_2d(coords)
        if basis == "xyz":
            coords = xyz2rpz(coords)
        Rq, phiq, Zq = coords.T
        if self._axisym:
            BRq = interp2d(
                Rq,
                Zq,
                self._R,
                self._Z,
                self._BR[:, 0, :],
                self._method,
                (0, 0),
                self._extrap,
                (None, None),
                **self._derivs["BR"],
            )
            Bphiq = interp2d(
                Rq,
                Zq,
                self._R,
                self._Z,
                self._Bphi[:, 0, :],
                self._method,
                (0, 0),
                self._extrap,
                (None, None),
                **self._derivs["Bphi"],
            )
            BZq = interp2d(
                Rq,
                Zq,
                self._R,
                self._Z,
                self._BZ[:, 0, :],
                self._method,
                (0, 0),
                self._extrap,
                (None, None),
                **self._derivs["BZ"],
            )

        else:
            BRq = interp3d(
                Rq,
                phiq,
                Zq,
                self._R,
                self._phi,
                self._Z,
                self._BR,
                self._method,
                (0, 0, 0),
                self._extrap,
                (None, self._period, None),
                **self._derivs["BR"],
            )
            Bphiq = interp3d(
                Rq,
                phiq,
                Zq,
                self._R,
                self._phi,
                self._Z,
                self._Bphi,
                self._method,
                (0, 0, 0),
                self._extrap,
                (None, self._period, None),
                **self._derivs["Bphi"],
            )
            BZq = interp3d(
                Rq,
                phiq,
                Zq,
                self._R,
                self._phi,
                self._Z,
                self._BZ,
                self._method,
                (0, 0, 0),
                self._extrap,
                (None, self._period, None),
                **self._derivs["BZ"],
            )
        B = jnp.array([BRq, Bphiq, BZq]).T
        if basis == "xyz":
            B = rpz2xyz_vec(B, phi=coords[:, 1])
        return B

    @classmethod
    def from_mgrid(
        cls, mgrid_file, extcur=1, method="cubic", extrap=False, period=None
    ):
        """Create a SplineMagneticField from an "mgrid" file from MAKEGRID.

        Parameters
        ----------
        mgrid_file : str or path-like
            path to mgrid file in netCDF format
        extcur : array-like
            currents for each subset of the field
        method : str
            interpolation method
        extrap : bool
            whether to extrapolate beyond the domain of known field values or return nan
        period : float
            period in the toroidal direction (usually 2pi/NFP)

        """
        mgrid = Dataset(mgrid_file, "r")
        ir = int(mgrid["ir"][()])
        jz = int(mgrid["jz"][()])
        kp = int(mgrid["kp"][()])
        nfp = mgrid["nfp"][()].data
        nextcur = int(mgrid["nextcur"][()])
        rMin = mgrid["rmin"][()]
        rMax = mgrid["rmax"][()]
        zMin = mgrid["zmin"][()]
        zMax = mgrid["zmax"][()]

        br = np.zeros([kp, jz, ir])
        bp = np.zeros([kp, jz, ir])
        bz = np.zeros([kp, jz, ir])
        extcur = np.broadcast_to(extcur, nextcur)
        for i in range(nextcur):

            # apply scaling by currents given in VMEC input file
            scale = extcur[i]

            # sum up contributions from different coils
            coil_id = "%03d" % (i + 1,)
            br[:, :, :] += scale * mgrid["br_" + coil_id][()]
            bp[:, :, :] += scale * mgrid["bp_" + coil_id][()]
            bz[:, :, :] += scale * mgrid["bz_" + coil_id][()]
        mgrid.close()

        # shift axes to correct order
        br = np.moveaxis(br, (0, 1, 2), (1, 2, 0))
        bp = np.moveaxis(bp, (0, 1, 2), (1, 2, 0))
        bz = np.moveaxis(bz, (0, 1, 2), (1, 2, 0))

        # re-compute grid knots in radial and vertical direction
        Rgrid = np.linspace(rMin, rMax, ir)
        Zgrid = np.linspace(zMin, zMax, jz)
        pgrid = 2.0 * np.pi / (nfp * kp) * np.arange(kp)
        if period is None:
            period = 2 * np.pi / (nfp)

        return cls(Rgrid, pgrid, Zgrid, br, bp, bz, method, extrap, period)

    @classmethod
    def from_field(
        cls, field, R, phi, Z, params={}, method="cubic", extrap=False, period=None
    ):
        """Create a splined magnetic field from another field for faster evaluation.

        Parameters
        ----------
        field : MagneticField or callable
            field to interpolate. If a callable, should take a vector of
            cylindrical coordinates and return the field in cylindrical components
        R, phi, Z : ndarray
            1d arrays of interpolation nodes in cylindrical coordinates
        params : dict, optional
            parameters passed to field
        method : str
            spline method for SplineMagneticField
        extrap : bool
            whether to extrapolate splines beyond specified R,phi,Z
        period : float
            period for phi coordinate. Usually 2pi/NFP

        """
        R, phi, Z = map(np.asarray, (R, phi, Z))
        rr, pp, zz = np.meshgrid(R, phi, Z, indexing="ij")
        shp = rr.shape
        coords = np.array([rr.flatten(), pp.flatten(), zz.flatten()]).T
        BR, BP, BZ = field.compute_magnetic_field(coords, params, basis="rpz").T
        return cls(
            R,
            phi,
            Z,
            BR.reshape(shp),
            BP.reshape(shp),
            BZ.reshape(shp),
            method,
            extrap,
            period,
        )


class ScalarPotentialField(MagneticField):
    """Magnetic field due to a scalar magnetic potential in cylindrical coordinates.

    Parameters
    ----------
    potential : callable
        function to compute the scalar potential. Should have a signature of
        the form potential(R,phi,Z,*params) -> ndarray.
        R,phi,Z are arrays of cylindrical coordinates.
    params : dict, optional
        default parameters to pass to potential function

    """

    def __init__(self, potential, params={}):
        self._potential = potential
        self._params = params

    def compute_magnetic_field(self, coords, params=None, basis="rpz"):
        """Compute magnetic field at a set of points.

        Parameters
        ----------
        coords : array-like shape(N,3) or Grid
            cylindrical or cartesian coordinates
        params : dict, optional
            parameters to pass to scalar potential function
        basis : {"rpz", "xyz"}
            basis for input coordinates and returned magnetic field

        Returns
        -------
        field : ndarray, shape(N,3)
            magnetic field at specified points

        """
        assert basis.lower() in ["rpz", "xyz"]
        if isinstance(coords, Grid):
            coords = coords.nodes
        coords = jnp.atleast_2d(coords)
        if basis == "xyz":
            coords = xyz2rpz(coords)
        Rq, phiq, Zq = coords.T

        if (params is None) or (len(params) == 0):
            params = self._params
        r, p, z = coords.T
        funR = lambda x: self._potential(x, p, z, **params)
        funP = lambda x: self._potential(r, x, z, **params)
        funZ = lambda x: self._potential(r, p, x, **params)
        br = Derivative.compute_jvp(funR, 0, (jnp.ones_like(r),), r)
        bp = Derivative.compute_jvp(funP, 0, (jnp.ones_like(p),), p)
        bz = Derivative.compute_jvp(funZ, 0, (jnp.ones_like(z),), z)
        B = jnp.array([br, bp / r, bz]).T
        if basis == "xyz":
            B = rpz2xyz_vec(B, phi=coords[:, 1])
        return B


class DommaschkPotentialField(ScalarPotentialField):
    """Magnetic field due to a Dommaschk scalar magnetic potential in rpz coordinates.

        From Dommaschk 1986 paper https://doi.org/10.1016/0010-4655(86)90109-8

        this is the field due to the dommaschk potential (eq. 1) for
        a given set of m,l indices and their corresponding
        coefficients a_ml, b_ml, c_ml d_ml.

    Parameters
    ----------
    ms : 1D array-like of int
        first indices of V_m_l terms (eq. 12 of reference)
    ls : 1D array-like of int
        second indices of V_m_l terms (eq. 12 of reference)
    a_arr : 1D array-like of float
        a_m_l coefficients of V_m_l terms, which multiply the cos(m*phi)*D_m_l terms
    b_arr : 1D array-like of float
        b_m_l coefficients of V_m_l terms, which multiply the sin(m*phi)*D_m_l terms
    c_arr : 1D array-like of float
        c_m_l coefficients of V_m_l terms, which multiply the cos(m*phi)*N_m_l-1 term
    d_arr : 1D array-like of float
        d_m_l coefficients of V_m_l terms, which multiply the sin(m*phi)*N_m_l-1 terms
    B0: float
        scale strength of the magnetic field's 1/R portion

    """

    def __init__(self, ms, ls, a_arr, b_arr, c_arr, d_arr, B0=1.0):
        params = {}
        params["ms"] = ms
        params["ls"] = ls
        params["a_arr"] = a_arr
        params["b_arr"] = b_arr
        params["c_arr"] = c_arr
        params["d_arr"] = d_arr
        params["B0"] = B0

        super().__init__(dommaschk_potential, params)

    @classmethod
    def fit_magnetic_field(cls, field, coords, max_m, max_l):
        """Fit a vacuum magnetic field with a Dommaschk Potential field.

        Parameters
        ----------
            field (MagneticField or callable): magnetic field to fit
            coords (ndarray): shape (num_nodes,3) of R,phi,Z points to fit field at
            max_m (int): maximum m to use for Dommaschk Potentials
            max_l (int): maximum l to use for Dommaschk Potentials
        """
        # We seek c in  Ac = b
        # A will be the BR, Bphi and BZ from each individual
        # dommaschk potential basis function evaluated at each node
        # c is the dommaschk potential coefficients
        # c will be [B0, a_00, a_10, a_01, a_11... etc]
        # b is the magnetic field at each node which we are fitting

        if not isinstance(field, MagneticField):
            B = field(coords)
        else:
            B = field.compute_magnetic_field(coords)

        num_nodes = coords.shape[0]  # number of coordinate nodes

        # we will have the rhs be 3*num_nodes in length (bc of vector B)

        #########
        # make b
        #########

        rhs = jnp.vstack((B[:, 0], B[:, 1], B[:, 2])).T.flatten(order="F")

        #####################
        # b is made, now do A
        #####################
        num_modes = 1 + (max_l + 1) * (max_m + 1) * 4
        # TODO: technically we can drop some modes
        # since if max_l=0, there are only ever nonzero terms
        # for a and b
        # and if max_m=0, there are only ever nonzero terms
        # for a and c
        # but since we are only fitting in a least squares sense,
        # and max_l and max_m should probably be both nonzero anyways,
        # this is not an issue right now

        A = jnp.zeros((3 * num_nodes, num_modes))

        # B0 first, the scale magnitude of the 1/R field
        Bf_temp = DommaschkPotentialField(0, 0, 0, 0, 0, 0, 1)
        B_temp = Bf_temp.compute_magnetic_field(coords)
        for i in range(B_temp.shape[1]):
            A = A.at[i * num_nodes : (i + 1) * num_nodes, 0:1].add(
                B_temp[:, i].reshape(num_nodes, 1)
            )

        # mode numbers
        ms = []
        ls = []

        # order of coeffs are a_ml and
        coef_ind = 1
        for l in range(max_l + 1):
            for m in range(max_m + 1):
                ms.append(m)
                ls.append(l)
                for which_coef in range(4):
                    a = 1 if which_coef == 0 else 0
                    b = 1 if which_coef == 1 else 0
                    c = 1 if which_coef == 2 else 0
                    d = 1 if which_coef == 3 else 0

                    Bf_temp = DommaschkPotentialField(m, l, a, b, c, d, 0)
                    B_temp = Bf_temp.compute_magnetic_field(coords)
                    for i in range(B_temp.shape[1]):
                        A = A.at[
                            i * num_nodes : (i + 1) * num_nodes, coef_ind : coef_ind + 1
                        ].add(B_temp[:, i].reshape(num_nodes, 1))
                    coef_ind += 1

        # now solve Ac=b for the coefficients c

        Ainv = scipy.linalg.pinv(A, rcond=None)
        c = jnp.matmul(Ainv, rhs)

        res = jnp.matmul(A, c) - rhs
        print(f"Mean Residual of fit: {jnp.mean(res):1.4e} T")
        print(f"Max Residual of fit: {jnp.max(res):1.4e} T")
        print(f"Min Residual of fit: {jnp.min(res):1.4e} T")

        # recover the params from the c coefficient vector
        B0 = c[0]
        a_arr = c[1::4]
        b_arr = c[2::4]
        c_arr = c[3::4]
        d_arr = c[4::4]
        return cls(ms, ls, a_arr, b_arr, c_arr, d_arr, B0)


def field_line_integrate(
    r0, z0, phis, field, params={}, rtol=1e-8, atol=1e-8, maxstep=1000
):
    """Trace field lines by integration.

    Parameters
    ----------
    r0, z0 : array-like
        initial starting coordinates for r,z on phi=phis[0] plane
    phis : array-like
        strictly increasing array of toroidal angles to output r,z at
        Note that phis is the geometric toroidal angle for positive Bphi,
        and the negative toroidal angle for negative Bphi
    field : MagneticField
        source of magnetic field to integrate
    params: dict
        parameters passed to field
    rtol, atol : float
        relative and absolute tolerances for ode integration
    maxstep : int
        maximum number of steps between different phis

    Returns
    -------
    r, z : ndarray
        arrays of r, z coordinates at specified phi angles

    """
    r0, z0, phis = map(jnp.asarray, (r0, z0, phis))
    assert r0.shape == z0.shape, "r0 and z0 must have the same shape"
    rshape = r0.shape
    r0 = r0.flatten()
    z0 = z0.flatten()
    x0 = jnp.array([r0, phis[0] * jnp.ones_like(r0), z0]).T

    @jit
    def odefun(rpz, s):
        rpz = rpz.reshape((3, -1)).T
        r = rpz[:, 0]
        br, bp, bz = field.compute_magnetic_field(rpz, params, basis="rpz").T
        return jnp.array(
            [r * br / bp * jnp.sign(bp), jnp.sign(bp), r * bz / bp * jnp.sign(bp)]
        ).squeeze()

    intfun = lambda x: odeint(odefun, x, phis, rtol=rtol, atol=atol, mxstep=maxstep)
    x = jnp.vectorize(intfun, signature="(k)->(n,k)")(x0)
    r = x[:, :, 0].T.reshape((len(phis), *rshape))
    z = x[:, :, 2].T.reshape((len(phis), *rshape))
    return r, z


### Dommaschk potential utility functions ###

# based off Representations for vacuum potentials in stellarators
# https://doi.org/10.1016/0010-4655(86)90109-8

# written with naive for loops initially and can jaxify later


def gamma(n):
    """Gamma function, only implemented for integers (equiv to factorial of (n-1))."""
    return jnp.prod(jnp.arange(1, n))


def alpha(m, n):
    """Alpha of eq 27, 1st ind comes from C_m_k, 2nd is the subscript of alpha."""
    return (-1) ** n / (gamma(m + n + 1) * gamma(n + 1) * 2.0 ** (2 * n + m))


def alphastar(m, n):
    """Alphastar of eq 27, 1st ind comes from C_m_k, 2nd is the subscript of alpha."""
    return (2 * n + m) * alpha(m, n)


def beta(m, n):
    """Beta of eq 28."""
    return gamma(m - n) / (gamma(n + 1) * 2.0 ** (2 * n - m + 1))


def betastar(m, n):
    """Betastar of eq 28."""
    return (2 * n - m) * beta(m, n)


# TODO: generalize the below 2 terms according to
# eqns 31,32 so they are valid for all indices of m,k>=0?
def CD_m_k(R, m, k):
    """Eq 25 of Dommaschk paper."""
    if m == k == 0:  # the initial term, defined in eqn 8
        return jnp.ones_like(R)
    else:
        if m > k:
            warnings.warn("Sum only valid for m > k!")
    sum1 = 0
    for j in range(k + 1):
        sum1 += alpha(m, j) * betastar(m, k - j) * R ** (2 * j)
    sum2 = 0
    for j in range(k + 1):
        sum2 += alphastar(m, k - j) * beta(m, j) * R ** (2 * j)
    return -(R ** (m)) * sum1 + R ** (-m) * sum2


def CN_m_k(R, m, k):
    """Eq 26 of Dommaschk paper."""
    if m == k == 0:  # the initial term, defined in eqn 9
        return jnp.log(R)
    else:
        if m > k:
            warnings.warn("Sum only valid for m > k!")

    sum1 = 0
    for j in range(k + 1):
        sum1 += alpha(m, j) * beta(m, k - j) * R ** (2 * j)
    sum2 = 0
    for j in range(k + 1):
        sum2 += alpha(m, k - j) * beta(m, j) * R ** (2 * j)
    return R ** (m) * sum1 - R ** (-m) * sum2


def D_m_n(R, Z, m, n):
    """D_m_n term in eqn 8 of Dommaschk paper."""
    # the sum comes from fact that D_mn = I_mn and the def of I_mn in eq 2 of the paper

    max_ind = (
        n // 2
    )  # find the top of the summation ind, the range should be up to and including this
    # i.e. this is the index of k at
    # which 2k<=n, and 2(max_ind+1) would be > n and so not included in the sum
    result = 0
    for k in range(max_ind + 1):
        result += Z ** (n - 2 * k) / gamma(n - 2 * k + 1) * CD_m_k(R, m, k)
    return result


def N_m_n(R, Z, m, n):
    """N_m_n term in eqn 9 of Dommaschk paper."""
    # the sum comes from fact that N_mn = I_mn and the def of I_mn in eq 2 of the paper

    max_ind = (
        n // 2
    )  # find the top of the summation ind, the range should be up to and including this
    # i.e. this is the index of k at
    #  which 2k<=n, and 2(max_ind+1) would be > n and so not included in the sum
    result = 0
    for k in range(max_ind + 1):
        result += Z ** (n - 2 * k) / gamma(n - 2 * k + 1) * CN_m_k(R, m, k)
    return result


# TODO: note on how stell sym affects, i.e.
# if stell sym then a=d=0 for even l and b=c=0 for odd l


def V_m_l(R, phi, Z, m, l, a, b, c, d):
    """Eq 12 of Dommaschk paper.

    Parameters
    ----------
    R,phi,Z : array-like
        Cylindrical coordinates (1-D arrays of each of size num_eval_pts)
            to evaluate the Dommaschk potential term at.
    m : int
        first index of V_m_l term
    l : int
        second index of V_m_l term
    a : float
        a_m_l coefficient of V_m_l term, which multiplies cos(m*phi)*D_m_l
    b : float
        b_m_l coefficient of V_m_l term, which multiplies sin(m*phi)*D_m_l
    c : float
        c_m_l coefficient of V_m_l term, which multiplies cos(m*phi)*N_m_l-1
    d : float
        d_m_l coefficient of V_m_l term, which multiplies sin(m*phi)*N_m_l-1

    Returns
    -------
    value : array-like
        Value of this V_m_l term evaluated at the given R,phi,Z points
        (same size as the size of the given R,phi, or Z arrays).

    """
    return (a * jnp.cos(m * phi) + b * jnp.sin(m * phi)) * D_m_n(R, Z, m, l) + (
        c * jnp.cos(m * phi) + d * jnp.sin(m * phi)
    ) * N_m_n(R, Z, m, l - 1)


def dommaschk_potential(R, phi, Z, ms, ls, a_arr, b_arr, c_arr, d_arr, B0=1):
    """Eq 1 of Dommaschk paper.

        this is the total dommaschk potential for
        a given set of m,l indices and their corresponding
        coefficients a_ml, b_ml, c_ml d_ml.

    Parameters
    ----------
    R,phi,Z : array-like
        Cylindrical coordinates (1-D arrays of each of size num_eval_pts)
        to evaluate the Dommaschk potential term at.
    ms : 1D array-like of int
        first indices of V_m_l terms
    ls : 1D array-like of int
        second indices of V_m_l terms
    a_arr : 1D array-like of float
        a_m_l coefficients of V_m_l terms, which multiplies cos(m*phi)*D_m_l
    b_arr : 1D array-like of float
        b_m_l coefficients of V_m_l terms, which multiplies sin(m*phi)*D_m_l
    c_arr : 1D array-like of float
        c_m_l coefficients of V_m_l terms, which multiplies cos(m*phi)*N_m_l-1
    d_arr : 1D array-like of float
        d_m_l coefficients of V_m_l terms, which multiplies sin(m*phi)*N_m_l-1
    B0: float, toroidal magnetic field strength scale, this is the strength of the
        1/R part of the magnetic field and is the Bphi at R=1.

    Returns
    -------
    value : array-like
        Value of the total dommaschk potential evaluated
        at the given R,phi,Z points
        (same size as the size of the given R,phi, Z arrays).
    """
    value = B0 * phi  # phi term

    # make sure all are 1D arrays
    ms = jnp.atleast_1d(ms)
    ls = jnp.atleast_1d(ls)
    a_arr = jnp.atleast_1d(a_arr)
    b_arr = jnp.atleast_1d(b_arr)
    c_arr = jnp.atleast_1d(c_arr)
    d_arr = jnp.atleast_1d(d_arr)

    assert (
        ms.size == ls.size == a_arr.size == b_arr.size == c_arr.size == d_arr.size
    ), "Passed in arrays must all be of the same size!"

    for m, l, a, b, c, d in zip(ms, ls, a_arr, b_arr, c_arr, d_arr):
        value += V_m_l(R, phi, Z, m, l, a, b, c, d)
    return value
