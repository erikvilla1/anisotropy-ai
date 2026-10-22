"""Converting a read Abaqus-dialect deck to CalculiX: mesh promotion, couplings as direct constraints, material and section rewrite (ADR-0030)."""

from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.calculix import find_ccx, parse_dat, run_calculix
from anisotropy_fea.convert_deck import TransverseChoice, calculix_from_deck, promote_to_order2
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.mesh import mesh_from_deck
from anisotropy_fea.write_calculix import CalculixWriterError
from anisotropy_fea import paths  # where the files live (ADR-0036)

DECKS = paths.CHECK_DECKS
GRIPS = DECKS / "coupon-2x8-grips-im7-8552.inp"
LOCAL_DECK = paths.local_test("X840PW-UNT-L1") / paths.TEAM_FILES / "2026-10-16" / "Tension-test.inp"
needs_ccx = pytest.mark.skipif(find_ccx() is None, reason="CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)")
TRANSVERSE = TransverseChoice(nu23=0.45)


def test_promotion_adds_one_midside_node_per_edge_and_extends_sets_along_edges():
    mesh = mesh_from_deck(read_deck(GRIPS, "mm-MPa"))
    promoted = promote_to_order2(mesh, {"bottom": np.array([0, 1, 2]), "corner": np.array([0])})
    assert promoted.xy.shape[0] == 29 + 42  # 2 by 8 grid: 18 horizontal and 24 vertical unique edges; the two reference nodes are already in the mesh
    assert promoted.connectivity.shape == (16, 8)
    for e, nodes in enumerate(promoted.connectivity):
        for k in range(4):
            assert promoted.xy[nodes[4 + k]] == pytest.approx((promoted.xy[nodes[k]] + promoted.xy[nodes[(k + 1) % 4]]) / 2)
    assert promoted.node_sets["bottom"].size == 5 and promoted.node_sets["corner"].size == 1


def test_the_converted_deck_rewrites_what_calculix_needs():
    deck = read_deck(GRIPS, "mm-MPa")
    text = calculix_from_deck(deck, TRANSVERSE)
    assert "*ELEMENT, TYPE=S8R, ELSET=All" in text and text.count("\n16, ") >= 1
    assert "*NSET, NSET=Coupled-Grip-Top\n" in text and "*NSET, NSET=Coupled-Grip-Bottom\n" in text
    assert "*ELASTIC, TYPE=ENGINEERING CONSTANTS\n162095.74, 8963.18, 8963.18, 0.316, 0.316, 0.45, 4688.43, 4688.43\n3000., 293." in text
    section = text[text.index("*SHELL SECTION"):text.index("*BOUNDARY")]
    assert section.count("0.18288, , IM7-8552, Ori-") == 10 and "COMPOSITE" in section
    fixed = text[text.index("*BOUNDARY"):text.index("*STEP")]
    for dof in range(1, 7):  # ENCASTRE on the bottom reference node, expanded by the reader, lands on the coupled set
        assert f"\nCoupled-Grip-Bottom, {dof}, {dof}\n" in fixed
    for dof in (1, 3, 4, 5, 6):
        assert f"\nCoupled-Grip-Top, {dof}, {dof}\n" in fixed
    assert "*STEP\n*STATIC\n*BOUNDARY\nCoupled-Grip-Top, 2, 2, 0.8\n" in text
    assert "*NODE PRINT, NSET=Coupled-Grip-Top, TOTALS=YES\nRF" in text and "*NODE PRINT, NSET=Nall\nU" in text
    assert "Assembly" not in text.split("*NODE, NSET=Nall")[1].split("*ELEMENT")[0]  # reference nodes are not carried over
    assert "transverse isotropy, stated by the caller" in text and "nu23 = 0.45 given by the caller" in text
    assert "replaced by direct constraints on its 5 coupled nodes" in text  # 3 corner nodes of the edge plus the 2 midside nodes between them
    assert text == calculix_from_deck(deck, TRANSVERSE)


def test_the_out_of_plane_choice_is_explicit():
    deck = read_deck(GRIPS, "mm-MPa")
    with pytest.raises(CalculixWriterError, match="E3 and nu13 must be given"):
        calculix_from_deck(deck, TransverseChoice(nu23=0.45, transverse_isotropy=False))
    with pytest.raises(CalculixWriterError, match="do not give them"):
        calculix_from_deck(deck, TransverseChoice(nu23=0.45, transverse_isotropy=True, E3=9e9, nu13=0.3))
    explicit = calculix_from_deck(deck, TransverseChoice(nu23=0.4, transverse_isotropy=False, E3=9000e6, nu13=0.3))
    assert "162095.74, 8963.18, 9000., 0.316, 0.3, 0.4, 4688.43, 4688.43" in explicit


@needs_ccx
def test_the_converted_fixture_runs_and_agrees_with_the_kernel(tmp_path):
    deck = read_deck(GRIPS, "mm-MPa")
    mesh = mesh_from_deck(deck)
    path = tmp_path / "grips.inp"
    path.write_text(calculix_from_deck(deck, TRANSVERSE, probe_elements=[mesh.element_keys[8]]), encoding="utf-8")
    result = run_calculix(path, workdir=tmp_path)
    assert result.errors == () and result.warnings == ()
    dat = parse_dat(result.dat_text)
    solution = solve_membrane(deck)
    top = dat.total_force("Coupled-Grip-Top")
    ours = solution.reaction_of([(None, 1)])
    assert top[1] == pytest.approx(ours[1], rel=0.02)  # 4640.6 against 4705.3 N: S8R against Q4 on a 2 by 8 mesh
    assert np.allclose(top, -dat.total_force("Coupled-Grip-Bottom"), atol=1e-6 * abs(top[1]))
    strains = dat.strains("Probe").values[:, [0, 1, 3]].mean(axis=0)
    assert strains[1] == pytest.approx(solution.strain[8][1], rel=0.01)
    assert dat.displacements("Nall").values[:, 1].max() == pytest.approx(0.8, abs=1e-9)


@needs_ccx
@pytest.mark.skipif(not LOCAL_DECK.exists(), reason="team deck not present at .local/fea/X840PW-UNT-L1/from-team/2026-10-16/Tension-test.inp")
def test_the_team_coupon_converts_runs_and_agrees_with_the_kernel(tmp_path):
    deck = read_deck(LOCAL_DECK, "mm-MPa")
    path = tmp_path / "tension.inp"
    path.write_text(calculix_from_deck(deck, TRANSVERSE), encoding="utf-8")
    dat = parse_dat(run_calculix(path, workdir=tmp_path).dat_text)
    solution = solve_membrane(deck)
    top = dat.total_force("Coupled-Constraint-1")
    assert top[1] == pytest.approx(solution.reaction_of([(None, 1)])[1], rel=0.05)
    assert dat.displacements("Nall").values[:, 1].max() == pytest.approx(10.0, abs=1e-6)  # the numbers stay in the local note


def test_plane_stress_in_the_converter():
    deck = read_deck(GRIPS, "mm-MPa")
    text = calculix_from_deck(deck, TransverseChoice(plane_stress=True))
    assert "*ELASTIC, TYPE=ENGINEERING CONSTANTS\n162095.74, 8963.18, 8963.18, 0.316, 0., 0., 4688.43, 4688.43\n3000., 293." in text
    out_of_plane = next(line for line in text.splitlines() if line.startswith("** Out-of-plane constants"))
    assert "nu13 = nu23 = 0 written for plane stress" in out_of_plane and "nu23 = 0.45" not in out_of_plane
    explicit = calculix_from_deck(deck, TransverseChoice(plane_stress=True, transverse_isotropy=False, E3=9000e6))
    assert "162095.74, 8963.18, 9000., 0.316, 0., 0., 4688.43, 4688.43" in explicit
    with pytest.raises(CalculixWriterError, match="do not give them"):
        calculix_from_deck(deck, TransverseChoice(nu23=0.45, plane_stress=True))
    with pytest.raises(CalculixWriterError, match="nu23 must be given unless plane_stress"):
        calculix_from_deck(deck, TransverseChoice())
