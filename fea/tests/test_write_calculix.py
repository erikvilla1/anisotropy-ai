"""The CalculiX-dialect writer: S8R composite with four-field layers, engineering constants, one orientation per angle (ADR-0030)."""

from pathlib import Path

import pytest

from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec, parse_spec, to_si
from anisotropy_fea.write_calculix import CalculixWriterError, orientation_name, write_calculix

SPECS = Path(__file__).parents[1] / "validation" / "specs"
NODAL = (SPECS / "unnotched-im7-8552-nodal.toml").read_text(encoding="utf-8")


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
    assert "*ORIENTATION, NAME=Ori-45\n0.7071067812, 0.7071067812, 0., -0.7071067812, 0.7071067812, 0." in text
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
        write_calculix(build_model(load_spec(SPECS / "unnotched-im7-8552-nodal.toml")))
    coupling = order2(NODAL.replace('kind = "nodal"', 'kind = "coupling"'))
    with pytest.raises(CalculixWriterError, match="cannot print the reaction at a coupled reference node"):
        write_calculix(build_model(coupling))
    force = order2(NODAL.replace('control = "displacement"\nvalue = 1.0', 'control = "force"\nvalue = 5000.0').replace('region = "tabs"', 'region = "line"'))
    with pytest.raises(CalculixWriterError, match="force control with nodal grips"):
        write_calculix(build_model(force))


def test_the_committed_calculix_deck_matches_its_spec():
    spec = load_spec(SPECS / "unnotched-im7-8552-nodal.toml")
    text = write_calculix(build_model(spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"element_order": 2})})))
    committed = (SPECS.parent / "decks" / "generated" / "unnotched-im7-8552-nodal-ccx.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert committed == text, "regenerate with examples/run_calculix.py and copy the deck into validation/decks/generated/"


def test_plane_stress_puts_zero_poisson_ratios_in_the_engineering_constants_and_says_so():
    text = write_calculix(build_model(order2(NODAL.replace("nu23 = 0.45         # nominal, no source\n", "")
                                                  .replace("plane_stress = false", "plane_stress = true"))))
    assert "*ELASTIC, TYPE=ENGINEERING CONSTANTS\n162095.744, 8963.184481, 8963.184481, 0.316, 0., 0., 4688.434959, 4688.43\n3000., 293." in text
    assert "nu13 = nu23 = 0 written for plane stress, as Abaqus LAMINA and our kernel assume (plane_stress = true in the spec)" in text
    assert "plane stress" not in write_calculix(build_model(order2()))
