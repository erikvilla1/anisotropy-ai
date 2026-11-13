"""The script that builds a coupon in Abaqus/CAE as a native model (ADR-0094, step 3): `write_cae_script` on the public D3039 check. The
script is run here against stand-ins for Abaqus's modules that record every call, so what it would ask Abaqus/CAE for is read back and
set beside the deck written from the same model. No Abaqus runs here: that the calls are ones Abaqus/CAE takes, and that the model they
build gives our deck's answer, is checked on the founder's machine."""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus
from anisotropy_fea.write_cae_script import CaeScriptError, cae_facts, cae_name, write_cae_script

TOOLS = Path(__file__).parents[1] / "tools"
SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"


class Recorder:
    """Any object of Abaqus's: every call is written to the log with the path that led to it, and gives another one back."""

    def __init__(self, log: list, path: str, taken: dict):
        self.__dict__.update(_log=log, _path=path, _taken=taken)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return Recorder(self._log, f"{self._path}.{name}", self._taken)

    def __call__(self, *args, **kwargs):
        self._log.append((self._path, args, kwargs))
        return Recorder(self._log, f"{self._path}()", self._taken)

    def __getitem__(self, key):
        return Recorder(self._log, f"{self._path}[{key!r}]", self._taken)

    def __delitem__(self, key):
        self._log.append((f"{self._path}.__delitem__", (key,), {}))

    def __len__(self):
        return 7

    def __repr__(self):
        return self._path

    def keys(self):
        return list(self._taken.get(self._path, ()))


def run(text: str, monkeypatch, argv=(), taken=None) -> list:
    """Run the script with Abaqus's modules replaced, and give back every call it made, in order."""
    tree = ast.parse(text)
    log: list = []
    taken = taken or {}
    abaqus, constants, cae, mesh, regions = (ModuleType(n) for n in ("abaqus", "abaqusConstants", "caeModules", "mesh", "regionToolset"))
    abaqus.mdb = Recorder(log, "mdb", taken)
    abaqus.session = Recorder(log, "session", taken)
    for node in ast.walk(tree):  # a symbolic constant stands for its own name
        if isinstance(node, ast.Name) and node.id.isupper():
            setattr(constants, node.id, node.id)
    mesh.ElemType = Recorder(log, "mesh.ElemType", taken)
    regions.Region = Recorder(log, "regionToolset.Region", taken)
    for module in (abaqus, constants, cae, mesh, regions):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(sys, "argv", ["ABQcaeK.exe", "-cae", "-noGUI", *argv])
    exec(compile(tree, "build.py", "exec"), {"__name__": "__main__"})
    return log


def calls(log: list, name: str) -> list:
    return [(args, kwargs) for path, args, kwargs in log if path.endswith("." + name)]


@pytest.fixture(scope="module")
def model():
    return build_model(load_spec(SPEC))


def with_spec(model, **changes):
    return build_model(model.spec.model_copy(update=changes))


def test_the_script_is_plain_python_of_both_languages_inside_abaqus_and_the_same_text_every_time(model):
    text = write_cae_script(model)
    assert text == write_cae_script(build_model(load_spec(SPEC))) and text.isascii() and text.endswith("\n")
    tree = ast.parse(text)
    assert tree.body[0].module == "__future__"  # Python 2.7 inside Abaqus before 2024: print as a function, and nothing newer than it reads
    newer = (ast.JoinedStr, ast.AnnAssign, ast.NamedExpr, ast.AsyncFunctionDef, ast.Starred)
    assert not [node for node in ast.walk(tree) if isinstance(node, newer) and not (isinstance(node, ast.Starred) and isinstance(node.ctx, ast.Load))]
    assert not [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.arg)) and getattr(node, "annotation", None) is not None]
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported == {"__future__", "os", "sys", "traceback", "abaqus", "abaqusConstants", "caeModules", "mesh", "regionToolset"}


def test_what_the_script_asks_abaqus_cae_for_is_the_coupon_the_deck_is_written_from(model, monkeypatch):
    log = run(write_cae_script(model), monkeypatch)
    spec, mm = model.spec, lambda v: float(from_si(v, "length", "mm-MPa"))
    assert calls(log, "Model") == [((), {"name": "IM7-UNT-L1", "description": cae_facts(model)["description"]})]
    assert calls(log, "rectangle") == [((), {"point1": (0.0, 0.0), "point2": (25.0, 250.0)})]
    assert [kwargs["offset"] for _, kwargs in calls(log, "DatumPlaneByPrincipalPlane")] == [56.0, 112.5, 137.5, 194.0]
    assert [kwargs["faces"]._log is log for _, kwargs in calls(log, "PartitionFaceByDatumPlane")] == [True] * 4
    # the seeds divide each stretch evenly: the rows they give are our mesh's rows
    seeds = [kwargs["number"] for _, kwargs in calls(log, "seedEdgeByNumber")]
    assert seeds == [12, 28, 28, 12, 28, 28]
    lines = [0.0, 56.0, 112.5, 137.5, 194.0, 250.0]
    rows = np.unique(np.concatenate([np.linspace(a, b, n + 1) for a, b, n in zip(lines, lines[1:], seeds[1:])]))
    assert np.allclose(rows, np.unique(np.round([mm(y) for y in model.mesh.xy[:, 1]], 9)), atol=1e-9)
    assert sum(seeds[1:]) * seeds[0] == model.mesh.element_count == 1488
    assert calls(log, "ElemType") == [((), {"elemCode": "S4", "elemLibrary": "STANDARD"})]
    assert calls(log, "setMeshControls")[0][1]["technique"] == "STRUCTURED" and len(calls(log, "generateMesh")) == 1
    # the material and the layup, number for number what the deck's lines hold
    deck = write_abaqus(model).splitlines()
    elastic = [float(v) for v in deck[deck.index("*Elastic, type=LAMINA") + 1].split(",")]
    strengths = [float(v) for v in deck[deck.index("*Fail Stress") + 1].split(",")]
    assert calls(log, "Elastic") == [((), {"type": "LAMINA", "table": (tuple(elastic),)})]
    assert calls(log, "FailStress") == [((), {"table": (tuple(strengths) + (0.0, 0.0),)})]
    assert calls(log, "CompositeLayup")[0][1]["symmetric"] is True and calls(log, "CompositeLayup")[0][1]["name"] == "Layup-1"
    section = deck.index("*Shell Section, elset=All, composite, orientation=Ori-1, layup=Layup-1, symmetric")
    layers = [[part.strip() for part in line.split(",")] for line in deck[section + 1:section + 5]]
    plies = [kwargs for _, kwargs in calls(log, "CompositePly")]
    assert [(p["plyName"], p["thickness"], p["numIntPoints"], p["material"], p["orientationValue"]) for p in plies] == [
        (name, float(thickness), int(points), material, float(angle)) for thickness, points, material, angle, name in layers]
    assert all(p["orientationType"] == "SPECIFY_ORIENT" and p["thicknessType"] == "SPECIFY_THICKNESS" for p in plies)
    # the layup's axes are the deck's *Orientation: 1 along the length, 2 toward -x, so the normal is +z
    axes = calls(log, "DatumCsysByThreePoints")[0][1]
    one = np.subtract(axes["point1"], axes["origin"])
    two = np.subtract(axes["point2"], axes["origin"]) - np.dot(np.subtract(axes["point2"], axes["origin"]), one) * one
    assert deck[deck.index("*Orientation, name=Ori-1") + 1] == "0., 1., 0., -1., 0., 0."
    assert tuple(one) == (0.0, 1.0, 0.0) and tuple(two) == (-1.0, 0.0, 0.0) and tuple(np.cross(one, two)) == (0.0, 0.0, 1.0)
    assert calls(log, "ReferenceOrientation")[0][1]["orientationType"] == "SYSTEM"
    # the grips are the tabs, held as the deck's *Boundary lines hold them, and the pull is the spec's
    sets = {kwargs["name"]: kwargs for _, kwargs in calls(log, "Set")}
    assert list(sets) == ["Tab-Bottom", "Gauge", "Tab-Top", "Grip-Bottom", "Grip-Top"] and all("faces" in kwargs for kwargs in sets.values())
    found = {args for args, _ in calls(log, "findAt") if len(args[0][0]) == 3}
    assert (((12.5, 28.0, 0.0),),) in found and (((12.5, 222.0, 0.0),),) in found
    held = {kwargs["name"]: [kwargs[k] for k in ("u1", "u2", "u3", "ur1", "ur2", "ur3")] for _, kwargs in calls(log, "DisplacementBC")}
    assert held == {"Grip-Bottom": [0.0] * 6, "Grip-Top": [0.0, mm(spec.loading.value), 0.0, 0.0, 0.0, 0.0]} and held["Grip-Top"][1] == 1.0
    assert deck[deck.index("*Boundary") + 1:deck.index("*Boundary") + 5] == ["Grip-Bottom, 1, 6", "Grip-Top, 1, 1", "Grip-Top, 3, 6", "Grip-Top, 2, 2, 1."]
    assert all(kwargs["createStepName"] == "Step-1" for _, kwargs in calls(log, "DisplacementBC"))
    step = calls(log, "StaticStep")[0][1]
    assert (step["name"], step["nlgeom"], step["timePeriod"], step["initialInc"], step["minInc"], step["maxInc"]) == ("Step-1", "OFF", 1.0, 1.0, 1e-05, 1.0)
    # every ply's middle point is asked for, as the deck's *Element Output asks: what the connector reads on the way back
    request = calls(log, "FieldOutputRequest")[0][1]
    assert request["sectionPoints"] == (2, 5, 8, 11, 14, 17, 20, 23) and request["variables"] == ("S", "E", "SF", "SE")
    assert deck[deck.index("*Element Output, directions=YES") + 1] == "2, 5, 8, 11, 14, 17, 20, 23"
    assert calls(log, "Job") == [((), {"name": "IM7-UNT-L1", "model": "IM7-UNT-L1", "description": cae_facts(model)["description"]})]
    assert not calls(log, "ReferencePoint") and not calls(log, "Coupling") and not calls(log, "ConcentratedForce")


def test_nothing_is_saved_unless_asked_and_never_over_a_file_or_a_model_that_is_there(model, monkeypatch, tmp_path, capsys):
    text = write_cae_script(model)
    log = run(text, monkeypatch)
    assert not calls(log, "saveAs") and not calls(log, "writeInput")
    assert "built: model IM7-UNT-L1" in capsys.readouterr().out
    target = tmp_path / "coupon.cae"
    log = run(text, monkeypatch, argv=["--", f"save={target}"])
    assert calls(log, "saveAs") == [((), {"pathName": str(target)})] and calls(log, "writeInput") == [((), {"consistencyChecking": "OFF"})]
    assert f"saved as {target}, input file IM7-UNT-L1.inp" in capsys.readouterr().out
    target.write_bytes(b"the user's own model")
    with pytest.raises(RuntimeError, match="does not save over a file"):
        run(text, monkeypatch, argv=[f"save={target}"])
    assert target.read_bytes() == b"the user's own model" and "not built" in capsys.readouterr().out
    for taken, words in (({"mdb.models": ["IM7-UNT-L1"]}, "a model named IM7-UNT-L1 is already in this session"),
                         ({"mdb.jobs": ["IM7-UNT-L1"]}, "a job named IM7-UNT-L1 is already in this session")):
        log = []
        with pytest.raises(RuntimeError, match=words):
            log = run(text, monkeypatch, taken=taken)
        assert not calls(log, "Model")
    # a .cae named on the command line for Abaqus itself is not ours to write: only save= is
    assert not calls(run(text, monkeypatch, argv=["database=mine.cae"]), "saveAs")


def test_coupled_grips_are_reference_points_that_carry_the_tabs_and_a_force_pulls_one(model, monkeypatch):
    spec = model.spec
    coupled = with_spec(model, grips=spec.grips.model_copy(update={"kind": "coupling"}))
    log = run(write_cae_script(coupled), monkeypatch)
    assert [kwargs["point"] for _, kwargs in calls(log, "ReferencePoint")] == [(12.5, 0.0, 0.0), (12.5, 250.0, 0.0)]
    assert [(k["name"], k["couplingType"], repr(k["controlPoint"]).split(".")[-1], repr(k["surface"]).split(".")[-1]) for _, k in calls(log, "Coupling")] == [
        ("Grip-Bottom", "KINEMATIC", "sets['RF-Bottom']", "sets['Grip-Bottom']"), ("Grip-Top", "KINEMATIC", "sets['RF-Top']", "sets['Grip-Top']")]
    held = {kwargs["name"]: [kwargs[k] for k in ("u1", "u2", "u3", "ur1", "ur2", "ur3")] for _, kwargs in calls(log, "DisplacementBC")}
    assert held == {"RF-Bottom": [0.0] * 6, "RF-Top": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]}
    forced = with_spec(model, grips=spec.grips.model_copy(update={"kind": "coupling"}),
                       loading=spec.loading.model_copy(update={"control": "force", "value": 5000.0}))
    log = run(write_cae_script(forced), monkeypatch)
    held = {kwargs["name"]: [kwargs[k] for k in ("u1", "u2", "u3", "ur1", "ur2", "ur3")] for _, kwargs in calls(log, "DisplacementBC")}
    assert held == {"RF-Bottom": [0.0] * 6, "RF-Top": [0.0, "UNSET", 0.0, 0.0, 0.0, 0.0]}  # the pulled direction is left free for the force
    force = calls(log, "ConcentratedForce")[0][1]
    assert (force["cf1"], force["cf2"], force["cf3"]) == ("UNSET", 5000.0, "UNSET") and repr(force["region"]).endswith("['RF-Top']")


def test_grips_on_the_end_rows_are_the_end_edges(model, monkeypatch):
    lined = with_spec(model, grips=model.spec.grips.model_copy(update={"region": "line"}))
    log = run(write_cae_script(lined), monkeypatch)
    sets = {kwargs["name"]: sorted(set(kwargs) - {"name"}) for _, kwargs in calls(log, "Set")}
    assert sets["Grip-Bottom"] == ["edges"] and sets["Grip-Top"] == ["edges"] and sets["Gauge"] == ["faces"]


def test_a_coupon_the_script_cannot_draw_is_refused_with_every_reason(model):
    spec = model.spec
    bent = dataclasses.replace(model, spec=spec.model_copy(update={"kind": "three_point_bending"}))
    with pytest.raises(CaeScriptError) as refused:
        write_cae_script(bent)
    assert "the unnotched tension coupon only, not three_point_bending" in refused.value.problems[0]
    forced = with_spec(model, loading=spec.loading.model_copy(update={"control": "force", "value": 5000.0}))
    with pytest.raises(CaeScriptError, match="a force on nodal grips"):
        write_cae_script(forced)
    uneven = with_spec(model, mesh=spec.mesh.model_copy(update={"y_partitions": [0.056, 0.194], "y_seeds": [28, 68, 28]}))
    assert cae_facts(uneven)["rows"] == [28, 68, 28]  # fewer lines, still even between them
    stretched = dataclasses.replace(model, spec=spec.model_copy(update={"mesh": spec.mesh.model_copy(update={"y_partitions": [0.056, 0.194]})}))
    with pytest.raises(CaeScriptError, match="node rows between 0.056 and 0.194 m are not evenly spaced"):
        cae_facts(stretched)  # our mesh changes its spacing at a line the script would not draw


def test_a_name_abaqus_cae_takes():
    assert cae_name("IM7-UNT-L1", "Coupon") == "IM7-UNT-L1" and cae_name("7781 / fabric (dry)", "Coupon") == "Coupon-7781-fabric-dry"
    assert cae_name("", "Coupon") == "Coupon" and len(cae_name("A" * 60, "Coupon")) == 38


def test_the_command_writes_the_script_or_refuses_with_the_reason(tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("abaqus_build_script", TOOLS / "abaqus_build_script.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    out = tmp_path / "build.py"
    assert tool.main([str(SPEC), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == write_cae_script(build_model(load_spec(SPEC))) and "builds model IM7-UNT-L1" in capsys.readouterr().out
    assert tool.main([str(tmp_path / "missing.toml"), "--out", str(out)]) == 2 and "refused" in capsys.readouterr().err
