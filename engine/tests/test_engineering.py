import math

import pytest

from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.lamina import Lamina, reduced_stiffness
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads, midplane_response

# AS4/3501-6, Daniel & Ishai Table A.4 (p. 377), the same values as the website's material library. Pa.
AS4 = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27)
Q = reduced_stiffness(AS4)
Q11, Q22, Q12, Q66 = Q[0, 0], Q[1, 1], Q[0, 1], Q[2, 2]
T = 0.13e-3  # ply thickness, m
QUASI_ISOTROPIC = [0, 45, -45, 90, 90, -45, 45, 0]
MSI = 6.894757e9  # Pa per Msi


def stack(angles, thickness=T):
    """AS4 plies at the given angles, bottom face first."""
    return [Ply(material=AS4, angle_deg=angle, thickness_m=thickness) for angle in angles]


def test_single_zero_degree_ply_returns_the_ply_constants():
    c = engineering_constants(stack([0]))
    assert c.Ex == pytest.approx(147e9)
    assert c.Ey == pytest.approx(10.3e9)
    assert c.Gxy == pytest.approx(7e9)
    assert c.nu_xy == pytest.approx(0.27)
    assert c.nu_yx == pytest.approx(AS4.nu21)
    assert c.eta_xs == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("angle", [30, 45, 60])
def test_off_axis_ply_matches_the_lamina_transformation_formula(angle):
    # 1/Ex = m^4/E1 + (1/G12 - 2 nu12/E1) m^2 n^2 + n^4/E2 for a single ply at angle theta.
    m, n = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    expected = 1 / (m**4 / 147e9 + (1 / 7e9 - 2 * 0.27 / 147e9) * m**2 * n**2 + n**4 / 10.3e9)
    assert engineering_constants(stack([angle])).Ex == pytest.approx(expected, rel=1e-12)


def test_angle_ply_matches_printed_table_7_3():
    # Daniel & Ishai Table 7.3, exact values for an AS4/3501-6 [+-45]s laminate: Ex = 23.9 GPa,
    # Gxy = 5.53 Msi (the table's GPa column prints 38.2, but 5.53 Msi is 38.13 GPa), nu_xy = 0.71.
    c = engineering_constants(stack([45, -45, -45, 45]))
    assert c.Ex / 1e9 == pytest.approx(23.9, abs=0.05)
    assert c.Gxy / MSI == pytest.approx(5.53, abs=0.005)
    assert c.nu_xy == pytest.approx(0.71, abs=0.005)
    assert c.eta_xs == pytest.approx(0, abs=1e-12)


def test_angle_ply_matches_closed_form_equations_7_92_and_7_97():
    c = engineering_constants(stack([45, -45, -45, 45]))
    assert c.Ex == pytest.approx(4 * (Q11 + Q22 + 2 * Q12) * Q66 / (Q11 + Q22 + 2 * Q12 + 4 * Q66), rel=1e-12)
    assert c.Gxy == pytest.approx((Q11 + Q22 - 2 * Q12) / 4, rel=1e-12)


def test_quasi_isotropic_laminate_behaves_like_an_isotropic_plate():
    c = engineering_constants(stack(QUASI_ISOTROPIC))
    assert c.Ex == pytest.approx(c.Ey)
    # Daniel & Ishai Eq. 7.107.
    assert c.nu_xy == pytest.approx((Q11 + Q22 + 6 * Q12 - 4 * Q66) / (3 * Q11 + 3 * Q22 + 2 * Q12 + 4 * Q66))
    assert c.Gxy == pytest.approx(c.Ex / (2 * (1 + c.nu_xy)))
    assert c.Ex / 1e9 == pytest.approx(58.1798, abs=1e-4)


def test_quasi_isotropic_stiffness_does_not_depend_on_direction():
    reference = engineering_constants(stack(QUASI_ISOTROPIC))
    rotated = engineering_constants(stack([angle + 15 for angle in QUASI_ISOTROPIC]))
    assert rotated.Ex == pytest.approx(reference.Ex)
    assert rotated.Gxy == pytest.approx(reference.Gxy)
    assert rotated.nu_xy == pytest.approx(reference.nu_xy)


def test_coupon_layup_predicted_modulus():
    # [45/-45/0/90]2s is quasi-isotropic, so the D3039 coupon modulus is the quasi-isotropic Ex.
    angles = [45, -45, 0, 90] * 2
    c = engineering_constants(stack(angles + angles[::-1]))
    assert c.Ex / 1e9 == pytest.approx(58.1798, abs=1e-4)


def test_unsymmetric_cross_ply_is_softer_than_symmetric_when_free_to_bend():
    # Daniel & Ishai Section 7.12.3: [0/90] and [0/90]s have different moduli because of coupling.
    free = engineering_constants(stack([0, 90]))
    symmetric = engineering_constants(stack([0, 90, 90, 0]))
    assert free.Ex / 1e9 == pytest.approx(34.1771, abs=1e-4)
    assert symmetric.Ex / 1e9 == pytest.approx(78.9550, abs=1e-4)


def test_constants_do_not_depend_on_ply_thickness():
    thin = engineering_constants(stack(QUASI_ISOTROPIC, thickness=0.1e-3))
    thick = engineering_constants(stack(QUASI_ISOTROPIC, thickness=0.3e-3))
    assert thick.Ex == pytest.approx(thin.Ex)
    assert thick.nu_xy == pytest.approx(thin.nu_xy)


@pytest.mark.parametrize("angles", [QUASI_ISOTROPIC, [0, 90], [30, -45, 10]])
def test_poisson_ratios_obey_reciprocity(angles):
    c = engineering_constants(stack(angles))
    assert c.nu_xy / c.Ex == pytest.approx(c.nu_yx / c.Ey)


@pytest.mark.parametrize("angles", [QUASI_ISOTROPIC, [0, 90], [30, -45, 10]])
def test_constants_agree_with_a_simulated_tension_test(angles):
    # Pull in x with chunk 4's solver and measure the strains, as a D3039 extensometer would.
    plies = stack(angles)
    h = T * len(angles)
    eps0, _ = midplane_response(plies, Loads(Nx=1e5))
    c = engineering_constants(plies)
    assert c.Ex == pytest.approx(1e5 / h / eps0[0])
    assert c.nu_xy == pytest.approx(-eps0[1] / eps0[0])
    assert c.eta_xs == pytest.approx(eps0[2] / eps0[0], abs=1e-12)


def test_empty_stack_is_rejected():
    with pytest.raises(ValueError):
        engineering_constants([])
