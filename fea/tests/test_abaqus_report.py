"""Abaqus/CAE field reports (CSV): the reader, its refusals, the mapping into record tables, and a round trip through the kernel (ADR-0030, amendment 2)."""

import math
from pathlib import Path

import numpy as np
import pytest

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.abaqus_report import FieldReport, ReportError, read_field_report, report_quantities
from anisotropy_fea.compare import RecordError, format_record, load_record, record_disagreements, sha256_of, validate_record
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.recovery import element_ply_states, ply_mises
from anisotropy_fea.units import from_si
from anisotropy_fea import paths  # where the files live (ADR-0036)

FIXTURES = Path(__file__).parent / "fixtures"
DECKS = paths.CHECK_DECKS
GRIPS = DECKS / "coupon-2x8-grips-im7-8552.inp"
SAMPLE = (FIXTURES / "field-report-S22.csv").read_text(encoding="utf-8")
HEADER = SAMPLE.splitlines()[0]


def test_the_sample_report_is_read_with_its_repeated_block_and_faces():
    report = read_field_report(FIXTURES / "field-report-S22.csv")
    assert report.quantity == "S22" and report.instance == "STRIP-1" and report.step == "Step-1"
    assert report.blocks == 2 and report.rows == 6  # the second block repeats two rows, which must agree
    assert report.values == {(3, 1): 1234.5, (3, 8): 1234.5, (8, 1): -12.25, (8, 4): 56.0}
    assert report.faces == {(3, 1): "SNEG", (3, 8): "SPOS", (8, 1): "SNEG", (8, 4): ""}
    assert report.centroids == {3: (2.5, 7.5), 8: (7.5, 12.5)}


def row(element: int, x: float, y: float, point: str, value: str, intpt: int = 1, instance: str = "STRIP-1") -> str:
    return (f'H:/example/coupon.odb,Step-1,Increment      1: Step Time =    1.000,"{instance}",{element:14d},{intpt:14d},{x:13g},{y:13g},            0.,'
            f'"ASSEMBLY_COUPON-1_LAYUP-1","IM7-8552","shell < composite > < elset = ASSEMBLY_COUPON-1_LAYUP-1 > : {point}",{value:>13s}')


@pytest.mark.parametrize("lines, message", [
    ([HEADER, row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0", intpt=2)], "integration point 2"),
    ([HEADER, row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0"), row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "2.0")], "repeated with a different value"),
    ([HEADER, row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0"), row(3, 2.5, 7.6, "SPOS, (fraction = 1.0), Layer = 8", "2.0")], "different coordinates"),
    ([HEADER, row(3, 2.5, 7.5, "SNEG, (fraction = -1.0)", "1.0")], "names no layer"),
    ([HEADER, row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0"), row(4, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0", instance="OTHER-1")], "Part Instance Name changes"),
    ([HEADER.replace("S-S22", "S-E22"), row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0")], "not one of"),
    ([HEADER.replace("IntPt", "Point"), row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0")], "header lacks"),
    ([row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "1.0")], "data before the first header"),
    ([HEADER, row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "abc")], "does not parse"),
    ([HEADER], "no report block with data"),
])
def test_refusals_name_the_line(tmp_path, lines, message):
    path = tmp_path / "report.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ReportError, match=message):
        read_field_report(path)


def test_quantities_map_into_record_tables_with_nan_for_what_was_not_reported(tmp_path):
    deck = read_deck(GRIPS, "mm-MPa")
    (instance,) = deck.instances
    s22 = read_field_report(FIXTURES / "field-report-S22.csv")
    s11_path = tmp_path / "s11.csv"
    s11_path.write_text(HEADER.replace("S-S22", "S-S11") + "\n" + row(3, 2.5, 7.5, "SNEG, (fraction = -1.0), Layer = 1", "-5.0") + "\n"
                        + row(8, 7.5, 12.5, "SNEG, (fraction = -1.0), Layer = 1", "7.0") + "\n", encoding="utf-8")
    s11 = read_field_report(s11_path)
    expected = report_quantities([s22, s11], deck, [3])
    assert list(expected) == ["ply_stress_local"]
    rows = expected["ply_stress_local"][f"{instance}.3"]
    assert rows["1"][:2] == [-5.0, 1234.5] and math.isnan(rows["1"][2])
    assert math.isnan(rows["8"][0]) and rows["8"][1] == 1234.5 and math.isnan(rows["8"][2])
    with pytest.raises(ReportError, match="element 5 is not in"):
        report_quantities([s22], deck, [5])
    with pytest.raises(ReportError, match="given twice"):
        report_quantities([s22, s22], deck)
    other = FieldReport(**{**s11.__dict__, "instance": "ELSEWHERE-1"})
    with pytest.raises(ReportError, match="instance 'ELSEWHERE-1' differs"):
        report_quantities([s22, other], deck)
    with pytest.raises(ReportError, match="is not in the deck"):
        report_quantities([other], deck)


def test_ply_mises_is_the_plane_stress_invariant():
    solution = solve_membrane(read_deck(GRIPS, "mm-MPa"))
    field = element_ply_states(solution)
    mises = ply_mises(field)
    for e in range(solution.mesh.element_count):
        for k in range(field.stress_12[e].shape[0]):
            s = field.stress_12[e][k]
            assert mises[e][k, 0] == pytest.approx(math.sqrt(s[0] ** 2 - s[0] * s[1] + s[1] ** 2 + 3 * s[2] ** 2))
            sxy = field.stress_xy[e][k]  # the same number in laminate axes
            assert mises[e][k, 0] == pytest.approx(math.sqrt(sxy[0] ** 2 - sxy[0] * sxy[1] + sxy[1] ** 2 + 3 * sxy[2] ** 2), rel=1e-9)


def cae_report(deck, solution, quantity: str, elements: list[int], layers: list[int]) -> str:
    """CAE-format report text filled with the kernel's own numbers, two blocks (the second repeats the first element)."""
    (instance,) = deck.instances
    field = element_ply_states(solution)
    mises = ply_mises(field)
    mesh = solution.mesh
    lines = [HEADER.replace("S-S22", f"S-{quantity}")]
    body = []
    for label in elements:
        e = mesh.element((instance, label))
        x, y = mesh.xy[mesh.connectivity[e]].mean(axis=0) * 1e3
        for layer in layers:
            k = layer - 1
            s = field.stress_12[e][k]
            value = {"S11": s[0], "S22": s[1], "S12": s[2], "Mises": mises[e][k, 0]}[quantity]
            point = {1: "SNEG, (fraction = -1.0), Layer = 1", 8: "SPOS, (fraction = 1.0), Layer = 8"}.get(layer, f"(fraction = 0.0), Layer = {layer}")
            body.append(row(label, round(x, 6), round(y, 6), point, repr(from_si(float(value), "stress", "mm-MPa")), instance=instance.upper()))
    return "\n".join(lines + body + [lines[0]] + body[: len(layers)]) + "\n"


def test_round_trip_a_report_of_the_kernels_own_numbers_gives_a_record_the_kernel_passes(tmp_path):
    deck = read_deck(GRIPS, "mm-MPa")
    solution = solve_membrane(deck)
    (instance,) = deck.instances
    elements, layers = [3, 8, 16], [1, 4, 8]
    reports = []
    for quantity in ("S11", "S22", "Mises"):  # no S12, as in the team's export
        path = tmp_path / f"{quantity}.csv"
        path.write_text(cae_report(deck, solution, quantity, elements, layers), encoding="utf-8")
        reports.append(read_field_report(path))
    assert all(r.instance == instance.upper() and r.blocks == 2 for r in reports)
    expected = report_quantities(reports, deck)
    assert set(expected) == {"ply_stress_local", "ply_mises"}
    assert set(expected["ply_stress_local"]) == {f"{instance}.{e}" for e in elements}
    assert all(math.isnan(v[2]) for plies in expected["ply_stress_local"].values() for v in plies.values())
    record = {"title": "round trip", "units": "mm-MPa", "spec": "none", "deck_kernel": GRIPS.name, "deck_reference": GRIPS.name,
              "deck_kernel_sha256": sha256_of(GRIPS), "deck_reference_sha256": sha256_of(GRIPS),
              "solver": {"name": "abaqus", "version": "test", "element_type": "S4R", "run_by": "test", "run_date": "2026-10-18", "machine": "test", "source": "csv"},
              "expected": {"tolerance": 1e-9, "floor": 0.0, **expected}}
    path = tmp_path / "record.toml"
    path.write_text(format_record(record), encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    assert "nan]" in text and 'source = "csv"' in text
    # the record is read back from disk next to the deck, as a committed one would be
    (tmp_path / GRIPS.name).write_bytes(GRIPS.read_bytes())
    loaded = load_record(path)
    assert record_disagreements(loaded) == []
    # a wrong non-nan number is caught; nan never is
    wrong = text.replace("[expected.ply_mises", "[expected.ply_mises", 1)
    rows = loaded["expected"]["ply_mises"][f"{instance}.3"]
    rows["1"] = [rows["1"][0] * 1.01]
    assert len(record_disagreements(loaded)) == 1
    bad = {**record, "solver": {**record["solver"], "source": "odb"}}
    with pytest.raises(RecordError, match="dat, rpt or csv"):
        validate_record({**bad, "_dir": str(tmp_path)})
    assert wrong == text
