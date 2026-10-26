"""The Abaqus runner: finding the command, reading a failed run, and, when Abaqus is present, a solve of the public check deck whose
exported fields the kernel reproduces (ADR-0045). The licence on the founder's machine is a teaching licence; CI has none and skips."""

import os
from pathlib import Path

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)
from anisotropy_fea.abaqus import (ENV_VARIABLE, EXTRACT_SCRIPT, AbaqusError, analysis_problems, extract_fields, find_abaqus, reactions_by_set,
                                   read_provenance, read_reactions, run_abaqus)
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.abaqus_report import read_field_report, report_quantities
from anisotropy_fea.compare import format_record, load_record, record_disagreements, sha256_of
from anisotropy_fea.femodel import build_model
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus

needs_abaqus = pytest.mark.skipif(find_abaqus() is None, reason=f"Abaqus not found: set {ENV_VARIABLE} or put abaqus on PATH (docs/installation-fea-tools.md)")
PUBLIC_DECK = paths.CHECKS / "unnotched-im7-8552" / "decks" / "unnotched-im7-8552-coupling-abaqus.inp"


def test_find_abaqus_precedence(tmp_path, monkeypatch):
    fake = tmp_path / "abaqus.bat"
    fake.write_bytes(b"")
    assert find_abaqus(fake) == fake
    monkeypatch.setenv(ENV_VARIABLE, str(fake))
    assert find_abaqus() == fake
    monkeypatch.setenv(ENV_VARIABLE, str(tmp_path / "missing.bat"))
    with pytest.raises(AbaqusError, match="not found"):
        find_abaqus()
    monkeypatch.delenv(ENV_VARIABLE)
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert find_abaqus() is None


def test_a_failed_run_is_read_from_what_abaqus_wrote():
    msg = "   ***ERROR: 2 NODES ARE MISSING DEGREE OF FREEDOMS. THE NODES HAVE BEEN IDENTIFIED IN NODE SET ErrNodeMissingDofConstrDef.\n\n   ***WARNING: a warning\n"
    sta = " SUMMARY OF JOB INFORMATION:\n THE ANALYSIS HAS NOT BEEN COMPLETED\n"
    problems = analysis_problems("Abaqus/Analysis exited with errors\n", sta, msg, "")
    assert problems[0].startswith("***ERROR: 2 NODES ARE MISSING") and "The analysis has not been completed" in problems
    assert problems[-1] == "Abaqus/Analysis exited with errors"
    assert analysis_problems("Abaqus JOB x COMPLETED\n", " THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n", "", "") == []
    assert analysis_problems("", "", "", "") == ["the .sta does not say the analysis completed"]


def test_reactions_are_summed_per_grip_set_whatever_the_case_of_the_instance_name():
    """The ODB spells the deck's instance Coupon-1 as COUPON-1; a reference point is an assembly node, with no instance."""
    nodal = read_deck(paths.deck_path(paths.spec_path("unnotched-im7-8552-nodal"), "abaqus"), "mm-MPa")
    top = nodal.nsets["Grip-Top"]
    assert {instance for instance, _ in top} == {"Coupon-1"}
    reactions = {(instance.upper(), label): (0.0, 2.0, 0.0) for instance, label in top}
    assert reactions_by_set(nodal, reactions) == {"Grip-Top": [0.0, 2.0 * len(top)]}
    coupled = read_deck(PUBLIC_DECK, "mm-MPa")
    (instance, label), = coupled.nsets["RF-Top"]
    assert reactions_by_set(coupled, {((instance or ""), label): (0.5, 7.0, 0.0)}) == {"RF-Top": [0.5, 7.0]}


def test_the_environment_variable_and_the_script_are_in_place():
    assert ENV_VARIABLE == "ANISOTROPY_ABAQUS" and ENV_VARIABLE in (Path(__file__).parents[2] / "docs" / "installation-fea-tools.md").read_text(encoding="utf-8")
    assert os.environ.get(ENV_VARIABLE) is None or find_abaqus() is not None
    assert EXTRACT_SCRIPT.is_file() and EXTRACT_SCRIPT.name == "abaqus_extract_fields.py"


@needs_abaqus
def test_abaqus_solves_the_public_check_deck_and_the_kernel_reproduces_the_export(tmp_path):
    """One licence seat, about a minute: the IM7/8552 coupling coupon in Abaqus/Standard, its fields exported without the GUI, and the
    kernel's reaction and centre-element ply stresses against them."""
    spec = load_spec(paths.spec_path("unnotched-im7-8552-coupling"))
    units = spec.units
    assert PUBLIC_DECK.read_text(encoding="utf-8").replace("\r\n", "\n") == write_abaqus(build_model(spec))
    result = run_abaqus(PUBLIC_DECK, workdir=tmp_path)  # the committed deck as written: valid Abaqus/Standard input (ADR-0045 amendment 2)
    deck_path = tmp_path / PUBLIC_DECK.name
    assert result.errors == () and result.returncode == 0 and result.odb_path.is_file() and result.version
    assert not [w for w in result.warnings if "truncated" in w.lower()]  # every line within Abaqus's 256 bytes
    assert "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in result.sta_text
    with pytest.raises(AbaqusError, match="exists"):
        (tmp_path / f"{deck_path.stem}.lck").write_text("")
        run_abaqus(deck_path, workdir=tmp_path)
    files = extract_fields(result.odb_path, tmp_path)
    provenance = read_provenance(files["json"])
    assert provenance["element_type"] == "S4R" and provenance["frame"].startswith("Increment") and set(provenance["files"]) >= {"S11", "S22", "S12", "Mises", "RF"}
    deck = read_deck(deck_path, units)
    solution = solve_membrane(deck)
    reactions = read_reactions(files["RF"])
    (instance, label), = deck.nsets["RF-Top"]
    abaqus_top = reactions[(instance or "", label)]
    ours = solution.reaction_of(deck.nsets["RF-Top"])
    assert abaqus_top[1] == pytest.approx(from_si(ours[1], "force", units), rel=0.02)
    reports = [read_field_report(files[q]) for q in ("S11", "S22", "S12", "Mises")]
    assert all(r.rows == 2 * len(r.centroids) for r in reports)  # the two outer faces per element, the default field output
    centre = deck.elsets["Probe-centre"][0][1]
    expected = report_quantities(reports, deck, [centre])
    record = {"title": "public check in Abaqus", "units": units, "spec": "none", "deck_kernel": deck_path.name, "deck_reference": deck_path.name,
              "deck_kernel_sha256": sha256_of(deck_path), "deck_reference_sha256": sha256_of(deck_path),
              "solver": {"name": "abaqus", "version": result.version, "element_type": "S4R", "run_by": "test", "run_date": "2026-10-24", "machine": "test", "source": "csv"},
              "expected": {"tolerance": 0.03, "floor": 0.05, **expected}}
    path = tmp_path / "record.toml"
    path.write_text(format_record(record), encoding="utf-8")
    assert record_disagreements(load_record(path)) == []
