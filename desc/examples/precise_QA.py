"""Example script for recreating the precise QA configuration of Landreman and Paul."""

from desc import set_device

set_device("gpu")

import numpy as np

from desc.continuation import solve_continuation_automatic
from desc.equilibrium import EquilibriaFamily, Equilibrium
from desc.geometry import FourierRZToroidalSurface
from desc.grid import LinearGrid
from desc.objectives import (
    AspectRatio,
    FixBoundaryR,
    FixBoundaryZ,
    FixCurrent,
    FixPressure,
    FixPsi,
    ForceBalance,
    ObjectiveFunction,
    QuasisymmetryTwoTerm,
    RotationalTransform,
)
from desc.optimize import Optimizer

# create initial equilibrium
surf = FourierRZToroidalSurface(
    R_lmn=[1, 0.166, 0.1],
    Z_lmn=[-0.166, -0.1],
    modes_R=[[0, 0], [1, 0], [0, 1]],
    modes_Z=[[-1, 0], [0, -1]],
    NFP=2,
)
eq = Equilibrium(M=8, N=8, Psi=0.087, surface=surf)
eq = solve_continuation_automatic(eq, objective="force", bdry_step=0.5, verbose=3)[-1]
eqfam = EquilibriaFamily(eq)

# optimize in steps
grid = LinearGrid(M=eq.M, N=eq.N, NFP=eq.NFP, rho=np.array([0.6, 0.8, 1.0]), sym=True)
for n in range(1, eq.M + 1):
    print("\n==================================")
    print("Optimizing boundary modes M,N <= {}".format(n))
    print("====================================")
    objective = ObjectiveFunction(
        (
            QuasisymmetryTwoTerm(helicity=(1, 0), grid=grid, normalize=False),
            AspectRatio(target=6, weight=1e1, normalize=False),
            RotationalTransform(target=0.42, weight=10, normalize=False),
        ),
        verbose=0,
    )
    R_modes = np.vstack(
        (
            [0, 0, 0],
            eq.surface.R_basis.modes[
                np.max(np.abs(eq.surface.R_basis.modes), 1) > n, :
            ],
        )
    )
    Z_modes = eq.surface.Z_basis.modes[
        np.max(np.abs(eq.surface.Z_basis.modes), 1) > n, :
    ]
    constraints = (
        ForceBalance(),  # J x B - grad(p) = 0
        FixBoundaryR(modes=R_modes),
        FixBoundaryZ(modes=Z_modes),
        FixPressure(),
        FixCurrent(),
        FixPsi(),
    )
    optimizer = Optimizer("lsq-exact")
    eq_new, out = eqfam[-1].optimize(
        objective=objective,
        constraints=constraints,
        optimizer=optimizer,
        maxiter=50,
        verbose=3,
        copy=True,
        options={
            "initial_trust_radius": 0.5,
            "perturb_options": {"verbose": 0},
            "solve_options": {"verbose": 0},
        },
    )
    eqfam.append(eq_new)

eqfam.save("precise_QA_output.h5")
