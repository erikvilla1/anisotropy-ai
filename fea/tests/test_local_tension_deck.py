"""The team's own coupon deck, when it is present locally. Its material may be proprietary, so the file lives in `.local/abaqus/`,
is never committed, and this test prints no material values (ADR-0029, AGENTS.md)."""

from pathlib import Path

import pytest

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.model import coupled_nodes, reference_node

LOCAL_DECK = Path(__file__).parents[2] / ".local" / "abaqus" / "Tension-test.inp"

pytestmark = pytest.mark.skipif(not LOCAL_DECK.exists(), reason="team deck not present at .local/abaqus/Tension-test.inp")


def test_the_team_coupon_deck_is_read_in_full():
    deck = read_deck(LOCAL_DECK, "mm-MPa")
    (part,) = deck.parts.values()
    assert len(part.nodes) == 891 and len(part.elements) == 800 and part.elements.element_type == "S4R"
    assert len(deck.assembly_nodes) == 2
    (section,) = part.sections
    assert section.symmetric and len(section.layers) == 5
    assert len(deck.couplings) == 2
    assert {entry.split(": ")[1] for entry in deck.ignored_keywords} == {"*preprint", "*restart", "*output"}
    (step,) = deck.steps
    (pull,) = [b for b in step.boundaries if b.value != 0]
    assert (pull.dof_first, pull.value) == (2, pytest.approx(0.010))  # 10 mm in SI
    assert len(deck.notes) == 1 and "dropped" in deck.notes[0]
    for coupling in deck.couplings:
        assert reference_node(deck, coupling) not in coupled_nodes(deck, coupling)
        assert len(coupled_nodes(deck, coupling)) > 0
    assert deck.units == "mm-MPa"


def test_the_team_coupon_deck_solves_in_equilibrium():
    from anisotropy_fea.membrane import solve_membrane

    deck = read_deck(LOCAL_DECK, "mm-MPa")
    solution = solve_membrane(deck)
    top, bottom = solution.reaction_of([(None, 1)]), solution.reaction_of([(None, 2)])
    assert top[1] > 0 and top == pytest.approx(-bottom, abs=1e-9 * top[1])
    assert solution.total_reaction == pytest.approx([0.0, 0.0], abs=1e-9 * top[1])
    assert solution.free_residual < 1e-9 * top[1]
    assert solution.displacement_of((None, 1)) == pytest.approx([0.0, 0.010])
    assert solution.displacement_of((None, 2)) == pytest.approx([0.0, 0.0])
    assert solution.strain[:, 1].max() > 0.0  # the numbers themselves stay in the local note, not here
