from .compute_funs import (
    compute_toroidal_flux,
    compute_pressure,
    compute_rotational_transform,
    compute_lambda,
    compute_toroidal_coords,
    compute_cartesian_coords,
    compute_covariant_basis,
    compute_contravariant_basis,
    compute_jacobian,
    compute_covariant_metric_coefficients,
    compute_contravariant_metric_coefficients,
    compute_contravariant_magnetic_field,
    compute_covariant_magnetic_field,
    compute_magnetic_field_magnitude,
    compute_magnetic_pressure_gradient,
    compute_magnetic_tension,
    compute_B_dot_gradB,
    compute_contravariant_current_density,
    compute_force_error,
    compute_quasisymmetry_error,
    compute_volume,
    compute_energy,
)


__all__ = [
    "compute_toroidal_flux",
    "compute_rotational_transform",
    "compute_pressure",
    "compute_lambda",
    "compute_toroidal_coords",
    "compute_cartesian_coords",
    "compute_covariant_basis",
    "compute_contravariant_basis",
    "compute_jacobian",
    "compute_covariant_metric_coefficients",
    "compute_contravariant_metric_coefficients",
    "compute_contravariant_magnetic_field",
    "compute_covariant_magnetic_field",
    "compute_magnetic_field_magnitude",
    "compute_magnetic_pressure_gradient",
    "compute_magnetic_tension",
    "compute_B_dot_gradB",
    "compute_contravariant_current_density",
    "compute_force_error",
    "compute_quasisymmetry_error",
    "compute_volume",
    "compute_energy",
]

# defines the order in which objective arguments get concatenated into the state vector
arg_order = ("R_lmn", "Z_lmn", "L_lmn", "Rb_lmn", "Zb_lmn", "p_l", "i_l", "Psi")

"""Format for data index:
label = (str) title of the quantity in LaTeX format
units = (str) units of the quantity in LaTeX format
fun = (str) function name in compute_funs.py that computes the quantity
dim = (int) dimension of the quantity: 0-D, 1-D, or 3-D
order = (int) order of derivatives of R, Z, lambda required for base quantity
kwargs = (dict) any keyword arguments required to evaluate the quantity
"""

data_index = {
    # 0-D
    "V": {
        "label": "V",
        "units": "m^3",
        "fun": "compute_volume",
        "dim": 0,
        "order": 1,
        "kwargs": {},
    },
    "W": {
        "label": "W",
        "units": "J",
        "fun": "compute_energy",
        "dim": 0,
        "order": 1,
        "kwargs": {"gamma": 0},
    },
    "W_B": {
        "label": "W_B",
        "units": "J",
        "fun": "compute_energy",
        "dim": 0,
        "order": 1,
        "kwargs": {"gamma": 0},
    },
    "W_p": {
        "label": "W_p",
        "units": "J",
        "fun": "compute_energy",
        "dim": 0,
        "order": 1,
        "kwargs": {"gamma": 0},
    },
    # 1-D
    "psi": {
        "label": "\\Psi \\ 2 \\pi",
        "units": "Wb",
        "fun": "compute_toroidal_flux",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0},
    },
    "psi_r": {
        "label": "\\Psi' \\ 2 \\pi",
        "units": "Wb",
        "fun": "compute_toroidal_flux",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 1},
    },
    "psi_rr": {
        "label": "\\Psi'' \\ 2 \\pi",
        "units": "Wb",
        "fun": "compute_toroidal_flux",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 2},
    },
    "p": {
        "label": "p",
        "units": "Pa",
        "fun": "compute_pressure",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0},
    },
    "p_r": {
        "label": "\\partial_{\\rho} p",
        "units": "Pa",
        "fun": "compute_pressure",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 1},
    },
    "iota": {
        "label": "\\iota",
        "units": "",
        "fun": "compute_rotational_transform",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0},
    },
    "iota_r": {
        "label": "\\partial_{\\rho} \\iota",
        "units": "",
        "fun": "compute_rotational_transform",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 1},
    },
    "iota_rr": {
        "label": "\\partial_{\\rho\\rho} \\iota",
        "units": "",
        "fun": "compute_rotational_transform",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 2},
    },
    "lambda": {
        "label": "\\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0, "dt": 0, "dz": 0, "drtz": 1},
    },
    "lambda_r": {
        "label": "\\partial_{\\rho} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 1, "dt": 0, "dz": 0, "drtz": 1},
    },
    "lambda_t": {
        "label": "\\partial_{\\theta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0, "dt": 1, "dz": 0, "drtz": 1},
    },
    "lambda_z": {
        "label": "\\partial_{\\zeta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0, "dt": 0, "dz": 1, "drtz": 1},
    },
    "lambda_rr": {
        "label": "\\partial_{\\rho\\rho} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 2, "dt": 0, "dz": 0, "drtz": 1},
    },
    "lambda_tt": {
        "label": "\\partial_{\\theta\\theta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0, "dt": 2, "dz": 0, "drtz": 1},
    },
    "lambda_zz": {
        "label": "\\partial_{\\zeta\\zeta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0, "dt": 0, "dz": 2, "drtz": 1},
    },
    "lambda_rt": {
        "label": "\\partial_{\\rho\\theta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 1, "dt": 1, "dz": 0, "drtz": 2},
    },
    "lambda_rz": {
        "label": "\\partial_{\\rho\\zeta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 1, "dt": 0, "dz": 1, "drtz": 2},
    },
    "lambda_tz": {
        "label": "\\partial_{\\theta\\zeta} \\lambda",
        "units": "",
        "fun": "compute_lambda",
        "dim": 1,
        "order": 0,
        "kwargs": {"dr": 0, "dt": 1, "dz": 1, "drtz": 2},
    },
    # 3-D
    "B": {
        "label": "B",
        "units": "T",
        "fun": "compute_contravariant_magnetic_field",
        "dim": 3,
        "order": 1,
        "kwargs": {},
    },
}
