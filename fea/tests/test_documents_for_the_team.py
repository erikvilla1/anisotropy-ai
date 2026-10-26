"""What the team reads in a coupon package, as the document reviewers of 2026-10-25 found it wanting (ADR-0047): the figures' scales,
the Abaqus/CAE guide, the hand check and the prose. Each test pins one finding so that it cannot come back."""

import importlib.util
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.audit import Evidence, _displacement, _Facts, _fpf, _reaction, _short, load_rubric
from anisotropy_fea.recovery import deck_f12_star, strength_ratios
from anisotropy_fea.report import gauge_element
from anisotropy_fea.compare import load_record
from anisotropy_fea.report import comparison_rows, solve_record

ROOT = Path(__file__).parents[2]
UNNOTCHED = paths.CHECKS / "unnotched-im7-8552" / "records" / "unnotched-im7-8552-nodal-calculix.toml"
OPEN_HOLE = paths.CHECKS / "open-hole-im7-8552" / "records" / "open-hole-im7-8552-calculix.toml"
COUPLED_DECK = paths.CHECKS / "unnotched-im7-8552" / "decks" / "unnotched-im7-8552-coupling-abaqus.inp"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build():
    pytest.importorskip("matplotlib")
    return load("anisotropy_models_build", ROOT / "docs/models/build.py")


@pytest.fixture(scope="module")
def coupon():
    pytest.importorskip("matplotlib")
    return load("anisotropy_models_coupon", ROOT / "docs/models/coupon.py")


def guide(build, record_path: Path) -> str:
    record = load_record(record_path)
    deck, solution = solve_record(record)
    return build.rebuild_section(record, record_path, deck, solution, record["units"])


def test_a_field_negative_everywhere_but_for_roundoff_is_drawn_on_the_negative_scale(build):
    """The compression coupon's axial strain and force came out white: a roundoff-sized positive value put the scale at 0 and up."""
    import matplotlib.pyplot as plt
    polys = [np.array([[x, 0.0], [x + 1, 0.0], [x + 1, 1.0], [x, 1.0]]) for x in range(3)]
    fig, ax = plt.subplots()
    try:
        for diverging in (True, False):
            norm = build.plot_deck_module.field_panel(ax, polys, [-0.008, -0.004, 1e-12], "t", "l", diverging, "mm").norm
            assert (norm.vmin, norm.vmax) == (pytest.approx(-0.008), 0.0)
        norm = build.plot_deck_module.field_panel(ax, polys, [0.008, 0.004, -1e-12], "t", "l", False, "mm").norm
        assert (norm.vmin, norm.vmax) == (0.0, pytest.approx(0.008))
    finally:
        plt.close(fig)


def test_each_coupling_is_printed_with_its_own_kinematic_line(build):
    blocks = build.rebuild.coupling_blocks(COUPLED_DECK)
    assert len(blocks) == 2
    for block in blocks:
        first, second = block.splitlines()[:2]
        assert first.lower().startswith("*coupling") and second.lower().startswith("*kinematic")


def test_the_guide_names_the_static_values_in_abaqus_order_and_asks_for_the_decks_five_strengths(build):
    text = guide(build, UNNOTCHED)
    static = re.search(r"initial increment (\S+), time period (\S+), minimum increment (\S+), maximum increment (\S+)", text)
    assert static is not None and "(period, initial, minimum, maximum)" not in text
    assert f"Time period {static.group(2)}" in text  # the period on the Basic tab, the increments on the Incrementation tab
    assert "one row with the five values of the deck: Xt, Xc, Yt, Yc, S" in text and "sixth value f*" not in text
    assert "State the material form" not in text and "ADR-" not in text.split("Evidence tags")[1].split("Rule for authors")[0]


def test_the_guide_of_an_open_hole_coupon_cuts_the_hole_and_takes_the_mesh_from_our_deck(build):
    text = guide(build, OPEN_HOLE)
    assert "Create Circle: Center and Perimeter" in text and "the circle inside the rectangle leaves the hole in the shell" in text
    assert "cannot be made again in Abaqus/CAE" in text and "File > Import > Model" in text
    assert "the inner edges of the gripped node groups" in text and "every y where the node-row spacing changes" not in text
    assert r"\begin{tabular}{lll}" not in text  # the table of sketch points is a long table that breaks across pages


def test_the_hand_check_of_an_open_hole_coupon_reads_the_far_field_and_is_not_scored(build):
    record = load_record(OPEN_HOLE)
    deck, solution = solve_record(record)
    rows, _ = comparison_rows(record)
    text = build.clt_section(deck, solution, record, rows, record["units"], "OHT")
    assert "the far-field probe" in text and "here it is shown, not scored" in text
    assert "The record holds no values at this element" not in text  # the far-field probe is in the record


def reaction_row(text: str) -> tuple[float, float]:
    """Our engine's reaction and the reference solver's, from the hand check's reaction row."""
    cells = [c.strip().replace("$-$", "-") for c in re.search(r"Reaction \$R_y\$ at the moving grip &(.*?)\\\\", text).group(1).split("&")]
    return float(cells[2]), float(cells[4])  # the document writes a minus sign as $-$


LOCAL_COMPRESSION = [d.name for d in paths.model_dirs() if "-UNC-" in d.name
                     and (d / paths.OURS / paths.VERIFICATION / f"{d.name}-calculix.toml").is_file()]


@pytest.mark.parametrize("record_path", [UNNOTCHED] + [paths.MODELS / c / paths.OURS / paths.VERIFICATION / f"{c}-calculix.toml" for c in LOCAL_COMPRESSION])
def test_the_reference_reaction_is_the_moving_grips(build, record_path):
    """In compression the first positive reaction is the other grip's: the reference value must have our engine's sign."""
    record = load_record(record_path)
    deck, solution = solve_record(record)
    rows, _ = comparison_rows(record)
    ours, reference = reaction_row(build.clt_section(deck, solution, record, rows, record["units"]))
    assert np.sign(ours) == np.sign(reference) and abs(ours - reference) / abs(reference) < 0.03


def test_the_team_reads_no_decision_record_numbers_and_finds_every_theory_section(coupon):
    tex = "\n".join(["Grips (ADR-0030, amendment 1) hold the width (engine theory, Sections 3 and 4); see engine theory, Section 5.",
                     r"\begin{plainfile}", "# a comment of the spec (ADR-0035)", r"\end{plainfile}", "Angles counterclockwise, as in ADR-0004."])
    out = coupon.for_the_team(tex)
    assert "ADR-0030" not in out and "ADR-0004" not in out and "# a comment of the spec (ADR-0035)" in out  # a listing stays as the file is
    assert r"Sections~\ref{sec:engine-3} and~\ref{sec:engine-4}" in out and r"Section~\ref{sec:engine-5}" in out
    assert "the engine manual, Sections 3 and 4" in coupon.for_the_team(tex, theory=False)  # no theory printed: no label to point to


def test_a_reaction_shows_whole_in_the_comparison_table(build):
    """Two six-digit reactions 0.1 % apart were both printed as 1.06e5: the table hid the two numbers it compares."""
    assert build.compact(123456.0) == "123456" and build.compact(123579.4) == "123579"
    assert "times" in build.compact(-1.51e-14)  # roundoff keeps its exponent, three digits


def test_row_c7_leads_with_the_earliest_criterion_and_names_the_others():
    item = next(item for item in load_rubric().items if item.id == "C7")
    evidence = Evidence(test_code="UNC", units="mm-MPa", card=(), our_deck=None, solution=None, material=None,
                        fpf=("tsai_hill", 0.5, 2, 45.0), fpf_others=(("max_stress", 0.75, 2, 45.0),))
    _, found = _fpf(item, evidence, None)
    assert found.ours[0].startswith("The first ply to fail is ply 2 (45 deg) by Tsai-Hill, at 0.5") and "the earliest of the criteria" in found.ours[0]
    assert found.ours[1] == "By maximum stress: ply 2 (45 deg), at 0.75 of the applied loading"


def test_a_coupling_keeps_its_position_in_the_model_rows():
    """Row B7 read "Coupling, reference point at: the same" twice: the name was cut at its first parenthesis."""
    assert _short("Coupling, reference point at (12.5, 250)") == "Coupling, reference point at (12.5, 250)"
    assert _short("Material E1 (MPa)") == "E1"


def test_the_cover_names_the_points_the_record_compares(coupon):
    record = load_record(OPEN_HOLE)
    rows, _ = comparison_rows(record)
    points = coupon.record_points(rows)
    assert points.startswith("the grips, our node ") and ", our element " in points and "hole" not in points
    named = coupon.record_points(rows, {name: "far" for name in {r.name for r in rows if r.group == "strain"}})
    assert "(far probe)" in named  # a point the spec names as a probe says which


def test_the_physics_row_says_who_judges_each_check(coupon):
    audit = sys.modules["anisotropy_models_audit"]
    rows = audit.files_compared(c=None, our_deck="2-our-model/abaqus/X-abaqus.inp", spec="2-our-model/spec/X.toml",
                                physics=(("Equilibrium", "our tools judge"), ("Mesh convergence where the stress peaks", "not built yet")))
    physics = dict(rows)["Physics"]
    assert "equilibrium (our tools judge)" in physics and "mesh convergence where the stress peaks (not built yet)" in physics


def test_row_c4_reads_the_probe_node_beside_the_gauge_element():
    """The largest displacement was the prescribed grip motion, at no point the team could set a value beside."""
    record = load_record(OPEN_HOLE)
    deck, solution = solve_record(record)
    item = next(item for item in load_rubric().items if item.id == "C4")
    facts = _Facts(None, "", (0.0,), "mm", "MPa", gauge=gauge_element(deck, solution), units="mm-MPa")
    evidence = Evidence(test_code="OHT", units="mm-MPa", card=(), our_deck=deck, solution=solution, material=None)
    _, found = _displacement(item, evidence, facts)
    assert re.match(r"Displacement at our node \d+, the \w+ probe at \(", found.ours[0]) and "Largest displacement" not in found.ours[0]


def test_the_first_ply_to_fail_of_an_open_hole_coupon_is_placed_beside_the_hole(coupon):
    record = load_record(OPEN_HOLE)
    deck, solution = solve_record(record)
    field = strength_ratios(solution, "max_stress", deck_f12_star(deck))
    place, at_grip, tied = coupon.fpf_place(deck, solution, field, "mm-MPa")
    assert place == "beside the hole" and not at_grip and field.ply in tied


def test_the_reaction_row_says_tension_or_compression():
    item = next(item for item in load_rubric().items if item.id == "C1")
    facts = _Facts(None, "", (0.0,), "mm", "MPa", reaction_N=-1234.5)

    class Evidence:  # only what the scorer reads
        team_reaction = None

    _, found = _reaction(item, Evidence(), facts)
    assert found.ours == ("1234.5 N along the coupon at the top grip, in compression",)
