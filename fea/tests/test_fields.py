"""The viewer's fields (ADR-0051): every array is the solution in the deck's units, the display averages are the means over the
elements sharing a node, the summary's extremes are the arrays' extremes, the first-ply failure is `strength_ratios`', and the
explanation's sentences quote the facts and nothing else. On the public IM7/8552 check decks, nothing under .local/."""

import json
import math

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.explain import MODE_WORDS, explanation, fact_sheet, number, numbers_in, result_sentences, setup_sentences
from anisotropy_fea.fields import GAUGE_STAND_OFF, MODES, applied_loading, field_data, gauge_elements, gauge_reading, nodal_averages, per_ply_spans, rounded, run_answer, span
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import KernelError
from anisotropy_fea.recovery import deck_f12_star, element_ply_states, strength_ratios
from anisotropy_fea.report import fpf_place
from anisotropy_fea.units import UNIT_LABEL, from_si

UNITS = "mm-MPa"


@pytest.fixture(scope="module")
def solved():
    deck = read_deck(paths.deck_path(paths.spec_path("unnotched-im7-8552-nodal"), "abaqus"), UNITS)
    return deck, solve_membrane(deck)


@pytest.fixture(scope="module")
def data(solved):
    deck, solution = solved
    return field_data(deck, solution, UNITS, coupon={"designation": "IM7-UNT-L1", "test": "unnotched tension", "layup": "[45/0/-45/90]s"})


def test_the_fields_are_the_solution_in_the_decks_units(solved, data):
    deck, solution = solved
    mesh = solution.mesh
    json.dumps(data)  # JSON-ready
    assert data["units"] == UNITS and data["labels"]["stress"] == "MPa" and data["labels"]["strain"] == "-"
    assert data["mesh"]["node_count"] == mesh.node_count and data["mesh"]["element_count"] == mesh.element_count and data["mesh"]["plies"] == 8
    assert data["mesh"]["angles"] == [45, 0, -45, 90, 90, -45, 0, 45] and len(data["mesh"]["quads"]) == mesh.element_count
    assert np.allclose(data["nodal"]["displacement"], from_si(solution.displacement, "length", UNITS), rtol=1e-8)
    assert np.allclose(data["nodal"]["reaction"], solution.reaction, rtol=1e-8)
    assert np.allclose(data["element"]["strain"], solution.strain, rtol=1e-8)
    assert np.allclose(data["element"]["section_force"], from_si(solution.section_force, "force_per_length", UNITS), rtol=1e-8)
    field = element_ply_states(solution)
    assert np.allclose(data["element"]["ply"]["stress_12"], from_si(np.stack(field.stress_12), "stress", UNITS), rtol=1e-8)
    assert np.allclose(data["element"]["ply"]["strain_12"], np.stack(field.strain_12), rtol=1e-8)
    assert set(data["element"]["failure"]) == {"max_stress", "tsai_hill", "tsai_wu"}  # the deck states f* = 0, so every criterion is allowed
    assert data["mesh"]["node_sets"]["Grip-Top"] == [mesh.node(key) for key in deck.nsets["Grip-Top"]]
    assert data["element"]["modes"] == list(MODES)


def test_the_averages_are_the_means_over_the_elements_sharing_a_node(solved, data):
    _, solution = solved
    mesh = solution.mesh
    corners = mesh.connectivity[:, :4]
    averages = np.asarray(data["nodal"]["averages"]["strain"], dtype=float)
    held = set(data["mesh"]["held_elements"])
    middle = data["summary"]["gauge_centre"]["element"]
    node = int(corners[middle, 2])  # a corner in the gauge, shared by four free elements
    sharing = [e for e in range(mesh.element_count) if node in corners[e]]
    assert len(sharing) == 4 and not held & set(sharing)
    assert np.allclose(averages[node], solution.strain[sharing].mean(axis=0), rtol=1e-8)
    assert "display averages" in data["nodal"]["averages_note"] and "held_elements" in data["nodal"]["averages_note"]
    one = nodal_averages(np.array([[0, 1, 2, 3]]), 5, np.array([[1.0, 2.0]]))
    assert one[0].tolist() == [1.0, 2.0] and np.isnan(one[4]).all()  # a node no element touches
    assert rounded(one)[4] == [None, None] and rounded(np.array([1.23456789012345])) == [1.23456789]
    two = nodal_averages(np.array([[0, 1, 2, 3], [1, 4, 5, 2]]), 6, np.array([0.0, 6.0]), np.array([True, False]))
    assert two[1] == 6.0 and np.isnan(two[0]) and two[4] == 6.0  # a skipped element counts at no node


def test_an_element_clamped_in_a_grip_is_left_out_of_the_averages_and_the_ends(solved, data):
    """ADR-0063 amendment 4: a tab clamped by its grip moves as one body, so its zero stress is the clamp's. Its elements are named
    (`mesh.held_elements`), every node of the tab line takes the mean of the gauge's elements alone, so the step from the clamp to the
    gauge is not drawn as a ramp, and the legend's ends of a stress are the free part's; the displacement keeps every node."""
    _, solution = solved
    mesh = solution.mesh
    corners = mesh.connectivity[:, :4]
    held = data["mesh"]["held_elements"]
    tabs = set(data["mesh"]["element_sets"]["Tab-Bottom"]) | set(data["mesh"]["element_sets"]["Tab-Top"])
    assert held and set(held) <= tabs  # every clamped element is in a tab; the row along the tab line is free
    line = data["mesh"]["node_sets"]["Tab-Bottom-Line"] if "Tab-Bottom-Line" in data["mesh"]["node_sets"] else None
    index = np.asarray(data["element"]["failure"]["tsai_hill"]["element_index"], dtype=float)
    average = np.asarray(data["nodal"]["averages"]["failure_index"]["tsai_hill"], dtype=float)
    on_line = [i for i in range(mesh.node_count) if any(i in corners[e] for e in held) and any(i in corners[e] for e in range(mesh.element_count) if e not in held)]
    assert on_line and (line is None or set(line) <= set(on_line))
    for node in on_line:
        free = [e for e in range(mesh.element_count) if node in corners[e] and e not in held]
        assert average[node] == pytest.approx(index[free].mean(), rel=1e-8)  # the gauge's elements alone
    inside = [i for i in range(mesh.node_count) if all(e in held for e in range(mesh.element_count) if i in corners[e]) and i in corners]
    assert inside and all(np.isnan(average[i]) for i in inside)  # a node only clamped elements touch: no average
    free = np.ones(mesh.element_count, dtype=bool)
    free[held] = False
    assert data["ranges"]["failure_index"]["tsai_hill"]["element"] == [index[free].min(), index[free].max()]
    assert data["ranges"]["failure_index"]["tsai_hill"]["element"][0] > 0.5  # the clamp's zero is not the legend's low end
    magnitude = np.asarray(data["nodal"]["magnitude"], dtype=float)
    assert data["ranges"]["u_mag"]["nodal"] == [magnitude.min(), magnitude.max()]  # the grips' travel is a result: every node


def test_the_summary_names_the_extremes(solved, data):
    deck, solution = solved
    summary = data["summary"]
    magnitude = np.linalg.norm(solution.displacement, axis=1)
    assert summary["max_displacement"]["value"] == pytest.approx(from_si(magnitude.max(), "length", UNITS)) and summary["max_displacement"]["node"] == int(np.argmax(magnitude))
    stress = np.asarray(data["element"]["ply"]["stress_12"])
    e, k = summary["max_ply"]["S11"]["element"], summary["max_ply"]["S11"]["ply"] - 1
    assert abs(stress[e, k, 0]) == pytest.approx(np.abs(stress[:, :, 0]).max()) and summary["max_ply"]["S11"]["value"] == pytest.approx(stress[e, k, 0])
    assert summary["max_ply"]["mises"]["value"] == pytest.approx(np.asarray(data["element"]["ply"]["mises"]).max())
    assert summary["applied"] == {"control": "displacement", "value": pytest.approx(1.0), "unit": "mm", "dof": 2, "direction": "along the coupon"}
    applied = applied_loading(deck, solution)
    assert (applied["control"], applied["value"], applied["dof"], applied["set"]) == ("displacement", pytest.approx(1e-3), 2, "the top grip")
    assert summary["reaction"]["sense"] == "in tension" and summary["reaction"]["value"] > 0 and summary["reaction"]["set"] == "the top grip"
    assert summary["equilibrium_residual"] < 1e-6 and summary["free_residual"] < 1e-6
    for criterion, found in summary["fpf"].items():
        expected = strength_ratios(solution, criterion, deck_f12_star(deck))
        assert found["factor"] == pytest.approx(expected.factor) and found["index"] == pytest.approx(1 / expected.factor)
        assert found["ply"] == expected.ply and found["mode"] == expected.governing_mode and found["label"] == f"{expected.element[0]}.{expected.element[1]}"
        place, grip, tied = fpf_place(deck, solution, expected, UNITS)
        assert found["place"] == place and found["touches_grip"] == grip and found["tied_plies"] == tied
        index = np.asarray(data["element"]["failure"][criterion]["index"])
        assert index.max() == pytest.approx(1 / expected.factor) and data["element"]["failure"][criterion]["worst_ply"][found["element"]] == expected.ply
    assert summary["earliest"] == min(summary["fpf"], key=lambda c: summary["fpf"][c]["factor"])


def test_the_ranges_are_the_ends_of_the_arrays_as_written(data):
    """ADR-0063: every field's [min, max], element values and display averages apart, equals the extremes of the array the viewer reads,
    so the legend's ends are written here and the browser derives none."""
    ranges = data["ranges"]
    assert "legend" in data["ranges_note"]
    free = np.ones(data["mesh"]["element_count"], dtype=bool)
    free[data["mesh"]["held_elements"]] = False  # an element clamped inside a grip is out of every end but the displacement's (ADR-0063 amendment 4)
    strain = np.asarray(data["element"]["strain"], dtype=float)[free]
    assert ranges["eps_y"]["element"] == [strain[:, 1].min(), strain[:, 1].max()]
    averages = np.asarray(data["nodal"]["averages"]["strain"], dtype=float)
    assert ranges["eps_y"]["nodal"] == [np.nanmin(averages[:, 1]), np.nanmax(averages[:, 1])]
    magnitude = np.asarray(data["nodal"]["magnitude"], dtype=float)
    assert ranges["u_mag"]["nodal"] == [magnitude.min(), magnitude.max()]
    assert "u_z" not in ranges and "M_y" not in ranges and "theta_x" not in ranges  # a membrane solve
    stress = np.asarray(data["element"]["ply"]["stress_12"], dtype=float)[free]  # (elements, plies, 3)
    assert len(ranges["S11"]["element"]) == 8 and ranges["S22"]["element"][2] == [stress[:, 2, 1].min(), stress[:, 2, 1].max()]
    stress_averages = np.asarray(data["nodal"]["averages"]["ply_stress_12"], dtype=float)
    assert ranges["S12"]["nodal"][5] == [np.nanmin(stress_averages[:, 5, 2]), np.nanmax(stress_averages[:, 5, 2])]
    mises = np.asarray(data["element"]["ply"]["mises"], dtype=float)[free]
    assert ranges["mises"]["element"][0] == [mises[:, 0].min(), mises[:, 0].max()]
    index = np.asarray(data["element"]["failure"]["tsai_hill"]["element_index"], dtype=float)[free]
    assert ranges["failure_index"]["tsai_hill"]["element"] == [index.min(), index.max()]
    assert ranges["failure_index"]["tsai_hill"]["element"][1] == pytest.approx(data["summary"]["fpf"]["tsai_hill"]["index"])
    per_ply = np.asarray(data["element"]["failure"]["tsai_hill"]["index"], dtype=float)[free]  # (elements, plies)
    assert ranges["failure_index_ply"]["tsai_hill"]["element"][3] == [per_ply[:, 3].min(), per_ply[:, 3].max()]
    assert span(np.array([np.nan, 2.0, -1.0])) == [-1.0, 2.0] and span(np.array([np.nan])) == [None, None]
    assert per_ply_spans(np.array([[[1.0, 2.0], [3.0, 4.0]]])) == [[[1.0, 1.0], [2.0, 2.0]], [[3.0, 3.0], [4.0, 4.0]]]  # one element, two plies, two faces


def test_the_criteria_asked_for_are_reported_and_a_missing_one_refused(solved):
    deck, solution = solved
    only = field_data(deck, solution, UNITS, criteria=("max_stress",))
    assert list(only["element"]["failure"]) == ["max_stress"] and only["summary"]["earliest"] == "max_stress"
    none = field_data(deck, solution, UNITS, criteria=())
    assert none["element"]["failure"] == {} and none["summary"]["fpf"] == {} and none["summary"]["earliest"] is None
    with pytest.raises(KernelError, match="have no strain limits"):
        field_data(deck, solution, UNITS, criteria=("max_strain",))


# --------------------------------------------------------------------------------------------- the explanation

def test_every_number_in_a_sentence_is_a_fact(data):
    facts = fact_sheet(data["summary"], data["coupon"], UNITS, data["labels"])
    sentences = result_sentences(facts)
    printed = set()
    for value in facts.values():
        for v in (value if isinstance(value, list) else [value]):
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                printed.update({f"{v:.4g}", str(v), f"{v:g}"})
            elif isinstance(v, str):
                printed.add(v)  # a node or element number is a name the facts carry as text
                printed.update(numbers_in(v))  # and a place says its distance in words ("3.5 mm from the nearer tab line"), as the API's guard reads it
    for sentence in sentences:
        for token in numbers_in(sentence):
            assert token in printed or token.lstrip("-+") in printed, (token, sentence)
    # the verdict leads; the load, the displacement and the ply stresses, which the page's summary shows, follow (ADR-0091 amendment 2)
    assert sentences[0].startswith("By the ") and " criterion the laminate " in sentences[0]
    loading = next(i for i, s in enumerate(sentences) if "under a displacement of 1 mm along the coupon: the top grip carries" in s)
    assert sentences[loading].startswith("Unnotched tension, under a displacement") or sentences[loading].startswith("Unnotched tension, [")
    assert not any("IM7-UNT-L1" in s for s in sentences)  # the record's name stays out of the words
    assert "The largest displacement is" in sentences[loading + 1]
    # the ply stresses are said with their symbols, not the CAE names a viewer's global S11 collides with (ADR-0066), and no ply von Mises;
    # in the gauge section, tension and compression apart (ADR-0085)
    ply = sentences[loading + 2]
    assert ply.startswith("In the gauge section, each ply in its own fibre axes: the largest tension along the fibres (sigma_1) is")
    assert "the largest compression along the fibres (sigma_1)" in ply and "the largest in-plane shear (tau_12)" in ply
    assert "in the ply's axes" in ply and "S11 =" not in ply and "von Mises" not in ply and "max_mises" not in facts
    assert any("criterion the laminate" in s and "at the applied loading, in the gauge section" in s for s in sentences)
    assert any(s.startswith("The earliest of the criteria is") for s in sentences)
    assert any(MODE_WORDS[facts[f"{c}_mode"]] in s for c in facts["criteria"] for s in sentences)


def test_a_float_fact_holds_the_digits_the_sentences_print(data):
    """ADR-0052 amendment 1: a writer that copies a number from the sheet copies the sentences' four significant figures."""
    facts = fact_sheet(data["summary"], data["coupon"], UNITS, data["labels"])
    floats = {key: value for key, value in facts.items() if isinstance(value, float)}
    assert {"reaction", "max_displacement", "max_S11", "max_S11_angle"} <= set(floats)
    for key, value in floats.items():
        assert value == float(f"{value:.4g}"), (key, value)  # no digit beyond the fourth
    exact = abs(float(data["summary"]["reaction"]["value"]))  # the engine's value, as the summary keeps it
    assert f"{facts['reaction']:.4g}" == f"{exact:.4g}"  # the same four digits the sentence prints
    assert abs(facts["reaction"] - exact) <= 0.5 * 10 ** (math.floor(math.log10(exact)) - 3)  # within half a unit of the fourth digit


def test_the_limiting_ply_is_named_with_its_place_and_mode(data):
    facts = fact_sheet(data["summary"], data["coupon"], UNITS, data["labels"])
    earliest = facts["earliest"]
    sentence = next(s for s in result_sentences(facts) if f"the {facts[earliest + '_mode']}" in s or MODE_WORDS[facts[earliest + "_mode"]] in s)
    assert f"ply {facts[earliest + '_ply']} ({facts[earliest + '_angle']:.4g} degrees)" in sentence and facts[earliest + "_place"] in sentence
    assert ("holds at the applied loading" in sentence) == (facts[earliest + "_factor"] > 1.0) == (not facts[earliest + "_fails"])
    loading = f"{number(facts[earliest + '_applied_at_failure'])} {facts['applied_unit']}, {number(facts[earliest + '_reaction_at_failure'])} N at the top grip"
    assert loading in sentence and f"({number(facts[earliest + '_x'])}, {number(facts[earliest + '_y'])} mm)" in sentence


@pytest.mark.parametrize(("value", "written"), [
    (16220.0, "16220"), (100000.0, "100000"), (-364.5, "-364.5"), (0.9748, "0.9748"), (0.001, "0.001"), (1.5e6, "1.5e+06"),
    (6.018e-6, "6.018e-06"), (999999.7, "1e+06"), (0.0, "0"),
])
def test_a_sentence_writes_the_sites_one_number_rule_in_ascii(value, written):
    """Plain digits from 0.001 up to a million and an exponent outside, four figures, as lib/number-format.ts prints them and the API's
    laminate sentences write them; the page turns the exponent into "x 10^n" and the sign into a minus (ADR-0091 amendment 1)."""
    assert number(value) == written
    assert numbers_in(f"It is {written} N.") == [written]  # the guard reads it back as one number


def test_without_criteria_the_explanation_says_so(solved):
    deck, solution = solved
    none = field_data(deck, solution, UNITS, criteria=())
    out = explanation(none["summary"], {}, UNITS, none["labels"])
    assert out["writer"] == "template" and out["sentences"][0] == "No failure criterion was asked for, so first-ply failure is not reported."
    assert out["sentences"][1].startswith("Under a displacement")  # no test or layup named: the sentence opens on the load
    assert out["facts"]["designation"] == "the coupon" and out["setup_sentences"] == []


def test_the_setup_sentences_follow_the_checklist():
    checklist = {"items": [{"id": "units", "label": "Units consistent", "state": "pass", "message": "every row in mm, MPa and N", "rows": []},
                           {"id": "mesh", "label": "Mesh quality acceptable", "state": "warn", "message": "aspect ratio 12 at worst", "rows": []},
                           {"id": "load", "label": "Load applied", "state": "missing", "message": "Value (mm or N): required", "rows": ["Value (mm or N)"]},
                           {"id": "probes", "label": "Result points inside the coupon", "state": "pending", "message": "", "rows": []}]}
    out = setup_sentences(checklist)
    assert out == ["The setup is blocked: 1 item needs input (load applied).", "Units consistent: every row in mm, MPa and N.",
                   "Warning, mesh quality acceptable: aspect ratio 12 at worst.", "Load applied needs attention: Value (mm or N): required (rows: Value (mm or N))."]
    ready = setup_sentences({"items": [item for item in checklist["items"] if item["state"] in ("pass", "warn")]})
    assert ready[0] == "The setup is ready to solve, with 1 warning."
    assert numbers_in("ply 3 (-45 degrees) at element 16, 2.1e+03 MPa, f12") == ["3", "-45", "16", "2.1e+03"]


def test_the_gauge_sections_first_ply_failure_sits_away_from_the_tabs(data):
    public_fields = data
    # the grip-edge factor is the model's smallest; the gauge section's is what a test coupon, which breaks in its gauge, is compared with
    summary = public_fields["summary"]
    assert set(summary["fpf_gauge"]) == set(summary["fpf"]) and summary["earliest_gauge"] in summary["fpf_gauge"]
    for criterion, grip in summary["fpf"].items():
        gauge = summary["fpf_gauge"][criterion]
        assert gauge["factor"] >= grip["factor"] - 1e-9 and gauge["touches_grip"] is False and gauge["place"].endswith("from the nearer tab line")
        assert gauge["index"] == pytest.approx(1.0 / gauge["factor"]) and gauge["mode"] and 1 <= gauge["ply"] <= public_fields["mesh"]["plies"]
        assert gauge["element"] in public_fields["mesh"]["element_sets"]["Gauge"]


def test_the_gauge_section_is_read_a_quarter_width_from_each_tab_line(solved, data):
    """ADR-0108: the `Gauge` elements whose centroid is at least a quarter of the 25 mm width from the tab lines at 56 and 194 mm, none
    of them at a gripped node; the rest of the set is left out, and the fields say where the reading is and which elements it holds."""
    deck, solution = solved
    mesh = solution.mesh
    reading = gauge_reading(deck, solution)
    assert reading["fraction"] == GAUGE_STAND_OFF == 0.25 and reading["of"] == "width"
    assert reading["stand_off"] == pytest.approx(0.25 * 0.025) and reading["tab_lines"] == pytest.approx((0.056, 0.194)) and reading["width"] == pytest.approx(0.025)
    gauge = [mesh.element(key) for key in deck.elsets["Gauge"]]
    assert sorted(reading["elements"] + reading["near"]) == sorted(gauge) and reading["elements"] and reading["near"]
    y = mesh.xy[mesh.connectivity[:, :4]].mean(axis=1)[:, 1]
    lo, hi = reading["tab_lines"]
    assert all(lo + reading["stand_off"] - 1e-9 <= y[e] <= hi - reading["stand_off"] + 1e-9 for e in reading["elements"])
    assert all(y[e] < lo + reading["stand_off"] or y[e] > hi - reading["stand_off"] for e in reading["near"])
    assert gauge_elements(deck, solution) == reading["elements"]
    said = data["summary"]["gauge_reading"]
    assert said == {"stand_off": pytest.approx(6.25), "fraction": 0.25, "of": "width", "tab_lines": pytest.approx([56.0, 194.0]),
                    "elements": len(reading["elements"]), "left_out": len(reading["near"])}
    assert data["mesh"]["gauge_elements"] == reading["elements"]
    for criterion, found in data["summary"]["fpf_gauge"].items():
        assert found["element"] in reading["elements"] and found["near_tab"] is False, criterion
        assert min(found["xy"][1] - 56.0, 194.0 - found["xy"][1]) >= 6.25 - 1e-6


def test_the_fields_name_the_gauge_centre_element(solved, data):
    """ADR-0099 amendment 3: a question that names no place is answered at the gauge centre, so the fields name that element: the one
    the hand check and the Verification table read (`report.gauge_element`), inside the gauge section as it is read, at the coupon's
    middle in the fields' own length unit."""
    from anisotropy_fea.report import gauge_element

    deck, solution = solved
    centre = gauge_element(deck, solution)
    said = data["summary"]["gauge_centre"]
    assert said == {"element": centre.index, "label": centre.name, "xy": pytest.approx([1000.0 * v for v in centre.xy]), "basis": centre.basis}
    assert said["element"] in data["mesh"]["gauge_elements"] and data["mesh"]["element_labels"][said["element"]] == said["label"]
    assert said["xy"] == pytest.approx([12.5, 125.0], abs=2.0)  # the 25 by 250 mm coupon's middle, within an element


@pytest.mark.parametrize("fixture", ["studio", "studio-standards"])
def test_the_page_fixtures_hold_the_packages_gauge_centre(fixture, tmp_path):
    """`tests/fixtures/<fixture>/fields.json` is what the page's tests show; its gauge centre must be the package's answer to `values.json`
    today (rewrite it from `uv run python tools/studio_tool.py live ../tests/fixtures/<fixture>/values.json --out <dir>`, `fields.json`'s
    `summary.gauge_centre`)."""
    import json
    import subprocess
    import sys

    folder = paths.ROOT / "tests" / "fixtures" / fixture
    done = subprocess.run([sys.executable, str(paths.ROOT / "fea" / "tools" / "studio_tool.py"), "--root", str(tmp_path / "none"), "live",
                           str(folder / "values.json"), "--out", str(tmp_path / "out")], capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr
    today = json.loads((tmp_path / "out" / "fields.json").read_text(encoding="utf-8"))["summary"]["gauge_centre"]
    kept = json.loads((folder / "fields.json").read_text(encoding="utf-8"))["summary"]["gauge_centre"]
    assert today is not None and kept == {**today, "xy": pytest.approx(today["xy"])}


def test_a_gauge_shorter_than_the_width_is_read_over_its_middle_half():
    """ADR-0108: the stand-off is a quarter of the smaller of the width and the gauge length, so a gauge shorter than the coupon is wide
    is still read, over its middle half, and the reading says which length set it."""
    from anisotropy_fea.convergence import solve
    from anisotropy_fea.spec import load_spec

    base = load_spec(paths.FEA / "checks" / "compression-im7-8552" / "compression-im7-8552.toml")
    _, deck, solution = solve(base)
    reading = gauge_reading(deck, solution)  # 13 mm between the tabs of a 12 mm wide coupon: the width is the smaller
    assert reading["of"] == "width" and reading["stand_off"] == pytest.approx(0.003) and reading["elements"]
    wide = base.model_copy(update={"geometry": base.geometry.model_copy(update={"width": 0.020})})
    _, deck, solution = solve(wide)
    reading = gauge_reading(deck, solution)
    lo, hi = reading["tab_lines"]
    assert reading["of"] == "gauge length" and reading["stand_off"] == pytest.approx(0.25 * (hi - lo)) and hi - lo == pytest.approx(0.013)
    y = solution.mesh.xy[solution.mesh.connectivity[:, :4]].mean(axis=1)[:, 1]
    assert reading["elements"] and all(lo + 0.25 * (hi - lo) - 1e-9 <= y[e] <= hi - 0.25 * (hi - lo) + 1e-9 for e in reading["elements"])


def test_a_finer_mesh_moves_the_grip_edge_and_not_the_answer():
    """ADR-0108: with every element split in two the whole model's first failure, at the row beside a grip, comes 12 % earlier; it is
    the answer's `outside_earlier`, and the gauge section's answer is the coarse mesh's to three figures. The sentences say where the
    gauge section is read."""
    from anisotropy_fea.convergence import refined, solve
    from anisotropy_fea.spec import load_spec

    spec = load_spec(paths.spec_path("unnotched-im7-8552-nodal"))
    answers = []
    for factor in (1, 2):
        _, deck, solution = solve(refined(spec, factor))
        data = field_data(deck, solution, UNITS)
        summary = data["summary"]
        verdict, whole = summary["verdict"], summary["fpf"][summary["earliest"]]
        outside = verdict["outside_earlier"]
        assert verdict["basis"] == "gauge" and outside["factor"] == whole["factor"] < verdict["factor"]
        assert outside["touches_grip"] is True and outside["near_tab"] is False and outside["element"] not in data["mesh"]["gauge_elements"]
        answers.append((summary["fpf_gauge"]["tsai_hill"]["factor"], whole["factor"]))
        first = summary["fpf_gauge"][verdict["earliest"]]  # a list of past runs shows the verdict's own values, picked (ADR-0109)
        assert run_answer(summary) == {"basis": "gauge", "criterion": verdict["earliest"], "fails": verdict["fails"], "factor": verdict["factor"],
                                       "ply": first["ply"], "angle": first["angle"], "face": first["face"]}
        sentences = " ".join(result_sentences(fact_sheet(summary, data["coupon"], data["units"], data["labels"])))
        assert "reported apart from the answer" in sentences
        assert "The gauge section is read at least 6.25 mm from each tab line, a quarter of the width, the same distance on every mesh." in sentences
    facts = fact_sheet(summary, data["coupon"], data["units"], data["labels"])
    facts.update(outside_touches_grip=False, outside_near_tab=True)  # the same failure, had it sat one row further in
    assert "inside the stand-off from a tab line, where the corner of the grip sets the stress" in " ".join(result_sentences(facts))
    (gauge_coarse, whole_coarse), (gauge_fine, whole_fine) = answers
    assert gauge_fine == pytest.approx(gauge_coarse, rel=1e-3) and whole_fine < 0.9 * whole_coarse
    assert run_answer({**summary, "verdict": None}) is None  # no criterion, no answer to list


def test_a_failure_inside_the_stand_off_is_marked_and_said_apart():
    """ADR-0108: a first failure of the whole model that sits inside the stand-off without touching a gripped node is `near_tab`; the
    verdict carries the mark and the sentence says why it is not the answer."""
    from anisotropy_fea.fields import verdict_of

    row = {"index": 1.0, "element": 7, "label": "Strip-1.8", "ply": 4, "angle": 90.0, "face": None, "mode": "transverse tension", "tied_plies": [4, 5], "xy": [1.0, 58.0]}
    whole = {"tsai_hill": {**row, "factor": 0.93, "place": "2 mm from the nearer tab line", "touches_grip": False, "near_tab": True}}
    gauge = {"tsai_hill": {**row, "factor": 1.03, "element": 90, "label": "Strip-1.91", "place": "13 mm from the nearer tab line", "touches_grip": False, "near_tab": False}}
    verdict = verdict_of(whole, gauge)
    assert verdict["fails"] is False and verdict["factor"] == 1.03
    assert verdict["outside_earlier"]["near_tab"] is True and verdict["outside_earlier"]["touches_grip"] is False and verdict["outside_earlier"]["factor"] == 0.93
    older = {"tsai_hill": {k: v for k, v in whole["tsai_hill"].items() if k != "near_tab"}}  # a result written before ADR-0108
    assert verdict_of(older, gauge)["outside_earlier"]["near_tab"] is False


def test_every_ply_has_its_own_peaks_and_the_clamped_edge_is_marked(solved, data):
    # ADR-0066: one entry per ply, each component's largest magnitude over the elements, the element named, the grip row marked
    deck, solution = solved
    summary = data["summary"]
    stress = np.asarray(data["element"]["ply"]["stress_12"])  # (ne, plies, 3)
    peaks = summary["ply_peaks"]
    assert [p["ply"] for p in peaks] == list(range(1, stress.shape[1] + 1)) and [p["angle"] for p in peaks] == [45.0, 0.0, -45.0, 90.0, 90.0, -45.0, 0.0, 45.0]
    for k, p in enumerate(peaks):
        for i, name in enumerate(("S11", "S22", "S12")):
            e = p[name]["element"]
            assert abs(p[name]["value"]) == pytest.approx(np.abs(stress[:, k, i]).max()) and p[name]["value"] == pytest.approx(stress[e, k, i])
            assert p[name]["label"] == f"Coupon-1.{solution.mesh.element_keys[e][1]}" and p[name]["face"] is None
    fibre = peaks[1]["S11"]  # the stated 0-degree ply carries the largest fibre stress, at the tab line (ADR-0065)
    assert fibre["value"] == pytest.approx(summary["max_ply"]["S11"]["value"]) and fibre["element"] == summary["max_ply"]["S11"]["element"] and fibre["touches_grip"] is True
    assert peaks[3]["S11"]["touches_grip"] is False  # the 90-degree ply's largest |sigma_1| is a compression in the gauge section


def test_classical_laminate_theory_sits_beside_the_gauge_centre(solved, data):
    # ADR-0066: N_y = reaction / width, N_x = N_xy = 0, each ply at its middle; on a straight coupon it equals the kernel's gauge-centre element
    from anisotropy_fea.fields import classical_laminate_check

    deck, solution = solved
    summary = data["summary"]
    clt = summary["clt"]
    assert clt["width"] == pytest.approx(25.0) and clt["Ny"] == pytest.approx(summary["reaction"]["value"] / 25.0)
    assert clt["strain"][1] > 0 > clt["strain"][0] and abs(clt["strain"][2]) < 1e-12  # a quasi-isotropic laminate under a pull: no shear coupling
    centre = solution.mesh.element(deck.elsets["Probe-centre"][0])
    stress = np.asarray(data["element"]["ply"]["stress_12"])[centre]  # (plies, 3), MPa
    assert [p["ply"] for p in clt["plies"]] == list(range(1, 9)) and clt["plies"][1]["angle"] == 0.0
    for p in clt["plies"]:
        assert np.allclose(p["stress_12"], stress[p["ply"] - 1], rtol=1e-3, atol=0.5)
    assert clt["plies"][1]["stress_12"][0] == pytest.approx(1180.76, abs=0.05)  # the fibre stress of the 0-degree ply, as the public record's CalculiX value within 0.01 %
    # another loading (a plate's pressure, a bending coupon's push) has no laminate-theory column
    applied = applied_loading(deck, solution)
    assert classical_laminate_check(solution, {**applied, "dof": 3}, 1.0, np.zeros(8), UNITS) is None
    assert classical_laminate_check(solution, {**applied, "set": "the supports"}, 1.0, np.zeros(8), UNITS) is None


# --- the answer (ADR-0085) ----------------------------------------------------------------------------


def test_each_criterion_says_whether_a_ply_fails_and_at_what_loading(data):
    """R at or below 1 fails; the loading at first-ply failure is R times the applied pull, and R times the grip's reaction."""
    summary = data["summary"]
    for table in (summary["fpf"], summary["fpf_gauge"]):
        assert table, "the public coupon has criteria and a gauge section"
        for entry in table.values():
            at = entry["at_failure"]
            assert entry["fails"] == (entry["factor"] <= 1.0)
            assert at["applied"] == pytest.approx(entry["factor"] * summary["applied"]["value"], rel=1e-12) and at["unit"] == "mm"
            assert at["reaction"] == pytest.approx(entry["factor"] * summary["reaction"]["value"], rel=1e-12) and at["reaction_unit"] == "N"
            assert at["every_load"] is False


def test_the_answer_reads_the_gauge_section_and_reports_the_grip_edge_apart(data):
    summary = data["summary"]
    verdict = summary["verdict"]
    assert verdict["basis"] == "gauge" and verdict["earliest"] == summary["earliest_gauge"]
    assert verdict["factor"] == summary["fpf_gauge"][verdict["earliest"]]["factor"] and verdict["fails"] == (verdict["factor"] <= 1.0)
    whole = summary["fpf"][summary["earliest"]]
    outside = verdict["outside_earlier"]
    if whole["factor"] < verdict["factor"]:
        assert outside["criterion"] == summary["earliest"] and outside["factor"] == whole["factor"]
        assert outside["touches_grip"] is True or outside["near_tab"] is True  # at the grip or inside the stand-off (ADR-0108)
        assert outside["element"] not in data["mesh"]["gauge_elements"]
    else:
        assert outside is None


def test_the_largest_ply_stresses_come_with_their_sign_and_place(data):
    """Over the gauge elements, each ply's sigma_1 and sigma_2 at their largest tension and compression apart, tau_12 at its largest
    magnitude, each the element's own value; and over every ply, the largest of them with its ply."""
    summary = data["summary"]
    extremes = summary["ply_extremes"]
    assert extremes["basis"] == "gauge"
    stress = np.asarray(data["element"]["ply"]["stress_12"])  # (ne, plies, 3), mm-MPa
    inside = sorted({e["element"] for p in extremes["plies"] for name in ("S11", "S22", "S12") for e in p[name].values() if e})
    gauge = set(data["mesh"]["element_sets"]["Gauge"])
    assert set(inside) <= gauge, "every extreme lies in the gauge section"
    for k, p in enumerate(extremes["plies"]):
        assert p["ply"] == k + 1
        for i, name in enumerate(("S11", "S22")):
            for pick, sign in (("tension", 1.0), ("compression", -1.0)):
                e = p[name][pick]
                if e is None:
                    continue
                assert sign * e["value"] > 0.0 and e["value"] == pytest.approx(stress[e["element"], k, i], rel=1e-6, abs=1e-6)  # the arrays are written rounded
        shear = p["S12"]["largest"]
        assert abs(shear["value"]) == pytest.approx(abs(stress[shear["element"], k, 2]), rel=1e-6, abs=1e-6)
    overall = extremes["overall"]["S11"]["tension"]
    assert overall["value"] == max(p["S11"]["tension"]["value"] for p in extremes["plies"] if p["S11"]["tension"])
    assert overall["ply"] == next(p["ply"] for p in extremes["plies"] if p["S11"]["tension"] and p["S11"]["tension"]["value"] == overall["value"])


def test_a_coupon_without_a_gauge_section_answers_on_the_whole_model():
    """A bending coupon has no grips and no gauge set: the answer is the whole model's, on the plate-like kernel (ADR-0053)."""
    from anisotropy_fea.kernel import solve_deck
    deck = read_deck(paths.deck_path(paths.spec_path("three-point-im7-8552"), "abaqus"), UNITS)
    summary = field_data(deck, solve_deck(deck), UNITS)["summary"]
    assert summary["fpf_gauge"] == {} and summary["verdict"]["basis"] == "whole" and summary["verdict"]["outside_earlier"] is None
    assert summary["verdict"]["earliest"] == summary["earliest"] and summary["ply_extremes"]["basis"] == "whole"
    for entry in summary["fpf"].values():
        assert entry["at_failure"]["applied"] == pytest.approx(entry["factor"] * summary["applied"]["value"], rel=1e-12)
    facts = fact_sheet(summary, {"designation": "IM7-3PB-L1", "test": "three-point bending", "layup": ""}, UNITS, UNIT_LABEL[UNITS])
    assert facts["basis"] == "the whole model" and any("in the whole model" in s for s in result_sentences(facts))


def test_each_ply_carries_what_abaqus_prints_beside_mises(solved, data):
    """ADR-0066 amendment 2: Tresca, the three principal stresses and the pressure, per element and ply, with their per-ply ranges and no
    display averages; the same numbers as `ply_invariants` on the solution, in the fields' units."""
    from anisotropy_fea.recovery import INVARIANTS, element_ply_states, ply_invariants

    deck, solution = solved
    written = data["element"]["ply"]["invariants"]
    assert tuple(written) == INVARIANTS
    ne, plies = len(data["element"]["ply"]["mises"]), len(data["element"]["ply"]["mises"][0])
    expected = ply_invariants(element_ply_states(solution))
    for name in INVARIANTS:
        values = np.array(written[name])
        assert values.shape == (ne, plies), name
        assert np.allclose(values, np.stack(expected[name]) / 1e6, rtol=1e-6, atol=1e-6), name  # Pa to MPa, as the fields are written
        assert set(data["ranges"][name]) == {"element"}, "element values only: no display averages for these"
        assert name not in data["nodal"]["averages"]
    tresca, mises = np.array(written["tresca"]), np.array(data["element"]["ply"]["mises"])
    assert np.all(tresca >= mises - 1e-6)  # Tresca is never below Mises
