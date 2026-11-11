"""tools/abaqus_detect.py (ADR-0089 part 7a): the decks that ask Abaqus which output requests our composite deck may carry."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.write_abaqus import write_abaqus

TOOL = Path(__file__).parents[1] / "tools" / "abaqus_detect.py"


def load(monkeypatch):
    spec = importlib.util.spec_from_file_location("abaqus_detect", TOOL)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def test_each_candidate_is_one_deck_our_deck_with_one_request_more(tmp_path, monkeypatch):
    tool = load(monkeypatch)
    written = tool.decks(tmp_path)
    assert set(written) == {"field-points", "sinv", "sp", "tshr", "cfailure", "ep"}
    base = write_abaqus(build_model(load_spec(tool.SPEC)))
    for name, path in written.items():
        text = path.read_text(encoding="utf-8")
        before, extra = text.split("*End Step")[0], text.split("*End Step")[0][len(base.split("*End Step")[0]):]
        assert before.startswith(base.split("*End Step")[0]), name  # the deck itself is untouched
        assert extra.strip(), name
    sinv = written["sinv"].read_text(encoding="utf-8")
    assert "*El Print, elset=Probe-centre, position=CENTROIDAL\n1, 2, 3, " in sinv and "\nSINV\n*End Step" in sinv  # every point of 8 layers
    field = written["field-points"].read_text(encoding="utf-8")
    assert "*Element Output, directions=YES\n2, 5, 8, 11, 14, 17, 20, 23\nS, E, SF, SE\n*End Step" in field  # the middle of every layer


def test_without_run_nothing_is_started(tmp_path, monkeypatch, capsys):
    tool = load(monkeypatch)
    assert tool.main(["--out", str(tmp_path)]) == 0
    assert capsys.readouterr().out.count("written") == 6
