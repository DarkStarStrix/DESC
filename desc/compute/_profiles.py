from scipy.constants import elementary_charge, mu_0

from desc.backend import jnp

from .data_index import register_compute_fun
from .utils import cumtrapz, dot, surface_averages, surface_integrals


@register_compute_fun(
    name="psi",
    label="\\psi = \\Psi / (2 \\pi)",
    units="Wb",
    units_long="Webers",
    description="Toroidal flux (normalized by 2pi)",
    dim=1,
    params=["Psi"],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["rho"],
)
def _psi(params, transforms, profiles, data, **kwargs):
    data["psi"] = params["Psi"] * data["rho"] ** 2 / (2 * jnp.pi)
    return data


@register_compute_fun(
    name="psi_r",
    label="\\partial_{\\rho} \\psi = \\partial_{\\rho} \\Psi / (2 \\pi)",
    units="Wb",
    units_long="Webers",
    description="Toroidal flux (normalized by 2pi), first radial derivative",
    dim=1,
    params=["Psi"],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["rho"],
)
def _psi_r(params, transforms, profiles, data, **kwargs):
    data["psi_r"] = params["Psi"] * data["rho"] / jnp.pi
    return data


@register_compute_fun(
    name="psi_rr",
    label="\\partial_{\\rho\\rho} \\psi = \\partial_{\\rho\\rho} \\Psi / (2 \\pi)",
    units="Wb",
    units_long="Webers",
    description="Toroidal flux (normalized by 2pi), second radial derivative",
    dim=1,
    params=["Psi"],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["rho"],
)
def _psi_rr(params, transforms, profiles, data, **kwargs):
    data["psi_rr"] = params["Psi"] * jnp.ones_like(data["rho"]) / jnp.pi
    return data


@register_compute_fun(
    name="psi_rrr",
    label="\\partial_{\\rho\\rho\\rho} \\psi = \\partial_{\\rho\\rho\\rho} \\Psi / "
    + "(2 \\pi)",
    units="Wb",
    units_long="Webers",
    description="Toroidal flux (normalized by 2pi), third radial derivative",
    dim=1,
    params=["Psi"],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["0"],
)
def _psi_rrr(params, transforms, profiles, data, **kwargs):
    data["psi_rrr"] = data["0"]
    return data


@register_compute_fun(
    name="chi_r",
    label="\\partial_{\\rho} \\chi",
    units="Wb",
    units_long="Webers",
    description="Poloidal flux (normalized by 2pi), first radial derivative",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["psi_r", "iota"],
)
def _chi_r(params, transforms, profiles, data, **kwargs):
    data["chi_r"] = data["psi_r"] * data["iota"]
    return data


@register_compute_fun(
    name="chi",
    label="\\chi",
    units="Wb",
    units_long="Webers",
    description="Poloidal flux (normalized by 2pi)",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["chi_r", "rho"],
)
def _chi(params, transforms, profiles, data, **kwargs):
    chi_r = transforms["grid"].compress(data["chi_r"])
    chi = cumtrapz(chi_r, transforms["grid"].compress(data["rho"]), initial=0)
    data["chi"] = transforms["grid"].expand(chi)
    return data


@register_compute_fun(
    name="Te",
    label="T_e",
    units="eV",
    units_long="electron-Volts",
    description="Electron temperature",
    dim=1,
    params=["Te_l"],
    transforms={},
    profiles=["electron_temperature"],
    coordinates="r",
    data=["0"],
)
def _Te(params, transforms, profiles, data, **kwargs):
    if profiles["electron_temperature"] is not None:
        data["Te"] = profiles["electron_temperature"].compute(params["Te_l"], dr=0)
    else:
        data["Te"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Te_r",
    label="\\partial_{\\rho} T_e",
    units="eV",
    units_long="electron-Volts",
    description="Electron temperature, first radial derivative",
    dim=1,
    params=["Te_l"],
    transforms={},
    profiles=["electron_temperature"],
    coordinates="r",
    data=["0"],
)
def _Te_r(params, transforms, profiles, data, **kwargs):
    if profiles["electron_temperature"] is not None:
        data["Te_r"] = profiles["electron_temperature"].compute(params["Te_l"], dr=1)
    else:
        data["Te_r"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Te_rr",
    label="\\partial_{\\rho \\rho} T_e",
    units="eV",
    units_long="electron-Volts",
    description="Electron temperature, second radial derivative",
    dim=1,
    params=["Te_l"],
    transforms={},
    profiles=["electron_temperature"],
    coordinates="r",
    data=["0"],
)
def _Te_rr(params, transforms, profiles, data, **kwargs):
    if profiles["electron_temperature"] is not None:
        data["Te_rr"] = profiles["electron_temperature"].compute(params["Te_l"], dr=2)
    else:
        data["Te_rr"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="ne",
    label="n_e",
    units="m^{-3}",
    units_long="1 / cubic meters",
    description="Electron density",
    dim=1,
    params=["ne_l"],
    transforms={},
    profiles=["electron_density"],
    coordinates="r",
    data=["0"],
)
def _ne(params, transforms, profiles, data, **kwargs):
    if profiles["electron_density"] is not None:
        data["ne"] = profiles["electron_density"].compute(params["ne_l"], dr=0)
    else:
        data["ne"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="ne_r",
    label="\\partial_{\\rho} n_e",
    units="m^{-3}",
    units_long="1 / cubic meters",
    description="Electron density, first radial derivative",
    dim=1,
    params=["ne_l"],
    transforms={},
    profiles=["electron_density"],
    coordinates="r",
    data=["0"],
)
def _ne_r(params, transforms, profiles, data, **kwargs):
    if profiles["electron_density"] is not None:
        data["ne_r"] = profiles["electron_density"].compute(params["ne_l"], dr=1)
    else:
        data["ne_r"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="ne_rr",
    label="\\partial_{\\rho \\rho} n_e",
    units="m^{-3}",
    units_long="1 / cubic meters",
    description="Electron density, second radial derivative",
    dim=1,
    params=["ne_l"],
    transforms={},
    profiles=["electron_density"],
    coordinates="r",
    data=["0"],
)
def _ne_rr(params, transforms, profiles, data, **kwargs):
    if profiles["electron_density"] is not None:
        data["ne_rr"] = profiles["electron_density"].compute(params["ne_l"], dr=2)
    else:
        data["ne_rr"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Ti",
    label="T_i",
    units="eV",
    units_long="electron-Volts",
    description="Ion temperature",
    dim=1,
    params=["Ti_l"],
    transforms={},
    profiles=["ion_temperature"],
    coordinates="r",
    data=["0"],
)
def _Ti(params, transforms, profiles, data, **kwargs):
    if profiles["ion_temperature"] is not None:
        data["Ti"] = profiles["ion_temperature"].compute(params["Ti_l"], dr=0)
    else:
        data["Ti"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Ti_r",
    label="\\partial_{\\rho} T_i",
    units="eV",
    units_long="electron-Volts",
    description="Ion temperature, first radial derivative",
    dim=1,
    params=["Ti_l"],
    transforms={},
    profiles=["ion_temperature"],
    coordinates="r",
    data=["0"],
)
def _Ti_r(params, transforms, profiles, data, **kwargs):
    if profiles["ion_temperature"] is not None:
        data["Ti_r"] = profiles["ion_temperature"].compute(params["Ti_l"], dr=1)
    else:
        data["Ti_r"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Ti_rr",
    label="\\partial_{\\rho \\rho} T_i",
    units="eV",
    units_long="electron-Volts",
    description="Ion temperature, second radial derivative",
    dim=1,
    params=["Ti_l"],
    transforms={},
    profiles=["ion_temperature"],
    coordinates="r",
    data=["0"],
)
def _Ti_rr(params, transforms, profiles, data, **kwargs):
    if profiles["ion_temperature"] is not None:
        data["Ti_rr"] = profiles["ion_temperature"].compute(params["Ti_l"], dr=2)
    else:
        data["Ti_rr"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Zeff",
    label="Z_{eff}",
    units="~",
    units_long="None",
    description="Effective atomic number",
    dim=1,
    params=["Zeff_l"],
    transforms={},
    profiles=["atomic_number"],
    coordinates="r",
    data=["0"],
)
def _Zeff(params, transforms, profiles, data, **kwargs):
    if profiles["atomic_number"] is not None:
        data["Zeff"] = profiles["atomic_number"].compute(params["Zeff_l"], dr=0)
    else:
        data["Zeff"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="Zeff_r",
    label="\\partial_{\\rho} Z_{eff}",
    units="~",
    units_long="None",
    description="Effective atomic number, first radial derivative",
    dim=1,
    params=["Zeff_l"],
    transforms={},
    profiles=["atomic_number"],
    coordinates="r",
    data=["0"],
)
def _Zeff_r(params, transforms, profiles, data, **kwargs):
    if profiles["atomic_number"] is not None:
        data["Zeff_r"] = profiles["atomic_number"].compute(params["Zeff_l"], dr=1)
    else:
        data["Zeff_r"] = jnp.nan * data["0"]
    return data


@register_compute_fun(
    name="p",
    label="p",
    units="Pa",
    units_long="Pascals",
    description="Pressure",
    dim=1,
    params=["p_l"],
    transforms={},
    profiles=["pressure"],
    coordinates="r",
    data=["Te", "ne", "Ti", "Zeff"],
)
def _p(params, transforms, profiles, data, **kwargs):
    if profiles["pressure"] is not None:
        data["p"] = profiles["pressure"].compute(params["p_l"], dr=0)
    else:
        data["p"] = elementary_charge * (
            data["ne"] * data["Te"] + data["Ti"] * data["ne"] / data["Zeff"]
        )
    return data


@register_compute_fun(
    name="p_r",
    label="\\partial_{\\rho} p",
    units="Pa",
    units_long="Pascals",
    description="Pressure, first radial derivative",
    dim=1,
    params=["p_l"],
    transforms={},
    profiles=["pressure"],
    coordinates="r",
    data=["Te", "Te_r", "ne", "ne_r", "Ti", "Ti_r", "Zeff", "Zeff_r"],
)
def _p_r(params, transforms, profiles, data, **kwargs):
    if profiles["pressure"] is not None:
        data["p_r"] = profiles["pressure"].compute(params["p_l"], dr=1)
    else:
        data["p_r"] = elementary_charge * (
            data["ne_r"] * data["Te"]
            + data["ne"] * data["Te_r"]
            + data["Ti_r"] * data["ne"] / data["Zeff"]
            + data["Ti"] * data["ne_r"] / data["Zeff"]
            - data["Ti"] * data["ne"] * data["Zeff_r"] / data["Zeff"] ** 2
        )
    return data


@register_compute_fun(
    name="grad(p)",
    label="\\nabla p",
    units="N \\cdot m^{-3}",
    units_long="Newtons / cubic meter",
    description="Pressure gradient",
    dim=3,
    params=[],
    transforms={},
    profiles=[],
    coordinates="rtz",
    data=["p_r", "e^rho"],
)
def _gradp(params, transforms, profiles, data, **kwargs):
    data["grad(p)"] = (data["p_r"] * data["e^rho"].T).T
    return data


@register_compute_fun(
    name="|grad(p)|^2",
    label="|\\nabla p|^{2}",
    units="N^2 \\cdot m^{-6}",
    units_long="Newtons per cubic meter squared",
    description="Magnitude of pressure gradient squared",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="rtz",
    data=["grad(p)"],
)
def _gradp_mag2(params, transforms, profiles, data, **kwargs):
    data["|grad(p)|^2"] = dot(data["grad(p)"], data["grad(p)"])
    return data


@register_compute_fun(
    name="|grad(p)|",
    label="|\\nabla p|",
    units="N \\cdot m^{-3}",
    units_long="Newtons per cubic meter",
    description="Magnitude of pressure gradient",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="rtz",
    data=["|grad(p)|^2"],
)
def _gradp_mag(params, transforms, profiles, data, **kwargs):
    data["|grad(p)|"] = jnp.sqrt(data["|grad(p)|^2"])
    return data


@register_compute_fun(
    name="<|grad(p)|>_vol",
    label="\\langle |\\nabla p| \\rangle_{vol}",
    units="N \\cdot m^{-3}",
    units_long="Newtons per cubic meter",
    description="Volume average of magnitude of pressure gradient",
    dim=0,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="",
    data=["|grad(p)|", "sqrt(g)", "V"],
)
def _gradp_mag_vol(params, transforms, profiles, data, **kwargs):
    data["<|grad(p)|>_vol"] = (
        jnp.sum(data["|grad(p)|"] * data["sqrt(g)"] * transforms["grid"].weights)
        / data["V"]
    )
    return data


@register_compute_fun(
    name="iota",
    label="\\iota",
    units="~",
    units_long="None",
    description="Rotational transform (normalized by 2pi)",
    dim=1,
    params=["i_l", "c_l"],
    transforms={"grid": []},
    profiles=["iota", "current"],
    coordinates="r",
    data=["iota_zero_current_den", "iota_zero_current_num", "psi_r"],
    axis_limit_data=["psi_rr", "psi_rrr"],
)
def _iota(params, transforms, profiles, data, **kwargs):
    if profiles["iota"] is not None:
        data["iota"] = profiles["iota"].compute(params["i_l"], dr=0)
    elif profiles["current"] is not None:
        # I = mu_0 profiles["current"] / 2π
        # params["Psi"] = 2π data["psi"]
        # supplement = 8π^3 I / params["Psi"]_r = 2π mu_0 profiles["current"] / psi_r
        # Supplement iota with additional term for the enclosed net toroidal current.
        supplement = (
            jnp.pi
            * mu_0
            * transforms["grid"].replace_at_axis(
                2 * profiles["current"].compute(params["c_l"], dr=0) / data["psi_r"],
                # Assumes current profile (zero derivative) is 0 at magnetic axis.
                # Below is the supplement term of the magnetic axis limit of iota,
                # not the magnetic axis limit of the supplement term.
                lambda: profiles["current"].compute(params["c_l"], dr=2)
                / data["psi_rr"]
                - profiles["current"].compute(params["c_l"], dr=1)
                * data["psi_rrr"]
                / data["psi_rr"] ** 2,
            )
        )
        data["iota"] = (supplement + data["iota_zero_current_num"]) / data[
            "iota_zero_current_den"
        ]
    return data


@register_compute_fun(
    name="iota_r",
    label="\\partial_{\\rho} \\iota",
    units="~",
    units_long="None",
    description="Rotational transform (normalized by 2pi), first radial derivative",
    dim=1,
    params=["i_l", "c_l"],
    transforms={"grid": []},
    profiles=["iota", "current"],
    coordinates="r",
    data=[
        "iota",
        "iota_zero_current_den",
        "iota_zero_current_den_r",
        "iota_zero_current_num_r",
        "psi_r",
        "psi_rr",
        "psi_rrr",
    ],
)
def _iota_r(params, transforms, profiles, data, **kwargs):
    if profiles["iota"] is not None:
        data["iota_r"] = profiles["iota"].compute(params["i_l"], dr=1)
    elif profiles["current"] is not None:
        # I = mu_0 profiles["current"] / 2π
        # params["Psi"] = 2π data["psi"]
        # supplement = 8π^3 I / params["Psi"]_r = 2π mu_0 profiles["current"] / psi_r
        # Supplement iota with additional term for the enclosed net toroidal current.
        current_r = profiles["current"].compute(params["c_l"], dr=1)
        supplement_r = (
            jnp.pi
            * mu_0
            * transforms["grid"].replace_at_axis(
                2 * current_r / data["psi_r"]
                - 2
                * profiles["current"].compute(params["c_l"], dr=0)
                * data["psi_rr"]
                / data["psi_r"] ** 2,
                # Assumes current profile (zero derivative) is 0 at magnetic axis.
                lambda: profiles["current"].compute(params["c_l"], dr=2)
                / data["psi_rr"]
                - current_r * data["psi_rrr"] / data["psi_rr"] ** 2,
            )
        )
        data["iota_r"] = (
            supplement_r
            + data["iota_zero_current_num_r"]
            - data["iota"] * data["iota_zero_current_den_r"]
        ) / data["iota_zero_current_den"]  # FIXME denominator limit wrong, actually 0...
    return data


@register_compute_fun(
    name="iota_rr",
    label="\\partial_{\\rho\\rho} \\iota",
    units="~",
    units_long="None",
    description="Rotational transform (normalized by 2pi), second radial derivative",
    dim=1,
    params=["i_l", "c_l"],
    transforms={"grid": []},
    profiles=["iota", "current"],
    coordinates="r",
    data=[
        "iota",
        "iota_r",
        "iota_zero_current_den",
        "iota_zero_current_den_r",
        "iota_zero_current_den_rr",
        "iota_zero_current_num_rr",
        "psi_r",
        "psi_rr",
        "psi_rrr",
    ],
)
def _iota_rr(params, transforms, profiles, data, **kwargs):
    if profiles["iota"] is not None:
        data["iota_rr"] = profiles["iota"].compute(params["i_l"], dr=2)
    elif profiles["current"] is not None:
        # I = mu_0 profiles["current"] / 2π
        # params["Psi"] = 2π data["psi"]
        # supplement = 8π^3 I / params["Psi"]_r = 2π mu_0 profiles["current"] / psi_r
        # Supplement iota with additional term for the enclosed net toroidal current.
        current_r = profiles["current"].compute(params["c_l"], dr=1)
        current_rr = profiles["current"].compute(params["c_l"], dr=2)
        supplement_rr = (
            jnp.pi
            * mu_0
            * transforms["grid"].replace_at_axis(
                2 * current_rr / data["psi_r"]
                - 4 * current_r * data["psi_rr"] / data["psi_r"] ** 2
                + 2
                * profiles["current"].compute(params["c_l"], dr=0)
                * (2 * data["psi_rr"] ** 2 - data["psi_rrr"] * data["psi_r"])
                / data["psi_r"] ** 3,
                # Assumes current profile (zero derivative) is 0 at magnetic axis.
                lambda: 2
                * profiles["current"].compute(params["c_l"], dr=3)
                / (3 * data["psi_rr"])
                - current_rr * data["psi_rrr"] / data["psi_rr"] ** 2
                + current_r * data["psi_rrr"] ** 2 / data["psi_rr"] ** 3,
            )
        )
        data["iota_rr"] = (
            supplement_rr
            + data["iota_zero_current_num_rr"]
            - 2 * data["iota_r"] * data["iota_zero_current_den_r"]
            - data["iota"] * data["iota_zero_current_den_rr"]
        ) / data["iota_zero_current_den"]  # FIXME denominator limit wrong, actually 0...
    return data


@register_compute_fun(
    name="iota_zero_current_num",
    label="\\iota_{0} numerator",
    units="m^{-1}",
    units_long="inverse meters",
    description="Zero toroidal current rotational transform numerator",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["lambda_z", "g_tt", "lambda_t", "g_tz", "sqrt(g)"],
    axis_limit_data=[
        "lambda_rt",
        "g_tt_rr",
        "g_tz_r",
        "g_tz_rr",
        "sqrt(g)_r",
        "sqrt(g)_rr",
    ],
)
def _iota_zero_current_num(params, transforms, profiles, data, **kwargs):
    num = transforms["grid"].replace_at_axis(
        (data["lambda_z"] * data["g_tt"] - (1 + data["lambda_t"]) * data["g_tz"])
        / data["sqrt(g)"],
        # Below is the numerator of the magnetic axis limit of iota (without
        # the supplement term for net toroidal current), not the magnetic axis
        # limit of the numerator of iota.
        lambda: (
            (1 + data["lambda_t"])
            * data["g_tz_r"]
            * data["sqrt(g)_rr"]
            / data["sqrt(g)_r"] ** 2
            + (
                data["lambda_z"] * data["g_tt_rr"]
                - 2 * data["lambda_rt"] * data["g_tz_r"]
                - (1 + data["lambda_t"]) * data["g_tz_rr"]
            )
            / data["sqrt(g)_r"]
        )
        / 2,
    )
    data["iota_zero_current_num"] = surface_integrals(transforms["grid"], num)
    return data


@register_compute_fun(
    name="iota_zero_current_num_r",
    label="\\partial_{\\rho} \\iota_{0} numerator",
    units="m^{-1}",
    units_long="inverse meters",
    description="Zero toroidal current rotational transform numerator,"
    " first radial derivative",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=[
        "lambda_t",
        "lambda_rt",
        "lambda_z",
        "lambda_rz",
        "g_tt",
        "g_tt_r",
        "g_tz",
        "g_tz_r",
        "sqrt(g)",
        "sqrt(g)_r",
    ],
    axis_limit_data=["g_tt_rr", "g_tz_rr", "sqrt(g)_rr"],
)
def _iota_zero_current_num_r(params, transforms, profiles, data, **kwargs):
    num = (
        data["lambda_z"] * data["g_tt"] - (1 + data["lambda_t"]) * data["g_tz"]
    ) / data["sqrt(g)"]
    num_r = transforms["grid"].replace_at_axis(
        (
            data["lambda_rz"] * data["g_tt"]
            + data["lambda_z"] * data["g_tt_r"]
            - data["lambda_rt"] * data["g_tz"]
            - (1 + data["lambda_t"]) * data["g_tz_r"]
            - num * data["sqrt(g)_r"]
        )
        / data["sqrt(g)"],
        lambda: (
            (1 + data["lambda_t"])
            * data["g_tz_r"]
            * data["sqrt(g)_rr"]
            / data["sqrt(g)_r"] ** 2
            + (
                data["lambda_z"] * data["g_tt_rr"]
                - 2 * data["lambda_rt"] * data["g_tz_r"]
                - (1 + data["lambda_t"]) * data["g_tz_rr"]
            )
            / data["sqrt(g)_r"]
        )
        / 2,
    )
    data["iota_zero_current_num_r"] = surface_integrals(transforms["grid"], num_r)
    return data


@register_compute_fun(
    name="iota_zero_current_num_rr",
    label="\\partial_{\\rho\\rho} \\iota_{0} numerator",
    units="m^{-1}",
    units_long="inverse meters",
    description="Zero toroidal current rotational transform numerator,"
    " second radial derivative",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=[
        "lambda_t",
        "lambda_rt",
        "lambda_rrt",
        "lambda_z",
        "lambda_rz",
        "lambda_rrz",
        "g_tt",
        "g_tt_r",
        "g_tt_rr",
        "g_tz",
        "g_tz_r",
        "g_tz_rr",
        "sqrt(g)",
        "sqrt(g)_r",
        "sqrt(g)_rr",
    ],
    axis_limit_data=["sqrt(g)_rrr", "g_tt_rrr", "g_tz_rrr"],
)
def _iota_zero_current_num_rr(params, transforms, profiles, data, **kwargs):
    num = (
        data["lambda_z"] * data["g_tt"] - (1 + data["lambda_t"]) * data["g_tz"]
    ) / data["sqrt(g)"]
    num_r = (
        data["lambda_rz"] * data["g_tt"]
        + data["lambda_z"] * data["g_tt_r"]
        - data["lambda_rt"] * data["g_tz"]
        - (1 + data["lambda_t"]) * data["g_tz_r"]
        - num * data["sqrt(g)_r"]
    ) / data["sqrt(g)"]
    num_rr = transforms["grid"].replace_at_axis(
        (
            data["lambda_rrz"] * data["g_tt"]
            + 2 * data["lambda_rz"] * data["g_tt_r"]
            + data["lambda_z"] * data["g_tt_rr"]
            - data["lambda_rrt"] * data["g_tz"]
            - 2 * data["lambda_rt"] * data["g_tz_r"]
            - (1 + data["lambda_t"]) * data["g_tz_rr"]
            - 2 * num_r * data["sqrt(g)_r"]
            - num * data["sqrt(g)_rr"]
        )
        / data["sqrt(g)"],
        lambda: (
            2
            * data["sqrt(g)_r"] ** 2
            * (
                3 * data["g_tt_rr"] * data["lambda_rz"]
                + data["g_tt_rrr"] * data["lambda_z"]
                - 3 * data["g_tz_rr"] * data["lambda_rt"]
                - 3 * data["g_tz_r"] * data["lambda_rrt"]
                - data["g_tz_rrr"] * (1 + data["lambda_t"])
            )
            + data["sqrt(g)_r"]
            * (
                3
                * data["sqrt(g)_rr"]
                * (
                    2 * data["g_tz_r"] * data["lambda_rt"]
                    - data["g_tt_rr"] * data["lambda_t"]
                    + data["g_tz_rr"] * (1 + data["lambda_t"])
                )
                + 2 * data["sqrt(g)_rrr"] * data["g_tz_r"] * (1 + data["lambda_t"])
            )
            - 3 * data["sqrt(g)_rr"] ** 2 * data["g_tz_r"] * (1 + data["lambda_t"])
        )
        / (6 * data["sqrt(g)_r"] ** 3),
    )
    data["iota_zero_current_num_rr"] = surface_integrals(transforms["grid"], num_rr)
    return data


@register_compute_fun(
    name="iota_zero_current_den",
    label="\\iota_{0} denominator",
    units="m^{-1}",
    units_long="inverse meters",
    description="Zero toroidal current rotational transform denominator",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["g_tt", "g_tz", "sqrt(g)", "omega_t", "omega_z"],
    axis_limit_data=[
        "g_tz_r",
        "sqrt(g)_r",
        "sqrt(g)_rr",
        "g_tt_rr",
        "omega_rt",
        "g_tz_rr",
    ],
)
def _iota_zero_current_den(params, transforms, profiles, data, **kwargs):
    den = transforms["grid"].replace_at_axis(
        ((1 + data["omega_z"]) * data["g_tt"] - data["omega_t"] * data["g_tz"])
        / data["sqrt(g)"],
        # Below is the denominator of the magnetic axis limit of iota (without
        # the supplement term for net toroidal current), not the magnetic axis
        # limit of the denominator of iota.
        lambda: (
            data["omega_t"]
            * data["g_tz_r"]
            * data["sqrt(g)_rr"]
            / data["sqrt(g)_r"] ** 2
            + (
                (1 + data["omega_z"]) * data["g_tt_rr"]
                - 2 * data["omega_rt"] * data["g_tz_r"]
                - data["omega_t"] * data["g_tz_rr"]
            )
            / data["sqrt(g)_r"]
        )
        / 2,
    )
    data["iota_zero_current_den"] = surface_integrals(transforms["grid"], den)
    return data


@register_compute_fun(
    name="iota_zero_current_den_r",
    label="\\partial_{\\rho} \\iota_{0} denominator",
    units="m^{-1}",
    units_long="inverse meters",
    description="Zero toroidal current rotational transform denominator,"
    " first radial derivative",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=[
        "g_tt",
        "g_tt_r",
        "g_tz",
        "g_tz_r",
        "sqrt(g)",
        "sqrt(g)_r",
        "omega_t",
        "omega_rt",
        "omega_z",
        "omega_rz",
    ],
    axis_limit_data=["sqrt(g)_rr", "g_tt_rr", "g_tz_rr"],
)
def _iota_zero_current_den_r(params, transforms, profiles, data, **kwargs):
    den = (
        (1 + data["omega_z"]) * data["g_tt"] - data["omega_t"] * data["g_tz"]
    ) / data["sqrt(g)"]
    den_r = transforms["grid"].replace_at_axis(
        (
            data["omega_rz"] * data["g_tt"]
            + (1 + data["omega_z"]) * data["g_tt_r"]
            - data["omega_rt"] * data["g_tz"]
            - data["omega_t"] * data["g_tz_r"]
            - den * data["sqrt(g)_r"]
        )
        / data["sqrt(g)"],
        lambda: (
            data["omega_t"]
            * data["g_tz_r"]
            * data["sqrt(g)_rr"]
            / data["sqrt(g)_r"] ** 2
            + (
                (1 + data["omega_z"]) * data["g_tt_rr"]
                - 2 * data["omega_rt"] * data["g_tz_r"]
                - data["omega_t"] * data["g_tz_rr"]
            )
            / data["sqrt(g)_r"]
        )
        / 2,
    )
    data["iota_zero_current_den_r"] = surface_integrals(transforms["grid"], den_r)
    return data


@register_compute_fun(
    name="iota_zero_current_den_rr",
    label="\\partial_{\\rho\\rho} \\iota_{0} denominator",
    units="m^{-1}",
    units_long="inverse meters",
    description="Zero toroidal current rotational transform denominator,"
    " second radial derivative",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=[
        "g_tt",
        "g_tt_r",
        "g_tt_rr",
        "g_tz",
        "g_tz_r",
        "g_tz_rr",
        "sqrt(g)",
        "sqrt(g)_r",
        "sqrt(g)_rr",
        "omega_t",
        "omega_rt",
        "omega_rrt",
        "omega_z",
        "omega_rz",
        "omega_rrz",
    ],
    axis_limit_data=["sqrt(g)_rrr", "g_tt_rrr", "g_tz_rrr"],
)
def _iota_zero_current_den_rr(params, transforms, profiles, data, **kwargs):
    den = (
        (1 + data["omega_z"]) * data["g_tt"] - data["omega_t"] * data["g_tz"]
    ) / data["sqrt(g)"]
    den_r = (
        data["omega_rz"] * data["g_tt"]
        + (1 + data["omega_z"]) * data["g_tt_r"]
        - data["omega_rt"] * data["g_tz"]
        - data["omega_t"] * data["g_tz_r"]
        - den * data["sqrt(g)_r"]
    ) / data["sqrt(g)"]
    den_rr = transforms["grid"].replace_at_axis(
        (
            data["omega_rrz"] * data["g_tt"]
            + 2 * data["omega_rz"] * data["g_tt_r"]
            + (1 + data["omega_z"]) * data["g_tt_rr"]
            - data["omega_rrt"] * data["g_tz"]
            - 2 * data["omega_rt"] * data["g_tz_r"]
            - data["omega_t"] * data["g_tz_rr"]
            - 2 * den_r * data["sqrt(g)_r"]
            - den * data["sqrt(g)_rr"]
        )
        / data["sqrt(g)"],
        lambda: (
            2
            * data["sqrt(g)_r"] ** 2
            * (
                3 * data["g_tt_rr"] * data["omega_rz"]
                + data["g_tt_rrr"] * (1 + data["omega_z"])
                - 3 * data["g_tz_rr"] * data["omega_rt"]
                - 3 * data["g_tz_r"] * data["omega_rrt"]
                - data["g_tz_rrr"] * data["omega_t"]
            )
            + data["sqrt(g)_r"]
            * (
                3
                * data["sqrt(g)_rr"]
                * (
                    2 * data["g_tz_r"] * data["omega_rt"]
                    - data["g_tt_rr"] * (1 + data["omega_z"])
                    + data["g_tz_rr"] * data["omega_t"]
                )
                + 2 * data["sqrt(g)_rrr"] * data["g_tz_r"] * data["omega_t"]
            )
            - 3 * data["sqrt(g)_rr"] ** 2 * data["g_tz_r"] * data["omega_t"]
        )
        / (6 * data["sqrt(g)_r"] ** 3),
    )
    data["iota_zero_current_den_rr"] = surface_integrals(transforms["grid"], den_rr)
    return data


@register_compute_fun(
    name="q",
    label="q = 1/\\iota",
    units="~",
    units_long="None",
    description="Safety factor 'q', inverse of rotational transform.",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["iota"],
)
def _q(params, transforms, profiles, data, **kwargs):
    data["q"] = 1 / data["iota"]
    return data


# TODO: add K(rho,theta,zeta)*grad(rho) term
@register_compute_fun(
    name="I",
    label="I",
    units="T \\cdot m",
    units_long="Tesla * meters",
    description="Covariant poloidal component of magnetic field in Boozer coordinates "
    + "(proportional to toroidal current)",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["B_theta"],
)
def _I(params, transforms, profiles, data, **kwargs):
    data["I"] = surface_averages(transforms["grid"], data["B_theta"])
    return data


@register_compute_fun(
    name="I_r",
    label="\\partial_{\\rho} I",
    units="T \\cdot m",
    units_long="Tesla * meters",
    description="Covariant poloidal component of magnetic field in Boozer coordinates "
    + "(proportional to toroidal current), derivative wrt radial coordinate",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["B_theta_r"],
)
def _I_r(params, transforms, profiles, data, **kwargs):
    data["I_r"] = surface_averages(transforms["grid"], data["B_theta_r"])
    return data


@register_compute_fun(
    name="I_rr",
    label="\\partial_{\\rho\\rho} I",
    units="T \\cdot m",
    units_long="Tesla * meters",
    description="Boozer toroidal current enclosed by flux surfaces, second derivative "
    + "wrt radial coordinate",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["B_theta_rr"],
)
def _I_rr(params, transforms, profiles, data, **kwargs):
    data["I_rr"] = surface_averages(transforms["grid"], data["B_theta_rr"])
    return data


@register_compute_fun(
    name="G",
    label="G",
    units="T \\cdot m",
    units_long="Tesla * meters",
    description="Covariant toroidal component of magnetic field in Boozer coordinates "
    + "(proportional to poloidal current)",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["B_zeta"],
)
def _G(params, transforms, profiles, data, **kwargs):
    data["G"] = surface_averages(transforms["grid"], data["B_zeta"])
    return data


@register_compute_fun(
    name="G_r",
    label="\\partial_{\\rho} G",
    units="T \\cdot m",
    units_long="Tesla * meters",
    description="Covariant toroidal component of magnetic field in Boozer coordinates "
    + "(proportional to poloidal current), derivative wrt radial coordinate",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["B_zeta_r"],
)
def _G_r(params, transforms, profiles, data, **kwargs):
    data["G_r"] = surface_averages(transforms["grid"], data["B_zeta_r"])
    return data


@register_compute_fun(
    name="G_rr",
    label="\\partial_{\\rho\\rho} G",
    units="T \\cdot m",
    units_long="Tesla * meters",
    description="Boozer poloidal current enclosed by flux surfaces, second derivative "
    + "wrt radial coordinate",
    dim=1,
    params=[],
    transforms={"grid": []},
    profiles=[],
    coordinates="r",
    data=["B_zeta_rr"],
)
def _G_rr(params, transforms, profiles, data, **kwargs):
    data["G_rr"] = surface_averages(transforms["grid"], data["B_zeta_rr"])
    return data


@register_compute_fun(
    name="current",
    label="\\frac{2\\pi}{\\mu_0} I",
    units="A",
    units_long="Amperes",
    description="Net toroidal current enclosed by flux surfaces",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["I"],
)
def _current(params, transforms, profiles, data, **kwargs):
    data["current"] = 2 * jnp.pi / mu_0 * data["I"]
    return data


@register_compute_fun(
    name="current_r",
    label="\\frac{2\\pi}{\\mu_0} \\partial_{\\rho} I",
    units="A",
    units_long="Amperes",
    description="Net toroidal current enclosed by flux surfaces, derivative "
    + "wrt radial coordinate",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["I_r"],
)
def _current_r(params, transforms, profiles, data, **kwargs):
    data["current_r"] = 2 * jnp.pi / mu_0 * data["I_r"]
    return data


@register_compute_fun(
    name="current_rr",
    label="\\frac{2\\pi}{\\mu_0} \\partial_{\\rho\\rho} I",
    units="A",
    units_long="Amperes",
    description="Net toroidal current enclosed by flux surfaces, second derivative "
    + "wrt radial coordinate",
    dim=1,
    params=[],
    transforms={},
    profiles=[],
    coordinates="r",
    data=["I_rr"],
)
def _current_rr(params, transforms, profiles, data, **kwargs):
    data["current_rr"] = 2 * jnp.pi / mu_0 * data["I_rr"]
    return data
