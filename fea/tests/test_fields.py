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
from anisotropy_fea.fields import MODES, applied_loading, field_data, nodal_averages, per_ply_spans, rounded, span
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
    node = int(corners[0, 2])  # a corner shared by several elements
    sharing = [e for e in range(mesh.element_count) if node in corners[e]]
    assert len(sharing) == 4 and np.allclose(averages[node], solution.strain[sharing].mean(axis=0), rtol=1e-8)
    assert "display averages" in data["nodal"]["averages_note"]
    one = nodal_averages(np.array([[0, 1, 2, 3]]), 5, np.array([[1.0, 2.0]]))
    assert one[0].tolist() == [1.0, 2.0] and np.isnan(one[4]).all()  # a node no element touches
    assert rounded(one)[4] == [None, None] and rounded(np.array([1.23456789012345])) == [1.23456789]


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
    strain = np.asarray(data["element"]["strain"], dtype=float)
    assert ranges["eps_y"]["element"] == [strain[:, 1].min(), strain[:, 1].max()]
    averages = np.asarray(data["nodal"]["averages"]["strain"], dtype=float)
    assert ranges["eps_y"]["nodal"] == [np.nanmin(averages[:, 1]), np.nanmax(averages[:, 1])]
    magnitude = np.asarray(data["nodal"]["magnitude"], dtype=float)
    assert ranges["u_mag"]["nodal"] == [magnitude.min(), magnitude.max()]
    assert "u_z" not in ranges and "M_y" not in ranges and "theta_x" not in ranges  # a membrane solve
    stress = np.asarray(data["element"]["ply"]["stress_12"], dtype=float)  # (elements, plies, 3)
    assert len(ranges["S11"]["element"]) == 8 and ranges["S22"]["element"][2] == [stress[:, 2, 1].min(), stress[:, 2, 1].max()]
    stress_averages = np.asarray(data["nodal"]["averages"]["ply_stress_12"], dtype=float)
    assert ranges["S12"]["nodal"][5] == [np.nanmin(stress_averages[:, 5, 2]), np.nanmax(stress_averages[:, 5, 2])]
    mises = np.asarray(data["element"]["ply"]["mises"], dtype=float)
    assert ranges["mises"]["element"][0] == [mises[:, 0].min(), mises[:, 0].max()]
    index = np.asarray(data["element"]["failure"]["tsai_hill"]["element_index"], dtype=float)
    assert ranges["failure_index"]["tsai_hill"]["element"] == [index.min(), index.max()]
    assert ranges["failure_index"]["tsai_hill"]["element"][1] == pytest.approx(data["summary"]["fpf"]["tsai_hill"]["index"])
    per_ply = np.asarray(data["element"]["failure"]["tsai_hill"]["index"], dtype=float)  # (elements, plies)
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
        assert outside["criterion"] == summary["earliest"] and outside["factor"] == whole["factor"] and outside["touches_grip"] is True
        assert outside["element"] not in data["mesh"]["element_sets"]["Gauge"] or outside["touches_grip"]
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
