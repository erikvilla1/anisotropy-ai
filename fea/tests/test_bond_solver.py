"""A bond that softens and lets go, followed along its load path (ADR-0140). The law is checked alone against its six
numbers; the solver against cases with exact answers: a block pulled off a bond, the peel test and the shear test of
fracture mechanics against beam theory, and a patch pulled off a strip held flat against its energy answer. The shear
test's largest load is also held to the one MOOSE gives for the same model (version 2026.08.12, input in
fea/checks/bond_cases/)."""

import math

import numpy as np
import pytest

from anisotropy_fea.bond_solver import BondError, BondLaw, BondModel, follow, rectangle, simpson_weights, solid_stiffness, stress_load

# A unidirectional carbon ply, fibres along the first axis, the slice held across its width
E1, E2, E3, NU12, NU13, NU23, G13 = 150e9, 11e9, 11e9, 0.25, 0.25, 0.45, 6e9
MM = 1e-3


def ply() -> np.ndarray:
    compliance = np.array([[1 / E1, -NU12 / E1, -NU13 / E1], [-NU12 / E1, 1 / E2, -NU23 / E2], [-NU13 / E1, -NU23 / E2, 1 / E3]])
    full = np.linalg.inv(compliance)
    plane = np.zeros((3, 3))
    plane[0, 0], plane[0, 1], plane[1, 0], plane[1, 1], plane[2, 2] = full[0, 0], full[0, 2], full[2, 0], full[2, 2], G13
    return plane


BENDING = E1 / (1 - NU12**2 * E2 / E1)  # a strip's modulus along the fibres when held across its width


def two_parts(lines, under_lines, over_lines, over_from: float = -math.inf):
    """Two rectangles, one over the other, on the same lines along the first axis; the upper may begin later."""
    upper_lines = lines[lines >= over_from - 1e-12]
    n1, e1, lower = rectangle(lines, under_lines)
    n2, e2, upper = rectangle(upper_lines, over_lines, start=len(n1))
    nodes, elements = np.vstack([n1, n2]), np.vstack([e1, e2])
    first = 2 * (len(lines) - len(upper_lines))
    return nodes, elements, lower, upper, lower[first:, -1], upper[:, 0], simpson_weights(np.diff(upper_lines))


def column(ids: np.ndarray, i: int) -> np.ndarray:
    return ids[i][ids[i] >= 0]


def face_weights(count: int) -> np.ndarray:
    """A unit force spread over a face of `count` nodes as an even stress."""
    return simpson_weights(np.full((count - 1) // 2, 2 / (count - 1)))


# ---------------------------------------------------------------- the law alone


LAW = BondLaw(peel_stiffness=4e13, shear_stiffness=1e13, peel_strength=40e6, shear_strength=30e6, peel_energy=500.0, shear_energy=2000.0)


def test_a_bond_needs_six_positive_numbers_and_energy_above_what_it_holds_at_its_strength():
    with pytest.raises(BondError, match="peel strength must be a positive number"):
        BondLaw(4e13, 1e13, 0.0, 30e6, 500.0, 2000.0)
    with pytest.raises(BondError, match="shear energy must be a positive number"):
        BondLaw(4e13, 1e13, 40e6, 30e6, 500.0, math.nan)
    # at 40 MPa and 4e13 Pa/m the bond holds 20 J/m^2 when it reaches its strength
    with pytest.raises(BondError, match="peel energy is under the energy it holds.*above 20 J/m\\^2"):
        BondLaw(4e13, 1e13, 40e6, 30e6, 20.0, 2000.0)


@pytest.mark.parametrize("angle", [0.0, 30.0, 45.0, 75.0, 90.0])
def test_along_any_direction_the_law_peaks_on_the_onset_line_and_spends_the_failure_lines_energy(angle):
    cn, cs = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    onset = 1 / math.hypot(LAW.peel_stiffness * cn / LAW.peel_strength, LAW.shear_stiffness * cs / LAW.shear_strength)
    tn, ts, damage = LAW.traction(np.array([onset * cn]), np.array([onset * cs]), np.zeros(1))
    assert (tn[0] / LAW.peel_strength) ** 2 + (ts[0] / LAW.shear_strength) ** 2 == pytest.approx(1.0, abs=1e-9) and damage[0] < 1e-9
    size = np.concatenate([np.linspace(0, onset, 11), np.linspace(onset, 3e-4, 20001)[1:]])
    tn, ts, damage = LAW.traction(size * cn, size * cs, np.zeros_like(size))
    assert np.argmax(np.hypot(tn, ts)) == 10  # the stress is largest at onset
    peel = np.trapezoid(tn, size * cn)
    shear = np.trapezoid(ts, size * cs)
    assert peel / LAW.peel_energy + shear / LAW.shear_energy == pytest.approx(1.0, abs=1e-6)
    assert damage[-1] == 1.0 and tn[-1] == 0.0 and ts[-1] == 0.0


def test_the_laws_end_points_are_the_pure_peel_and_pure_shear_ones():
    assert LAW.onset_opening == pytest.approx(1e-6) and LAW.final_opening == pytest.approx(25e-6)
    assert LAW.onset_slip == pytest.approx(3e-6) and LAW.final_slip == pytest.approx(2000 / 15e6)
    tn, ts, d = LAW.traction(np.array([13e-6]), np.array([0.0]), np.zeros(1))  # halfway down the peel line
    assert tn[0] == pytest.approx(20e6) and ts[0] == 0.0 and d[0] == pytest.approx(25 * 12 / (13 * 24))


def test_damage_only_grows_and_an_unloaded_bond_returns_along_a_straight_line_to_nothing():
    _, _, damaged = LAW.traction(np.array([13e-6]), np.array([0.0]), np.zeros(1))
    tn, _, after = LAW.traction(np.array([6.5e-6]), np.array([0.0]), damaged)
    assert after[0] == damaged[0] and tn[0] == pytest.approx(10e6)


def test_a_bond_pressed_together_carries_the_pressure_whole_and_its_shear_follows_the_shear_law_alone():
    tn, ts, d = LAW.traction(np.array([-2e-6, -2e-6]), np.array([2e-6, 4e-6]), np.array([0.0, 0.0]))
    assert tn == pytest.approx([-80e6, -80e6])
    assert d[0] == 0.0 and ts[0] == pytest.approx(20e6)
    assert d[1] > 0 and ts[1] == pytest.approx(30e6 * (LAW.final_slip - 4e-6) / (LAW.final_slip - LAW.onset_slip))
    # and a broken bond still carries pressure
    tn, ts, _ = LAW.traction(np.array([-2e-6]), np.array([1e-6]), np.array([1.0]))
    assert tn[0] == pytest.approx(-80e6) and ts[0] == 0.0


# ---------------------------------------------------------------- the solids


def test_the_plane_elements_return_an_even_stress_and_the_load_that_balances_a_stress_inside_them():
    nodes, elements, ids = rectangle(np.linspace(0, 4 * MM, 5), np.array([0.0, 0.3 * MM, MM]))
    stiffness = np.broadcast_to(ply(), (len(elements), 3, 3))
    matrix = solid_stiffness(nodes, elements, stiffness)
    strain = np.array([1e-3, -2e-4, 5e-4])
    displacement = np.zeros(2 * len(nodes))
    displacement[0::2] = strain[0] * nodes[:, 0] + strain[2] * nodes[:, 1]
    displacement[1::2] = strain[1] * nodes[:, 1]
    forces = matrix @ displacement
    inside = np.setdiff1d(ids[1:-1, 1:-1][ids[1:-1, 1:-1] >= 0], [])
    assert np.abs(forces.reshape(-1, 2)[inside]).max() < 1e-9 * np.abs(forces).max()  # an even stress needs forces on the edge only
    assert forces == pytest.approx(stress_load(nodes, elements, np.broadcast_to(ply() @ strain, (len(elements), 3))), abs=1e-9 * np.abs(forces).max())
    with pytest.raises(BondError, match="inside out"):
        solid_stiffness(nodes, elements[:, [0, 3, 2, 1, 7, 6, 5, 4]], stiffness)
    with pytest.raises(BondError, match="lines must rise"):
        rectangle([0.0, 1.0, 1.0], [0.0, 1.0])


def test_simpsons_weights_add_up_to_the_bonds_length():
    weights = simpson_weights([1.0, 2.0])
    assert weights == pytest.approx([1 / 6, 4 / 6, 1 / 6 + 2 / 6, 8 / 6, 2 / 6])


# ---------------------------------------------------------------- one bond pulled apart


def test_a_block_pulled_off_its_bond_reaches_the_strength_and_spends_the_fracture_energy():
    """Two blocks joined along 2 mm, the lower held, the upper pulled evenly: the stress is even, so the largest load is
    the peel strength times the length, and by the time the bond is gone it has spent the peel energy times the length. The
    blocks hold more energy at that load than the bond can spend, so the load and the movement both fall back: a path that
    plain steps of load or of movement cannot follow. The even state is also one the bond can leave, one pair parting while
    the others unload; the load must then rise again to part those, and the follower lets it."""
    length = 2 * MM
    nodes, elements, lower, upper, under, over, weight = two_parts(np.linspace(0, length, 3), np.linspace(-20 * MM, 0, 5), np.linspace(0, 20 * MM, 5))
    transverse = np.diag([E2, E2, G13])  # no sideways coupling, so the blocks strain evenly
    fixed = np.concatenate([2 * lower[:, 0] + 1, [2 * lower[0, 0]], [2 * upper[0, -1]]])
    load = np.zeros(2 * len(nodes))
    load[2 * upper[:, -1] + 1] = simpson_weights(np.diff(np.linspace(0, 1, 3)))
    model = BondModel(nodes, elements, np.broadcast_to(transverse, (len(elements), 3, 3)), under, over, weight, LAW, fixed, load)
    path = follow(model, stop=lambda point, _: point.damage.min() > 0.999)
    assert path.ended == "stopped"
    assert path.onset_load == pytest.approx(LAW.peel_strength * length, rel=1e-9)
    assert path.peak.load == pytest.approx(LAW.peel_strength * length, rel=1e-3)
    # In peel alone a pair that has reached damage d has spent half its strength times the largest opening it reached times
    # d, which is the peel energy once it is gone. The path's own count of the energy spent is the sum of those, but for
    # what its steps lose where the load turns sharply.
    last = path.points[-1]
    reached = LAW.onset_opening * LAW.final_opening / (LAW.final_opening - last.damage * (LAW.final_opening - LAW.onset_opening))
    assert last.spent == pytest.approx(float(weight @ (0.5 * LAW.peel_strength * reached * last.damage)), rel=0.05)
    assert 0.97 * LAW.peel_energy * length < last.spent < 1.05 * LAW.peel_energy * length
    assert last.load < 0.03 * path.peak.load and np.all(path.loads > 0)
    assert path.movements.max() > 1.5 * path.movements[-1]  # the movement fell back with the load
    assert np.all(np.diff([point.spent for point in path.points]) > -1e-12 * LAW.peel_energy * length)


def test_a_model_without_pairs_or_without_load_is_refused():
    nodes, elements, lower, upper, under, over, weight = two_parts(np.linspace(0, 2 * MM, 3), np.linspace(-MM, 0, 2), np.linspace(0, MM, 2))
    stiffness = np.broadcast_to(ply(), (len(elements), 3, 3))
    with pytest.raises(BondError, match="needs pairs"):
        BondModel(nodes, elements, stiffness, under[:0], over[:0], weight[:0], LAW, [0, 1], np.ones(2 * len(nodes)))
    model = BondModel(nodes, elements, stiffness, under, over, weight, LAW, 2 * lower[:, 0] + 1, np.zeros(2 * len(nodes)))
    with pytest.raises(BondError, match="no load"):
        follow(model)


# ---------------------------------------------------------------- the peel test (double cantilever beam)


def test_the_peel_tests_load_follows_beam_theory_while_the_crack_grows():
    """Two arms 100 by 1.98 mm bonded beyond a 30 mm crack and pulled apart at their ends. While the crack grows, beam
    theory gives P^2 = (2/3) G^1.5 sqrt(EI) / opening, whatever the crack's root does."""
    length, depth, crack, energy = 100 * MM, 1.98 * MM, 30 * MM, 352.0
    law = BondLaw(1e14, 1e14, 30e6, 30e6, energy, energy)
    lines = np.linspace(0, length, 201)
    nodes, elements, lower, upper, under, over, weight = two_parts(lines, np.linspace(-depth, 0, 5), np.linspace(0, depth, 5))
    bonded = nodes[under, 0] >= crack - 1e-12
    weight = simpson_weights(np.diff(lines[lines >= crack - 1e-12]))
    under, over = under[bonded], over[bonded]
    fixed = [2 * lower[-1, -1] + 1, 2 * lower[-1, 0], 2 * upper[-1, -1]]  # the far end, against moving and turning
    load = np.zeros(2 * len(nodes))
    load[2 * column(upper, 0) + 1] = face_weights(9)
    load[2 * column(lower, 0) + 1] = -face_weights(9)
    model = BondModel(nodes, elements, np.broadcast_to(ply(), (len(elements), 3, 3)), under, over, weight, law, fixed, load)
    place = nodes[under, 0]

    def front(point) -> float:
        gone = place[point.damage >= 1.0]
        return gone.max() if len(gone) else crack

    path = follow(model, largest_energy=0.25 * energy * 0.5 * MM, stop=lambda point, _: front(point) >= 40 * MM)
    assert path.ended == "stopped"
    opening, force = path.movements, path.loads
    inertia = BENDING * depth**3 / 12
    growing = opening > 1.3 * opening[np.argmax(force)]
    assert growing.sum() > 20
    theory = np.sqrt((2 / 3) * energy**1.5 * math.sqrt(inertia) / opening[growing])
    assert np.abs(force[growing] / theory - 1).max() < 0.02
    # the energy the path says the bond spent is the fracture energy of the crack's new length
    new = front(path.points[-1]) - crack
    assert path.points[-1].spent / new == pytest.approx(energy, rel=0.1)


# ---------------------------------------------------------------- the shear test (end-notched flexure)


def shear_test(strength: float, size: float = 0.5 * MM):
    span, depth, crack, energy = 100 * MM, 1.98 * MM, 35 * MM, 1000.0
    law = BondLaw(1e14, 1e14, strength, strength, energy, energy)
    lines = np.linspace(0, span, int(round(span / size)) + 1)
    nodes, elements, lower, upper, under, over, weight = two_parts(lines, np.linspace(-depth, 0, 5), np.linspace(0, depth, 5))
    fixed = [2 * lower[0, 0] + 1, 2 * lower[-1, 0] + 1, 2 * lower[0, 0]]
    load = np.zeros(2 * len(nodes))
    load[2 * upper[(upper.shape[0] - 1) // 2, -1] + 1] = -1.0
    cracked = np.where(nodes[under, 0] < crack - 1e-12, 1.0, 0.0)  # the crack's faces press on each other and slide
    model = BondModel(nodes, elements, np.broadcast_to(ply(), (len(elements), 3, 3)), under, over, weight, law, fixed, load, damage=cracked)
    path = follow(model, largest_energy=energy * size, stop=lambda point, points: point.load < 0.97 * max(p.load for p in points))
    # the load at which a sharp crack would grow, the crack lengthened by the give at its root
    give = 1.18 * math.sqrt(E1 * E3) / G13
    root = 0.42 * depth * math.sqrt(E1 / (11 * G13) * (3 - 2 * (give / (1 + give)) ** 2))
    beam = 4 / (3 * (crack + root)) * math.sqrt(BENDING * depth**3 * energy)
    return path, beam


def test_the_shear_tests_largest_load_is_mooses_and_nears_beam_theorys_as_the_strength_rises():
    """Beam theory assumes a sharp crack. A bond of finite strength softens over a length ahead of the crack, which lowers
    the largest load; the length shrinks as the strength rises (7.8 % under beam theory at 60 MPa; 2.65 % at 120 MPa and
    0.40 % at 240 MPa on the finer meshes those need, ADR-0140). MOOSE, with the same law on the same mesh, gives 729.5 N
    on a 20 mm width at 60 MPa as its damping is taken to nothing."""
    weak, beam = shear_test(30e6)
    stated, _ = shear_test(60e6)
    assert weak.ended == stated.ended == "stopped"
    assert stated.peak.load * 20 * MM == pytest.approx(729.5, rel=3e-3)
    assert weak.peak.load < stated.peak.load < beam
    assert stated.peak.load / beam - 1 == pytest.approx(-0.078, abs=0.005)


# ---------------------------------------------------------------- a patch pulled off a strip held flat


def strip_and_patch(law: BondLaw, size: float = MM):
    """A strip 2 mm thick held flat on its underside and pulled at one end; a patch 1 mm thick bonded to it from 20 mm in,
    both held at the far end as at a repair's middle. The repair's own arrangement."""
    length, start = 120 * MM, 20 * MM
    lines = np.linspace(0, length, int(round(length / size)) + 1)
    nodes, elements, lower, upper, under, over, weight = two_parts(lines, np.linspace(-2 * MM, 0, 5), np.linspace(0, MM, 3), over_from=start)
    fixed = np.concatenate([2 * lower[:, 0] + 1, 2 * column(lower, -1), 2 * column(upper, -1)])
    load = np.zeros(2 * len(nodes))
    load[2 * column(lower, 0)] = -face_weights(9)
    model = BondModel(nodes, elements, np.broadcast_to(ply(), (len(elements), 3, 3)), under, over, weight, law, fixed, load)
    place = nodes[under, 0]

    def front(point) -> float:
        gone = place[point.damage >= 1.0]
        return gone.max() - start if len(gone) else 0.0

    path = follow(model, largest_energy=2 * max(law.peel_energy, law.shear_energy) * size, stop=lambda point, _: front(point) >= 50 * MM)
    return path, np.array([front(point) for point in path.points])


def test_a_long_bond_runs_at_the_load_its_energy_gives_far_above_the_load_of_first_onset():
    """Once the bond runs, each length of it that lets go frees the same strain energy, so the load is steady at
    sqrt(2 G Sa (Sa + Sb) / Sb), with Sa and Sb the strip's and the patch's stiffness along the pull."""
    energy = 500.0
    path, run = strip_and_patch(BondLaw(2e13, 2e13, 30e6, 30e6, energy, energy))
    strip, patch = BENDING * 2 * MM, BENDING * MM
    exact = math.sqrt(2 * energy * strip * (strip + patch) / patch)
    steady = path.loads[run > 15 * MM]
    assert path.ended == "stopped" and len(steady) > 10
    assert np.abs(steady / exact - 1).max() < 0.005
    assert path.onset_load < 0.25 * exact
    assert path.first_peak() is None  # the load never falls: the bond runs at a steady load


def test_with_an_adhesives_unequal_numbers_the_bond_runs_between_the_two_pure_answers():
    path, run = strip_and_patch(LAW)
    strip, patch = BENDING * 2 * MM, BENDING * MM
    by_peel, by_shear = (math.sqrt(2 * energy * strip * (strip + patch) / patch) for energy in (LAW.peel_energy, LAW.shear_energy))
    steady = path.loads[run > 15 * MM]
    assert path.ended == "stopped" and len(steady) > 10
    assert steady.max() / steady.min() - 1 < 0.005
    assert by_peel < steady.mean() < by_shear
