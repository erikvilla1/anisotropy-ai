"""Every output of an Abaqus run beside our kernel (ADR-0089 part 7): the ODB exporter's plain helpers, the comparison by zone, the deck's
every-layer request, and the digest rule for a deck that changed in its output alone."""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus

TOOLS = Path(__file__).parents[1] / "tools"
SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"


def load(name: str, monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_the_exporter_takes_each_layers_middle_point_beside_the_faces_preselect_adds(monkeypatch):
    every = load("abaqus_every_output", monkeypatch)
    extract = sys.modules["abaqus_extract_fields"]
    descriptions = {1: "SNEG, (fraction = -1.0), Layer = 1", 2: "fraction = -0.750000, Layer = 1", 5: "fraction = -0.250000, Layer = 2",
                    8: "fraction = 0.250000, Layer = 3", 11: "fraction = 0.750000, Layer = 4", 12: "SPOS, (fraction = 1.0), Layer = 4"}
    points = {n: extract.parse_section_point(n, d) for n, d in descriptions.items()}
    assert every.middles_of(points) == {2: 1, 5: 2, 8: 3, 11: 4}
    stress = {(7, n): ((10.0 * n, 2.0, 3.0, 0.5), {name: float(n) for name, _ in every.INVARIANTS}) for n in descriptions}
    strain = {(7, n): (1e-3, 2e-4, 0.0, 3e-5) for n in descriptions}
    rows = every.rows_of(points, stress, strain, {7: (12.5, 125.0, 0.0)}, ("S11", "S22", "S33", "S12"), ("E11", "E22", "E33", "E12"))
    assert [row[1] for row in rows] == ["1", "2", "3", "4"]
    assert rows[0][2] == '"fraction = -0.750000, Layer = 1"' and rows[0][5:8] == ["20", "2", "0.5"]  # S11, S22, S12; S33 left out
    assert rows[0][-3:] == ["0.001", "0.0002", "3e-05"]
    with pytest.raises(extract.ExtractError, match="no interior section point"):
        every.middles_of({1: points[1], 12: points[12]})
    with pytest.raises(extract.ExtractError, match="no strain"):
        every.rows_of(points, stress, {}, {7: (0.0, 0.0, 0.0)}, ("S11", "S22", "S33", "S12"), ("E11", "E22", "E33", "E12"))


def test_our_own_values_compared_with_themselves_agree_everywhere_and_the_zones_cover_the_coupon(tmp_path, monkeypatch):
    compare = load("abaqus_compare", monkeypatch)
    spec = load_spec(SPEC)
    from anisotropy_fea.abaqus_reader import read_deck

    deck = read_deck(paths.deck_path(SPEC, "abaqus"), "mm-MPa")
    ours, solution = compare.ours_by_element(deck, "mm-MPa")
    zones = compare.zones_of(spec, solution.mesh, "mm-MPa")
    counts = {zone: sum(1 for z in zones.values() if z == zone) for zone in compare.ZONES}
    assert counts == {"gauge": 144, "free length": 384, "band": 264, "tab line": 24, "gripped": 672}  # 1488 elements, 12 across
    table = tmp_path / "job-every-output.csv"
    with table.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Element", "Layer", "Section Point", "X", "Y", *compare.QUANTITIES])
        for label, values in ours.items():
            for k in range(len(values["S11"])):
                writer.writerow([label, k + 1, "", 0, 0, *(values[q][k] for q in compare.QUANTITIES)])
    result = compare.compare(compare.read_abaqus(table), ours, zones)
    for zone, entry in result.items():
        for q in compare.QUANTITIES:
            assert entry[q]["within_1"] == entry[q]["values"], (zone, q)
    top = from_si(spec.geometry.length, "length", "mm-MPa") - from_si(spec.geometry.tab_length, "length", "mm-MPa")
    rf = tmp_path / "job-every-output-RF.csv"
    with rf.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Node", "X", "Y", "RF1", "RF2"])
        for i, key in enumerate(solution.mesh.node_keys):
            x, y = (from_si(v, "length", "mm-MPa") for v in solution.mesh.xy[i])
            if y >= top - 1e-6:
                writer.writerow([key[1], x, y, 0.0, from_si(solution.reaction[i, 1], "force", "mm-MPa")])
    reaction = compare.reaction(rf, spec, "mm-MPa", solution)
    assert reaction["relative"] == pytest.approx(0.0, abs=1e-12) and reaction["nodes"] > 0


def test_a_tension_spec_asks_for_every_layer_and_the_digest_rule_counts_it_as_output(monkeypatch):
    spec = load_spec(SPEC)
    deck = write_abaqus(build_model(spec))
    assert "*Output, field\n*Element Output, directions=YES\n2, 5, 8, 11, 14, 17, 20, 23\nS, E, SF, SE\n*End Step" in deck
    plain = write_abaqus(build_model(spec.model_copy(update={"output": spec.output.model_copy(update={"abaqus": spec.output.abaqus.model_copy(
        update={"every_layer": False})})})))
    assert "*Element Output" not in plain
    regenerate = load("regenerate_decks", monkeypatch)
    assert regenerate.without_output_requests(deck) == regenerate.without_output_requests(plain)
    assert regenerate.without_output_requests("** a comment\n*Node\n1, 0., 0., 0.") == "*Node\n1, 0., 0., 0."
