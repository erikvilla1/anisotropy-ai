"""A coupon's ply angles are counted from its length axis (ADR-0065): the deck we write carries them as stated under an *Orientation with
local 1 along +y, reads back to the spec's own engine plies, and a stated 0-degree ply under a pull carries the fibre stress E1 eps_y."""

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.model import fibre_angles as deck_fibre_angles, section_plies
from anisotropy_fea.recovery import element_ply_states
from anisotropy_fea.spec import fibre_angles, full_angles, load_spec, parse_spec, spec_material, spec_plies, to_si
from anisotropy_fea.write_abaqus import write_abaqus

NODAL = paths.spec_path("unnotched-im7-8552-nodal").read_text(encoding="utf-8")


def written_and_read(spec, folder):
    model = build_model(spec)
    path = folder / "coupon.inp"
    path.write_text(write_abaqus(model), encoding="utf-8")
    return model, read_deck(path, "mm-MPa")


def test_a_spec_built_deck_read_back_gives_the_specs_own_engine_plies(tmp_path):
    spec = load_spec(paths.spec_path("unnotched-im7-8552-nodal"))
    model, deck = written_and_read(spec, tmp_path)
    section = deck.parts["Coupon"].sections[0]
    assert section.rotation_deg == pytest.approx(90.0)
    assert [layer.angle_deg for layer in section.layers] == full_angles(spec)[:4] == [45, 0, -45, 90]  # the deck states the coupon's angles
    assert deck_fibre_angles(section) == fibre_angles(spec) == [-45, 90, 45, 0, 0, 45, 90, -45]
    read_plies, spec_built = section_plies(section, deck.materials), spec_plies(spec)
    assert [(p.angle_deg, p.thickness_m) for p in read_plies] == pytest.approx([(p.angle_deg, p.thickness_m) for p in spec_built])
    assert all(a.material.E1 == pytest.approx(b.material.E1, rel=1e-9) for a, b in zip(read_plies, spec_built))  # the deck writes ten digits
    # solved, the labels are the stated angles and the ply at stated 0 degrees carries the largest fibre stress
    field = element_ply_states(solve_membrane(deck))
    e = model.probe_elements["centre"]
    assert field.angles_deg[e].tolist() == [45, 0, -45, 90, 90, -45, 0, 45]
    s11 = field.stress_12[e][:, 0]
    assert int(np.argmax(s11)) in (1, 6) and s11[1] == pytest.approx(s11[6]) and s11[1] > 1.1e9  # about 1181 MPa in the public record's twin
    assert s11[3] < 0 and s11[3] == pytest.approx(s11[4])  # the stated 90-degree plies, fibres across the width, are compressed along their fibres


def test_a_stated_zero_degree_coupon_under_a_pull_carries_e1_times_the_axial_strain(tmp_path):
    """[0]8 stated from the length axis: every fibre runs along the pull, so sigma_1 = E1 eps_y + nu-coupling of order E2, sigma_2 small."""
    text = NODAL.replace("angles = [45, 0, -45, 90]", "angles = [0, 0, 0, 0]").replace('region = "tabs"', 'region = "line"')
    spec = to_si(parse_spec(text))
    assert fibre_angles(spec) == [90] * 8
    model, deck = written_and_read(spec, tmp_path)
    solution = solve_membrane(deck)
    field = element_ply_states(solution)
    e = model.probe_elements["centre"]
    material = spec_material(spec)
    eps = solution.strain[e]
    assert eps[1] == pytest.approx(1e-3 / 0.250, rel=1e-3)  # the 1 mm pull over the 250 mm between the end rows; the rows' hold on x adds a little
    sigma_1, sigma_2, tau_12 = field.stress_12[e][0]
    # the plane-stress law along the fibres: sigma_1 = E1 eps_y when sigma_2 = 0; the lateral edges are free, so sigma_2 is small at the centre
    assert sigma_1 == pytest.approx(material.E1 * eps[1], rel=2e-3)
    assert abs(sigma_2) < 1e-2 * abs(sigma_1) and abs(tau_12) < 1e-2 * abs(sigma_1)
    assert np.allclose(field.stress_12[e][:, 0], sigma_1)  # every ply the same: one direction, one state
    assert field.angles_deg[e].tolist() == [0] * 8 and all(p.angle_deg == 90 for p in section_plies(deck.parts["Coupon"].sections[0], deck.materials))


def test_a_stated_ninety_degree_coupon_is_the_old_zero_degree_one(tmp_path):
    """The same geometry with [90]8 stated from the length axis has its fibres across the width (the engine's 0 degrees): the reaction is the
    transverse modulus's, far below the fibre-direction coupon's."""
    along = to_si(parse_spec(NODAL.replace("angles = [45, 0, -45, 90]", "angles = [0, 0, 0, 0]")))
    across = to_si(parse_spec(NODAL.replace("angles = [45, 0, -45, 90]", "angles = [90, 90, 90, 90]")))
    assert fibre_angles(across) == [0] * 8
    reactions = {}
    for name, spec in (("along", along), ("across", across)):
        folder = tmp_path / name
        folder.mkdir()
        _, deck = written_and_read(spec, folder)
        reactions[name] = solve_membrane(deck).reaction_of(deck.nsets["Grip-Top"])[1]
    material = spec_material(along)
    assert reactions["along"] / reactions["across"] == pytest.approx(material.E1 / material.E2, rel=0.03)
