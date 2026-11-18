"""The CalculiX-dialect writer: S8R composite with four-field layers, engineering constants, one orientation per angle (ADR-0030)."""

from pathlib import Path

import pytest

from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec, parse_spec, to_si
from anisotropy_fea.write_calculix import CalculixWriterError, orientation_name, write_calculix
from anisotropy_fea import paths  # where the files live (ADR-0036)

NODAL = (paths.spec_path("unnotched-im7-8552-nodal")).read_text(encoding="utf-8")


def order2(text: str = NODAL):
    return to_si(parse_spec(text.replace("element_order = 1", "element_order = 2")))


def test_orientation_names():
    assert orientation_name(45.0) == "Ori-45" and orientation_name(-45.0) == "Ori-m45" and orientation_name(0.0) == "Ori-0"
    assert orientation_name(22.5) == "Ori-22p5"


def test_the_deck_has_calculix_syntax_and_is_deterministic():
    model = build_model(order2())
    text = write_calculix(model)
    assert text == write_calculix(model)
    assert text.startswith("*HEADING\nCalculiX deck written by anisotropy_fea from")
    assert "*ELEMENT, TYPE=S8R, ELSET=All" in text and "*NODE, NSET=Nall" in text
    first_element = next(line for line in text.splitlines() if line.startswith("1, ") and line.count(",") == 8)
    assert first_element.split(", ")[1:5] == ["1", "2", "13", "12"]  # 11 corner nodes per row
    assert "*ELASTIC, TYPE=ENGINEERING CONSTANTS\n162095.744, 8963.184481, 8963.184481, 0.316, 0.316, 0.45, 4688.434959, 4688.43\n3000., 293." in text
    for name in ("Ori-m45", "Ori-0", "Ori-45", "Ori-90"):
        assert f"*ORIENTATION, NAME={name}\n" in text
    # Ori-45 is named by the stated angle; its axes are the fibre direction from x, 45 + 90 = 135 degrees, written as the same line -45 degrees
    # (a fibre has no arrow, and fibre_angles brings every angle into (-90, 90]): a = (cos -45, sin -45), b = z cross a (ADR-0065).
    assert "*ORIENTATION, NAME=Ori-45\n0.7071067812, -0.7071067812, 0., 0.7071067812, 0.7071067812, 0." in text
    assert "*ORIENTATION, NAME=Ori-0\n6.123233996e-17, 1., 0., -1., 6.123233996e-17, 0." in text  # the stated 0 ply has its fibres along y
    assert "named by the ply angle the coupon states, counted from its length axis" in text
    section = text[text.index("*SHELL SECTION, ELSET=All, COMPOSITE"):text.index("*BOUNDARY")]
    layers = [line for line in section.splitlines()[1:] if line.strip()]
    assert layers == [f"0.18288, , IM7-8552, {name}" for name in ("Ori-45", "Ori-0", "Ori-m45", "Ori-90", "Ori-90", "Ori-m45", "Ori-0", "Ori-45")]
    assert "symmetric" not in section.lower() and "LAMINA" not in text and "*Fail Stress" not in text
    assert "*BOUNDARY\nGrip-Bottom, 1, 6\nGrip-Top, 1, 1\nGrip-Top, 3, 6\n*STEP\n*STATIC\n*BOUNDARY\nGrip-Top, 2, 2, 1.\n" in text
    assert "*NODE PRINT, NSET=Grip-Top, TOTALS=YES\nRF\n" in text and "*NODE PRINT, NSET=Probe-centre\nU\n" in text
    assert "*EL PRINT, ELSET=Probe-centre, GLOBAL=YES\nS, E, COORD\n" in text  # COORD maps each integration point to its ply
    assert "*NODE FILE\nU\n*EL FILE\nS, E\n*END STEP\n" in text


def test_refusals():
    with pytest.raises(CalculixWriterError, match="S8R only"):
        write_calculix(build_model(load_spec(paths.spec_path("unnotched-im7-8552-nodal"))))
    coupling = order2(NODAL.replace('kind = "nodal"', 'kind = "coupling"'))
    with pytest.raises(CalculixWriterError, match="cannot print the reaction at a coupled reference node"):
        write_calculix(build_model(coupling))
    force = order2(NODAL.replace('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0').replace('region = "tabs"', 'region = "line"'))
    with pytest.raises(CalculixWriterError, match="force control with nodal grips is written for CalculiX as a rigid grip only"):
        write_calculix(build_model(force))


FORCED = NODAL.replace('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0\nrigid_grip = true')


def test_a_rigid_grip_under_a_force_is_moved_by_the_travel_our_kernel_finds_for_it():
    """ADR-0030 amendment 7. CalculiX ties a shell node by its faces alone, so the deck moves the grip instead: by what our kernel finds
    for the force on the same model, which is the coupled model's travel. The deck says so and carries no load."""
    from anisotropy_fea.abaqus_reader import parse_deck, to_si as deck_to_si
    from anisotropy_fea.kernel import solve_deck
    from anisotropy_fea.write_abaqus import write_abaqus
    from anisotropy_fea.write_calculix import tied_grips

    model = build_model(order2(FORCED))
    [tie] = tied_grips(model)
    assert (tie.node_set, tie.reference_set, tie.dof, tie.force) == ("Grip-Top", "RF-Top", 2, 5000.0)
    coupled = build_model(to_si(parse_spec(FORCED.replace('kind = "nodal"', 'kind = "coupling"').replace("\nrigid_grip = true", ""))))
    deck = deck_to_si(parse_deck(write_abaqus(coupled, "mm-MPa")), "mm-MPa")
    [top] = deck.nsets["RF-Top"]
    travel = float(solve_deck(deck).displacement_of(top)[1])
    assert travel > 0 and tie.travel == pytest.approx(travel, rel=1e-9)
    text = write_calculix(model)
    assert text == write_calculix(model)
    assert "*BOUNDARY\nGrip-Bottom, 1, 6\nGrip-Top, 1, 1\nGrip-Top, 3, 6\n*STEP\n*STATIC\n** The coupon states a force of 5000. on Grip-Top, which moves as one." in text
    assert f"(ADR-0030 amendment 7).\n*BOUNDARY\nGrip-Top, 2, 2, {1000 * travel:.10g}\n" in text
    assert "*CLOAD" not in text and "*EQUATION" not in text and "RF-Top" not in text
    assert "*NODE PRINT, NSET=Grip-Bottom, TOTALS=YES\nRF\n" in text and "*NODE PRINT, NSET=Grip-Top" not in text  # the held grip carries the reaction
    turned = build_model(order2(FORCED))
    free = turned.__class__(**{**turned.__dict__, "boundaries": tuple(b for b in turned.boundaries if (b.target, b.dof_first) != ("RF-Top", 1))})  # the reference point free sideways
    with pytest.raises(CalculixWriterError, match="cannot print the reaction at a coupled reference node"):
        write_calculix(free)


def test_the_committed_calculix_deck_matches_its_spec():
    spec = load_spec(paths.spec_path("unnotched-im7-8552-nodal"))
    text = write_calculix(build_model(spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})))
    committed = (paths.deck_path(paths.spec_path("unnotched-im7-8552-nodal"), "ccx")).read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == text, "regenerate with examples/run_calculix.py into the test's decks/ folder"


def test_plane_stress_puts_zero_poisson_ratios_in_the_engineering_constants_and_says_so():
    text = write_calculix(build_model(order2(NODAL.replace("nu23 = 0.45         # nominal, no source\n", "")
                                                  .replace("plane_stress = false", "plane_stress = true"))))
    assert "*ELASTIC, TYPE=ENGINEERING CONSTANTS\n162095.744, 8963.184481, 8963.184481, 0.316, 0., 0., 4688.434959, 4688.43\n3000., 293." in text
    assert "nu13 = nu23 = 0 written for plane stress, as Abaqus LAMINA and our kernel assume (plane_stress = true in the spec)" in text
    assert "plane stress" not in write_calculix(build_model(order2()))
