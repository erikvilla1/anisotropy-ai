"""Open-hole coupons from a spec: the Gmsh mesh through the model and the writers, the committed decks, and the Kirsch reference (ADR-0030, chunk A2)."""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.femodel import build_model, mesh_for_spec
from anisotropy_fea.spec import SpecError, load_spec, parse_spec, to_si
from anisotropy_fea.write_abaqus import write_abaqus

ROOT = Path(__file__).parents[1]
SPECS = ROOT / "validation" / "specs"
GENERATED = ROOT / "validation" / "decks" / "generated"
sys.path.insert(0, str(ROOT / "tools"))
from kirsch_hole import kirsch_polar, kirsch_xy  # noqa: E402

from anisotropy_fea.mesher import gmsh_available  # noqa: E402

needs_gmsh = pytest.mark.skipif(gmsh_available() is None,
                                reason="Gmsh is not available: from fea/ run `uv sync --extra mesh` (on Linux also apt install libglu1-mesa)")

IM7 = (SPECS / "open-hole-im7-8552.toml").read_text(encoding="utf-8")
KIRSCH = (SPECS / "open-hole-isotropic-kirsch.toml").read_text(encoding="utf-8")


def spec_with(old: str, new: str, base: str = IM7):
    assert old in base, f"the spec no longer contains {old!r}"
    return parse_spec(base.replace(old, new, 1))


# --- the spec's rules for the hole ------------------------------------------------------------------


def test_open_hole_needs_gmsh_and_element_size_and_gmsh_is_for_open_holes_only():
    with pytest.raises(SpecError, match="cannot cut a hole"):
        spec_with('mesher = "gmsh"', 'mesher = "structured"')
    with pytest.raises(SpecError, match="takes mesh.element_size"):
        spec_with("element_size = 2.0    # the blocks around the hole; the inner square and the arcs follow [mesh.hole]", "nx = 12\nny = 150")
    unnotched = (SPECS / "unnotched-im7-8552-nodal.toml").read_text(encoding="utf-8")
    with pytest.raises(SpecError, match="goes with open_hole_tension"):
        spec_with('mesher = "structured"', 'mesher = "gmsh"', base=unnotched)


def test_the_inner_square_must_fit_between_the_tabs_and_inside_the_width():
    with pytest.raises(SpecError, match="must end before the inner square"):
        spec_with("tab_length = 50.0", "tab_length = 145.0")
    with pytest.raises(SpecError, match="inside the width"):
        spec_with("ring_ratio = 2.0      # inner square half-side = 2 hole radii = 6 mm", "ring_ratio = 7.0")
    with pytest.raises(SpecError, match="multiple of 4"):
        spec_with("circumferential = 32", "circumferential = 30")


# --- the model and the decks -------------------------------------------------------------------------


@needs_gmsh
def test_the_im7_open_hole_model_has_the_hole_set_tab_bands_and_probes():
    spec = load_spec(SPECS / "open-hole-im7-8552.toml")
    model = build_model(spec)
    assert model.mesh.mesher == "gmsh" and model.mesh.element_count == 3168 and model.mesh.node_count == 3356
    assert model.node_sets["Hole"].size == 32 and model.element_sets["Gauge"].size == 2168
    assert model.node_sets["Grip-Bottom"].size == model.node_sets["Grip-Top"].size == 546  # whole tabs
    assert set(model.probe_elements) == {"hole_side", "hole_top", "far"} and set(model.probe_nodes) == {"centre_top", "hole_side", "gauge"}
    hole_side = model.mesh.centroids()[model.probe_elements["hole_side"]]
    assert math.hypot(hole_side[0] - 0.018, hole_side[1] - 0.150) < 0.0035  # the element beside the hole
    assert any("central hole of diameter 0.006 m" in line for line in model.heading)


@needs_gmsh
def test_the_written_deck_reads_back_and_the_kernel_solves_it(tmp_path):
    spec = load_spec(SPECS / "open-hole-isotropic-kirsch.toml")
    model = build_model(spec)
    path = tmp_path / "kirsch.inp"
    path.write_text(write_abaqus(model), encoding="utf-8", newline="\n")
    deck = read_deck(path, "mm-MPa")
    assert len(deck.nsets["Hole"]) == 60 and len(deck.elsets["Probe-far_side"]) == 1
    from anisotropy_fea.membrane import solve_membrane

    solution = solve_membrane(deck)
    assert solution.total_reaction == pytest.approx([0.0, -12000.0], abs=1e-6)


@needs_gmsh
@pytest.mark.parametrize("name", ["open-hole-im7-8552-abaqus", "open-hole-isotropic-kirsch-abaqus"])
def test_the_committed_open_hole_decks_match_their_specs(name):
    spec_name = name.removesuffix("-abaqus")
    text = write_abaqus(build_model(load_spec(SPECS / f"{spec_name}.toml")))
    committed = (GENERATED / f"{name}.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == text, f"{name}: regenerate with examples/build_model.py --no-solve and copy the deck into validation/decks/generated/"


@needs_gmsh
def test_the_committed_open_hole_calculix_deck_matches_its_spec():
    from anisotropy_fea.write_calculix import write_calculix

    spec = load_spec(SPECS / "open-hole-im7-8552.toml")
    spec2 = spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})
    text = write_calculix(build_model(spec2))
    committed = (GENERATED / "open-hole-im7-8552-ccx.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == text, "regenerate with examples/build_model.py --target both and copy the deck into validation/decks/generated/"
    assert "*ELEMENT, TYPE=S8R" in text and "NSET=Hole" in text


def test_the_committed_open_hole_decks_are_what_the_kirsch_case_and_prepomax_read():
    """Without Gmsh the decks still exist and read back: the validation case needs no mesher."""
    for name, probe, hole in (("open-hole-im7-8552-abaqus", "Probe-far", 32), ("open-hole-isotropic-kirsch-abaqus", "Probe-far_side", 60)):
        deck = read_deck(GENERATED / f"{name}.inp", "mm-MPa")
        assert len(deck.elsets[probe]) == 1 and len(deck.nsets["Hole"]) == hole


# --- the Kirsch closed form -------------------------------------------------------------------------


def test_kirsch_limits_three_sigma_beside_the_hole_minus_sigma_above_it_sigma_far_away():
    sigma, a = 100.0, 3.0
    assert kirsch_polar(sigma, a, a, math.pi / 2)[1] == pytest.approx(3 * sigma)  # hoop stress beside the hole (90 degrees from the load)
    assert kirsch_polar(sigma, a, a, 0.0)[1] == pytest.approx(-sigma)  # hoop stress at the top of the hole
    rr, tt, rt = kirsch_polar(sigma, a, a, 0.7)
    assert rr == pytest.approx(0.0, abs=1e-12) and rt == pytest.approx(0.0, abs=1e-12)  # the hole edge is traction free
    assert kirsch_xy(sigma, a, 1000 * a, 0.0, (0.0, 0.0)) == pytest.approx((0.0, sigma, 0.0), abs=1e-5 * sigma)
    sxx, syy, txy = kirsch_xy(sigma, a, a, 0.0, (0.0, 0.0))
    assert (sxx, syy, txy) == pytest.approx((0.0, 3 * sigma, 0.0), abs=1e-12)
    sxx, syy, txy = kirsch_xy(sigma, a, 0.0, a, (0.0, 0.0))
    assert (sxx, syy, txy) == pytest.approx((-sigma, 0.0, 0.0), abs=1e-12)


def test_kirsch_in_plate_axes_is_the_rotated_polar_tensor():
    sigma, a, centre = 100.0, 3.0, (60.0, 180.0)
    x, y = 64.0, 182.5
    sxx, syy, txy = kirsch_xy(sigma, a, x, y, centre)
    alpha = math.atan2(y - centre[1], x - centre[0])
    rr, tt, rt = kirsch_polar(sigma, a, math.hypot(x - centre[0], y - centre[1]), alpha - math.pi / 2)
    c, s = math.cos(alpha), math.sin(alpha)
    # the first invariant is the same in both bases, and the polar components come back from the plate components
    assert sxx + syy == pytest.approx(rr + tt)
    assert rr == pytest.approx(sxx * c * c + syy * s * s + 2 * txy * s * c)
    assert tt == pytest.approx(sxx * s * s + syy * c * c - 2 * txy * s * c)


def test_the_kirsch_case_names_the_committed_deck_and_the_probe_elements_of_the_spec():
    import tomllib

    case = tomllib.loads((ROOT / "validation" / "cases" / "open-hole-isotropic-kirsch.toml").read_text(encoding="utf-8"))
    assert case["mesh"]["deck"] == "../decks/generated/open-hole-isotropic-kirsch-abaqus.inp"
    deck = read_deck(GENERATED / "open-hole-isotropic-kirsch-abaqus.inp", "mm-MPa")
    probe_labels = sorted(int(label) for name in ("hole_side", "hole_top", "ring_side", "far_side") for _, label in deck.elsets[f"Probe-{name}"])
    assert sorted(int(key.split(".")[1]) for key in case["expected"]["ply_stress_local"]) == probe_labels
    sigma_yy = case["expected"]["ply_stress_local"]["Coupon-1.3501"]["1"][1]
    assert 2.8 * 100 < sigma_yy < 3 * 100  # beside the hole, just outside r = a
    assert np.isnan(case["expected"]["ply_stress_local"]["Coupon-1.3501"]["1"][0])
