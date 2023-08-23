"""Classes for parameterized 3D space curves."""

import numbers

import numpy as np

from desc.backend import jnp, put
from desc.basis import FourierSeries
from desc.grid import LinearGrid
from desc.optimizable import optimizable_parameter
from desc.transform import Transform
from desc.utils import copy_coeffs

from .core import Curve

__all__ = [
    "FourierRZCurve",
    "FourierXYZCurve",
    "FourierPlanarCurve",
]


class FourierRZCurve(Curve):
    """Curve parameterized by Fourier series for R,Z in terms of toroidal angle phi.

    Parameters
    ----------
    R_n, Z_n: array-like
        Fourier coefficients for R, Z.
    modes_R : array-like, optional
        Mode numbers associated with R_n. If not given defaults to [-n:n].
    modes_Z : array-like, optional
        Mode numbers associated with Z_n, If not given defaults to modes_R.
    NFP : int
        Number of field periods.
    sym : bool
        Whether to enforce stellarator symmetry.
    name : str
        Name for this curve.

    """

    _io_attrs_ = Curve._io_attrs_ + [
        "_R_n",
        "_Z_n",
        "_R_basis",
        "_Z_basis",
        "_sym",
        "_NFP",
    ]

    def __init__(
        self,
        R_n=10,
        Z_n=0,
        modes_R=None,
        modes_Z=None,
        NFP=1,
        sym="auto",
        name="",
    ):
        super().__init__(name)
        R_n, Z_n = np.atleast_1d(R_n), np.atleast_1d(Z_n)
        if modes_R is None:
            modes_R = np.arange(-(R_n.size // 2), R_n.size // 2 + 1)
        if modes_Z is None:
            modes_Z = modes_R

        if R_n.size == 0:
            raise ValueError("At least 1 coefficient for R must be supplied")
        if Z_n.size == 0:
            Z_n = np.array([0.0])
            modes_Z = np.array([0])

        modes_R, modes_Z = np.asarray(modes_R), np.asarray(modes_Z)

        assert issubclass(modes_R.dtype.type, np.integer)
        assert issubclass(modes_Z.dtype.type, np.integer)

        if sym == "auto":
            if np.all(R_n[modes_R < 0] == 0) and np.all(Z_n[modes_Z >= 0] == 0):
                sym = True
            else:
                sym = False
        self._sym = sym
        NR = np.max(abs(modes_R))
        NZ = np.max(abs(modes_Z))
        N = max(NR, NZ)
        self._NFP = NFP
        self._R_basis = FourierSeries(N, NFP, sym="cos" if sym else False)
        self._Z_basis = FourierSeries(N, NFP, sym="sin" if sym else False)

        self._R_n = copy_coeffs(R_n, modes_R, self.R_basis.modes[:, 2])
        self._Z_n = copy_coeffs(Z_n, modes_Z, self.Z_basis.modes[:, 2])

    @property
    def sym(self):
        """Whether this curve has stellarator symmetry."""
        return self._sym

    @property
    def R_basis(self):
        """Spectral basis for R_Fourier series."""
        return self._R_basis

    @property
    def Z_basis(self):
        """Spectral basis for Z_Fourier series."""
        return self._Z_basis

    @property
    def NFP(self):
        """Number of field periods."""
        return self._NFP

    @NFP.setter
    def NFP(self, new):
        assert (
            isinstance(new, numbers.Real) and int(new) == new and new > 0
        ), f"NFP should be a positive integer, got {type(new)}"
        self.change_resolution(NFP=new)

    @property
    def N(self):
        """Maximum mode number."""
        return max(self.R_basis.N, self.Z_basis.N)

    def change_resolution(self, N=None, NFP=None, sym=None):
        """Change the maximum toroidal resolution."""
        if (
            ((N is not None) and (N != self.N))
            or ((NFP is not None) and (NFP != self.NFP))
            or (sym is not None)
            and (sym != self.sym)
        ):
            self._NFP = NFP if NFP is not None else self.NFP
            self._sym = sym if sym is not None else self.sym
            N = N if N is not None else self.N
            R_modes_old = self.R_basis.modes
            Z_modes_old = self.Z_basis.modes
            self.R_basis.change_resolution(
                N=N, NFP=self.NFP, sym="cos" if self.sym else self.sym
            )
            self.Z_basis.change_resolution(
                N=N, NFP=self.NFP, sym="sin" if self.sym else self.sym
            )
            self.R_n = copy_coeffs(self.R_n, R_modes_old, self.R_basis.modes)
            self.Z_n = copy_coeffs(self.Z_n, Z_modes_old, self.Z_basis.modes)

    def get_coeffs(self, n):
        """Get Fourier coefficients for given mode number(s)."""
        n = np.atleast_1d(n).astype(int)
        R = np.zeros_like(n).astype(float)
        Z = np.zeros_like(n).astype(float)

        idxR = np.where(n[:, np.newaxis] == self.R_basis.modes[:, 2])
        idxZ = np.where(n[:, np.newaxis] == self.Z_basis.modes[:, 2])

        R[idxR[0]] = self.R_n[idxR[1]]
        Z[idxZ[0]] = self.Z_n[idxZ[1]]
        return R, Z

    def set_coeffs(self, n, R=None, Z=None):
        """Set specific Fourier coefficients."""
        n, R, Z = np.atleast_1d(n), np.atleast_1d(R), np.atleast_1d(Z)
        R = np.broadcast_to(R, n.shape)
        Z = np.broadcast_to(Z, n.shape)
        for nn, RR, ZZ in zip(n, R, Z):
            if RR is not None:
                idxR = self.R_basis.get_idx(0, 0, nn)
                self.R_n = put(self.R_n, idxR, RR)
            if ZZ is not None:
                idxZ = self.Z_basis.get_idx(0, 0, nn)
                self.Z_n = put(self.Z_n, idxZ, ZZ)

    @optimizable_parameter
    @property
    def R_n(self):
        """Spectral coefficients for R."""
        return self._R_n

    @R_n.setter
    def R_n(self, new):
        if len(new) == self.R_basis.num_modes:
            self._R_n = jnp.asarray(new)
        else:
            raise ValueError(
                f"R_n should have the same size as the basis, got {len(new)} for "
                + f"basis with {self.R_basis.num_modes} modes."
            )

    @optimizable_parameter
    @property
    def Z_n(self):
        """Spectral coefficients for Z."""
        return self._Z_n

    @Z_n.setter
    def Z_n(self, new):
        if len(new) == self.Z_basis.num_modes:
            self._Z_n = jnp.asarray(new)
        else:
            raise ValueError(
                f"Z_n should have the same size as the basis, got {len(new)} for "
                + f"basis with {self.Z_basis.num_modes} modes"
            )

    def to_FourierXYZCurve(self, N=None):
        """Convert to FourierXYZCurve representation.

        Parameters
        ----------
        N : int
            Fourier resolution of the new X,Y,Z representation.
            Default is the resolution of the old R,Z representation.

        Returns
        -------
        curve : FourierXYZCurve
            New representation of the curve parameterized by Fourier series for X,Y,Z.

        """
        if N is None:
            N = max(self.R_basis.N, self.Z_basis.N)
        grid = LinearGrid(N=4 * N, NFP=1, sym=False)
        basis = FourierSeries(N=N, NFP=1, sym=False)
        xyz = self.compute("x", grid=grid, basis="xyz")["x"]
        transform = Transform(grid, basis, build_pinv=True)
        X_n = transform.fit(xyz[:, 0])
        Y_n = transform.fit(xyz[:, 1])
        Z_n = transform.fit(xyz[:, 2])
        return FourierXYZCurve(X_n=X_n, Y_n=Y_n, Z_n=Z_n)


class FourierXYZCurve(Curve):
    """Curve parameterized by Fourier series for X,Y,Z in terms of arbitrary angle phi.

    Parameters
    ----------
    X_n, Y_n, Z_n: array-like
        Fourier coefficients for X, Y, Z
    modes : array-like
        mode numbers associated with X_n etc.
    name : str
        name for this curve

    """

    _io_attrs_ = Curve._io_attrs_ + [
        "_X_n",
        "_Y_n",
        "_Z_n",
        "_X_basis",
        "_Y_basis",
        "_Z_basis",
    ]

    def __init__(
        self,
        X_n=[0, 10, 2],
        Y_n=[0, 0, 0],
        Z_n=[-2, 0, 0],
        modes=None,
        name="",
    ):
        super().__init__(name)
        X_n, Y_n, Z_n = np.atleast_1d(X_n), np.atleast_1d(Y_n), np.atleast_1d(Z_n)
        if modes is None:
            modes = np.arange(-(X_n.size // 2), X_n.size // 2 + 1)
        else:
            modes = np.asarray(modes)

        assert issubclass(modes.dtype.type, np.integer)

        N = np.max(abs(modes))
        self._X_basis = FourierSeries(N, NFP=1, sym=False)
        self._Y_basis = FourierSeries(N, NFP=1, sym=False)
        self._Z_basis = FourierSeries(N, NFP=1, sym=False)
        self._X_n = copy_coeffs(X_n, modes, self.X_basis.modes[:, 2])
        self._Y_n = copy_coeffs(Y_n, modes, self.Y_basis.modes[:, 2])
        self._Z_n = copy_coeffs(Z_n, modes, self.Z_basis.modes[:, 2])

    @property
    def X_basis(self):
        """Spectral basis for X Fourier series."""
        return self._X_basis

    @property
    def Y_basis(self):
        """Spectral basis for Y Fourier series."""
        return self._Y_basis

    @property
    def Z_basis(self):
        """Spectral basis for Z Fourier series."""
        return self._Z_basis

    @property
    def N(self):
        """Maximum mode number."""
        return max(self.X_basis.N, self.Y_basis.N, self.Z_basis.N)

    def change_resolution(self, N=None):
        """Change the maximum angular resolution."""
        if (N is not None) and (N != self.N):
            Xmodes_old = self.X_basis.modes
            Ymodes_old = self.Y_basis.modes
            Zmodes_old = self.Z_basis.modes
            self.X_basis.change_resolution(N=N)
            self.Y_basis.change_resolution(N=N)
            self.Z_basis.change_resolution(N=N)
            self.X_n = copy_coeffs(self.X_n, Xmodes_old, self.X_basis.modes)
            self.Y_n = copy_coeffs(self.Y_n, Ymodes_old, self.Y_basis.modes)
            self.Z_n = copy_coeffs(self.Z_n, Zmodes_old, self.Z_basis.modes)

    def get_coeffs(self, n):
        """Get Fourier coefficients for given mode number(s)."""
        n = np.atleast_1d(n).astype(int)
        X = np.zeros_like(n).astype(float)
        Y = np.zeros_like(n).astype(float)
        Z = np.zeros_like(n).astype(float)

        Xidx = np.where(n[:, np.newaxis] == self.X_basis.modes[:, 2])
        Yidx = np.where(n[:, np.newaxis] == self.Y_basis.modes[:, 2])
        Zidx = np.where(n[:, np.newaxis] == self.Z_basis.modes[:, 2])

        X[Xidx[0]] = self.X_n[Xidx[1]]
        Y[Yidx[0]] = self.Y_n[Yidx[1]]
        Z[Zidx[0]] = self.Z_n[Zidx[1]]
        return X, Y, Z

    def set_coeffs(self, n, X=None, Y=None, Z=None):
        """Set specific Fourier coefficients."""
        n, X, Y, Z = (
            np.atleast_1d(n),
            np.atleast_1d(X),
            np.atleast_1d(Y),
            np.atleast_1d(Z),
        )
        X = np.broadcast_to(X, n.shape)
        Y = np.broadcast_to(Y, n.shape)
        Z = np.broadcast_to(Z, n.shape)
        for nn, XX in zip(n, X):
            idx = self.X_basis.get_idx(0, 0, nn)
            if XX is not None:
                self.X_n = put(self.X_n, idx, XX)

        for nn, YY in zip(n, Y):
            idx = self.Y_basis.get_idx(0, 0, nn)
            if YY is not None:
                self.Y_n = put(self.Y_n, idx, YY)

        for nn, ZZ in zip(n, Z):
            idx = self.Z_basis.get_idx(0, 0, nn)
            if ZZ is not None:
                self.Z_n = put(self.Z_n, idx, ZZ)

    @optimizable_parameter
    @property
    def X_n(self):
        """Spectral coefficients for X."""
        return self._X_n

    @X_n.setter
    def X_n(self, new):
        if len(new) == self.X_basis.num_modes:
            self._X_n = jnp.asarray(new)
        else:
            raise ValueError(
                f"X_n should have the same size as the basis, got {len(new)} for "
                + f"basis with {self.X_basis.num_modes} modes."
            )

    @optimizable_parameter
    @property
    def Y_n(self):
        """Spectral coefficients for Y."""
        return self._Y_n

    @Y_n.setter
    def Y_n(self, new):
        if len(new) == self.Y_basis.num_modes:
            self._Y_n = jnp.asarray(new)
        else:
            raise ValueError(
                f"Y_n should have the same size as the basis, got {len(new)} for "
                + f"basis with {self.Y_basis.num_modes} modes."
            )

    @optimizable_parameter
    @property
    def Z_n(self):
        """Spectral coefficients for Z."""
        return self._Z_n

    @Z_n.setter
    def Z_n(self, new):
        if len(new) == self.Z_basis.num_modes:
            self._Z_n = jnp.asarray(new)
        else:
            raise ValueError(
                f"Z_n should have the same size as the basis, got {len(new)} for "
                + f"basis with {self.Z_basis.num_modes} modes."
            )

    # TODO: to_rz method for converting to FourierRZCurve representation
    # (might be impossible to parameterize with toroidal angle phi)


class FourierPlanarCurve(Curve):
    """Curve that lies in a plane.

    Parameterized by a point (the center of the curve), a vector (normal to the plane),
    and a Fourier series defining the radius from the center as a function of
    a polar angle theta.

    Parameters
    ----------
    center : array-like, shape(3,)
        x,y,z coordinates of center of curve
    normal : array-like, shape(3,)
        x,y,z components of normal vector to planar surface
    r_n : array-like
        Fourier coefficients for radius from center as function of polar angle
    modes : array-like
        mode numbers associated with r_n
    name : str
        name for this curve

    """

    _io_attrs_ = Curve._io_attrs_ + [
        "_r_n",
        "_center",
        "_normal",
        "_r_basis",
    ]

    # Reference frame is centered at the origin with normal in the +Z direction.
    # The curve is computed in this frame and then shifted/rotated to the correct frame.
    def __init__(
        self,
        center=[10, 0, 0],
        normal=[0, 1, 0],
        r_n=2,
        modes=None,
        name="",
    ):
        super().__init__(name)
        r_n = np.atleast_1d(r_n)
        if modes is None:
            modes = np.arange(-(r_n.size // 2), r_n.size // 2 + 1)
        else:
            modes = np.asarray(modes)
        assert issubclass(modes.dtype.type, np.integer)

        N = np.max(abs(modes))
        self._r_basis = FourierSeries(N, NFP=1, sym=False)
        self._r_n = copy_coeffs(r_n, modes, self.r_basis.modes[:, 2])

        self.normal = normal
        self.center = center

    @property
    def r_basis(self):
        """Spectral basis for Fourier series."""
        return self._r_basis

    @property
    def N(self):
        """Maximum mode number."""
        return self.r_basis.N

    def change_resolution(self, N=None):
        """Change the maximum angular resolution."""
        if (N is not None) and (N != self.N):
            modes_old = self.r_basis.modes
            self.r_basis.change_resolution(N=N)
            self.r_n = copy_coeffs(self.r_n, modes_old, self.r_basis.modes)

    @optimizable_parameter
    @property
    def center(self):
        """Center of planar curve polar coordinates."""
        return self._center

    @center.setter
    def center(self, new):
        if len(new) == 3:
            self._center = np.asarray(new)
        else:
            raise ValueError(
                "center should be a 3 element vector [cx, cy, cz], got {}".format(new)
            )

    @optimizable_parameter
    @property
    def normal(self):
        """Normal vector to plane."""
        return self._normal

    @normal.setter
    def normal(self, new):
        if len(np.asarray(new)) == 3:
            self._normal = np.asarray(new) / np.linalg.norm(new)
        else:
            raise ValueError(
                "normal should be a 3 element vector [nx, ny, nz], got {}".format(new)
            )

    @optimizable_parameter
    @property
    def r_n(self):
        """Spectral coefficients for r."""
        return self._r_n

    @r_n.setter
    def r_n(self, new):
        if len(np.asarray(new)) == self.r_basis.num_modes:
            self._r_n = jnp.asarray(new)
        else:
            raise ValueError(
                f"r_n should have the same size as the basis, got {len(new)} for "
                + f"basis with {self.r_basis.num_modes} modes."
            )

    def get_coeffs(self, n):
        """Get Fourier coefficients for given mode number(s)."""
        n = np.atleast_1d(n).astype(int)
        r = np.zeros_like(n).astype(float)

        idx = np.where(n[:, np.newaxis] == self.r_basis.modes[:, 2])

        r[idx[0]] = self.r_n[idx[1]]
        return r

    def set_coeffs(self, n, r=None):
        """Set specific Fourier coefficients."""
        n, r = np.atleast_1d(n), np.atleast_1d(r)
        r = np.broadcast_to(r, n.shape)
        for nn, rr in zip(n, r):
            idx = self.r_basis.get_idx(0, 0, nn)
            if rr is not None:
                self.r_n = put(self.r_n, idx, rr)
