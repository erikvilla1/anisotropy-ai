"""The viewer's fields (ADR-0051): every array is the solution in the deck's units, the display averages are the means over the
elements sharing a node, the summary's extremes are the arrays' extremes, the first-ply failure is `strength_ratios`', and the
explanation's sentences quote the facts and nothing else. On the public IM7/8552 check decks, nothing under .local/."""

import json

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.explain import MODE_WORDS, explanation, fact_sheet, numbers_in, result_sentences, setup_sentences
from anisotropy_fea.fields import MODES, applied_loading, field_data, nodal_averages, rounded
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
    assert summary["applied"] == {"control": "displacement", "value": pytest.approx(1.0), "unit": "mm"}
    assert applied_loading(deck, solution) == ("displacement", pytest.approx(1e-3))
    assert summary["reaction"]["sense"] == "tension" and summary["reaction"]["value"] > 0
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
    for sentence in sentences:
        for token in numbers_in(sentence):
            assert token in printed or token.lstrip("-+") in printed, (token, sentence)
    assert sentences[0].startswith("IM7-UNT-L1, unnotched tension, under a displacement of 1 mm: the top grip carries")
    assert "The largest displacement is" in sentences[1] and "S11 =" in sentences[2] and "von Mises" in sentences[2]
    assert any("criterion at the applied loading" in s for s in sentences) and sentences[-1].startswith("The earliest of the criteria is")
    assert any(MODE_WORDS[facts[f"{c}_mode"]] in s for c in facts["criteria"] for s in sentences)


def test_the_limiting_ply_is_named_with_its_place_and_mode(data):
    facts = fact_sheet(data["summary"], data["coupon"], UNITS, data["labels"])
    earliest = facts["earliest"]
    sentence = next(s for s in result_sentences(facts) if f"the {facts[earliest + '_mode']}" in s or MODE_WORDS[facts[earliest + "_mode"]] in s)
    assert f"ply {facts[earliest + '_ply']} ({facts[earliest + '_angle']:.4g} degrees)" in sentence and facts[earliest + "_place"] in sentence
    assert ("does not exceed" in sentence) == (facts[earliest + "_factor"] >= 1.0)


def test_without_criteria_the_explanation_says_so(solved):
    deck, solution = solved
    none = field_data(deck, solution, UNITS, criteria=())
    out = explanation(none["summary"], {}, UNITS, none["labels"])
    assert out["writer"] == "template" and out["sentences"][-1] == "No failure criterion was asked for, so first-ply failure is not reported."
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
