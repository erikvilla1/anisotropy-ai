"""The committed fixture decks parse to the model the kernel will consume (ADR-0029)."""

import hashlib
from pathlib import Path

import numpy as np
import pytest

from anisotropy_engine.laminate import abd_matrices
from anisotropy_fea.abaqus_reader import SUPPORTED_KEYWORDS, parse_deck, read_deck
from anisotropy_fea.model import (
    ElementSurface,
    NodeSurface,
    coupled_nodes,
    expanded_layers,
    is_symmetric_layup,
    node_name,
    prescribed_dofs,
    reference_node,
    section_plies,
    validate_deck,
)

DECKS = Path(__file__).parents[1] / "validation" / "decks"
GRIPS = DECKS / "coupon-2x8-grips-im7-8552.inp"
ONE = DECKS / "coupon-1x1-im7-8552.inp"
ISOTROPIC = DECKS / "plate-1x1-isotropic.inp"
LAYUP = [0.0, 45.0, -45.0, 45.0, 0.0, 0.0, 45.0, -45.0, 45.0, 0.0]


def test_the_gripped_coupon_parses_as_written():
    deck = parse_deck(GRIPS.read_text(encoding="utf-8"), source_path=str(GRIPS))
    part = deck.parts["CFRP-Coupon"]
    assert len(part.nodes) == 27 and len(part.elements) == 16 and part.elements.element_type == "S4R"
    assert part.nodes.xyz[part.nodes.index_of(27)].tolist() == [10.0, 80.0, 0.0]
    assert part.elements.connectivity[0].tolist() == [1, 2, 5, 4]
    assert part.elsets["CompositeLayup-1-1"].tolist() == list(range(1, 17))
    (section,) = part.sections
    assert section.symmetric and section.orientation == "Ori-1" and section.layup_name == "CompositeLayup-1"
    assert [layer.angle_deg for layer in section.layers] == LAYUP[:5]
    assert [layer.angle_deg for layer in expanded_layers(section)] == LAYUP
    assert [layer.ply_name for layer in section.layers] == ["Ply-1", "Ply-2", "Ply-3", "Ply-4", "Ply-5"]
    assert all(layer.thickness == 0.18288 and layer.integration_points == 3 for layer in section.layers)
    assert part.orientations["Ori-1"].a == (1.0, 0.0, 0.0) and part.orientations["Ori-1"].rotation_deg == 0.0
    material = deck.materials["IM7-8552"]
    assert material.elastic.kind == "LAMINA"
    assert (material.elastic.E1, material.elastic.E2, material.elastic.nu12, material.elastic.G12) == (162095.74, 8963.18, 0.316, 4688.43)
    assert material.elastic.G13 == 4688.43 and material.elastic.G23 == 3000.0
    assert material.fail_stress.Xt == 2558.51 and material.fail_stress.Xc == -1731.48 and material.fail_stress.f_star == 0.0
    assert deck.instances["CFRP-Coupon-1"].part == "CFRP-Coupon"
    assert deck.assembly_nodes.labels.tolist() == [1, 2]
    assert deck.assembly_nodes.xyz.tolist() == [[5.0, 80.0, 0.0], [5.0, 0.0, 0.0]]
    assert deck.nsets["s_Top"] == (("CFRP-Coupon-1", 25), ("CFRP-Coupon-1", 26), ("CFRP-Coupon-1", 27))
    # the same set name twice is one set: the three edge nodes and the assembly reference node
    assert deck.nsets["s_Bottom"] == (("CFRP-Coupon-1", 1), ("CFRP-Coupon-1", 2), ("CFRP-Coupon-1", 3), (None, 2))
    assert deck.elsets["s_Top"] == (("CFRP-Coupon-1", 15), ("CFRP-Coupon-1", 16))
    assert deck.elsets["_s_Surf-1_SPOS"] == tuple(("CFRP-Coupon-1", label) for label in range(1, 17))
    assert isinstance(deck.surfaces["s_Surf-1"], ElementSurface) and deck.surfaces["s_Surf-1"].side == "SPOS"
    assert isinstance(deck.surfaces["s_Top_CNS_"], NodeSurface) and deck.surfaces["s_Top_CNS_"].internal
    top, bottom = deck.couplings
    assert (top.name, top.ref_node_set, top.surface, top.dofs) == ("Grip-Top", "RF-Top", "s_Top_CNS_", frozenset(range(1, 7)))
    assert bottom.name == "Grip-Bottom"
    (step,) = deck.steps
    assert step.name == "Step-1" and step.nlgeom is False and step.cloads == ()
    encastre = [b for b in step.boundaries if b.target == "Set-Encastre"]
    assert [(b.dof_first, b.value) for b in encastre] == [(1, 0.0), (2, 0.0), (3, 0.0), (4, 0.0), (5, 0.0), (6, 0.0)]
    assert [b.dof_first for b in step.boundaries if b.target == "Set-TopFix"] == [1, 3, 4, 5, 6]
    (pull,) = [b for b in step.boundaries if b.target == "Set-TopPull"]
    assert (pull.dof_first, pull.dof_last, pull.value) == (2, 2, 0.8)
    assert [entry.split(": ")[1] for entry in deck.ignored_keywords] == ["*preprint", "*restart", "*output", "*output"]
    assert deck.source_sha256 == hashlib.sha256(GRIPS.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert deck.units is None and deck.notes == ()


def test_validation_resolves_the_couplings_and_notes_the_reference_node_in_its_own_set():
    deck = parse_deck(GRIPS.read_text(encoding="utf-8"))
    notes = validate_deck(deck)
    top, bottom = deck.couplings
    assert reference_node(deck, top) == (None, 1) and reference_node(deck, bottom) == (None, 2)
    assert coupled_nodes(deck, bottom) == (("CFRP-Coupon-1", 1), ("CFRP-Coupon-1", 2), ("CFRP-Coupon-1", 3))
    assert len(notes) == 1 and "Assembly.2" in notes[0] and "dropped" in notes[0]
    assert prescribed_dofs(deck, (None, 1)) == {1: 0.0, 3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 2: 0.8}
    assert prescribed_dofs(deck, (None, 2)) == {dof: 0.0 for dof in range(1, 7)}
    assert node_name((None, 2)) == "Assembly.2" and node_name(("CFRP-Coupon-1", 7)) == "CFRP-Coupon-1.7"


def test_read_deck_converts_to_si_and_builds_engine_plies():
    deck = read_deck(GRIPS, "mm-MPa")
    assert deck.units == "mm-MPa" and len(deck.notes) == 1
    part = deck.parts["CFRP-Coupon"]
    assert part.nodes.xyz[part.nodes.index_of(27)] == pytest.approx([0.010, 0.080, 0.0])
    assert deck.assembly_nodes.xyz[0] == pytest.approx([0.005, 0.080, 0.0])
    (pull,) = [b for step in deck.steps for b in step.boundaries if b.target == "Set-TopPull"]
    assert pull.value == pytest.approx(0.8e-3)
    material = deck.materials["IM7-8552"]
    assert material.elastic.E1 == pytest.approx(162095.74e6) and material.fail_stress.S == pytest.approx(91.15e6)
    plies = section_plies(part.sections[0], deck.materials)
    assert [ply.angle_deg for ply in plies] == LAYUP
    assert sum(ply.thickness_m for ply in plies) == pytest.approx(10 * 0.18288e-3)
    assert plies[0].material.E1 == pytest.approx(162095.74e6) and plies[0].material.strengths.F1c == pytest.approx(1731.48e6)
    assert is_symmetric_layup(plies)
    A, B, D = abd_matrices(plies)
    assert abs(A[0, 2]) > 1e-3 * abs(A[0, 0])  # unbalanced: shear-extension coupling is real
    assert np.allclose(B, 0.0, atol=1e-9 * np.linalg.norm(A) * sum(ply.thickness_m for ply in plies))


def test_the_one_element_coupon_has_simple_edge_conditions_and_no_couplings():
    deck = read_deck(ONE, "mm-MPa")
    part = deck.parts["Coupon"]
    assert len(part.nodes) == 4 and len(part.elements) == 1
    assert deck.couplings == () and deck.notes == ()
    (step,) = deck.steps
    assert [(b.target, b.dof_first, b.value) for b in step.boundaries] == [("Bottom", 2, 0.0), ("Corner", 1, 0.0), ("Top", 2, pytest.approx(0.8e-3))]
    plies = section_plies(part.sections[0], deck.materials)
    assert len(plies) == 10 and is_symmetric_layup(plies)
    assert not is_symmetric_layup(plies[:4])  # [0/45/-45/45] has no mirror plane


def test_the_isotropic_plate_uses_a_homogeneous_section_and_a_node_target_with_an_instance_prefix():
    deck = read_deck(ISOTROPIC, "mm-MPa")
    part = deck.parts["Plate"]
    assert part.elements.element_type == "S4" and part.elsets["All"].tolist() == [1]
    (section,) = part.sections
    assert not section.symmetric and section.orientation is None
    (layer,) = section.layers
    assert (layer.material, layer.angle_deg, layer.integration_points) == ("Nominal-Alloy", 0.0, 5)
    assert layer.thickness == pytest.approx(2e-3)
    elastic = deck.materials["Nominal-Alloy"].elastic
    assert elastic.kind == "ISOTROPIC" and elastic.E1 == elastic.E2 == pytest.approx(70000e6)
    assert elastic.G12 == pytest.approx(70000e6 / (2 * 1.33)) and elastic.G13 is None
    (step,) = deck.steps
    assert step.boundaries[1].target == ("Plate-1", 1)
    (ply,) = section_plies(section, deck.materials)
    assert ply.material.strengths is None and ply.thickness_m == pytest.approx(2e-3)


def test_the_supported_keyword_list_is_what_the_readme_documents():
    assert SUPPORTED_KEYWORDS == (
        "assembly", "boundary", "cload", "coupling", "elastic", "element", "elset", "end assembly", "end instance", "end part",
        "end step", "fail stress", "heading", "instance", "kinematic", "material", "node", "nset", "orientation", "part",
        "shell section", "static", "step", "surface",
    )
