"""Base classes for objectives."""

import warnings
from abc import ABC, abstractmethod

import numpy as np

from desc.backend import jit, jnp, use_jax
from desc.derivatives import Derivative
from desc.io import IOAble
from desc.optimizeable import Optimizeable
from desc.utils import Timer, errorif, flatten_list, is_broadcastable, sort_things

from .utils import map_params


class ObjectiveFunction(IOAble):
    """Objective function comprised of one or more Objectives.

    Parameters
    ----------
    objectives : tuple of Objective
        List of objectives to be minimized.
    use_jit : bool, optional
        Whether to just-in-time compile the objectives and derivatives.
    deriv_mode : {"batched", "looped"}
        method for computing derivatives. "batched" is generally faster, "looped" may
        use less memory.
    verbose : int, optional
        Level of output.

    """

    _io_attrs_ = ["_objectives"]

    def __init__(self, objectives, use_jit=True, deriv_mode="batched", verbose=1):
        if not isinstance(objectives, (tuple, list)):
            objectives = (objectives,)
        assert all(
            isinstance(obj, _Objective) for obj in objectives
        ), "members of ObjectiveFunction should be instances of _Objective"
        assert use_jit in {True, False}
        assert deriv_mode in {"batched", "looped"}

        self._objectives = objectives
        self._use_jit = use_jit
        self._deriv_mode = deriv_mode
        self._built = False
        self._compiled = False

    def _set_derivatives(self):
        """Set up derivatives of the objective functions."""
        if self._deriv_mode in {"batched", "looped"}:
            self._grad = Derivative(self.compute_scalar, mode="grad")
            self._hess = Derivative(self.compute_scalar, mode="hess")
        if self._deriv_mode == "batched":
            self._jac_scaled = Derivative(self.compute_scaled, mode="fwd")
            self._jac_unscaled = Derivative(self.compute_unscaled, mode="fwd")
        if self._deriv_mode == "looped":
            self._jac_scaled = Derivative(self.compute_scaled, mode="looped")
            self._jac_unscaled = Derivative(self.compute_unscaled, mode="looped")

    def jit(self):  # noqa: C901
        """Apply JIT to compute methods, or re-apply after updating self."""
        # can't loop here because del doesn't work on getattr
        # main idea is that when jitting a method, jax replaces that method
        # with a CompiledFunction object, with self compiled in. To re-jit
        # (ie, after updating attributes of self), we just need to delete the jax
        # CompiledFunction object, which will then leave the raw method in its place,
        # and then jit the raw method with the new self

        self._use_jit = True

        try:
            del self.compute_scaled
        except AttributeError:
            pass
        self.compute_scaled = jit(self.compute_scaled)

        try:
            del self.compute_scaled_error
        except AttributeError:
            pass
        self.compute_scaled_error = jit(self.compute_scaled_error)

        try:
            del self.compute_unscaled
        except AttributeError:
            pass
        self.compute_unscaled = jit(self.compute_unscaled)

        try:
            del self.compute_scalar
        except AttributeError:
            pass
        self.compute_scalar = jit(self.compute_scalar)

        try:
            del self.jac_scaled
        except AttributeError:
            pass
        self.jac_scaled = jit(self.jac_scaled)

        try:
            del self.jac_unscaled
        except AttributeError:
            pass
        self.jac_unscaled = jit(self.jac_unscaled)

        try:
            del self.hess
        except AttributeError:
            pass
        self.hess = jit(self.hess)

        try:
            del self.grad
        except AttributeError:
            pass
        self.grad = jit(self.grad)

        try:
            del self.jvp_scaled
        except AttributeError:
            pass
        self.jvp_scaled = jit(self.jvp_scaled)

        try:
            del self.jvp_unscaled
        except AttributeError:
            pass
        self.jvp_unscaled = jit(self.jvp_unscaled)

        try:
            del self.vjp_scaled
        except AttributeError:
            pass
        self.vjp_scaled = jit(self.vjp_scaled)

        try:
            del self.vjp_unscaled
        except AttributeError:
            pass
        self.vjp_unscaled = jit(self.vjp_unscaled)

        for obj in self._objectives:
            if obj._use_jit:
                obj.jit()

    def build(self, eq=None, use_jit=None, verbose=1):
        """Build the objective.

        Parameters
        ----------
        eq : Equilibrium, optional
            Equilibrium that will be optimized to satisfy the Objective.
        use_jit : bool, optional
            Whether to just-in-time compile the objective and derivatives.
        verbose : int, optional
            Level of output.

        """
        if use_jit is not None:
            self._use_jit = use_jit
        timer = Timer()
        timer.start("Objective build")

        # build objectives
        self._dim_f = 0
        for objective in self.objectives:
            if verbose > 0:
                print("Building objective: " + objective.name)
            objective.build(eq, use_jit=self.use_jit, verbose=verbose)
            self._dim_f += objective.dim_f
        if self._dim_f == 1:
            self._scalar = True
        else:
            self._scalar = False

        self._set_derivatives()
        if self.use_jit:
            self.jit()

        self._built = True
        timer.stop("Objective build")
        if verbose > 1:
            timer.disp("Objective build")

    def compute_unscaled(self, x, constants=None):
        """Compute the raw value of the objective function.

        Parameters
        ----------
        x : ndarray
            State vector.
        constants : list
            Constant parameters passed to sub-objectives.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        params = self.unpack_state(x)
        if constants is None:
            constants = self.constants
        f = jnp.concatenate(
            [
                obj.compute_unscaled(
                    *map_params(params, obj, self.things), constants=const
                )
                for obj, const in zip(self.objectives, constants)
            ]
        )
        return f

    def compute_scaled(self, x, constants=None):
        """Compute the objective function and apply weighting and normalization.

        Parameters
        ----------
        x : ndarray
            State vector.
        constants : list
            Constant parameters passed to sub-objectives.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        params = self.unpack_state(x)
        if constants is None:
            constants = self.constants
        f = jnp.concatenate(
            [
                obj.compute_scaled(
                    *map_params(params, obj, self.things), constants=const
                )
                for obj, const in zip(self.objectives, constants)
            ]
        )
        return f

    def compute_scaled_error(self, x, constants=None):
        """Compute and apply the target/bounds, weighting, and normalization.

        Parameters
        ----------
        x : ndarray
            State vector.
        constants : list
            Constant parameters passed to sub-objectives.

        Returns
        -------
        f : ndarray
            Objective function value(s).

        """
        params = self.unpack_state(x)
        if constants is None:
            constants = self.constants
        f = jnp.concatenate(
            [
                obj.compute_scaled_error(
                    *map_params(params, obj, self.things), constants=const
                )
                for obj, const in zip(self.objectives, constants)
            ]
        )
        return f

    def compute_scalar(self, x, constants=None):
        """Compute the sum of squares error.

        Parameters
        ----------
        x : ndarray
            State vector.
        constants : list
            Constant parameters passed to sub-objectives.

        Returns
        -------
        f : float
            Objective function scalar value.

        """
        f = jnp.sum(self.compute_scaled_error(x, constants=constants) ** 2) / 2
        return f

    def print_value(self, x, constants=None):
        """Print the value(s) of the objective.

        Parameters
        ----------
        x : ndarray
            State vector.
        constants : list
            Constant parameters passed to sub-objectives.

        """
        if constants is None:
            constants = self.constants
        if self.compiled and self._compile_mode in {"scalar", "all"}:
            f = self.compute_scalar(x, constants=constants)
        else:
            f = jnp.sum(self.compute_scaled(x, constants=constants) ** 2) / 2
        print("Total (sum of squares): {:10.3e}, ".format(f))
        params = self.unpack_state(x)
        for obj, const in zip(self.objectives, constants):
            obj.print_value(*map_params(params, obj, self.things), constants=const)
        return None

    def unpack_state(self, x):
        """Unpack the state vector into its components.

        Parameters
        ----------
        x : ndarray
            State vector.

        Returns
        -------
        params : list of dict
            List of parameter dictionary for each optimizeable object tied to the
            ObjectiveFunction.

        """
        if not self.built:
            raise RuntimeError("ObjectiveFunction must be built first.")

        x = jnp.atleast_1d(x)
        if x.size != self.dim_x:
            raise ValueError(
                "Input vector dimension is invalid, expected "
                + f"{self.dim_x} got {x.size}."
            )

        xs_splits = np.cumsum([t.dim_x for t in self.things])
        xs = jnp.split(x, xs_splits)
        params = [t.unpack_params(xi) for t, xi in zip(self.things, xs)]
        return params

    def x(self, *things):
        """Return the full state vector from the Optimizeable objects things."""
        # TODO: also check resolution etc?
        assert [type(t1) == type(t2) for t1, t2 in zip(things, self.things)]
        xs = [t.pack_params(t.params_dict) for t in things]
        return jnp.concatenate(xs)

    def grad(self, x, constants=None):
        """Compute gradient vector of scalar form of the objective wrt x."""
        if constants is None:
            constants = self.constants
        return jnp.atleast_1d(self._grad(x, constants).squeeze())

    def hess(self, x, constants=None):
        """Compute Hessian matrix of scalar form of the objective wrt x."""
        if constants is None:
            constants = self.constants
        return jnp.atleast_2d(self._hess(x, constants).squeeze())

    def jac_scaled(self, x, constants=None):
        """Compute Jacobian matrx of vector form of the objective wrt x."""
        if constants is None:
            constants = self.constants
        return jnp.atleast_2d(self._jac_scaled(x, constants).squeeze())

    def jac_unscaled(self, x, constants=None):
        """Compute Jacobian matrx of vector form of the objective wrt x, unweighted."""
        if constants is None:
            constants = self.constants
        return jnp.atleast_2d(self._jac_unscaled(x, constants).squeeze())

    def jvp_scaled(self, v, x):
        """Compute Jacobian-vector product of the objective function.

        Uses the scaled form of the objective.

        Parameters
        ----------
        v : tuple of ndarray
            Vectors to right-multiply the Jacobian by.
            The number of vectors given determines the order of derivative taken.
        x : ndarray
            Optimization variables.

        """
        if not isinstance(v, tuple):
            v = (v,)
        if len(v) == 1:
            return Derivative.compute_jvp(self.compute_scaled, 0, v[0], x)
        elif len(v) == 2:
            return Derivative.compute_jvp2(self.compute_scaled, 0, 0, v[0], v[1], x)
        elif len(v) == 3:
            return Derivative.compute_jvp3(
                self.compute_scaled, 0, 0, 0, v[0], v[1], v[2], x
            )
        else:
            raise NotImplementedError("Cannot compute JVP higher than 3rd order.")

    def jvp_unscaled(self, v, x):
        """Compute Jacobian-vector product of the objective function.

        Uses the unscaled form of the objective.

        Parameters
        ----------
        v : tuple of ndarray
            Vectors to right-multiply the Jacobian by.
            The number of vectors given determines the order of derivative taken.
        x : ndarray
            Optimization variables.

        """
        if not isinstance(v, tuple):
            v = (v,)
        if len(v) == 1:
            return Derivative.compute_jvp(self.compute_unscaled, 0, v[0], x)
        elif len(v) == 2:
            return Derivative.compute_jvp2(self.compute_unscaled, 0, 0, v[0], v[1], x)
        elif len(v) == 3:
            return Derivative.compute_jvp3(
                self.compute_unscaled, 0, 0, 0, v[0], v[1], v[2], x
            )
        else:
            raise NotImplementedError("Cannot compute JVP higher than 3rd order.")

    def vjp_scaled(self, v, x):
        """Compute vector-Jacobian product of the objective function.

        Uses the scaled form of the objective.

        Parameters
        ----------
        v : ndarray
            Vector to left-multiply the Jacobian by.
        x : ndarray
            Optimization variables.

        """
        return Derivative.compute_vjp(self.compute_scaled, 0, v, x)

    def vjp_unscaled(self, v, x):
        """Compute vector-Jacobian product of the objective function.

        Uses the unscaled form of the objective.

        Parameters
        ----------
        v : ndarray
            Vector to left-multiply the Jacobian by.
        x : ndarray
            Optimization variables.

        """
        return Derivative.compute_vjp(self.compute_unscaled, 0, v, x)

    def compile(self, mode="auto", verbose=1):
        """Call the necessary functions to ensure the function is compiled.

        Parameters
        ----------
        mode : {"auto", "lsq", "scalar", "bfgs", "all"}
            Whether to compile for least squares optimization or scalar optimization.
            "auto" compiles based on the type of objective, either scalar or lsq
            "bfgs" compiles only scalar objective and gradient,
            "all" compiles all derivatives.
        verbose : int, optional
            Level of output.

        """
        if not self.built:
            raise RuntimeError("ObjectiveFunction must be built first.")
        if not use_jax:
            self._compiled = True
            return

        timer = Timer()
        if mode == "auto" and self.scalar:
            mode = "scalar"
        elif mode == "auto":
            mode = "lsq"
        self._compile_mode = mode
        # variable values are irrelevant for compilation
        x = np.zeros((self.dim_x,))

        if verbose > 0:
            print(
                "Compiling objective function and derivatives: "
                + f"{[obj.name for obj in self.objectives]}"
            )
        timer.start("Total compilation time")

        if mode in ["scalar", "bfgs", "all"]:
            timer.start("Objective compilation time")
            _ = self.compute_scalar(x, self.constants).block_until_ready()
            timer.stop("Objective compilation time")
            if verbose > 1:
                timer.disp("Objective compilation time")
            timer.start("Gradient compilation time")
            _ = self.grad(x, self.constants).block_until_ready()
            timer.stop("Gradient compilation time")
            if verbose > 1:
                timer.disp("Gradient compilation time")
        if mode in ["scalar", "all"]:
            timer.start("Hessian compilation time")
            _ = self.hess(x, self.constants).block_until_ready()
            timer.stop("Hessian compilation time")
            if verbose > 1:
                timer.disp("Hessian compilation time")
        if mode in ["lsq", "all"]:
            timer.start("Objective compilation time")
            _ = self.compute_scaled(x, self.constants).block_until_ready()
            timer.stop("Objective compilation time")
            if verbose > 1:
                timer.disp("Objective compilation time")
            timer.start("Jacobian compilation time")
            _ = self.jac_scaled(x, self.constants).block_until_ready()
            timer.stop("Jacobian compilation time")
            if verbose > 1:
                timer.disp("Jacobian compilation time")

        timer.stop("Total compilation time")
        if verbose > 1:
            timer.disp("Total compilation time")
        self._compiled = True

    @property
    def constants(self):
        """list: constant parameters for each sub-objective."""
        return [obj.constants for obj in self.objectives]

    @property
    def objectives(self):
        """list: List of objectives."""
        return self._objectives

    @property
    def use_jit(self):
        """bool: Whether to just-in-time compile the objective and derivatives."""
        return self._use_jit

    @property
    def scalar(self):
        """bool: Whether default "compute" method is a scalar or vector."""
        if not self._built:
            raise RuntimeError("ObjectiveFunction must be built first.")
        return self._scalar

    @property
    def built(self):
        """bool: Whether the objectives have been built or not."""
        return self._built

    @property
    def compiled(self):
        """bool: Whether the functions have been compiled or not."""
        return self._compiled

    @property
    def dim_x(self):
        """int: Dimensional of the state vector."""
        return sum(t.dim_x for t in self.things)

    @property
    def dim_f(self):
        """int: Number of objective equations."""
        if not self.built:
            raise RuntimeError("ObjectiveFunction must be built first.")
        return self._dim_f

    @property
    def target_scaled(self):
        """ndarray: target vector."""
        target = []
        for obj in self.objectives:
            if obj.target is not None:
                target_i = jnp.ones(obj.dim_f) * obj.target
            else:
                # need to return something, so use midpoint of bounds as approx target
                target_i = jnp.ones(obj.dim_f) * (obj.bounds[0] + obj.bounds[1]) / 2
            if obj._normalize_target:
                target_i /= obj.normalization
            target += [target_i]
        return jnp.concatenate(target)

    @property
    def bounds_scaled(self):
        """tuple: lower and upper bounds for residual vector."""
        lb, ub = [], []
        for obj in self.objectives:
            if obj.bounds is not None:
                lb_i = jnp.ones(obj.dim_f) * obj.bounds[0]
                ub_i = jnp.ones(obj.dim_f) * obj.bounds[1]
            else:
                lb_i = jnp.ones(obj.dim_f) * obj.target
                ub_i = jnp.ones(obj.dim_f) * obj.target
            if obj._normalize_target:
                lb_i /= obj.normalization
                ub_i /= obj.normalization
            lb += [lb_i]
            ub += [ub_i]
        return (jnp.concatenate(lb), jnp.concatenate(ub))

    @property
    def weights(self):
        """ndarray: weight vector."""
        return jnp.concatenate(
            [jnp.ones(obj.dim_f) * obj.weight for obj in self.objectives]
        )

    @property
    def things(self):
        """list: Optimizeable things that this objective is tied to."""
        return sort_things([obj.things for obj in self._objectives])

    @things.setter
    def things(self, new):
        if not isinstance(new, (tuple, list)):
            new = [new]
        assert all(isinstance(x, Optimizeable) for x in new)
        # in general this is a hard problem, since we don't really know which object
        # to replace with which if there are multiple of the same type, but we can
        # do our best and throw an error if we can't figure it out here.
        inclasses = {thing.__class__ for thing in new}
        classes = {thing.__class__ for thing in self.things}
        errorif(
            len(inclasses) != len(new) or len(classes) != len(self.things),
            ValueError,
            "Cannot unambiguosly parse Optimizeable objects to individual Objectives,"
            + " try setting Objective.things on each sub Objective individually.",
        )
        # now we know that new and self.things contains instances of unique classes, so
        # we should be able to just replace like with like
        for obj in self.objectives:
            objthings = obj.things.copy()
            for i, thing1 in enumerate(obj.things):
                for thing2 in new:
                    if type(thing1) == type(thing2):
                        objthings[i] = thing2
            obj.things = objthings


class _Objective(IOAble, ABC):
    """Objective (or constraint) used in the optimization of an Equilibrium.

    Parameters
    ----------
    things : Optimizeable or tuple/list of Optimizeable
        Objects that will be optimized to satisfy the Objective.
    target : float, ndarray, optional
        Target value(s) of the objective. Only used if bounds is None.
        len(target) must be equal to Objective.dim_f
    bounds : tuple, optional
        Lower and upper bounds on the objective. Overrides target.
        len(bounds[0]) and len(bounds[1]) must be equal to Objective.dim_f
    weight : float, ndarray, optional
        Weighting to apply to the Objective, relative to other Objectives.
        len(weight) must be equal to Objective.dim_f
    normalize : bool
        Whether to compute the error in physical units or non-dimensionalize.
    normalize_target : bool
        Whether target and bounds should be normalized before comparing to computed
        values. If `normalize` is `True` and the target is in physical units,
        this should also be set to True.
    name : str
        Name of the objective function.

    """

    _scalar = False
    _linear = False
    _equilibrium = False
    _io_attrs_ = [
        "_target",
        "_weight",
        "_name",
        "_normalize",
        "_normalize_target",
        "_normalization",
    ]

    def __init__(
        self,
        things=None,
        target=0,
        bounds=None,
        weight=1,
        normalize=True,
        normalize_target=True,
        name=None,
    ):
        assert np.all(np.asarray(weight) > 0)
        assert normalize in {True, False}
        assert normalize_target in {True, False}
        assert (bounds is None) or (isinstance(bounds, tuple) and len(bounds) == 2)
        assert (bounds is None) or (target is None), "Cannot use both bounds and target"
        self._target = target
        self._bounds = bounds
        self._weight = weight
        self._normalize = normalize
        self._normalize_target = normalize_target
        self._normalization = 1
        self._name = name
        self._use_jit = None
        self._built = False
        if things is None:
            warnings.warn(
                FutureWarning(
                    "Creating an Objective without specifying the Equilibrium to"
                    " optimize is deprecated, in the future this will raise an error."
                )
            )
        self._things = flatten_list([things], True)

    def _set_derivatives(self):
        """Set up derivatives of the objective wrt each argument."""
        self._grad = Derivative(self.compute_scalar, mode="grad")
        self._hess = Derivative(self.compute_scalar, mode="hess")
        self._jac_scaled = Derivative(self.compute_scaled, mode="fwd")
        self._jac_unscaled = Derivative(self.compute_unscaled, mode="fwd")

    def jit(self):  # noqa: C901
        """Apply JIT to compute methods, or re-apply after updating self."""
        self._use_jit = True

        try:
            del self.compute_scaled
        except AttributeError:
            pass
        self.compute_scaled = jit(self.compute_scaled)

        try:
            del self.compute_scaled_error
        except AttributeError:
            pass
        self.compute_scaled_error = jit(self.compute_scaled_error)

        try:
            del self.compute_unscaled
        except AttributeError:
            pass
        self.compute_unscaled = jit(self.compute_unscaled)

        try:
            del self.compute_scalar
        except AttributeError:
            pass
        self.compute_scalar = jit(self.compute_scalar)

        try:
            del self.jac_scaled
        except AttributeError:
            pass
        self.jac_scaled = jit(self.jac_scaled)

        try:
            del self.jac_unscaled
        except AttributeError:
            pass
        self.jac_unscaled = jit(self.jac_unscaled)

        try:
            del self.hess
        except AttributeError:
            pass
        self.hess = jit(self.hess)

        try:
            del self.grad
        except AttributeError:
            pass
        self.grad = jit(self.grad)

    def _check_dimensions(self):
        """Check that len(target) = len(bounds) = len(weight) = dim_f."""
        if self.bounds is not None:  # must be a tuple of length 2
            self._bounds = tuple([np.asarray(bound) for bound in self._bounds])
            for bound in self.bounds:
                if not is_broadcastable((self.dim_f,), bound.shape):
                    raise ValueError("len(bounds) != dim_f")
            if np.any(self.bounds[1] < self.bounds[0]):
                raise ValueError("bounds must be: (lower bound, upper bound)")
        else:  # target only gets used if bounds is None
            self._target = np.asarray(self._target)
            if not is_broadcastable((self.dim_f,), self.target.shape):
                raise ValueError("len(target) != dim_f")

        self._weight = np.asarray(self._weight)
        if not is_broadcastable((self.dim_f,), self.weight.shape):
            raise ValueError("len(weight) != dim_f")

    def update_target(self, eq):
        """Update target values using an Equilibrium.

        Parameters
        ----------
        eq : Equilibrium
            Equilibrium that will be optimized to satisfy the Objective.

        """
        self.target = np.atleast_1d(getattr(eq, self.target_arg, self.target))
        if self._use_jit:
            self.jit()

    @abstractmethod
    def build(self, things=None, use_jit=True, verbose=1):
        """Build constant arrays."""
        self._check_dimensions()
        self._set_derivatives()
        if use_jit is not None:
            self._use_jit = use_jit
        if self._use_jit:
            self.jit()
        self._built = True

    @abstractmethod
    def compute(self, *args, **kwargs):
        """Compute the objective function."""

    def compute_unscaled(self, *args, **kwargs):
        """Compute the raw value of the objective."""
        return jnp.atleast_1d(self.compute(*args, **kwargs))

    def compute_scaled(self, *args, **kwargs):
        """Compute and apply weighting and normalization."""
        f = self.compute(*args, **kwargs)
        return self._scale(f)

    def compute_scaled_error(self, *args, **kwargs):
        """Compute and apply the target/bounds, weighting, and normalization."""
        f = self.compute(*args, **kwargs)
        return self._scale(self._shift(f))

    def _shift(self, f):
        """Subtract target or clamp to bounds."""
        if self.bounds is not None:  # using lower/upper bounds instead of target
            if self._normalize_target:
                bounds = self.bounds
            else:
                bounds = tuple([bound * self.normalization for bound in self.bounds])
            f_target = jnp.where(  # where f is within target bounds, return 0 error
                jnp.logical_and(f >= bounds[0], f <= bounds[1]),
                jnp.zeros_like(f),
                jnp.where(  # otherwise return error = f - bound
                    jnp.abs(f - bounds[0]) < jnp.abs(f - bounds[1]),
                    f - bounds[0],  # errors below lower bound are negative
                    f - bounds[1],  # errors above upper bound are positive
                ),
            )
        else:  # using target instead of lower/upper bounds
            if self._normalize_target:
                target = self.target
            else:
                target = self.target * self.normalization
            f_target = f - target
        return f_target

    def _scale(self, f):
        """Apply weighting, normalization etc."""
        f_norm = jnp.atleast_1d(f) / self.normalization  # normalization
        return f_norm * self.weight  # weighting

    def compute_scalar(self, *args, **kwargs):
        """Compute the scalar form of the objective."""
        if self.scalar:
            f = self.compute_scaled_error(*args, **kwargs)
        else:
            f = jnp.sum(self.compute_scaled_error(*args, **kwargs) ** 2) / 2
        return f.squeeze()

    def grad(self, *args, **kwargs):
        """Compute gradient vector of scalar form of the objective wrt x."""
        return self._grad(*args, **kwargs)

    def hess(self, *args, **kwargs):
        """Compute Hessian matrix of scalar form of the objective wrt x."""
        return self._hess(*args, **kwargs)

    def jac_scaled(self, *args, **kwargs):
        """Compute Jacobian matrx of vector form of the objective wrt x."""
        return self._jac_scaled(*args, **kwargs)

    def jac_unscaled(self, *args, **kwargs):
        """Compute Jacobian matrx of vector form of the objective wrt x, unweighted."""
        return self._jac_unscaled(*args, **kwargs)

    def print_value(self, *args, **kwargs):
        """Print the value of the objective."""
        f = self.compute_unscaled(*args, **kwargs)
        print(
            self._print_value_fmt.format(jnp.linalg.norm(self._shift(f))) + self._units
        )
        if self._normalize:
            print(
                self._print_value_fmt.format(
                    jnp.linalg.norm(self._scale(self._shift(f)))
                )
                + "(normalized)"
            )

    def xs(self, *things):
        """Return a tuple of args required by this objective from the Equilibrium eq."""
        return tuple([t.params_dict for t in things])

    @property
    def constants(self):
        """dict: Constant parameters such as transforms and profiles."""
        if hasattr(self, "_constants"):
            return self._constants
        return None

    @property
    def target(self):
        """float: Target value(s) of the objective."""
        return self._target

    @target.setter
    def target(self, target):
        self._target = np.atleast_1d(target)
        self._check_dimensions()

    @property
    def bounds(self):
        """tuple: Lower and upper bounds of the objective."""
        return self._bounds

    @bounds.setter
    def bounds(self, bounds):
        assert (bounds is None) or (isinstance(bounds, tuple) and len(bounds) == 2)
        self._bounds = bounds
        self._check_dimensions()

    @property
    def weight(self):
        """float: Weighting to apply to the Objective, relative to other Objectives."""
        return self._weight

    @weight.setter
    def weight(self, weight):
        assert np.all(np.asarray(weight) > 0)
        self._weight = np.atleast_1d(weight)
        self._check_dimensions()

    @property
    def normalization(self):
        """float: normalizing scale factor."""
        if self._normalize and not self.built:
            raise ValueError("Objective must be built first")
        return self._normalization

    @property
    def built(self):
        """bool: Whether the transforms have been precomputed (or not)."""
        return self._built

    @property
    def target_arg(self):
        """str: Name of argument corresponding to the target."""
        return ""

    @property
    def dim_f(self):
        """int: Number of objective equations."""
        return self._dim_f

    @property
    def scalar(self):
        """bool: Whether default "compute" method is a scalar or vector."""
        return self._scalar

    @property
    def linear(self):
        """bool: Whether the objective is a linear function (or nonlinear)."""
        return self._linear

    @property
    def fixed(self):
        """bool: Whether the objective fixes individual parameters (or linear combo)."""
        if self.linear:
            return self._fixed
        else:
            return False

    @property
    def name(self):
        """Name of objective function (str)."""
        return self._name

    @property
    def things(self):
        """list: Optimizeable things that this objective is tied to."""
        if not hasattr(self, "_things"):
            self._things = []
        return self._things

    @things.setter
    def things(self, new):
        if not isinstance(new, (tuple, list)):
            new = [new]
        assert all(isinstance(x, Optimizeable) for x in new)
        self._things = list(new)
