"""Classes for linear optimization constraints.

Linear objective functions must be of the form `A*x-b`, where:
    - `A` is a constant matrix that can be pre-computed
    - `x` is a vector of one or more arguments included in `compute.arg_order`
    - `b` is the desired vector set by `objective.target`
"""

import warnings
from abc import ABC

import numpy as np
from termcolor import colored

from desc.backend import jnp
from desc.basis import zernike_radial, zernike_radial_coeffs

from .objective_funs import _Objective

# TODO: need dim_x attribute


class FixBoundaryR(_Objective):
    """Boundary condition on the R boundary parameters.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Boundary surface coefficients to fix. If None, uses surface coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    fixed_boundary : bool, optional
        True to enforce the boundary condition on flux surfaces,
        or False to fix the boundary surface coefficients (default).
    modes : ndarray, optional
        Basis modes numbers [l,m,n] of boundary modes to fix.
        len(target) = len(weight) = len(modes).
        If True/False uses all/none of the profile modes.
    surface_label : float
        Surface to enforce boundary conditions on. Defaults to Equilibrium.surface.rho
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = False  # TODO: can we dynamically detect this instead?

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        fixed_boundary=False,
        modes=True,
        surface_label=None,
        name="lcfs R",
    ):

        self._fixed_boundary = fixed_boundary
        self._modes = modes
        self._surface_label = surface_label
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "R boundary error: {:10.3e} (m)"

        if self._fixed_boundary:
            self.compute = self._compute_R
        else:
            self.compute = self._compute_Rb

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
        if self._modes is False or self._modes is None:  # no modes
            modes = np.array([[]], dtype=int)
            idx = np.array([], dtype=int)
        elif self._modes is True:  # all modes
            modes = eq.surface.R_basis.modes
            idx = np.arange(eq.surface.R_basis.num_modes)
        else:  # specified modes
            modes = np.atleast_2d(self._modes)
            dtype = {
                "names": ["f{}".format(i) for i in range(3)],
                "formats": 3 * [modes.dtype],
            }
            _, idx, modes_idx = np.intersect1d(
                eq.surface.R_basis.modes.astype(modes.dtype).view(dtype),
                modes.view(dtype),
                return_indices=True,
            )
            if idx.size < modes.shape[0]:
                warnings.warn(
                    colored(
                        "Some of the given modes are not in the surface, "
                        + "these modes will not be fixed.",
                        "yellow",
                    )
                )

        self._dim_f = idx.size

        if self._fixed_boundary:  # R_lmn -> Rb_lmn boundary condition
            self._A = np.zeros((self._dim_f, eq.R_basis.num_modes))
            for i, (l, m, n) in enumerate(eq.R_basis.modes):
                if eq.bdry_mode == "lcfs":
                    j = np.argwhere((modes[:, 1:] == [m, n]).all(axis=1))
                    surf = (
                        eq.surface.rho
                        if self._surface_label is None
                        else self._surface_label
                    )
                    self._A[j, i] = zernike_radial(surf, l, m)

        else:  # Rb_lmn -> Rb optimization space
            self._A = np.eye(eq.surface.R_basis.num_modes)[idx, :]

        # use given targets and weights if specified
        if self.target.size == modes.shape[0] and None not in self.target:
            self.target = self._target[modes_idx]
        if self.weight.size == modes.shape[0] and self.weight != np.array(1):
            self.weight = self._weight[modes_idx]

        # use surface parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = eq.surface.R_lmn[idx]

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, *args, **kwargs):
        """Compute deviation from desired boundary."""
        pass

    def _compute_R(self, R_lmn, **kwargs):
        Rb = jnp.dot(self._A, R_lmn)
        return self._shift_scale(Rb)

    def _compute_Rb(self, Rb_lmn, **kwargs):
        Rb = jnp.dot(self._A, Rb_lmn)
        return self._shift_scale(Rb)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "Rb_lmn"


class FixBoundaryZ(_Objective):
    """Boundary condition on the Z boundary parameters.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Boundary surface coefficients to fix. If None, uses surface coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    fixed_boundary : bool, optional
        True to enforce the boundary condition on flux surfaces,
        or False to fix the boundary surface coefficients (default).
    modes : ndarray, optional
        Basis modes numbers [l,m,n] of boundary modes to fix.
        len(target) = len(weight) = len(modes).
        If True/False uses all/none of the surface modes.
    surface_label : float
        Surface to enforce boundary conditions on. Defaults to Equilibrium.surface.rho
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = False

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        fixed_boundary=False,
        modes=True,
        surface_label=None,
        name="lcfs Z",
    ):

        self._fixed_boundary = fixed_boundary
        self._modes = modes
        self._surface_label = surface_label
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "Z boundary error: {:10.3e} (m)"

        if self._fixed_boundary:
            self.compute = self._compute_Z
        else:
            self.compute = self._compute_Zb

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
        if self._modes is False or self._modes is None:  # no modes
            modes = np.array([[]], dtype=int)
            idx = np.array([], dtype=int)
        elif self._modes is True:  # all modes
            modes = eq.surface.Z_basis.modes
            idx = np.arange(eq.surface.Z_basis.num_modes)
        else:  # specified modes
            modes = np.atleast_2d(self._modes)
            dtype = {
                "names": ["f{}".format(i) for i in range(3)],
                "formats": 3 * [modes.dtype],
            }
            _, idx, modes_idx = np.intersect1d(
                eq.surface.Z_basis.modes.astype(modes.dtype).view(dtype),
                modes.view(dtype),
                return_indices=True,
            )
            if idx.size < modes.shape[0]:
                warnings.warn(
                    colored(
                        "Some of the given modes are not in the surface, "
                        + "these modes will not be fixed.",
                        "yellow",
                    )
                )

        self._dim_f = idx.size

        if self._fixed_boundary:  # Z_lmn -> Zb_lmn boundary condition
            self._A = np.zeros((self._dim_f, eq.Z_basis.num_modes))
            for i, (l, m, n) in enumerate(eq.Z_basis.modes):
                if eq.bdry_mode == "lcfs":
                    j = np.argwhere((modes[:, 1:] == [m, n]).all(axis=1))
                    surf = (
                        eq.surface.rho
                        if self._surface_label is None
                        else self._surface_label
                    )
                    self._A[j, i] = zernike_radial(surf, l, m)
        else:  # Zb_lmn -> Zb optimization space
            self._A = np.eye(eq.surface.Z_basis.num_modes)[idx, :]

        # use given targets and weights if specified
        if self.target.size == modes.shape[0] and None not in self.target:
            self.target = self._target[modes_idx]
        # logic on weight prevents an error if target is None (and )
        if self.weight.size == modes.shape[0] and self.weight != np.array(1):
            self.weight = self._weight[modes_idx]

        # use surface parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = eq.surface.Z_lmn[idx]

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, *args, **kwargs):
        """Compute deviation from desired boundary."""
        pass

    def _compute_Z(self, Z_lmn, **kwargs):
        Zb = jnp.dot(self._A, Z_lmn)
        return self._shift_scale(Zb)

    def _compute_Zb(self, Zb_lmn, **kwargs):
        Zb = jnp.dot(self._A, Zb_lmn)
        return self._shift_scale(Zb)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "Zb_lmn"


class FixLambdaGauge(_Objective):
    """Fixes gauge freedom for lambda: lambda(rho=0)=0 and lambda(theta=0,zeta=0)=0.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Value to fix lambda to at rho=0 and (theta=0,zeta=0)
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = False

    def __init__(self, eq=None, target=0, weight=1, name="lambda gauge"):

        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "lambda gauge error: {:10.3e} (m)"

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
        L_basis = eq.L_basis

        if L_basis.sym:
            # l(0,t,z) = 0
            # any zernike mode that has m != 0 (i.e., has any theta dependence)
            # contains radial dependence at least as rho^m
            # therefore if m!=0, no constraint is needed to make the mode go to
            # zero at rho=0

            # for the other modes with m=0, at rho =0 the basis reduces
            # to just a linear combination of sin(n*zeta), cos(n*zeta), and 1
            # since these are all linearly independent, to make lambda -> 0 at rho=0,
            # each coefficient on these terms must individually go to zero
            # i.e. if at rho=0 the lambda basis is given by
            # Lambda(rho=0) = (L_{00-1} - L_{20-1})sin(zeta) + (L_{001}
            #                   - L_{201})cos(zeta) + L_{000} - L_{200}
            # Lambda(rho=0) = 0 constraint being enforced means that each
            # coefficient goes to zero:
            # L_{00-1} - L_{20-1} = 0
            # L_{001} - L_{201} = 0
            # L_{000} - L_{200} = 0
            self._A = np.zeros((L_basis.N, L_basis.num_modes))
            ns = np.arange(-L_basis.N, 1)
            for i, (l, m, n) in enumerate(L_basis.modes):
                if m != 0:
                    continue
                if (
                    l // 2
                ) % 2 == 0:  # this basis mode radial polynomial is +1 at rho=0
                    j = np.argwhere(n == ns)
                    self._A[j, i] = 1
                else:  # this basis mode radial polynomial is -1 at rho=0
                    j = np.argwhere(n == ns)
                    self._A[j, i] = -1
        else:
            # l(0,t,z) = 0

            ns = np.arange(-L_basis.N, L_basis.N + 1)
            self._A = np.zeros((len(ns), L_basis.num_modes))
            for i, (l, m, n) in enumerate(L_basis.modes):
                if m != 0:
                    continue
                if (l // 2) % 2 == 0:
                    j = np.argwhere(n == ns)
                    self._A[j, i] = 1
                else:
                    j = np.argwhere(n == ns)
                    self._A[j, i] = -1
            # l(rho,0,0) = 0
            # at theta=zeta=0, basis for lamba reduces to just a polynomial in rho
            # what this constraint does is make all the coefficients of each power
            # of rho equal to zero
            # i.e. if lambda = (L_200 + 2*L_310) rho**2 + (L_100 + 2*L_210)*rho
            # this constraint will make
            # L_200 + 2*L_310 = 0
            # L_100 + 2*L_210 = 0
            L_modes = L_basis.modes
            mnpos = np.where((L_modes[:, 1:] >= [0, 0]).all(axis=1))[0]
            l_lmn = L_modes[mnpos, :]
            if len(l_lmn) > 0:
                c = zernike_radial_coeffs(l_lmn[:, 0], l_lmn[:, 1])
            else:
                c = np.zeros((0, 0))

            A = np.zeros((c.shape[1], L_basis.num_modes))
            A[:, mnpos] = c.T
            self._A = np.vstack((self._A, A))

        self._dim_f = self._A.shape[0]

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, L_lmn, **kwargs):
        """Compute lambda gauge symmetry errors.

        Parameters
        ----------
        L_lmn : ndarray
            Spectral coefficients of L(rho,theta,zeta) -- poloidal stream function.

        Returns
        -------
        f : ndarray
            Lambda gauge symmetry errors.

        """
        f = jnp.dot(self._A, L_lmn)
        return self._shift_scale(f)


# TODO: make base class for FixAxis?
class FixAxisR(_Objective):
    """Fixes magnetic axis R coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Magnetic axis coefficients to fix. If None, uses Equilibrium's axis coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    modes : ndarray, optional
        Basis modes numbers [l,m,n] of axis modes to fix.
        len(target) = len(weight) = len(modes).
        If True/False uses all/none of the axis modes.
    surface_label : float
        Surface to enforce boundary conditions on. Defaults to Equilibrium.surface.rho
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = False

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        modes=True,
        name="axis R",
    ):

        self._modes = modes
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "R axis error: {:10.3e} (m)"

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
        R_basis = eq.R_basis

        if self._modes is False or self._modes is None:  # no modes
            modes = np.array([[]], dtype=int)
            idx = np.array([], dtype=int)
        elif self._modes is True:  # all modes
            modes = eq.axis.R_basis.modes
            idx = np.arange(eq.axis.R_basis.num_modes)
        else:  # specified modes
            modes = np.atleast_1d(self._modes)
            dtype = {
                "names": ["f{}".format(i) for i in range(3)],
                "formats": 3 * [modes.dtype],
            }
            _, idx, modes_idx = np.intersect1d(
                eq.axis.R_basis.modes.astype(modes.dtype).view(dtype),
                modes.view(dtype),
                return_indices=True,
            )
            if idx.size < modes.shape[0]:
                warnings.warn(
                    colored(
                        "Some of the given modes are not in the axis, "
                        + "these modes will not be fixed.",
                        "yellow",
                    )
                )

        # self._A = np.zeros((self._dim_f, eq.R_basis.num_modes))
        # for i, (l, m, n) in enumerate(eq.R_basis.modes):
        #     j = np.argwhere((modes[:, 1:] == [m, n]).all(axis=1))
        #     surf = (
        #         eq.surface.rho
        #         if self._surface_label is None
        #         else self._surface_label
        #     )
        #     self._A[j, i] = zernike_radial(surf, l, m)
        # # else:  # Zb_lmn -> Zb optimization space
        # #     self._A = np.eye(eq.surface.Z_basis.num_modes)[idx, :]
        num_extra_modes = 0
        ##### stupid hack to fix R110 ###
        for i, (l, m, n) in enumerate(R_basis.modes):
            if m == 1 and l == 1:
                num_extra_modes += 1
        ns = np.unique(eq.R_basis.modes[:, 2])  ## + is dumb hack for R11n modes
        self._A = np.zeros(
            (len(ns) + num_extra_modes, R_basis.num_modes)
        )  # + from hack
        self._dim_f = len(ns) + num_extra_modes  # +1 hack

        for i, (l, m, n) in enumerate(R_basis.modes):
            if m != 0:
                continue
            if (l // 2) % 2 == 0:
                j = np.argwhere(n == ns)
                self._A[j, i] = 1
            else:
                j = np.argwhere(n == ns)
                self._A[j, i] = -1
        jj = 0
        for i, (l, m, n) in enumerate(R_basis.modes):
            if m == 1 and l == 1:
                self._A[-1 - jj, i] = 1
                jj += 1

        ###############################################
        # use given targets and weights if specified
        if self.target.size == modes.shape[0] and None not in self.target:
            self.target = self._target[modes_idx]
        if self.weight.size == modes.shape[0] and self.weight != np.array(1):
            self.weight = self._weight[modes_idx]
        jj = 0
        # use axis parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = np.zeros((len(ns) + num_extra_modes,))  # +1 from hack
            for n, Rn in zip(eq.axis.R_basis.modes[:, 2], eq.axis.R_n):
                j = np.argwhere(ns == n)
                self.target[j] = Rn
            ##### hack
            for i, (l, m, n) in enumerate(R_basis.modes):
                if m == 1 and l == 1:
                    self.target[-1 - jj] = eq.R_lmn[eq.R_basis.get_idx(L=l, M=m, N=n)]
                    jj += 1
            #####
        print("R target: ", self.target)

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True
        ################################################

    def compute(self, R_lmn, **kwargs):
        """Compute axis R errors.

        Parameters
        ----------
        R_lmn : ndarray
            Spectral coefficients of L(rho,theta,zeta) -- poloidal stream function.

        Returns
        -------
        f : ndarray
            Axis R errors..

        """
        f = jnp.dot(self._A, R_lmn)
        return self._shift_scale(f)


class FixAxisZ(_Objective):
    """Fixes magnetic axis Z coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Magnetic axis coefficients to fix. If None, uses Equilibrium's axis coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    modes : ndarray, optional
        Basis modes numbers [l,m,n] of axis modes to fix.
        len(target) = len(weight) = len(modes).
        If True/False uses all/none of the axis modes.
    surface_label : float
        Surface to enforce boundary conditions on. Defaults to Equilibrium.surface.rho
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = False

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        modes=True,
        name="axis Z",
    ):

        self._modes = modes
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "Z axis error: {:10.3e} (m)"

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
        Z_basis = eq.Z_basis

        if self._modes is False or self._modes is None:  # no modes
            modes = np.array([[]], dtype=int)
            idx = np.array([], dtype=int)
        elif self._modes is True:  # all modes
            modes = eq.axis.Z_basis.modes
            idx = np.arange(eq.axis.Z_basis.num_modes)
        else:  # specified modes
            modes = np.atleast_1d(self._modes)
            dtype = {
                "names": ["f{}".format(i) for i in range(3)],
                "formats": 3 * [modes.dtype],
            }
            _, idx, modes_idx = np.intersect1d(
                eq.axis.Z_basis.modes.astype(modes.dtype).view(dtype),
                modes.view(dtype),
                return_indices=True,
            )
            if idx.size < modes.shape[0]:
                warnings.warn(
                    colored(
                        "Some of the given modes are not in the axis, "
                        + "these modes will not be fixed.",
                        "yellow",
                    )
                )

        # self._A = np.zeros((self._dim_f, eq.R_basis.num_modes))
        # for i, (l, m, n) in enumerate(eq.R_basis.modes):
        #     j = np.argwhere((modes[:, 1:] == [m, n]).all(axis=1))
        #     surf = (
        #         eq.surface.rho
        #         if self._surface_label is None
        #         else self._surface_label
        #     )
        #     self._A[j, i] = zernike_radial(surf, l, m)
        # # else:  # Zb_lmn -> Zb optimization space
        # #     self._A = np.eye(eq.surface.Z_basis.num_modes)[idx, :]
        num_extra_modes = 0

        ##### stupid hack to fix R110 ###
        for i, (l, m, n) in enumerate(Z_basis.modes):
            if m == 1 and l == 1:
                num_extra_modes += 1
        ns = np.unique(eq.Z_basis.modes[:, 2])
        self._A = np.zeros((len(ns) + num_extra_modes, Z_basis.num_modes))
        self._dim_f = len(ns) + num_extra_modes

        for i, (l, m, n) in enumerate(Z_basis.modes):
            if m != 0:
                continue
            if (l // 2) % 2 == 0:
                j = np.argwhere(n == ns)
                self._A[j, i] = 1
            else:
                j = np.argwhere(n == ns)
                self._A[j, i] = -1
        ##### stupid hack to fix Z110 ###
        jj = 0
        for i, (l, m, n) in enumerate(Z_basis.modes):
            if m == 1 and l == 1:
                self._A[-1 - jj, i] = 1
                jj += 1
        ###############################################
        # use given targets and weights if specified
        if self.target.size == modes.shape[0] and None not in self.target:
            self.target = self._target[modes_idx]
        if self.weight.size == modes.shape[0] and self.weight != np.array(1):
            self.weight = self._weight[modes_idx]
        jj = 0
        # use axis parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = np.zeros((len(ns) + 1,))
            for n, Zn in zip(eq.axis.Z_basis.modes[:, 2], eq.axis.Z_n):
                j = np.argwhere(ns == n)
                self.target[j] = Zn
            ##### hack
            for i, (l, m, n) in enumerate(Z_basis.modes):
                if m == 1 and l == 1:
                    self.target[-1 - jj] = eq.Z_lmn[eq.Z_basis.get_idx(L=l, M=m, N=n)]
                    jj += 1
            #####

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True
        ################################################

    def compute(self, Z_lmn, **kwargs):
        """Compute axis Z errors.

        Parameters
        ----------
        Z_lmn : ndarray
            Spectral coefficients of Z(rho,theta,zeta) .

        Returns
        -------
        f : ndarray
            Axis Z errors.

        """
        f = jnp.dot(self._A, Z_lmn)
        return self._shift_scale(f)


class FixModeR(_Objective):
    """Fixes Fourier-Zernike R coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Fourier-Zernike R coefficient target values. If None, uses Equilibrium's R coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    modes : ndarray, optional
        Basis modes numbers [l,m,n] of Fourier-Zernike modes to fix.
        len(target) = len(weight) = len(modes).
        If True/False uses all/none of the Equilibrium's modes.
    surface_label : float
        Surface to enforce boundary conditions on. Defaults to Equilibrium.surface.rho
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = True

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        modes=False,
        name="Fix Mode R",
    ):

        self._modes = modes
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "Fixed-R modes error: {:10.3e} (m)"

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
        R_basis = eq.R_basis
        # we give modes, we should convert to indices?

        if self._modes is False or self._modes is None:  # no modes
            modes = np.array([[]], dtype=int)
            idx = np.array([], dtype=int)
            modes_idx = idx
            # FIXME: we don't want this option right? fix all modes...
        elif self._modes is True:  # all modes
            modes = eq.R_basis.modes
            idx = np.arange(eq.R_basis.num_modes)
        else:  # specified modes
            modes = np.atleast_2d(self._modes)
            dtype = {
                "names": ["f{}".format(i) for i in range(3)],
                "formats": 3 * [modes.dtype],
            }
            _, idx, modes_idx = np.intersect1d(
                eq.R_basis.modes.astype(modes.dtype).view(dtype),
                modes.view(dtype),
                return_indices=True,
            )
            self._idx = idx
            if idx.size < modes.shape[0]:
                warnings.warn(
                    colored(
                        "Some of the given modes are not in the basis, "
                        + "these modes will not be fixed.",
                        "yellow",
                    )
                )

        self._dim_f = modes_idx.size
        # FIXME: should modes_idx be in the target?
        # use given targets and weights if specified
        if self.target.size == modes.shape[0] and None not in self.target:
            self.target = self._target[modes_idx]
        if self.weight.size == modes.shape[0] and self.weight != np.array(1):
            self.weight = self._weight[modes_idx]

        # use axis parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = eq.R_lmn[self._idx]

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True
        ################################################

    def compute(self, R_lmn, **kwargs):
        """Compute Fixed mode R errors.

        Parameters
        ----------
        R_lmn : ndarray
            Spectral coefficients of R(rho,theta,zeta) .

        Returns
        -------
        f : ndarray
            Fixed mode R errors.

        """
        fixed_params = R_lmn[self._idx]
        return self._shift_scale(fixed_params)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "R_lmn"


class FixModeZ(_Objective):
    """Fixes Fourier-Zernike Z coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Fourier-Zernike Z coefficient target values. If None, uses Equilibrium's Z coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    modes : ndarray, optional
        Basis modes numbers [l,m,n] of Fourier-Zernike modes to fix.
        len(target) = len(weight) = len(modes).
        If True/False uses all/none of the Equilibrium's modes.
    surface_label : float
        Surface to enforce boundary conditions on. Defaults to Equilibrium.surface.rho
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = True

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        modes=False,
        name="Fix Mode Z",
    ):

        self._modes = modes
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "Fixed-Z modes error: {:10.3e} (m)"

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
        Z_basis = eq.Z_basis
        # we give modes, we should convert to indices?

        if self._modes is False or self._modes is None:  # no modes
            modes = np.array([[]], dtype=int)
            idx = np.array([], dtype=int)
            modes_idx = idx
            # FIXME: we don't want this option right? fix all modes...
        elif self._modes is True:  # all modes
            modes = eq.Z_basis.modes
            idx = np.arange(eq.Z_basis.num_modes)
        else:  # specified modes
            modes = np.atleast_2d(self._modes)
            dtype = {
                "names": ["f{}".format(i) for i in range(3)],
                "formats": 3 * [modes.dtype],
            }
            _, idx, modes_idx = np.intersect1d(
                eq.Z_basis.modes.astype(modes.dtype).view(dtype),
                modes.view(dtype),
                return_indices=True,
            )
            self._idx = idx
            if idx.size < modes.shape[0]:
                warnings.warn(
                    colored(
                        "Some of the given modes are not in the basis, "
                        + "these modes will not be fixed.",
                        "yellow",
                    )
                )

        self._dim_f = modes_idx.size
        # FIXME: should modes_idx be in the target?
        # use given targets and weights if specified
        if self.target.size == modes.shape[0] and None not in self.target:
            self.target = self._target[modes_idx]
        if self.weight.size == modes.shape[0] and self.weight != np.array(1):
            self.weight = self._weight[modes_idx]

        # use axis parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = eq.Z_lmn[self._idx]

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True
        ################################################

    def compute(self, Z_lmn, **kwargs):
        """Compute Fixed mode Z errors.

        Parameters
        ----------
        Z_lmn : ndarray
            Spectral coefficients of Z(rho,theta,zeta) .

        Returns
        -------
        f : ndarray
            Fixed mode Z errors.

        """
        fixed_params = Z_lmn[self._idx]
        return self._shift_scale(fixed_params)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "Z_lmn"


class _FixProfile(_Objective, ABC):
    """Fixes profile coefficients (or values, for SplineProfile).

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : tuple, float, ndarray, optional
        Target value(s) of the objective.
        len(target) = len(weight) = len(modes). If None, uses Profile.params.
        e.g. for PowerSeriesProfile these are profile coefficients, and for
        SplineProfile they are values at knots.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(target) = len(weight) = len(modes)
    profile : Profile, optional
        Profile containing the radial modes to evaluate at.
    indices : ndarray or Bool, optional
        indices of the Profile.params array to fix.
        (e.g. indices corresponding to modes for a PowerSeriesProfile or indices
        corresponding to knots for a SplineProfile).
        Must have len(target) = len(weight) = len(modes).
        If True/False uses all/none of the Profile.params indices.
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = True

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        profile=None,
        indices=True,
        name="",
    ):

        self._profile = profile
        self._indices = indices
        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = None

    def build(self, eq, profile=None, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium
            Equilibrium that will be optimized to satisfy the Objective.
        profile : Profile, optional
            profile to fix
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if self._profile is None or self._profile.params.size != eq.L + 1:
            self._profile = profile

        # find indices to fix
        if self._indices is False or self._indices is None:  # no indices to fix
            self._idx = np.array([], dtype=int)
            indices = np.array([[]], dtype=int)
            idx = self._idx
        elif self._indices is True:  # all indices of Profile.params
            self._idx = np.arange(np.size(self._profile.params))
            indices = self._idx
            idx = self._idx
        else:  # specified indices
            self._idx = np.atleast_1d(self._indices)
            idx = self._idx

        self._dim_f = self._idx.size
        # use given targets and weights if specified
        if self.target.size == indices.shape[0]:
            self.target = self._target[idx]
        if self.weight.size == indices.shape[0]:
            self.weight = self._weight[idx]
        # use profile parameters as target if needed
        if None in self.target or self.target.size != self.dim_f:
            self.target = self._profile.params[self._idx]

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True


class FixPressure(_FixProfile):
    """Fixes pressure coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : tuple, float, ndarray, optional
        Target value(s) of the objective.
        len(target) = len(weight) = len(modes). If None, uses profile coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(target) = len(weight) = len(modes)
    profile : Profile, optional
        Profile containing the radial modes to evaluate at.
    indices : ndarray or bool, optional
        indices of the Profile.params array to fix.
        (e.g. indices corresponding to modes for a PowerSeriesProfile or indices
        corresponding to knots for a SplineProfile).
        Must have len(target) = len(weight) = len(modes).
        If True/False uses all/none of the Profile.params indices.
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = True

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        profile=None,
        indices=True,
        name="fixed-pressure",
    ):

        super().__init__(
            eq=eq,
            target=target,
            weight=weight,
            profile=profile,
            indices=indices,
            name=name,
        )
        self._print_value_fmt = "Fixed-pressure profile error: {:10.3e} (Pa)"

    def build(self, eq, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        profile = eq.pressure
        super().build(eq, profile, use_jit, verbose)

    def compute(self, p_l, **kwargs):
        """Compute fixed pressure profile errors.

        Parameters
        ----------
        p_l : ndarray
            parameters of the pressure profile.

        Returns
        -------
        f : ndarray
            Fixed profile errors.

        """
        fixed_params = p_l[self._idx]
        return self._shift_scale(fixed_params)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "p_l"


class FixIota(_FixProfile):
    """Fixes rotational transform coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : tuple, float, ndarray, optional
        Target value(s) of the objective.
        len(target) = len(weight) = len(modes). If None, uses profile coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(target) = len(weight) = len(modes)
    profile : Profile, optional
        Profile containing the radial modes to evaluate at.
    indices : ndarray or bool, optional
        indices of the Profile.params array to fix.
        (e.g. indices corresponding to modes for a PowerSeriesProfile or indices.
        corresponding to knots for a SplineProfile).
        Must len(target) = len(weight) = len(modes).
        If True/False uses all/none of the Profile.params indices.
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = True

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        profile=None,
        indices=True,
        name="fixed-iota",
    ):

        super().__init__(
            eq=eq,
            target=target,
            weight=weight,
            profile=profile,
            indices=indices,
            name=name,
        )
        self._print_value_fmt = "Fixed-iota profile error: {:10.3e}"

    def build(self, eq, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if eq.iota is None:
            raise RuntimeError(
                "Attempt to fix rotational transform on an equilibrium with no "
                + "rotational transform profile assigned"
            )
        profile = eq.iota
        super().build(eq, profile, use_jit, verbose)

    def compute(self, i_l, **kwargs):
        """Compute fixed iota errors.

        Parameters
        ----------
        i_l : ndarray
            parameters of the iota profile.

        Returns
        -------
        f : ndarray
            Fixed profile errors.

        """
        fixed_params = i_l[self._idx]
        return self._shift_scale(fixed_params)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "i_l"


class FixCurrent(_FixProfile):
    """Fixes toroidal current profile coefficients.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : tuple, float, ndarray, optional
        Target value(s) of the objective.
        len(target) = len(weight) = len(modes). If None, uses profile coefficients.
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(target) = len(weight) = len(modes)
    profile : Profile, optional
        Profile containing the radial modes to evaluate at.
    indices : ndarray or bool, optional
        indices of the Profile.params array to fix.
        (e.g. indices corresponding to modes for a PowerSeriesProfile or indices
        corresponding to knots for a SplineProfile).
        Must have len(target) = len(weight) = len(modes).
        If True/False uses all/none of the Profile.params indices.
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = True
    _fixed = True

    def __init__(
        self,
        eq=None,
        target=None,
        weight=1,
        profile=None,
        indices=True,
        name="fixed-current",
    ):

        super().__init__(
            eq=eq,
            target=target,
            weight=weight,
            profile=profile,
            indices=indices,
            name=name,
        )
        self._print_value_fmt = "Fixed-current profile error: {:10.3e}"

    def build(self, eq, use_jit=True, verbose=1):
        """Build constant arrays.

        Parameters
        ----------
        eq : Equilibrium
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if eq.current is None:
            raise RuntimeError(
                "Attempt to fix toroidal current on an equilibrium no "
                + "current profile assigned"
            )
        profile = eq.current
        super().build(eq, profile, use_jit, verbose)

    def compute(self, c_l, **kwargs):
        """Compute fixed current errors.

        Parameters
        ----------
        c_l : ndarray
            parameters of the current profile.

        Returns
        -------
        f : ndarray
            Fixed profile errors.

        """
        fixed_params = c_l[self._idx]
        return self._shift_scale(fixed_params)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "c_l"


class FixPsi(_Objective):
    """Fixes total toroidal magnetic flux within the last closed flux surface.

    Parameters
    ----------
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the Objective.
    target : float, optional
        Target value(s) of the objective. If None, uses Equilibrium value.
    weight : float, optional
        Weighting to apply to the Objective, relative to other Objectives.
    name : str
        Name of the objective function.

    """

    _scalar = True
    _linear = True
    _fixed = True

    def __init__(self, eq=None, target=None, weight=1, name="fixed-Psi"):

        super().__init__(eq=eq, target=target, weight=weight, name=name)
        self._print_value_fmt = "Fixed-Psi error: {:10.3e} (Wb)"

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
        self._dim_f = 1

        if None in self.target:
            self.target = eq.Psi

        self._check_dimensions()
        self._set_dimensions(eq)
        self._set_derivatives(use_jit=use_jit)
        self._built = True

    def compute(self, Psi, **kwargs):
        """Compute fixed-Psi error.

        Parameters
        ----------
        Psi : float
            Total toroidal magnetic flux within the last closed flux surface (Wb).

        Returns
        -------
        f : ndarray
            Total toroidal magnetic flux error (Wb).

        """
        return self._shift_scale(Psi)

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return "Psi"
