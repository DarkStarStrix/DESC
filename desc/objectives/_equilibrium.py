import numpy as np
from desc.backend import jnp
from desc.utils import Timer
from desc.grid import QuadratureGrid, ConcentricGrid
from desc.transform import Transform
from desc.compute import (
    data_index,
    compute_force_error,
    compute_energy,
)
from .objective_funs import _Objective


class RadialForceBalance(_Objective):
    """Radial MHD force balance.

    F_rho = sqrt(g) (B^zeta J^theta - B^theta J^zeta) - grad(p)
    f_rho = F_rho |grad(rho)| dV  (N)

    """

    _scalar = False
    _linear = False

    def __init__(
        self, eq=None, target=0, weight=1, grid=None, norm=False, name="radial force"
    ):
        """Initialize a RadialForceBalance Objective.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        target : float, ndarray, optional
            Target value(s) of the objective.
            len(target) must be equal to Objective.dim_f
        weight : float, ndarray, optional
            Weighting to apply to the Objective, relative to other Objectives.
            len(weight) must be equal to Objective.dim_f
        grid : Grid, ndarray, optional
            Collocation grid containing the nodes to evaluate at.
        norm : bool, optional
            Whether to normalize the objective values (make dimensionless).
        name : str
            Name of the objective function.

        """
        self.grid = grid
        self.norm = norm
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        units = "(normalized)" if self.norm else "(N)"
        self._callback_fmt = "Radial force: {:10.3e} " + units

    def build(self, eq, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if self.grid is None:
            self.grid = ConcentricGrid(
                L=eq.L_grid,
                M=eq.M_grid,
                N=eq.N_grid,
                NFP=eq.NFP,
                sym=eq.sym,
                axis=False,
                rotation="cos",
                node_pattern=eq.node_pattern,
            )

        self._dim_f = self.grid.num_nodes

        timer = Timer()
        if verbose > 0:
            print("Precomputing transforms")
        timer.start("Precomputing transforms")

        self._pressure = eq.pressure.copy()
        self._iota = eq.iota.copy()
        self._pressure.grid = self.grid
        self._iota.grid = self.grid

        self._R_transform = Transform(
            self.grid, eq.R_basis, derivs=data_index["F_rho"]["R_derivs"], build=True
        )
        self._Z_transform = Transform(
            self.grid, eq.Z_basis, derivs=data_index["F_rho"]["R_derivs"], build=True
        )
        self._L_transform = Transform(
            self.grid, eq.L_basis, derivs=data_index["F_rho"]["L_derivs"], build=True
        )

        timer.stop("Precomputing transforms")
        if verbose > 1:
            timer.disp("Precomputing transforms")

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, R_lmn, Z_lmn, L_lmn, i_l, p_l, Psi, **kwargs):
        """Compute radial MHD force balance errors.

        Parameters
        ----------
        R_lmn : ndarray
            Spectral coefficients of R(rho,theta,zeta) -- flux surface R coordinate (m).
        Z_lmn : ndarray
            Spectral coefficients of Z(rho,theta,zeta) -- flux surface Z coordinate (m).
        L_lmn : ndarray
            Spectral coefficients of lambda(rho,theta,zeta) -- poloidal stream function.
        i_l : ndarray
            Spectral coefficients of iota(rho) -- rotational transform profile.
        p_l : ndarray
            Spectral coefficients of p(rho) -- pressure profile.
        Psi : float
            Total toroidal magnetic flux within the last closed flux surface (Wb).

        Returns
        -------
        f_rho : ndarray
            Radial MHD force balance error at each node (N).

        """
        data = compute_force_error(
            R_lmn,
            Z_lmn,
            L_lmn,
            p_l,
            i_l,
            Psi,
            self._R_transform,
            self._Z_transform,
            self._L_transform,
            self._pressure,
            self._iota,
        )
        f = data["F_rho"] * data["|grad(rho)|"]
        if self.norm:
            # FIXME: pre-compute normalization based on initial condition,
            # use averaged (not local) values
            f = f / data["|grad(p)|"]
        f = f * data["sqrt(g)"] * self.grid.weights
        # XXX: when normalized this has units of m^3 ?
        return self._shift_scale(f)

    @property
    def norm(self):
        """bool: Whether the objective values are normalized."""
        return self._norm

    @norm.setter
    def norm(self, norm):
        assert norm in [True, False]
        self._norm = norm
        units = "(normalized)" if self.norm else "(N)"
        self._callback_fmt = "Radial force: {:10.3e} " + units


class HelicalForceBalance(_Objective):
    """Helical MHD force balance.

    F_beta = sqrt(g) J^rho
    beta = -B^zeta grad(theta) + B^theta grad(zeta)
    f_beta = F_beta |beta| dV  (N)

    """

    _scalar = False
    _linear = False

    def __init__(
        self, eq=None, target=0, weight=1, grid=None, norm=False, name="helical force"
    ):
        """Initialize a HelicalForceBalance Objective.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        target : float, ndarray, optional
            Target value(s) of the objective.
            len(target) must be equal to Objective.dim_f
        weight : float, ndarray, optional
            Weighting to apply to the Objective, relative to other Objectives.
            len(weight) must be equal to Objective.dim_f
        grid : Grid, ndarray, optional
            Collocation grid containing the nodes to evaluate at.
        norm : bool, optional
            Whether to normalize the objective values (make dimensionless).
        name : str
            Name of the objective function.

        """
        self.grid = grid
        self.norm = norm
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        units = "(normalized)" if self.norm else "(N)"
        self._callback_fmt = "Helical force: {:10.3e}, " + units

    def build(self, eq, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if self.grid is None:
            self.grid = ConcentricGrid(
                L=eq.L_grid,
                M=eq.M_grid,
                N=eq.N_grid,
                NFP=eq.NFP,
                sym=eq.sym,
                axis=False,
                rotation="sin",
                node_pattern=eq.node_pattern,
            )

        self._dim_f = self.grid.num_nodes

        timer = Timer()
        if verbose > 0:
            print("Precomputing transforms")
        timer.start("Precomputing transforms")

        self._iota = eq.iota.copy()
        self._pressure = eq.pressure.copy()
        self._iota.grid = self.grid
        self._pressure.grid = self.grid

        self._R_transform = Transform(
            self.grid, eq.R_basis, derivs=data_index["F_beta"]["R_derivs"], build=True
        )
        self._Z_transform = Transform(
            self.grid, eq.Z_basis, derivs=data_index["F_beta"]["R_derivs"], build=True
        )
        self._L_transform = Transform(
            self.grid, eq.L_basis, derivs=data_index["F_beta"]["L_derivs"], build=True
        )

        timer.stop("Precomputing transforms")
        if verbose > 1:
            timer.disp("Precomputing transforms")

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, R_lmn, Z_lmn, L_lmn, i_l, p_l, Psi, **kwargs):
        """Compute helical MHD force balance errors.

        Parameters
        ----------
        R_lmn : ndarray
            Spectral coefficients of R(rho,theta,zeta) -- flux surface R coordinate (m).
        Z_lmn : ndarray
            Spectral coefficients of Z(rho,theta,zeta) -- flux surface Z coordinate (m).
        L_lmn : ndarray
            Spectral coefficients of lambda(rho,theta,zeta) -- poloidal stream function.
        i_l : ndarray
            Spectral coefficients of iota(rho) -- rotational transform profile.
        p_l : ndarray
            Spectral coefficients of p(rho) -- pressure profile.
        Psi : float
            Total toroidal magnetic flux within the last closed flux surface (Wb).

        Returns
        -------
        f : ndarray
            Helical MHD force balance error at each node (N).

        """
        data = compute_force_error(
            R_lmn,
            Z_lmn,
            L_lmn,
            p_l,
            i_l,
            Psi,
            self._R_transform,
            self._Z_transform,
            self._L_transform,
            self._pressure,
            self._iota,
        )
        f = data["F_beta"] * data["|beta|"]
        if self.norm:
            f = f / data["|grad(p)|"]
        f = f * data["sqrt(g)"] * self.grid.weights
        # XXX: when normalized this has units of m^3 ?
        return self._shift_scale(f)

    @property
    def norm(self):
        """bool: Whether the objective values are normalized."""
        return self._norm

    @norm.setter
    def norm(self, norm):
        assert norm in [True, False]
        self._norm = norm
        units = "(normalized)" if self.norm else "(N)"
        self._callback_fmt = "Helical force: {:10.3e}, " + units


class Energy(_Objective):
    """MHD energy.

    W = integral( B^2 / (2*mu0) + p / (gamma - 1) ) dV  (J)

    """

    _io_attrs_ = _Objective._io_attrs_ + ["gamma"]
    _scalar = True
    _linear = False

    def __init__(self, eq=None, target=0, weight=1, grid=None, gamma=0, name="energy"):
        """Initialize an Energy Objective.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        target : float, ndarray, optional
            Target value(s) of the objective.
            len(target) must be equal to Objective.dim_f
        weight : float, ndarray, optional
            Weighting to apply to the Objective, relative to other Objectives.
            len(weight) must be equal to Objective.dim_f
        grid : Grid, ndarray, optional
            Collocation grid containing the nodes to evaluate at.
        gamma : float, optional
            Adiabatic (compressional) index. Default = 0.
        name : str
            Name of the objective function.

        """
        self.grid = grid
        self.gamma = gamma
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._callback_fmt = "Total MHD energy: {:10.3e} (J)"

    def build(self, eq, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if self.grid is None:
            self.grid = QuadratureGrid(
                L=eq.L_grid, M=eq.M_grid, N=eq.N_grid, NFP=eq.NFP
            )

        self._dim_f = 1

        timer = Timer()
        if verbose > 0:
            print("Precomputing transforms")
        timer.start("Precomputing transforms")

        self._iota = eq.iota.copy()
        self._pressure = eq.pressure.copy()
        self._iota.grid = self.grid
        self._pressure.grid = self.grid

        self._R_transform = Transform(
            self.grid, eq.R_basis, derivs=data_index["W"]["R_derivs"], build=True
        )
        self._Z_transform = Transform(
            self.grid, eq.Z_basis, derivs=data_index["W"]["R_derivs"], build=True
        )
        self._L_transform = Transform(
            self.grid, eq.L_basis, derivs=data_index["W"]["L_derivs"], build=True
        )

        timer.stop("Precomputing transforms")
        if verbose > 1:
            timer.disp("Precomputing transforms")

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, R_lmn, Z_lmn, L_lmn, i_l, p_l, Psi, **kwargs):
        """Compute MHD energy.

        Parameters
        ----------
        R_lmn : ndarray
            Spectral coefficients of R(rho,theta,zeta) -- flux surface R coordinate (m).
        Z_lmn : ndarray
            Spectral coefficients of Z(rho,theta,zeta) -- flux surface Z coordinate (m).
        L_lmn : ndarray
            Spectral coefficients of lambda(rho,theta,zeta) -- poloidal stream function.
        i_l : ndarray
            Spectral coefficients of iota(rho) -- rotational transform profile.
        p_l : ndarray
            Spectral coefficients of p(rho) -- pressure profile.
        Psi : float
            Total toroidal magnetic flux within the last closed flux surface (Wb).

        Returns
        -------
        W : float
            Total MHD energy in the plasma volume (J).

        """
        data = compute_energy(
            R_lmn,
            Z_lmn,
            L_lmn,
            p_l,
            i_l,
            Psi,
            self._R_transform,
            self._Z_transform,
            self._L_transform,
            self._iota,
            self._pressure,
            self._gamma,
        )
        return self._shift_scale(jnp.atleast_1d(data["W"]))

    @property
    def gamma(self):
        """float: Adiabatic (compressional) index."""
        return self._gamma

    @gamma.setter
    def gamma(self, gamma):
        self._gamma = gamma
