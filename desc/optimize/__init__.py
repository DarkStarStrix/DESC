"""Functions for minimization and wrappers for scipy methods."""

from . import _desc_wrappers, _scipy_wrappers
from ._constraint_wrappers import (
    DESCNonlinearConstraint,
    LinearConstraintProjection,
    ProximalProjection,
)
from .aug_lagrangian import fmin_lag_stel
from .aug_lagrangian_ls_stel import fmin_lag_ls_stel
from .fmin_scalar import fmintr
from .least_squares import lsqtr
from .optimizer import Optimizer, optimizers, register_optimizer
from .stochastic import sgd
