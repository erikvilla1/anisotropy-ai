"""The team's own deck of the tension coupon, when it is present locally, against our local model of the same coupon (ADR-0035).
Both stay on the founder's machine (ADR-0042): the deck is found by its place, `.local/fea/<coupon>/from-team/<date>/`, and every
expected count is read from our model rather than written here, so this file names none of the team's numbers and prints no
material values (ADR-0029, AGENTS.md)."""

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.femodel import build_model
from anisotropy_fea.model import coupled_nodes, reference_node
from anisotropy_fea.spec import load_spec

COUPON = "X840PW-UNT-L1"
LOCAL_DECK = paths.team_deck(COUPON)
OURS = paths.local_test(COUPON) / f"{COUPON}.toml"

pytestmark = pytest.mark.skipif(LOCAL_DECK is None or not OURS.is_file(),
                                reason=f"the team's deck and our model of {COUPON} are not on this machine (.local/fea/{COUPON}/, ADR-0042)")


def test_the_team_coupon_deck_is_read_in_full_and_is_our_coupon():
    deck = read_deck(LOCAL_DECK, "mm-MPa")
    spec = load_spec(OURS)  # SI
    mesh = build_model(spec).mesh
    (part,) = deck.parts.values()
    assert len(part.nodes) == mesh.node_count and len(part.elements) == mesh.element_count and part.elements.element_type == "S4R"
    assert len(deck.assembly_nodes) == 2
    (section,) = part.sections
    assert section.symmetric and len(section.layers) == len(spec.layup.angles)
    assert len(deck.couplings) == 2
    assert {entry.split(": ")[1] for entry in deck.ignored_keywords} == {"*preprint", "*restart", "*output"}
    (step,) = deck.steps
    (pull,) = [b for b in step.boundaries if b.value != 0]
    assert (pull.dof_first, pull.value) == (2, pytest.approx(spec.loading.value))  # the same pull, in SI
    assert len(deck.notes) == 1 and "dropped" in deck.notes[0]
    for coupling in deck.couplings:
        assert reference_node(deck, coupling) not in coupled_nodes(deck, coupling)
        assert len(coupled_nodes(deck, coupling)) > 0
    assert deck.units == "mm-MPa"


def test_the_team_coupon_deck_solves_in_equilibrium():
    from anisotropy_fea.membrane import solve_membrane

    deck = read_deck(LOCAL_DECK, "mm-MPa")
    pull = load_spec(OURS).loading.value
    solution = solve_membrane(deck)
    top, bottom = solution.reaction_of([(None, 1)]), solution.reaction_of([(None, 2)])
    assert top[1] > 0 and top == pytest.approx(-bottom, abs=1e-9 * top[1])
    assert solution.total_reaction == pytest.approx([0.0, 0.0], abs=1e-9 * top[1])
    assert solution.free_residual < 1e-9 * top[1]
    assert solution.displacement_of((None, 1)) == pytest.approx([0.0, pull])
    assert solution.displacement_of((None, 2)) == pytest.approx([0.0, 0.0])
    assert solution.strain[:, 1].max() > 0.0  # the numbers themselves stay in the local note, not here


LOCAL_RECORD = paths.local_test(COUPON) / paths.COMPARISON / "tension-test-abaqus.toml"


@pytest.mark.skipif(not LOCAL_RECORD.exists(), reason=f"the local record of the team's Abaqus field reports is not on this machine (.local/fea/{COUPON}/comparison/)")
def test_the_kernel_reproduces_the_teams_abaqus_field_reports():
    """The team's Abaqus/CAE field reports (S11, S22, Mises at the outer plies) at gauge elements, within the record's tolerance;
    the numbers stay in the local record and note (ADR-0030, amendment 2)."""
    from anisotropy_fea.compare import compare_record, load_record, record_disagreements

    record = load_record(LOCAL_RECORD)
    assert record["solver"]["name"] == "abaqus" and record["solver"]["source"] == "csv"
    comparisons, problems = compare_record(record)
    assert not problems and len(comparisons) >= 24
    assert record_disagreements(record) == []


def test_our_coupling_deck_is_the_teams_model():
    """Our generated twin, seeded as the team seeded it, is the same model item by item (ADR-0035)."""
    from anisotropy_fea.equivalence import deck_equivalence

    team = read_deck(LOCAL_DECK, "mm-MPa")
    ours = paths.deck_path(OURS, "abaqus")
    eq = deck_equivalence(team, read_deck(ours, "mm-MPa"), 1e-8, "mm-MPa")
    assert eq.same_model, [(i.item, i.team, i.ours) for i in eq.differences]
    (part,) = team.parts.values()
    assert len(eq.element_map) == len(part.elements) and eq.largest_node_offset < 1e-8
