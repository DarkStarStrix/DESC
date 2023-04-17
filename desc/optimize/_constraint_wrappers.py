"""Wrappers for doing STELLOPT/SIMSOPT like optimization."""

import numpy as np

from desc.backend import jnp
from desc.compute import arg_order
from desc.objectives import ObjectiveFunction
from desc.objectives.utils import (
    align_jacobian,
    factorize_linear_constraints,
    get_fixed_boundary_constraints,
)
from desc.utils import Timer

from .utils import compute_jac_scale, f_where_x


class DESCNonlinearConstraint(ObjectiveFunction):
    _print_value_fmt = "Total constraint error: {:10.3e} "
    _scalar = False
    _linear = False

    def __init__(self, constraint):
        print("constraint is " + str(constraint))
        assert isinstance(constraint, ObjectiveFunction), (
            "constraint should be instance of ObjectiveFunction." ""
        )
        self._constraint = constraint
        self._built = False
        # don't want to compile this, just use the compiled objective
        self._use_jit = False
        self._compiled = False

        (
            self._equality_constraint,
            self._inequality_constraint,
        ) = self.parse_constraints()

        self._eq_dim, self._ineq_dim = self.dim()

    #        if eq is not None:
    #            self.build(eq, verbose=verbose)

    def parse_constraints(self):
        #        print("constraint objectives are " + str(self._constraint._objectives[0]._objectives))
        #        for constraint in self._constraint._objectives[0]._objectives:
        #            print("lower bounds are " + str(constraint.bounds[0]))
        #            print("upper bounds are " + str(constraint.bounds[1]))
        equality_constraints = tuple(
            constraint
            for constraint in self._constraint._objectives
            if np.array_equal(constraint.bounds[0], constraint.bounds[1])
        )
        inequality_constraints = tuple(
            constraint
            for constraint in self._constraint._objectives
            if not np.array_equal(constraint.bounds[0], constraint.bounds[1])
        )
        #        equality_objective = ObjectiveFunction(equality_constraints)
        #        inequality_objective = ObjectiveFunction(inequality_constraints)
        if len(equality_constraints):
            equality_objective = LinearConstraintProjection(
                equality_constraints[0], self._constraint._constraints
            )
            equality_objective.build(self._constraint._eq)
        else:
            equality_objective = None
        if len(inequality_constraints):
            inequality_objective = LinearConstraintProjection(
                equality_constraints[0], self._constraint._constraints
            )
            inequality_objective.build(self._constraint._eq)
        else:
            inequality_objective = None
        return equality_objective, inequality_objective

    def dim(self):
        eq_dim = 0
        ineq_dim = 0
        if self._inequality_constraint:
            for constr in self._inequality_constraint._objectives:
                if constr.bounds[0] != -np.inf:
                    ineq_dim += constr.dim_f
                if constr.bounds[1] != np.inf:
                    ineq_dim += constr.dim_f
        if self._equality_constraint:
            for constr in self._equality_constraint._objectives:
                eq_dim += constr.dim_f

        return eq_dim, ineq_dim

    def dim_f(self):
        return self._eq_dim + self._ineq_dim

    def recover(self, x):
        x_reduced = x[0 : len(x) - self._ineq_dim]
        slack = x[len(x_reduced) :] ** 2
        return x_reduced, slack

    def compute(self, x):
        x_reduced, slack = self.recover(x)
        c = jnp.array([])
        if self._equality_constraint:
            c = jnp.append(c, self._equality_constraint.compute_scaled(x_reduced))
            slack = jnp.append(jnp.zeros(self._equality_constraint.dim_f), slack)

        if self._inequality_constraint:
            c = jnp.append(c, self._inequality_constraint.compute_scaled(x_reduced))

        return c + slack


class LinearConstraintProjection(ObjectiveFunction):
    """Remove linear constraints via orthogonal projection.

    Given a problem of the form

    min_x f(x)  subject to A*x=b

    We can write any feasible x=xp + Z*x_reduced where xp is a particular solution to
    Ax=b (taken to be the least norm solution), Z is a representation for the null
    space of A (A*Z=0) and x_reduced is conconstrained. This transforms the problem into

    min_x_reduced f(x_reduced)

    Parameters
    ----------
    objective : ObjectiveFunction
        Objective function to optimize.
    constraints : tuple of Objective
        Linear constraints to enforce. Should be a tuple or list of Objective,
        and must all be linear.
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the objectives.
    verbose : int, optional
        Level of output.
    """

    def __init__(self, objective, constraints, eq=None, verbose=1):
        assert isinstance(objective, ObjectiveFunction), (
            "objective should be instance of ObjectiveFunction." ""
        )
        for con in constraints:
            if not con.linear:
                raise ValueError(
                    "LinearConstraintProjection method "
                    + "cannot handle nonlinear constraint {}.".format(con)
                )
        self._objective = objective
        self._objectives = [objective]
        self._constraints = constraints
        self._built = False
        # don't want to compile this, just use the compiled objective
        self._use_jit = False
        self._compiled = False

        if eq is not None:
            self.build(eq, verbose=verbose)

    def build(self, eq, use_jit=None, verbose=1):
        """Build the objective.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
            Note: unused by this class, should pass to sub-objectives directly.
        verbose : int, optional
            Level of output.

        """
        timer = Timer()
        timer.start("Linear constraint projection build")
        self._eq = eq

        if not self._objective.built:
            self._objective.build(eq, verbose=verbose)
        for con in self._constraints:
            if not con.built:
                con.build(eq, verbose=verbose)
        self._args = self._objective.args
        self._dim_f = self._objective.dim_f
        self._dimensions = self._objective.dimensions
        self._scalar = self._objective.scalar
        (
            self._xp,
            self._A,
            self._Ainv,
            self._b,
            self._Z,
            self._unfixed_idx,
            self._project,
            self._recover,
        ) = factorize_linear_constraints(
            self._constraints,
            self._objective.args,
        )
        self._dim_x = self._Z.shape[1]
        self._dim_x_full = self._objective.dim_x

        self._built = True
        timer.stop("Linear constraint projection build")
        if verbose > 1:
            timer.disp("Linear constraint projection build")

    def compile(self, mode="lsq", verbose=1):
        """Call the necessary functions to ensure the function is compiled.

        Parameters
        ----------
        mode : {"auto", "lsq", "scalar", "all"}
            Whether to compile for least squares optimization or scalar optimization.
            "auto" compiles based on the type of objective,
            "all" compiles all derivatives.
        verbose : int, optional
            Level of output.

        """
        self._objective.compile(mode, verbose)

    def project(self, x):
        """Project full vector x into x_reduced that satisfies constraints."""
        return self._project(x)

    def recover(self, x_reduced):
        """Recover the full state vector from the reduced optimization vector."""
        return self._recover(x_reduced)

    def x(self, eq):
        """Return the reduced state vector from the Equilibrium eq."""
        x = self._objective.x(eq)
        return self.project(x)

    def unpack_state(self, x):
        """Unpack the state vector into its components.

        Parameters
        ----------
        x : ndarray
            State vector, either full or reduced.

        Returns
        -------
        kwargs : dict
            Dictionary of the state components with argument names as keys.

        """
        if len(x) == self._dim_x:
            x = self.recover(x)
        return self._objective.unpack_state(x)

    def compute_unscaled(self, x_reduced):
        """Compute the unscaled form of the objective function.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        x = self.recover(x_reduced)
        f = self._objective.compute_unscaled(x)
        return f

    def compute_scaled(self, x_reduced):
        """Compute the objective function and apply weighting / bounds.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        x = self.recover(x_reduced)
        f = self._objective.compute_scaled(x)
        return f

    def compute_scalar(self, x_reduced):
        """Compute the scalar form of the objective function.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        f : float
            Objective function value.

        """
        x = self.recover(x_reduced)
        return self._objective.compute_scalar(x)

    def grad(self, x_reduced):
        """Compute gradient of the sum of squares of residuals.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        g : ndarray
            gradient vector.
        """
        x = self.recover(x_reduced)
        df = self._objective.grad(x)
        return df[self._unfixed_idx] @ self._Z

    def hess(self, x_reduced):
        """Compute Hessian of the sum of squares of residuals.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        H : ndarray
            Hessian matrix.
        """
        x = self.recover(x_reduced)
        df = self._objective.hess(x)
        return self._Z.T @ df[self._unfixed_idx, :][:, self._unfixed_idx] @ self._Z

    def jac_unscaled(self, x_reduced):
        """Compute Jacobian of the vector objective function without weighting / bounds.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        J : ndarray
            Jacobian matrix.
        """
        x = self.recover(x_reduced)
        df = self._objective.jac_unscaled(x)
        return df[:, self._unfixed_idx] @ self._Z

    def jac_scaled(self, x_reduced):
        """Compute Jacobian of the vector objective function with weighting / bounds.

        Parameters
        ----------
        x_reduced : ndarray
            Reduced state vector that satisfies linear constraints.

        Returns
        -------
        J : ndarray
            Jacobian matrix.
        """
        x = self.recover(x_reduced)
        df = self._objective.jac_scaled(x)
        return df[:, self._unfixed_idx] @ self._Z

    @property
    def target(self):
        """ndarray: target vector."""
        return self._objective.target

    @property
    def bounds(self):
        """tuple: lower and upper bounds for residual vector."""
        return self._objective.bounds

    @property
    def weights(self):
        """ndarray: weight vector."""
        return self._objective.weights


class ProximalProjection(ObjectiveFunction):
    """Remove equilibrium constraint by projecting onto constraint at each step.

    Combines objective and equilibrium constraint into a single objective to then pass
    to an unconstrained optimizer.

    At each iteration, after a step is taken to reduce the objective, the equilibrium
    is perturbed and re-solved to bring it back into force balance. This is analagous
    to a proximal method where each iterate is projected back onto the feasible set.

    Parameters
    ----------
    objective : ObjectiveFunction
        Objective function to optimize.
    constraint : ObjectiveFunction
        Equilibrium constraint to enforce. Should be an ObjectiveFunction with one or
        more of the following objectives: {ForceBalance, CurrentDensity,
        RadialForceBalance, HelicalForceBalance}
    eq : Equilibrium, optional
        Equilibrium that will be optimized to satisfy the objectives.
    verbose : int, optional
        Level of output.
    perturb_options, solve_options : dict
        dictionary of arguments passed to Equilibrium.perturb and Equilibrium.solve
        during the projection step.
    """

    def __init__(
        self,
        objective,
        constraint,
        eq=None,
        verbose=1,
        perturb_options=None,
        solve_options=None,
    ):
        assert isinstance(objective, ObjectiveFunction), (
            "objective should be instance of ObjectiveFunction." ""
        )
        assert isinstance(constraint, ObjectiveFunction), (
            "constraint should be instance of ObjectiveFunction." ""
        )
        for con in constraint.objectives:
            if not con._equilibrium:
                raise ValueError(
                    "ProximalProjection method "
                    + "cannot handle general nonlinear constraint {}.".format(con)
                )
        self._objective = objective
        self._constraint = constraint
        solve_options = {} if solve_options is None else solve_options
        perturb_options = {} if perturb_options is None else perturb_options
        perturb_options.setdefault("verbose", 0)
        perturb_options.setdefault("include_f", False)
        solve_options.setdefault("verbose", 0)
        self._perturb_options = perturb_options
        self._solve_options = solve_options
        self._built = False
        # don't want to compile this, just use the compiled objective and constraint
        self._use_jit = False
        self._compiled = False

        if eq is not None:
            self.build(eq, verbose=verbose)

    def build(self, eq, use_jit=None, verbose=1):  # noqa: C901
        """Build the objective.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
            Note: unused by this class, should pass to sub-objectives directly.
        verbose : int, optional
            Level of output.

        """
        timer = Timer()
        timer.start("Proximal projection build")

        self._eq = eq.copy()
        self._linear_constraints = get_fixed_boundary_constraints(
            iota=self._eq.iota is not None,
            kinetic=self._eq.electron_temperature is not None,
        )

        if not self._objective.built:
            self._objective.build(self._eq, verbose=verbose)
        if not self._constraint.built:
            self._constraint.build(self._eq, verbose=verbose)
        # remove constraints that aren't necessary
        self._linear_constraints = tuple(
            [
                con
                for con in self._linear_constraints
                if con.args[0] in self._constraint.args
            ]
        )
        for constraint in self._linear_constraints:
            constraint.build(self._eq, verbose=verbose)
        self._objectives = self._objective.objectives

        self._dim_f = self._objective.dim_f
        if self._dim_f == 1:
            self._scalar = True
        else:
            self._scalar = False

        # this is everything taken by either objective
        self._full_args = self._constraint.args + self._objective.args
        self._full_args = [arg for arg in arg_order if arg in self._full_args]

        # arguments being optimized are all args, but with internal degrees of freedom
        # replaced by boundary terms
        self._args = self._full_args.copy()
        if "L_lmn" in self._args:
            self._args.remove("L_lmn")
        if "R_lmn" in self._args:
            self._args.remove("R_lmn")
            if "Rb_lmn" not in self._args:
                self._args.append("Rb_lmn")
        if "Z_lmn" in self._args:
            self._args.remove("Z_lmn")
            if "Zb_lmn" not in self._args:
                self._args.append("Zb_lmn")

        self._dimensions = self._objective.dimensions
        self._dim_x = 0
        self._x_idx = {}
        for arg in self.args:
            self.x_idx[arg] = np.arange(self._dim_x, self._dim_x + self.dimensions[arg])
            self._dim_x += self.dimensions[arg]
        self._dim_x_full = 0
        self._x_idx_full = {}
        for arg in self._full_args:
            self._x_idx_full[arg] = np.arange(
                self._dim_x_full, self._dim_x_full + self.dimensions[arg]
            )
            self._dim_x_full += self.dimensions[arg]

        (
            xp,
            A,
            self._Ainv,
            b,
            self._Z,
            self._unfixed_idx,
            project,
            recover,
        ) = factorize_linear_constraints(self._linear_constraints, self._full_args)

        # dx/dc - goes from the full state to optimization variables
        x_idx = np.concatenate(
            [
                self._x_idx_full[arg]
                for arg in self._args
                if arg not in ["Rb_lmn", "Zb_lmn"]
            ]
        )
        x_idx.sort(kind="mergesort")
        self._dxdc = np.eye(self._dim_x_full)[:, x_idx]
        if "Rb_lmn" in self._args:
            dxdRb = (
                np.eye(self._dim_x_full)[:, self._x_idx_full["R_lmn"]]
                @ self._Ainv["R_lmn"]
            )
            self._dxdc = np.hstack((self._dxdc, dxdRb))
        if "Zb_lmn" in self._args:
            dxdZb = (
                np.eye(self._dim_x_full)[:, self._x_idx_full["Z_lmn"]]
                @ self._Ainv["Z_lmn"]
            )
            self._dxdc = np.hstack((self._dxdc, dxdZb))

        # history and caching
        self._x_old = np.zeros((self._dim_x,))
        for arg in self.args:
            self._x_old[self.x_idx[arg]] = getattr(eq, arg)

        self._allx = [self._x_old]
        self._allxopt = [self._objective.x(eq)]
        self._allxeq = [self._constraint.x(eq)]
        self.history = {}
        for arg in arg_order:
            self.history[arg] = [np.asarray(getattr(self._eq, arg)).copy()]

        self._built = True
        timer.stop("Proximal projection build")
        if verbose > 1:
            timer.disp("Proximal projection build")

    def compile(self, mode="lsq", verbose=1):
        """Call the necessary functions to ensure the function is compiled.

        Parameters
        ----------
        mode : {"auto", "lsq", "scalar", "all"}
            Whether to compile for least squares optimization or scalar optimization.
            "auto" compiles based on the type of objective,
            "all" compiles all derivatives.
        verbose : int, optional
            Level of output.

        """
        self._objective.compile(mode, verbose)
        self._constraint.compile(mode, verbose)

    def _update_equilibrium(self, x, store=False):
        """Update the internal equilibrium with new boundary, profile etc.

        Parameters
        ----------
        x : ndarray
            New values of optimization variables.
        store : bool
            Whether the new x should be stored in self.history

        Notes
        -----
        After updating, if store=False, self._eq will revert back to the previous
        solution when store was True
        """
        # first check if its something we've seen before, if it is just return
        # cached value, no need to perturb + resolve
        xopt = f_where_x(x, self._allx, self._allxopt)
        xeq = f_where_x(x, self._allx, self._allxeq)
        if xopt.size > 0 and xeq.size > 0:
            pass
        else:
            x_dict = self.unpack_state(x)
            x_dict_old = self.unpack_state(self._x_old)
            deltas = {str(key): x_dict[key] - x_dict_old[key] for key in x_dict}
            self._eq = self._eq.perturb(
                objective=self._constraint,
                constraints=self._linear_constraints,
                deltas=deltas,
                **self._perturb_options
            )
            self._eq.solve(
                objective=self._constraint,
                constraints=self._linear_constraints,
                **self._solve_options
            )
            xopt = self._objective.x(self._eq)
            xeq = self._constraint.x(self._eq)
            self._allx.append(x)
            self._allxopt.append(xopt)
            self._allxeq.append(xeq)

        if store:
            self._x_old = x
            xd = self.unpack_state(x)
            xod = self._objective.unpack_state(xopt)
            xed = self._constraint.unpack_state(xeq)
            xd.update(xod)
            xd.update(xed)
            for arg in arg_order:
                val = xd.get(arg, self.history[arg][-1])
                self.history[arg] += [np.asarray(val).copy()]
                # ensure eq has correct values if we didn't go into else block above.
                if val.size:
                    setattr(self._eq, arg, val)
            for con in self._linear_constraints:
                con.update_target(self._eq)
        else:
            for arg in arg_order:
                val = self.history[arg][-1].copy()
                if val.size:
                    setattr(self._eq, arg, val)
            for con in self._linear_constraints:
                con.update_target(self._eq)
        return xopt, xeq

    def compute_scaled(self, x):
        """Compute the objective function.

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        xopt, _ = self._update_equilibrium(x, store=False)
        return self._objective.compute_scaled(xopt)

    def compute_unscaled(self, x):
        """Compute the objective function.

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        xopt, _ = self._update_equilibrium(x, store=False)
        return self._objective.compute_unscaled(xopt)

    def grad(self, x):
        """Compute gradient of the sum of squares of residuals.

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        g : ndarray
            gradient vector.
        """
        f = jnp.atleast_1d(self.compute(x))
        J = self.jac_scaled(x)
        return f.T @ J

    def jac_unscaled(self, x):
        """Compute Jacobian of the vector objective function without weights / bounds.

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        J : ndarray
            Jacobian matrix.
        """
        raise NotImplementedError("Unscaled jacobian of proximal projection is hard.")

    def jac_scaled(self, x):
        """Compute Jacobian of the vector objective function with weights / bounds.

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        J : ndarray
            Jacobian matrix.
        """
        xg, xf = self._update_equilibrium(x, store=True)

        # Jacobian matrices wrt combined state vectors
        Fx = self._constraint.jac_scaled(xf)
        Gx = self._objective.jac_scaled(xg)
        Fx = align_jacobian(Fx, self._constraint, self._objective)
        Gx = align_jacobian(Gx, self._objective, self._constraint)

        # projections onto optimization space
        # possibly better way: Gx @ np.eye(Gx.shape[1])[:,self._unfixed_idx] @ self._Z
        Fx_reduced = Fx[:, self._unfixed_idx] @ self._Z
        Gx_reduced = Gx[:, self._unfixed_idx] @ self._Z
        Fc = Fx @ self._dxdc
        Gc = Gx @ self._dxdc

        # some scaling to improve conditioning
        wf, _ = compute_jac_scale(Fx_reduced)
        wg, _ = compute_jac_scale(Gx_reduced)
        wx = wf + wg
        Fxh = Fx_reduced * wx
        Gxh = Gx_reduced * wx

        cutoff = np.finfo(Fxh.dtype).eps * np.max(Fxh.shape)
        uf, sf, vtf = np.linalg.svd(Fxh, full_matrices=False)
        sf += sf[-1]  # add a tiny bit of regularization
        sfi = np.where(sf < cutoff * sf[0], 0, 1 / sf)
        Fxh_inv = vtf.T @ (sfi[..., np.newaxis] * uf.T)

        # TODO: make this more efficient for finite differences etc. Can probably
        # reduce the number of operations and tangents
        LHS = Gxh @ (Fxh_inv @ Fc) - Gc
        return -LHS

    def hess(self, x):
        """Compute Hessian of the sum of squares of residuals.

        Uses the "small residual approximation" where the Hessian is replaced by
        the square of the Jacobian: H = J.T @ J

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        H : ndarray
            Hessian matrix.
        """
        J = self.jac_scaled(x)
        return J.T @ J

    @property
    def target(self):
        """ndarray: target vector."""
        return self._objective.target

    @property
    def bounds(self):
        """tuple: lower and upper bounds for residual vector."""
        return self._objective.bounds

    @property
    def weights(self):
        """ndarray: weight vector."""
        return self._objective.weights
