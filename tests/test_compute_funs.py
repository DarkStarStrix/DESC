import numpy as np
from scipy.signal import convolve2d
import pytest
from desc.grid import LinearGrid, Grid
from desc.equilibrium import Equilibrium, EquilibriaFamily
from desc.geometry import FourierRZToroidalSurface
from desc.profiles import PowerSeriesProfile


# TODO: add tests for compute_geometry

# convolve kernel is reverse of FD coeffs
FD_COEF_1_2 = np.array([-1 / 2, 0, 1 / 2])[::-1]
FD_COEF_1_4 = np.array([1 / 12, -2 / 3, 0, 2 / 3, -1 / 12])[::-1]
FD_COEF_2_2 = np.array([1, -2, 1])[::-1]
FD_COEF_2_4 = np.array([-1 / 12, 4 / 3, -5 / 2, 4 / 3, -1 / 12])[::-1]


@pytest.mark.slow
def test_magnetic_field_derivatives(DummyStellarator):
    """Test that the partial derivatives of B and |B| match with numerical derivatives
    for a dummy stellarator example."""

    eq = Equilibrium.load(
        load_from=str(DummyStellarator["output_path"]), file_format="hdf5"
    )

    # partial derivatives wrt rho
    L = 50
    grid = LinearGrid(L=L)
    drho = grid.nodes[1, 0]
    data = eq.compute("J", grid)

    B_sup_theta_r = np.convolve(data["B^theta"], FD_COEF_1_4, "same") / drho
    B_sup_zeta_r = np.convolve(data["B^zeta"], FD_COEF_1_4, "same") / drho
    B_sub_rho_r = np.convolve(data["B_rho"], FD_COEF_1_4, "same") / drho
    B_sub_theta_r = np.convolve(data["B_theta"], FD_COEF_1_4, "same") / drho
    B_sub_zeta_r = np.convolve(data["B_zeta"], FD_COEF_1_4, "same") / drho

    np.testing.assert_allclose(
        data["B^theta_r"][3:-2],
        B_sup_theta_r[3:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["B^theta_r"])),
    )
    np.testing.assert_allclose(
        data["B^zeta_r"][3:-2],
        B_sup_zeta_r[3:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["B^zeta_r"])),
    )
    np.testing.assert_allclose(
        data["B_rho_r"][3:-2],
        B_sub_rho_r[3:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["B_rho_r"])),
    )
    np.testing.assert_allclose(
        data["B_theta_r"][3:-2],
        B_sub_theta_r[3:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["B_theta_r"])),
    )
    np.testing.assert_allclose(
        data["B_zeta_r"][3:-2],
        B_sub_zeta_r[3:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["B_zeta_r"])),
    )

    # partial derivatives wrt theta
    M = 90
    grid = LinearGrid(M=M, NFP=eq.NFP)
    dtheta = grid.nodes[1, 1]
    data = eq.compute("J", grid)
    data = eq.compute("|B|_tt", grid, data=data)

    B_sup_theta_t = np.convolve(data["B^theta"], FD_COEF_1_4, "same") / dtheta
    B_sup_theta_tt = np.convolve(data["B^theta"], FD_COEF_2_4, "same") / dtheta ** 2
    B_sup_zeta_t = np.convolve(data["B^zeta"], FD_COEF_1_4, "same") / dtheta
    B_sup_zeta_tt = np.convolve(data["B^zeta"], FD_COEF_2_4, "same") / dtheta ** 2
    B_sub_rho_t = np.convolve(data["B_rho"], FD_COEF_1_4, "same") / dtheta
    B_sub_zeta_t = np.convolve(data["B_zeta"], FD_COEF_1_4, "same") / dtheta
    B_t = np.convolve(data["|B|"], FD_COEF_1_4, "same") / dtheta
    B_tt = np.convolve(data["|B|"], FD_COEF_2_4, "same") / dtheta ** 2

    np.testing.assert_allclose(
        data["B^theta_t"][2:-2],
        B_sup_theta_t[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B^theta_t"])),
    )
    np.testing.assert_allclose(
        data["B^theta_tt"][2:-2],
        B_sup_theta_tt[2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["B^theta_tt"])),
    )
    np.testing.assert_allclose(
        data["B^zeta_t"][2:-2],
        B_sup_zeta_t[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B^zeta_t"])),
    )
    np.testing.assert_allclose(
        data["B^zeta_tt"][2:-2],
        B_sup_zeta_tt[2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["B^zeta_tt"])),
    )
    np.testing.assert_allclose(
        data["B_rho_t"][2:-2],
        B_sub_rho_t[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B_rho_t"])),
    )
    np.testing.assert_allclose(
        data["B_zeta_t"][2:-2],
        B_sub_zeta_t[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B_zeta_t"])),
    )
    np.testing.assert_allclose(
        data["|B|_t"][2:-2],
        B_t[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["|B|_t"])),
    )
    np.testing.assert_allclose(
        data["|B|_tt"][2:-2],
        B_tt[2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["|B|_tt"])),
    )

    # partial derivatives wrt zeta
    N = 90
    grid = LinearGrid(N=N, NFP=eq.NFP)
    dzeta = grid.nodes[1, 2]
    data = eq.compute("J", grid)
    data = eq.compute("|B|_zz", grid, data=data)

    B_sup_theta_z = np.convolve(data["B^theta"], FD_COEF_1_4, "same") / dzeta
    B_sup_theta_zz = np.convolve(data["B^theta"], FD_COEF_2_4, "same") / dzeta ** 2
    B_sup_zeta_z = np.convolve(data["B^zeta"], FD_COEF_1_4, "same") / dzeta
    B_sup_zeta_zz = np.convolve(data["B^zeta"], FD_COEF_2_4, "same") / dzeta ** 2
    B_sub_rho_z = np.convolve(data["B_rho"], FD_COEF_1_4, "same") / dzeta
    B_sub_theta_z = np.convolve(data["B_theta"], FD_COEF_1_4, "same") / dzeta
    B_z = np.convolve(data["|B|"], FD_COEF_1_4, "same") / dzeta
    B_zz = np.convolve(data["|B|"], FD_COEF_2_4, "same") / dzeta ** 2

    np.testing.assert_allclose(
        data["B^theta_z"][2:-2],
        B_sup_theta_z[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B^theta_z"])),
    )
    np.testing.assert_allclose(
        data["B^theta_zz"][2:-2],
        B_sup_theta_zz[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B^theta_zz"])),
    )
    np.testing.assert_allclose(
        data["B^zeta_z"][2:-2],
        B_sup_zeta_z[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B^zeta_z"])),
    )
    np.testing.assert_allclose(
        data["B^zeta_zz"][2:-2],
        B_sup_zeta_zz[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B^zeta_zz"])),
    )
    np.testing.assert_allclose(
        data["B_rho_z"][2:-2],
        B_sub_rho_z[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B_rho_z"])),
    )
    np.testing.assert_allclose(
        data["B_theta_z"][2:-2],
        B_sub_theta_z[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["B_theta_z"])),
    )
    np.testing.assert_allclose(
        data["|B|_z"][2:-2],
        B_z[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["|B|_z"])),
    )
    np.testing.assert_allclose(
        data["|B|_zz"][2:-2],
        B_zz[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["|B|_zz"])),
    )

    # mixed derivatives wrt theta & zeta
    M = 125
    N = 125
    grid = LinearGrid(M=M, N=N, NFP=eq.NFP)
    dtheta = grid.nodes[:, 1].reshape((N, M))[0, 1]
    dzeta = grid.nodes[:, 2].reshape((N, M))[1, 0]
    data = eq.compute("|B|_tz", grid)

    B_sup_theta = data["B^theta"].reshape((N, M))
    B_sup_zeta = data["B^zeta"].reshape((N, M))
    B = data["|B|"].reshape((N, M))

    B_sup_theta_tz = (
        convolve2d(
            B_sup_theta,
            FD_COEF_1_4[:, np.newaxis] * FD_COEF_1_4[np.newaxis, :],
            mode="same",
            boundary="wrap",
        )
        / (dtheta * dzeta)
    )
    B_sup_zeta_tz = (
        convolve2d(
            B_sup_zeta,
            FD_COEF_1_4[:, np.newaxis] * FD_COEF_1_4[np.newaxis, :],
            mode="same",
            boundary="wrap",
        )
        / (dtheta * dzeta)
    )
    B_tz = (
        convolve2d(
            B,
            FD_COEF_1_4[:, np.newaxis] * FD_COEF_1_4[np.newaxis, :],
            mode="same",
            boundary="wrap",
        )
        / (dtheta * dzeta)
    )

    np.testing.assert_allclose(
        data["B^theta_tz"].reshape((N, M))[2:-2, 2:-2],
        B_sup_theta_tz[2:-2, 2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["B^theta_tz"])),
    )
    np.testing.assert_allclose(
        data["B^zeta_tz"].reshape((N, M))[2:-2, 2:-2],
        B_sup_zeta_tz[2:-2, 2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["B^zeta_tz"])),
    )
    np.testing.assert_allclose(
        data["|B|_tz"].reshape((N, M))[2:-2, 2:-2],
        B_tz[2:-2, 2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["|B|_tz"])),
    )


@pytest.mark.slow
def test_magnetic_pressure_gradient(DummyStellarator):
    """Test that the components of grad(|B|^2)) match with numerical gradients
    for a dummy stellarator example."""

    eq = Equilibrium.load(
        load_from=str(DummyStellarator["output_path"]), file_format="hdf5"
    )

    # partial derivatives wrt rho
    L = 50
    grid = LinearGrid(L=L, NFP=eq.NFP)
    drho = grid.nodes[1, 0]
    data = eq.compute("|B|", grid)
    data = eq.compute("grad(|B|^2)_rho", grid, data=data)
    B2_r = np.convolve(data["|B|"] ** 2, FD_COEF_1_4, "same") / drho
    np.testing.assert_allclose(
        data["grad(|B|^2)_rho"][3:-2],
        B2_r[3:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["grad(|B|^2)_rho"])),
    )

    # partial derivative wrt theta
    M = 90
    grid = LinearGrid(M=M, NFP=eq.NFP)
    dtheta = grid.nodes[1, 1]
    data = eq.compute("|B|", grid)
    data = eq.compute("grad(|B|^2)_theta", grid, data=data)
    B2_t = np.convolve(data["|B|"] ** 2, FD_COEF_1_4, "same") / dtheta
    np.testing.assert_allclose(
        data["grad(|B|^2)_theta"][2:-2],
        B2_t[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.nanmean(np.abs(data["grad(|B|^2)_theta"])),
    )

    # partial derivative wrt zeta
    N = 90
    grid = LinearGrid(N=N, NFP=eq.NFP)
    dzeta = grid.nodes[1, 2]
    data = eq.compute("|B|", grid)
    data = eq.compute("grad(|B|^2)_zeta", grid, data=data)
    B2_z = np.convolve(data["|B|"] ** 2, FD_COEF_1_4, "same") / dzeta
    np.testing.assert_allclose(
        data["grad(|B|^2)_zeta"][2:-2],
        B2_z[2:-2],
        rtol=1e-2,
        atol=1e-2 * np.mean(np.abs(data["grad(|B|^2)_zeta"])),
    )


def test_currents(DSHAPE):
    """Test that two different methods for computing I and G agree."""

    eq = EquilibriaFamily.load(load_from=str(DSHAPE["desc_h5_path"]))[-1]
    grid = LinearGrid(M=2 * eq.M_grid + 1, N=2 * eq.N_grid + 1, NFP=eq.NFP, rho=1.0)

    data1 = eq.compute("f_C", grid)
    data2 = eq.compute("|B|_mn", grid)

    np.testing.assert_allclose(data1["I"], data2["I"], atol=1e-16)
    np.testing.assert_allclose(data1["G"], data2["G"], atol=1e-16)


@pytest.mark.slow
def test_quasisymmetry(DummyStellarator):
    """Test that the components of grad(B*grad(|B|)) match with numerical gradients
    for a dummy stellarator example."""

    eq = Equilibrium.load(
        load_from=str(DummyStellarator["output_path"]), file_format="hdf5"
    )

    # partial derivative wrt theta
    M = 120
    grid = LinearGrid(M=M, NFP=eq.NFP)
    dtheta = grid.nodes[1, 1]
    data = eq.compute("(B*grad(|B|))_t", grid)
    Btilde_t = np.convolve(data["B*grad(|B|)"], FD_COEF_1_4, "same") / dtheta
    np.testing.assert_allclose(
        data["(B*grad(|B|))_t"][2:-2],
        Btilde_t[2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["(B*grad(|B|))_t"])),
    )

    # partial derivative wrt zeta
    N = 120
    grid = LinearGrid(N=N, NFP=eq.NFP)
    dzeta = grid.nodes[1, 2]
    data = eq.compute("(B*grad(|B|))_z", grid)
    Btilde_z = np.convolve(data["B*grad(|B|)"], FD_COEF_1_4, "same") / dzeta
    np.testing.assert_allclose(
        data["(B*grad(|B|))_z"][2:-2],
        Btilde_z[2:-2],
        rtol=2e-2,
        atol=2e-2 * np.mean(np.abs(data["(B*grad(|B|))_z"])),
    )


# TODO: add test with stellarator example
def test_boozer_transform(DSHAPE):
    """Test that Boozer coordinate transform agrees with BOOZ_XFORM."""

    eq = EquilibriaFamily.load(load_from=str(DSHAPE["desc_h5_path"]))[-1]
    grid = LinearGrid(M=2 * eq.M_grid + 1, N=2 * eq.N_grid + 1, NFP=eq.NFP, rho=1.0)
    data = eq.compute("|B|_mn", grid, M_booz=eq.M, N_booz=eq.N)
    booz_xform = np.array(
        [
            2.49792355e-01,
            5.16668333e-02,
            1.11374584e-02,
            7.31614588e-03,
            3.36187451e-03,
            2.08897051e-03,
            1.20694516e-03,
            7.84513291e-04,
            5.19293744e-04,
            3.61983430e-04,
            2.57745929e-04,
            1.86013067e-04,
            1.34610049e-04,
            9.68119345e-05,
        ]
    )
    np.testing.assert_allclose(
        np.flipud(np.sort(np.abs(data["|B|_mn"]))),
        booz_xform,
        rtol=1e-2,
        atol=1e-4,
    )


def test_surface_areas():
    eq = Equilibrium()

    grid_r = LinearGrid(rho=1, M=10, N=10)
    grid_t = LinearGrid(L=10, theta=0, N=10)
    grid_z = LinearGrid(L=10, M=10, zeta=0)

    data_r = eq.compute("|e_theta x e_zeta|", grid_r)
    data_t = eq.compute("|e_zeta x e_rho|", grid_t)
    data_z = eq.compute("|e_rho x e_theta|", grid_z)

    Ar = np.sum(
        data_r["|e_theta x e_zeta|"] * grid_r.spacing[:, 1] * grid_r.spacing[:, 2]
    )
    At = np.sum(
        data_t["|e_zeta x e_rho|"] * grid_t.spacing[:, 2] * grid_t.spacing[:, 0]
    )
    Az = np.sum(
        data_z["|e_rho x e_theta|"] * grid_z.spacing[:, 0] * grid_z.spacing[:, 1]
    )

    np.testing.assert_allclose(Ar, 4 * 10 * np.pi ** 2)
    np.testing.assert_allclose(At, np.pi * (11 ** 2 - 10 ** 2))
    np.testing.assert_allclose(Az, np.pi)


def test_vector_signs():

    R_lmn = np.array([10, 1, 0.2])
    modes_R = np.array([[0, 0], [1, 0], [-1, 1]])
    Z_lmn = np.array([0, -2, -0.2])
    modes_Z = np.array([[0, 0], [-1, 0], [-1, 1]])
    surfacep = FourierRZToroidalSurface(R_lmn, Z_lmn, modes_R, modes_Z, NFP=1)
    R_lmn = np.array([10, 1, -0.2])
    modes_R = np.array([[0, 0], [1, 0], [-1, 1]])
    Z_lmn = np.array([0, 2, 0.2])
    modes_Z = np.array([[0, 0], [-1, 0], [-1, 1]])
    surfacem = FourierRZToroidalSurface(R_lmn, Z_lmn, modes_R, modes_Z, NFP=1)

    iotap = PowerSeriesProfile([1, 0, -0.5])
    iotam = PowerSeriesProfile([-1, 0, 0.5])

    # ppp = jacobian plus, psi plus, iota plus
    # mmp = jacobian minus, psi minus, iota plus
    # etc.

    eqmmm = Equilibrium(
        surface=surfacem, L=5, M=10, N=5, NFP=1, sym=False, iota=iotam, Psi=-1
    )
    eqmmp = Equilibrium(
        surface=surfacem, L=5, M=10, N=5, NFP=1, sym=False, iota=iotap, Psi=-1
    )
    eqmpm = Equilibrium(
        surface=surfacem, L=5, M=10, N=5, NFP=1, sym=False, iota=iotam, Psi=1
    )
    eqmpp = Equilibrium(
        surface=surfacem, L=5, M=10, N=5, NFP=1, sym=False, iota=iotap, Psi=1
    )
    eqpmm = Equilibrium(
        surface=surfacep, L=5, M=10, N=5, NFP=1, sym=False, iota=iotam, Psi=-1
    )
    eqpmp = Equilibrium(
        surface=surfacep, L=5, M=10, N=5, NFP=1, sym=False, iota=iotap, Psi=-1
    )
    eqppm = Equilibrium(
        surface=surfacep, L=5, M=10, N=5, NFP=1, sym=False, iota=iotam, Psi=1
    )

    eqppp = Equilibrium(
        surface=surfacep, L=5, M=10, N=5, NFP=1, sym=False, iota=iotap, Psi=1
    )

    grid = Grid(np.array([[1, 0, 0]]))

    # jacobian sign
    assert np.sign(eqmmm.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == -1.0
    assert np.sign(eqmmp.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == -1.0
    assert np.sign(eqmpm.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == -1.0
    assert np.sign(eqmpp.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == -1.0
    assert np.sign(eqpmm.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == 1.0
    assert np.sign(eqpmp.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == 1.0
    assert np.sign(eqppm.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == 1.0
    assert np.sign(eqppp.compute("sqrt(g)", grid=grid)["sqrt(g)"][0]) == 1.0

    grid = Grid(np.array([[0.1, 0, 0]]))
    # toroidal field sign
    assert np.sign(eqmmm.compute("B", grid=grid)["B"][0, 1]) == -1.0
    assert np.sign(eqmmp.compute("B", grid=grid)["B"][0, 1]) == -1.0
    assert np.sign(eqmpm.compute("B", grid=grid)["B"][0, 1]) == 1.0
    assert np.sign(eqmpp.compute("B", grid=grid)["B"][0, 1]) == 1.0
    assert np.sign(eqpmm.compute("B", grid=grid)["B"][0, 1]) == -1.0
    assert np.sign(eqpmp.compute("B", grid=grid)["B"][0, 1]) == -1.0
    assert np.sign(eqppm.compute("B", grid=grid)["B"][0, 1]) == 1.0
    assert np.sign(eqppp.compute("B", grid=grid)["B"][0, 1]) == 1.0

    grid = Grid(np.array([[1, 0, 0]]))
    # poloidal field sign = -Bz on outboard side
    assert np.sign(eqmmm.compute("B", grid=grid)["B"][0, 2]) == -1.0
    assert np.sign(eqmmp.compute("B", grid=grid)["B"][0, 2]) == 1.0
    assert np.sign(eqmpm.compute("B", grid=grid)["B"][0, 2]) == 1.0
    assert np.sign(eqmpp.compute("B", grid=grid)["B"][0, 2]) == -1.0
    assert np.sign(eqpmm.compute("B", grid=grid)["B"][0, 2]) == -1.0
    assert np.sign(eqpmp.compute("B", grid=grid)["B"][0, 2]) == 1.0
    assert np.sign(eqppm.compute("B", grid=grid)["B"][0, 2]) == 1.0
    assert np.sign(eqppp.compute("B", grid=grid)["B"][0, 2]) == -1.0

    grid = Grid(np.array([[0.1, 0, 0]]))
    # toroidal current sign
    assert np.sign(eqmmm.compute("J", grid=grid)["J"][0, 1]) == 1.0
    assert np.sign(eqmmp.compute("J", grid=grid)["J"][0, 1]) == -1.0
    assert np.sign(eqmpm.compute("J", grid=grid)["J"][0, 1]) == -1.0
    assert np.sign(eqmpp.compute("J", grid=grid)["J"][0, 1]) == 1.0
    assert np.sign(eqpmm.compute("J", grid=grid)["J"][0, 1]) == 1.0
    assert np.sign(eqpmp.compute("J", grid=grid)["J"][0, 1]) == -1.0
    assert np.sign(eqppm.compute("J", grid=grid)["J"][0, 1]) == -1.0
    assert np.sign(eqppp.compute("J", grid=grid)["J"][0, 1]) == 1.0

    grid = LinearGrid(rho=0.5, M=15, N=15)
    # toroidal current sign
    assert np.sign(eqmmm.compute("I", grid=grid)["I"]) == 1.0
    assert np.sign(eqmmp.compute("I", grid=grid)["I"]) == -1.0
    assert np.sign(eqmpm.compute("I", grid=grid)["I"]) == -1.0
    assert np.sign(eqmpp.compute("I", grid=grid)["I"]) == 1.0
    assert np.sign(eqpmm.compute("I", grid=grid)["I"]) == 1.0
    assert np.sign(eqpmp.compute("I", grid=grid)["I"]) == -1.0
    assert np.sign(eqppm.compute("I", grid=grid)["I"]) == -1.0
    assert np.sign(eqppp.compute("I", grid=grid)["I"]) == 1.0

    grid = LinearGrid(rho=0.5, M=15, N=15)
    # poloidal current sign
    assert np.sign(eqmmm.compute("G", grid=grid)["G"]) == -1.0
    assert np.sign(eqmmp.compute("G", grid=grid)["G"]) == -1.0
    assert np.sign(eqmpm.compute("G", grid=grid)["G"]) == 1.0
    assert np.sign(eqmpp.compute("G", grid=grid)["G"]) == 1.0
    assert np.sign(eqpmm.compute("G", grid=grid)["G"]) == -1.0
    assert np.sign(eqpmp.compute("G", grid=grid)["G"]) == -1.0
    assert np.sign(eqppm.compute("G", grid=grid)["G"]) == 1.0
    assert np.sign(eqppp.compute("G", grid=grid)["G"]) == 1.0

    # for positive jacobian
    pgrid = Grid(np.array([[1, 0, 0], [0.5, np.pi / 6, np.pi / 3]]))
    # same real space, but for negative jacobian need to flip theta
    mgrid = Grid(np.array([[1, 0, 0], [0.5, -np.pi / 6, np.pi / 3]]))

    # test that just flipping jacobian gives same physics:
    keys = ["B", "B_r", "B_z", "grad(|B|^2)", "curl(B)xB", "(B*grad)B", "J", "F"]
    for key in keys:
        np.testing.assert_allclose(
            eqpmm.compute(key, grid=pgrid)[key],
            eqmmm.compute(key, grid=mgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )
        np.testing.assert_allclose(
            eqpmp.compute(key, grid=pgrid)[key],
            eqmmp.compute(key, grid=mgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )
        np.testing.assert_allclose(
            eqppm.compute(key, grid=pgrid)[key],
            eqmpm.compute(key, grid=mgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )
        np.testing.assert_allclose(
            eqppp.compute(key, grid=pgrid)[key],
            eqmpp.compute(key, grid=mgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )

    # test that flipping helicity just flips sign of field
    keys = ["B", "B_r", "B_z", "J"]
    for key in keys:
        np.testing.assert_allclose(
            eqmmm.compute(key, grid=mgrid)[key],
            -eqppm.compute(key, grid=pgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )
        np.testing.assert_allclose(
            eqmmp.compute(key, grid=mgrid)[key],
            -eqppp.compute(key, grid=pgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )

    # test that flipping helicity leaves quadratic stuff unchanged
    keys = ["grad(|B|^2)", "curl(B)xB", "(B*grad)B", "F"]
    for key in keys:
        np.testing.assert_allclose(
            eqmmm.compute(key, grid=mgrid)[key],
            eqppm.compute(key, grid=pgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )
        np.testing.assert_allclose(
            eqmmp.compute(key, grid=mgrid)[key],
            eqppp.compute(key, grid=pgrid)[key],
            rtol=1e-8,
            atol=1e-8,
            err_msg=key,
        )
