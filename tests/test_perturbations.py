import unittest
import numpy as np

from desc.backend import jnp
from desc.equilibrium import Equilibrium
from desc.objective_funs import ObjectiveFunction, FixedPressure
from desc.perturbations import perturb


class TestPerturbations(unittest.TestCase):
    """Test pertubations."""

    def test_perturb_1D(self):
        """Linear test function where perturb order=1 is exact."""

        # circular tokamak
        inputs = {
            "sym": True,
            "NFP": 1,
            "Psi": 1.0,
            "L": 2,
            "M": 1,
            "N": 0,
            "profiles": np.zeros((1, 3)),  # no pressure
            "boundary": np.array([[0, -1, 0, 0, 1], [0, 0, 0, 5, 0], [0, 1, 0, 1, 0]]),
        }
        dp = 1e3 * np.array([1, 0, -1])  # perturbed pressure profile

        eq_old = Equilibrium(inputs=inputs)
        objective = ObjectiveFunction(FixedPressure(), eq=eq_old)

        eq_new = perturb(eq_old, objective, dp=dp, order=1, verbose=2, copy=True)

        np.testing.assert_allclose(eq_new.p_l, dp)

    def test_perturb_2D(self):
        """Nonlinear test function to check perturb convergence rates."""
        pass
