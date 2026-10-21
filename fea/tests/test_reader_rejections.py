"""Everything outside the supported subset is refused with the line number, never skipped (ADR-0003)."""

from pathlib import Path

import pytest

from anisotropy_fea.abaqus_reader import DeckError, parse_deck, read_deck
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECKS = paths.CHECK_DECKS
ONE = (DECKS / "coupon-1x1-im7-8552.inp").read_text(encoding="utf-8")
GRIPS = (DECKS / "coupon-2x8-grips-im7-8552.inp").read_text(encoding="utf-8")

TOP_FIX_ROTATIONS = "Set-TopFix, 4, 4\nSet-TopFix, 5, 5\nSet-TopFix, 6, 6\n"

CASES = [
    # (base text, text to replace, replacement, expected message fragment)
    ("one", "type=S4R", "type=S8R", "element type 'S8R' is not supported"),
    ("one", "nlgeom=NO", "nlgeom=YES", "nlgeom=YES"),
    ("one", "*Instance, name=Coupon-1, part=Coupon\n", "*Instance, name=Coupon-1, part=Coupon\n5., 0., 0.\n", "translated or rotated instance"),
    ("one", "1., 0., 0., 0., 1., 0.", "0., 1., 0., -1., 0., 0.", "not the global axes"),
    ("one", "3, 0.\n*Shell", "3, 30.\n*Shell", "not the global axes"),
    ("one", "layup=Layup-1, symmetric", "layup=Layup-1, symmetric, offset=0.5", "offset=0.5 is not supported"),
    ("one", "*End Step\n", "*End Step\n*Step, name=Step-2\n*Static\n*End Step\n", "second \\*Step"),
    ("one", "*Fail Stress\n2558.51", "*Density\n1.6e-9\n*Fail Stress\n2558.51", "\\*density is not supported by anisotropy_fea"),
    ("one", "*Part, name=Coupon\n*Node\n", "*Part, name=Coupon\n*Node, nset=Nall\n", "parameter 'nset' is not supported"),
    ("one", "4688.43, 3000.", "4688.43, 3000., 20.", "seventh value would be a temperature"),
    ("one", "*Elastic, type=LAMINA", "*Elastic, type=ENGINEERING CONSTANTS", "type 'ENGINEERING CONSTANTS' is not supported"),
    ("one", "Top, 2, 2, 0.8", "Top, 6, 6, 0.1", "nonzero prescribed rotation"),
    ("one", "Top, 2, 2, 0.8", "Top, 3, 3, 0.1", "nonzero out-of-plane displacement"),
    ("one", "*Boundary\nTop", "*Boundary, amplitude=Amp-1\nTop", "parameter 'amplitude' is not supported"),
    ("one", "1, 0., 0., 0.\n2, 10.", "1, 0., 0., 1.\n2, 10.", "z coordinates are not all zero"),
    ("one", "Top, 2, 2, 0.8", "Topp, 2, 2, 0.8", "node set 'Topp' is not defined in the assembly"),
    ("one", "*Elset, elset=All, generate\n1, 1, 1", "*Elset, elset=All, generate\n1, 0, 1", "have no shell section"),
    ("one", "*Restart", "*Cload\nTop, 3, 5.\n*Restart", "dofs 1 and 2 only"),
    ("one", "*Static\n", "*Static, riks\n", "\\*Static parameters"),
    ("one", "*Shell Section, elset=All, composite", "*Shell General Section, elset=All, composite", "\\*shell general section is not supported"),
    ("one", "*End Part", "*Shell Section, elset=All, material=IM7-8552\n1.\n*End Part", "is in two shell sections"),
    ("one", "*Fail Stress\n2558.51", "*Fail Stress\n2558.51, 1.\n2558.51", "\\*Fail Stress takes one line"),
    ("one", "*Boundary\nCorner, 1, 1", "*Boundary\nCorner, 2, 2, 0.5", "dof 2 is prescribed 0.5 here and 0.0 at line"),
    ("grips", "*Kinematic\n** Constraint: Grip-Bottom", "*Kinematic\n1, 1\n** Constraint: Grip-Bottom", "leaves an in-plane dof free"),
    ("grips", TOP_FIX_ROTATIONS, "", "rotation dofs \\[4, 5, 6\\] free"),
    ("grips", "*Kinematic\n** Constraint: Grip-Bottom", "*Distributing\n** Constraint: Grip-Bottom", "only \\*Kinematic couplings"),
    ("grips", "Set-Encastre, ENCASTRE", "Set-Encastre, XASYMM", "boundary type XASYMM is not supported"),
    ("grips", "s_Top, 1.\n", "s_Top, 0.5\n", "weights other than 1"),
    ("grips", "*Coupling, constraint name=Grip-Top", "*Coupling, influence radius=2., constraint name=Grip-Top", "influence radius"),
    ("grips", "*Nset, nset=s_Top, instance=CFRP-Coupon-1\n 25, 26, 27", "*Nset, nset=s_Top, instance=CFRP-Coupon-1\n 25, 26, 99", "names node CFRP-Coupon-1.99, which does not exist"),
]


@pytest.mark.parametrize("base, old, new, message", CASES, ids=[case[3][:40] for case in CASES])
def test_unsupported_or_inconsistent_decks_are_refused(tmp_path, base, old, new, message):
    text = ONE if base == "one" else GRIPS
    assert old in text, f"the fixture no longer contains {old!r}"
    deck = tmp_path / "deck.inp"
    deck.write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(DeckError, match=message):
        read_deck(deck, "mm-MPa")


def test_every_refusal_names_a_line_number(tmp_path):
    for base, old, new, _ in CASES:
        text = (ONE if base == "one" else GRIPS).replace(old, new, 1)
        deck = tmp_path / "deck.inp"
        deck.write_text(text, encoding="utf-8")
        with pytest.raises(DeckError) as excinfo:
            read_deck(deck, "mm-MPa")
        text = str(excinfo.value)
        assert text.startswith(("line ", "part ")) or " names " in text, text


def test_units_must_be_stated():
    with pytest.raises(ValueError, match="units must be stated"):
        read_deck(DECKS / "coupon-1x1-im7-8552.inp", None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="units must be stated"):
        read_deck(DECKS / "coupon-1x1-im7-8552.inp", "in-psi")


def test_an_unfinished_deck_is_refused():
    with pytest.raises(DeckError, match="has no \\*End Part"):
        parse_deck("*Part, name=P\n*Node\n1, 0., 0.\n")
    with pytest.raises(DeckError, match="has no \\*End Step"):
        parse_deck("*Step\n*Static\n")
    with pytest.raises(DeckError, match="has no \\*Static procedure"):
        parse_deck("*Step\n*End Step\n")
    with pytest.raises(DeckError, match="must be followed by \\*Kinematic"):
        parse_deck("*Assembly\n*Coupling, constraint name=C, ref node=R, surface=S\n*Boundary\nR, 1, 1\n*End Assembly\n")
