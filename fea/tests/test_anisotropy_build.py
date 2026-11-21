"""The coupon as data, and the connector's own code that builds it (ADR-0094 amendment 4). Three pieces are set side by side on
the public D3039 check: the build script our writer writes (`write_cae_script`), the data the site reads from that script's head
(`api/src/anisotropy_api/abaqus_coupon.py`, loaded here by its path), and what `tools/anisotropy_build.py` asks Abaqus/CAE for from
that data. The script and the builder run against the same stand-in for Abaqus, which records every call, and the two lists of calls
must be the same. No Abaqus runs here: that Abaqus/CAE takes the calls is checked where Abaqus is installed."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from anisotropy_fea.write_cae_script import cae_facts, write_cae_script
from test_write_cae_script import Recorder, calls, run, with_spec
from test_write_cae_script import model as coupon  # noqa: F401  the public D3039 check as a model

TOOLS = Path(__file__).parents[1] / "tools"
API = Path(__file__).parents[2] / "api" / "src" / "anisotropy_api"


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem + "_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return load(TOOLS / "anisotropy_build.py")


@pytest.fixture(scope="module")
def site():
    return load(API / "abaqus_coupon.py")


def as_sent(site, model, name: str = "IM7-UNT-L1") -> dict:
    """The coupon as the connector receives it: read from the build script by the site's code, and through JSON."""
    return json.loads(json.dumps(site.coupon_data(write_cae_script(model), name)))


class Constants(ModuleType):
    """Abaqus's symbolic constants: each stands for its own name, as in the recorder's run of the script."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return name


def built(builder, data: dict, monkeypatch, taken=None):
    """Build from the data with Abaqus's modules replaced: (what `build` returned, every call it made, in order)."""
    log: list = []
    taken = taken or {}
    abaqus, cae, mesh, regions = (ModuleType(n) for n in ("abaqus", "caeModules", "mesh", "regionToolset"))
    abaqus.mdb = Recorder(log, "mdb", taken)
    mesh.ElemType = Recorder(log, "mesh.ElemType", taken)
    regions.Region = Recorder(log, "regionToolset.Region", taken)
    for module in (abaqus, Constants("abaqusConstants"), cae, mesh, regions):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    return builder.build(data), log


def plain(log: list) -> list:
    """The calls as text, an argument that is one of Abaqus's objects by the path that led to it; named arguments in one order."""
    return [(path, repr(args), sorted((name, repr(value)) for name, value in kwargs.items())) for path, args, kwargs in log]


def variants(model) -> dict:
    spec = model.spec
    coupled = spec.grips.model_copy(update={"kind": "coupling"})
    return {
        "nodal grips on the tabs": model,
        "coupled grips": with_spec(model, grips=coupled),
        "coupled grips pulled by a force": with_spec(model, grips=coupled, loading=spec.loading.model_copy(update={"control": "force", "value": 5000.0})),
        "grips on the end rows": with_spec(model, grips=spec.grips.model_copy(update={"region": "line"})),
        "fewer lines": with_spec(model, mesh=spec.mesh.model_copy(update={"y_partitions": [0.056, 0.194], "y_seeds": [28, 68, 28]})),
        "reduced integration": with_spec(model, output=spec.output.model_copy(update={"abaqus": spec.output.abaqus.model_copy(update={"element": "S4R"})})),
    }


def test_the_data_is_the_literals_at_the_head_of_the_build_script_and_nothing_of_its_code(site, coupon):  # noqa: F811
    text = write_cae_script(coupon)
    data = site.coupon_data(text, "IM7-UNT-L1")
    facts = cae_facts(coupon)
    assert data["format"] == "anisotropy-coupon/1" and data["coupon"] == "IM7-UNT-L1" and set(data) == {"format", "coupon", *site.FIELDS.values()}
    assert (data["model"], data["job"], data["units"], data["element"], data["description"]) == ("IM7-UNT-L1", "IM7-UNT-L1", "mm-MPa", "S4", facts["description"])
    assert (data["width"], data["length"], data["lines"], data["rows"], data["columns"]) == (25.0, 250.0, [56.0, 112.5, 137.5, 194.0], [28, 28, 12, 28, 28], 12)
    assert data["plies"] == [["Ply-1", 0.18288, 45.0], ["Ply-2", 0.18288, 0.0], ["Ply-3", 0.18288, -45.0], ["Ply-4", 0.18288, 90.0]] and data["symmetric"] is True
    assert data["boundaries"] == [["Grip-Bottom", [0.0] * 6], ["Grip-Top", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]]]
    json.dumps(data)  # numbers, text, true, false, null and lists of them
    # every literal the script states is a field, so the writer cannot grow a constant that the data silently lacks
    stated = {node.targets[0].id for node in ast.parse(text).body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
    assert stated - {"ELEMENT", "SAVE"} == set(site.FIELDS)

    # the script is read and never run: code in it does nothing, and a script that is not ours or not whole gives no answer
    ran = text.replace("\nUNITS = ", "\nopen('ran.txt', 'w')\nimport os\nos.system('never')\nUNITS = ")
    assert site.coupon_data(ran, "IM7-UNT-L1") == data and not Path("ran.txt").exists()
    for wrong, why in ((text.replace("# Built by anisotropy_fea", "# Built by someone"), "not a build script Anisotropy wrote"),
                       ("import os\nos.system('calc')\n", "not a build script Anisotropy wrote"),
                       (text.replace("\nPLIES = ", "\nSTACK = "), "does not state PLIES"),
                       (text.replace("\nWIDTH = 25.", "\nWIDTH = __import__('os').getcwd()"), "WIDTH is not a literal"),
                       (text.replace("\nWIDTH = 25.", "\nWIDTH = {1, 2}"), "kind set"),
                       (text.replace("\nUNITS = ", "\nUNITS = ((((\n"), "cannot be read"),
                       (text + "#" * site.MAX_SCRIPT_BYTES, "not a build script Anisotropy wrote")):
        with pytest.raises(site.NotABuildScript, match=why):
            site.coupon_data(wrong, "IM7-UNT-L1")
    tree = ast.parse((API / "abaqus_coupon.py").read_text(encoding="utf-8"))
    imported = {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names} | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imported == {"__future__", "ast"}


def test_the_connector_asks_abaqus_cae_for_what_the_build_script_asks_call_for_call(builder, site, coupon, monkeypatch, capsys):  # noqa: F811
    for what, model in variants(coupon).items():
        script = [call for call in plain(run(write_cae_script(model), monkeypatch)) if not call[0].endswith((".keys", ".nodes", ".elements"))]
        done, log = built(builder, as_sent(site, model), monkeypatch)
        assert plain(log) == script and len(script) > 40, what
        assert done == {"model": "IM7-UNT-L1", "job": "IM7-UNT-L1", "nodes": 7, "elements": 7, "element": cae_facts(model)["element"], "units": "mm-MPa"}
        assert not calls(log, "saveAs") and not calls(log, "save") and not calls(log, "writeInput") and not calls(log, "submit")
    capsys.readouterr()
    # in the model's own units too: the numbers go as the script states them
    done, log = built(builder, as_sent(site, coupon), monkeypatch)
    si = json.loads(json.dumps(site.coupon_data(write_cae_script(coupon, "m-Pa"), "IM7-UNT-L1")))
    assert built(builder, si, monkeypatch)[0]["units"] == "m-Pa" and si["width"] == 0.025


def test_a_name_that_is_taken_is_refused_before_anything_is_added(builder, site, coupon, monkeypatch):  # noqa: F811
    data = as_sent(site, coupon)
    for taken, words in (({"mdb.models": ["IM7-UNT-L1"]}, "a model named IM7-UNT-L1 is already in this session"),
                         ({"mdb.jobs": ["IM7-UNT-L1"]}, "a job named IM7-UNT-L1 is already in this session")):
        log: list = []
        monkeypatch.setattr(Recorder, "__call__", lambda self, *args, _log=log, **kwargs: _log.append(self._path) or self)
        with pytest.raises(RuntimeError, match=words):
            built(builder, data, monkeypatch, taken=taken)
        assert log == []
        monkeypatch.undo()


def changed(data: dict, **fields) -> dict:
    other = copy.deepcopy(data)
    other.update(fields)
    return other


def test_data_is_read_as_hostile_and_every_reason_is_given(builder, site, coupon, monkeypatch):  # noqa: F811
    data = as_sent(site, coupon)
    checked = builder.check(data)
    assert checked["lines"] == (56.0, 112.5, 137.5, 194.0) and checked["sets"][0] == ("Tab-Bottom", "faces", ((12.5, 28.0),))
    assert builder.check(json.loads(json.dumps(checked))) == checked == builder.check(checked)  # what is checked is itself a coupon, as it is and through JSON
    for model in variants(coupon).values():
        builder.check(as_sent(site, model))
    assert builder.parse(json.dumps(data).encode("utf-8")) == checked

    refused = {
        "not one JSON object": [data],
        "does not say it is anisotropy-coupon/1": changed(data, format="anisotropy-coupon/2"),
        "it has no plies": {k: v for k, v in data.items() if k != "plies"},
        "a field this connector does not know, 'script'": changed(data, script="import os"),
        "coupon is not a plain name": changed(data, coupon="..\\..\\Startup\\x"),
        "units is not one of mm-MPa or m-Pa": changed(data, units="in-psi", description=data["description"].replace("mm-MPa", "in-psi")),
        "model is not a name Abaqus/CAE takes": changed(data, model="x'); import os; ('"),
        "job is not a name Abaqus/CAE takes": changed(data, job="a" * 39),
        "material is not a plain name": changed(data, material="IM7'\n"),
        "description is not the line Anisotropy writes": changed(data, description="My own coupon"),
        "description says the units m-Pa and units says mm-MPa": changed(data, description=data["description"].replace("mm-MPa", "m-Pa")),
        "width and length are not two positive numbers": changed(data, width=-25.0),
        "lines are not in rising order": changed(data, lines=[56.0, 194.0, 137.5, 112.5]),
        "bands are not the stretches between the lines": changed(data, bands=data["bands"][:-1]),
        "rows is not one count of elements for each band": changed(data, rows=[28, 28, 12, 28, 0]),
        "columns is not a count of elements": changed(data, columns=True),
        "the mesh has more than 2000000 elements": changed(data, columns=20000),
        "element is not one of S4 or S4R": changed(data, element="__class__"),
        "elastic is not six numbers": changed(data, elastic=[1.0, 2.0, "3", 4.0, 5.0, 6.0]),
        "fail_stress is neither seven numbers nor null": changed(data, fail_stress=[1.0] * 6),
        "symmetric is not true or false": changed(data, symmetric=1),
        "plies is not a list of 1 to 1000 plies": changed(data, plies=[["Ply-1", 0.0, 45.0]]),
        "two plies have one name": changed(data, plies=[["Ply-1", 0.2, 45.0], ["Ply-1", 0.2, 0.0]]),
        "integration_points is not a count": changed(data, integration_points=3.0),
        "section_points is not a list of section point numbers": changed(data, section_points=[]),
        "sets is not a list of sets": changed(data, sets=[["Gauge", "nodes", [[12.5, 125.0]]]]),
        "points is not a list of reference points": changed(data, points=[["RF", [1.0]]]),
        "two sets or reference points have one name": changed(data, points=[["Gauge", [1.0, 2.0]]]),
        "the coupling Grip does not join a reference point of this coupon to a set of it": changed(data, couplings=[["Grip", "Gauge", "Gauge"]]),
        "boundaries is not a list of a set and six values": changed(data, boundaries=[["Grip-Top", [0.0] * 5]]),
        "Elsewhere is held or loaded and is not a set or a reference point": changed(data, boundaries=[["Elsewhere", [0.0] * 6]]),
        "loads is not a list of loads": changed(data, loads=[["Pull-1", "Grip-Top", 4, 5000.0]]),
        "loads is not a list of loads, each a name": changed(data, loads=[["Pull-1", "Grip-Top", 2.0, 5000.0]]),
    }
    for why, wrong in refused.items():
        with pytest.raises(builder.NotACoupon) as refusal:
            builder.check(wrong)
        assert why in str(refusal.value), why
        with pytest.raises(builder.NotACoupon):
            built(builder, wrong, monkeypatch)  # and nothing unchecked reaches Abaqus, whoever calls
    for value in (float("inf"), float("nan"), 1e31, 10 ** 400, "25", None, [25.0], True):
        with pytest.raises(builder.NotACoupon, match="width and length"):
            builder.check(changed(data, width=value))
    with pytest.raises(builder.NotACoupon) as refusal:  # every reason at once
        builder.check(changed(data, units="in-psi", columns=0, element="C3D8"))
    assert len(refusal.value.problems) == 4  # the three, and the description that no longer names the units
    for body, why in ((b"\xff\xfe", "it is not JSON"), (b"[" * 100000, "it is not JSON"), (b" " * (builder.MAX_BYTES + 1), "larger than any coupon")):
        with pytest.raises(builder.NotACoupon, match=why):
            builder.parse(body)


def test_a_coupon_file_is_read_from_the_disk_whole_or_not_at_all(builder, site, coupon, tmp_path):  # noqa: F811
    data = as_sent(site, coupon)
    path = tmp_path / "IM7-UNT-L1-coupon.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert builder.read(path) == builder.check(data)
    with pytest.raises(builder.NotACoupon, match="no file at"):
        builder.read(tmp_path / "missing-coupon.json")
    path.write_text("MODEL = 'IM7-UNT-L1'\n", encoding="utf-8")
    with pytest.raises(builder.NotACoupon, match="it is not JSON"):
        builder.read(path)


def test_no_file_of_the_connector_runs_text(builder):
    """No file of the connector holds exec, eval, compile or an import of a name it was given: what runs in the user's Abaqus is the
    connector's own files, which the setup checked, and never text from the site or from a file. What they import is pinned by
    `test_anisotropy_connector.py`: the standard library, Abaqus's own modules and each other."""
    connector = load(TOOLS / "anisotropy_connector.py")
    assert "anisotropy_build.py" in connector.FILES
    for name in connector.FILES:
        path = TOOLS / name if (TOOLS / name).is_file() else TOOLS.parent / "src" / "anisotropy_fea" / name  # `bundle.py` lives in the package
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        assert not called & {"exec", "eval", "compile", "__import__", "execfile"}, name
        named = {node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        assert not named & {"import_module", "system", "popen", "run_path", "run_module"}, name
