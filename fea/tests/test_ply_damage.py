"""The plies that damage (ADR-0141): the law, a bar of one ply, and a cross-ply strip, each against an answer worked out
here and not taken from the code under test."""

from __future__ import annotations

import numpy as np
import pytest
from anisotropy_engine.repair.solid import turned_stiffness
from anisotropy_fea.bond_solver import BondError, BondModel, rectangle, stress_load
from anisotropy_fea.ply_damage import Holder, PlyDamage, largest_load, strain_turn

# A ply of round numbers, so that every answer below can be written by hand. Pa, and J/m^2 for the energies.
E1, E2, G = 100e9, 10e9, 5e9
F1T, F1C, F2T, F6 = 1000e6, 1500e6, 50e6, 80e6
G1T, G1C, G2T, G6 = 80e3, 80e3, 300.0, 800.0
ENERGIES = (G1T, G1C, G2T, G6)


def ply_axes_compliance(nu: float = 0.0) -> np.ndarray:
    """The ply's compliance in its own axes, 6 by 6."""
    s = np.zeros((6, 6))
    s[0, 0], s[1, 1], s[2, 2] = 1 / E1, 1 / E2, 1 / E2
    s[0, 1] = s[1, 0] = s[0, 2] = s[2, 0] = -nu / E1
    s[1, 2] = s[2, 1] = -nu / E2
    s[3, 3], s[4, 4], s[5, 5] = 2.6 / E2, 1 / G, 1 / G
    return s


def bar(count: int = 10, length: float = 10e-3, thickness: float = 1e-3, angle: float = 0.0, weaker: float = 0.99,
        rows: int = 1, nu: float = 0.0, energies=ENERGIES) -> tuple[BondModel, float]:
    """A bar of one ply pulled along its length, held at one end, with one element's strengths lowered so that the break
    happens there. Returns the model and the bar's thickness."""
    nodes, elements, ids = rectangle(np.linspace(0, length, count + 1), np.linspace(0, thickness, rows + 1))
    many = len(elements)
    compliance = np.repeat(ply_axes_compliance(nu)[None], many, axis=0)
    turn = strain_turn(angle)[0]
    plane = [0, 2, 4]
    stiffness = np.repeat((turn.T @ np.linalg.inv(ply_axes_compliance(nu)) @ turn)[np.ix_(plane, plane)][None], many, axis=0)
    fibre, matrix = np.full(many, F1T), np.full(many, F2T)
    middle = nodes[elements][:, :4, 0].mean(axis=1)
    column = np.isclose(middle, middle[np.argmin(np.abs(middle - 0.45 * length))])
    fibre[column] *= weaker
    matrix[column] *= weaker
    plies = PlyDamage(compliance, angle, fibre, F1C, matrix, F6, *energies, np.ones(many, dtype=bool))
    left, right = ids[0, :], ids[-1, :]
    left, right = left[left >= 0], right[right >= 0]
    fixed = np.concatenate([2 * left, [2 * left[0] + 1]])
    # the nodal forces of a stress of 1 Pa along the bar, kept on the far end alone
    balance = stress_load(nodes, elements, np.tile([1.0, 0, 0], (many, 1)))
    load = np.zeros(2 * len(nodes))
    load[2 * right] = balance[2 * right]
    return BondModel(nodes, elements, stiffness, [], [], [], None, fixed, load, plies=plies), thickness


def strip(angles=(0, 90, 90, 0), ply: float = 0.2e-3, length: float = 20e-3, count: int = 40, grip: int = 6,
          energies=ENERGIES, nu: float = 0.3):
    """A cross-ply strip pulled along the 0 degree plies, with the elements at the loaded end kept elastic so that the
    cracks stay away from where the load is put on. Returns the model, laminate theory's first ply failure and the two hand
    bounds on the last ply failure, all per metre of width."""
    lamina = ply_axes_compliance(nu)
    stiff = np.linalg.inv(lamina)
    # laminate theory in plane stress, written out here
    share = 1 - nu**2 * E2 / E1
    q = np.array([[E1 / share, nu * E2 / share, 0.0], [nu * E2 / share, E2 / share, 0.0], [0.0, 0.0, G]])

    def turned(angle):
        c, s = np.cos(np.radians(angle)), np.sin(np.radians(angle))
        to_ply = np.array([[c * c, s * s, s * c], [s * s, c * c, -s * c], [-2 * s * c, 2 * s * c, c * c - s * s]])
        return to_ply.T @ q @ to_ply

    a = sum(turned(angle) * ply for angle in angles)
    along = 1 / (a[0, 0] - a[0, 1] ** 2 / a[1, 1])  # the strain along the load per unit of load, the strip free across
    across = -a[0, 1] / a[1, 1] * along
    nodes, elements, ids = rectangle(np.linspace(0, length, count + 1), np.arange(len(angles) + 1) * ply)
    many = len(elements)
    row, column = np.arange(many) % len(angles), np.arange(many) // len(angles)
    angle = np.array(angles, dtype=float)[row]
    turn = strain_turn(angle)
    plane = [0, 2, 4]
    stiffness = np.einsum("eji,jk,ekl->eil", turn, stiff, turn)[:, plane][:, :, plane]
    plies = PlyDamage(np.repeat(lamina[None], many, axis=0), angle, F1T, F1C, F2T, F6, *energies, column < count - grip, across)
    # the end's forces: each ply's stress along the load under a load of 1 N/m, on its own face
    balance = stress_load(nodes, elements, np.array([(turned(one) @ [along, across, 0.0]) for one in angle]))
    right = ids[-1, :]
    right = right[right >= 0]
    load = np.zeros(2 * len(nodes))
    load[2 * right] = balance[2 * right]
    left = ids[0, :]
    left = left[left >= 0]
    fixed = np.concatenate([2 * left, [2 * left[0] + 1]])
    model = BondModel(nodes, elements, stiffness, [], [], [], None, fixed, load, plies=plies)
    first = (F2T / E2) / along  # the 90 degree plies reach their tensile strength across the fibres
    thick_0 = ply * sum(1 for one in angles if one == 0)
    thick_90 = ply * sum(1 for one in angles if one == 90)
    onset = F1T / E1  # the strain along the load at which the 0 degree plies break
    # The two bounds on the largest load the strip can hold. It can hold no more than the whole laminate at that strain,
    # since nothing stiffens; and no less than the 0 degree plies alone at it, since a 90 degree ply whose matrix has
    # cracked right through carries nothing along the load and the 0 degree plies are then the whole strip.
    whole = (thick_0 * q[0, 0] + thick_90 * turned(90)[0, 0]) * onset / (1 - (thick_0 * q[0, 1] + thick_90 * turned(90)[0, 1]) * across)
    alone = thick_0 * (q[0, 0] * onset + q[0, 1] * across * whole) / (1 + 0 * onset)
    return model, first, alone, whole


def test_the_strain_turn_is_the_engines_own_turn() -> None:
    stiffness = np.linalg.inv(ply_axes_compliance(0.3))
    for angle in (0.0, 45.0, -45.0, 90.0, 30.0, -60.0):
        turn = strain_turn(angle)[0]
        assert np.allclose(turn.T @ stiffness @ turn, turned_stiffness(stiffness, angle), rtol=1e-12, atol=0.0)


def test_the_law_peaks_at_the_strength_and_spends_the_fracture_energy() -> None:
    """The point of the crack band: the stress integrated over the strain, times the band's width, is the fracture energy."""
    model, _ = bar(weaker=1.0)
    plies = model.plies
    band = float(plies.fibre_band[0])
    strains = np.linspace(0.0, 4 * G1T / (F1T * band), 400001)
    damage, stresses = plies.begin(), []
    for strain in strains:
        own = np.zeros((len(model.elements), 6))
        own[:, 0] = strain
        damage = plies.damage(own, damage)
        stresses.append(plies.stress(own, damage, (np.ones(len(own), dtype=bool),) * 2)[0, 0])
    stresses = np.array(stresses)
    assert np.max(stresses) == pytest.approx(F1T, rel=1e-4)
    assert float(np.trapezoid(stresses, strains)) * band == pytest.approx(G1T, rel=1e-3)
    assert np.all(np.diff(np.maximum.accumulate(stresses)) >= 0)  # damage only grows, so the stress never rises again


def test_a_pressed_matrix_crack_carries_the_pressure_whole() -> None:
    model, _ = bar(angle=90.0, weaker=1.0)
    plies = model.plies
    open_ = np.zeros((len(model.elements), 6))
    open_[:, 1] = 4 * F2T / E2  # pulled well past the crack's onset
    damage = plies.damage(open_, plies.begin())
    assert damage[2][0] > 0.5
    shut = np.zeros_like(open_)
    shut[:, 1] = -F2T / E2
    pressed = plies.stress(shut, damage, plies.pulled(shut, damage, (np.ones(len(shut), dtype=bool),) * 2))
    assert pressed[0, 1] == pytest.approx(-F2T, rel=1e-9)


@pytest.mark.parametrize("angle", [0.0, 90.0])
@pytest.mark.parametrize("count", [10, 40])
def test_a_bar_breaks_at_its_strength_whatever_the_mesh(angle: float, count: int) -> None:
    """The load the bar breaks at is the weak element's strength times its area, on any mesh: what the crack band is for."""
    model, thickness = bar(angle=angle, count=count)
    held, failed, _ = largest_load(model, within=0.002)
    strength = 0.99 * (F1T if angle == 0.0 else F2T)
    middle = 0.5 * (held[-1].load + failed.load)
    assert middle == pytest.approx(strength, rel=0.003)


def test_a_crack_whose_plane_holds_the_load_is_not_followed() -> None:
    """A matrix crack in a 0 degree ply and a fibre break in a 90 degree ply lie along the load: a slice along the load
    cannot hold them, and they are left out."""
    along = bar(angle=0.0)[0].plies
    across = bar(angle=90.0)[0].plies
    assert along.fibre_follows.all() and not along.matrix_follows.any()
    assert across.matrix_follows.all() and not across.fibre_follows.any()


def test_an_element_too_long_to_soften_is_refused_in_words() -> None:
    """A crack softens over a band as wide as the element, so its fracture energy must be above the energy the ply holds at
    its strength. The bound for the matrix crack here is 2 G E2 / F2t^2 = 2.4 mm."""
    assert 2 * G2T * E2 / F2T**2 == pytest.approx(2.4e-3, rel=1e-12)  # the crack pulled open
    assert 2 * G6 * G / F6**2 == pytest.approx(1.25e-3, rel=1e-12)  # the same crack slid, which binds first here
    with pytest.raises(BondError, match="too long for a matrix crack in shear to soften"):
        bar(angle=90.0, count=5, length=10e-3)  # 2.0 mm elements
    with pytest.raises(BondError, match="too long for a matrix crack in tension to soften"):
        bar(angle=90.0, count=4, length=10e-3, energies=(G1T, G1C, G2T, 1e6))  # 2.5 mm with the shear energy raised, so tension binds
    bar(angle=90.0, count=10, length=10e-3)  # 1.0 mm, and allowed


def test_the_cross_ply_strips_first_ply_failure_is_laminate_theorys() -> None:
    model, first, alone, upper = strip()
    holder = Holder(model)
    assert holder.onset_load == pytest.approx(first, rel=1e-6)
    assert first < alone < upper  # first ply failure is well below either bound on the last


def test_the_cross_ply_strip_carries_a_load_between_the_two_hand_bounds() -> None:
    """Past first ply failure the 90 degree plies crack and the 0 degree plies carry on. The strip can hold no more than
    the laminate with its 90 degree plies whole, and no less than the laminate with them cracked as far as the fibre's
    onset strain takes them."""
    model, first, alone, whole = strip()
    held, failed, _ = largest_load(model, within=0.005)
    assert held[-1].load > 1.8 * first  # it carries well past first ply failure
    assert alone <= held[-1].load <= whole
    assert failed.load > held[-1].load


def test_damage_grows_and_never_falls_while_a_load_is_held() -> None:
    model = strip(count=20, grip=3, energies=(G1T, G1C, 2000.0, G6))[0]
    holder = Holder(model)
    first = holder.hold(holder.onset_load * 1.2, holder.begin())
    assert first.held
    assert (first.damage.plies[2] > 0).any()
    again = holder.hold(holder.onset_load * 1.2, first.damage)
    assert np.all(again.damage.plies[2] >= first.damage.plies[2] - 1e-12)
