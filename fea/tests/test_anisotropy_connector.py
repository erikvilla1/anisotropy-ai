"""The connector that writes a bundle under the user's own Abaqus (ADR-0094, step 2): `tools/anisotropy_connector.py` with the two
readers that need Abaqus replaced. The ODB reader's stand-in gives our own kernel's run of the public D3039 check in the shape
`abaqus_every_output.read` returns; the `.cae` reader is run on objects shaped as Abaqus's scripting interface documents them. No
Abaqus runs here: the two readers themselves are checked on the founder's machine."""

from __future__ import annotations

import ast
import csv
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.bundle import open_bundle
from anisotropy_fea.every_output import write_ours
from anisotropy_fea.femodel import build_model
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.spec import load_spec
from anisotropy_fea.units import from_si
from anisotropy_fea.write_abaqus import write_abaqus

TOOLS = Path(__file__).parents[1] / "tools"
SPEC = paths.CHECKS / "d3039-im7-8552" / "d3039-im7-8552.toml"
INVARIANTS = ("Mises", "Tresca", "Pressure", "Max. Principal", "Mid. Principal", "Min. Principal")


def load(name: str, folder: Path = TOOLS):
    spec = importlib.util.spec_from_file_location(f"test_{name}", folder / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def connector():
    before = list(sys.path)
    yield load("anisotropy_connector")
    sys.path[:] = before  # abaqus_every_output.py puts its own folder first, for its sibling


@pytest.fixture(scope="module")
def upload():
    sys.path.insert(0, str(TOOLS))
    try:
        yield load("abaqus_upload")
    finally:
        sys.path.remove(str(TOOLS))


@pytest.fixture(scope="module")
def job(tmp_path_factory, connector):
    """A finished job as the connector finds it: `Job-1.odb` (a stand-in file) with `Job-1.inp` beside it, our run of the same deck,
    and what Abaqus's ODB reader would return for it."""
    folder = tmp_path_factory.mktemp("job")
    spec = load_spec(SPEC)
    deck = folder / "Job-1.inp"
    deck.write_text(write_abaqus(build_model(spec)), encoding="utf-8", newline="\n")
    (folder / "Job-1.odb").write_bytes(b"not an ODB: the reader is replaced in these tests")
    solution = solve_deck(read_deck(deck, "mm-MPa"))
    write_ours(folder / "ours-every-output.csv", folder / "ours-every-output.json", spec, solution, "mm-MPa", "d3039", "S4", "test")
    with (folder / "ours-every-output.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    connector.load("abaqus_every_output")  # as the connector loads it; it brings its sibling with it
    extract = sys.modules["abaqus_extract_fields"]
    layers = max(int(row["Layer"]) for row in rows)
    points = {}
    for layer in range(1, layers + 1):  # three points a layer, as a deck that lists them gives: the middle one is 3k - 1
        for i, offset in enumerate((-1.0, 0.0, 1.0)):
            fraction = -1.0 + (2 * layer - 1 + offset) / layers
            number = 3 * (layer - 1) + i + 1
            points[number] = extract.parse_section_point(number, f"fraction = {fraction:.6f}, Layer = {layer}")
    stress, strain, centroids = {}, {}, {}
    for row in rows:
        element, layer = int(row["Element"]), int(row["Layer"])
        centroids[element] = (float(row["X"]), float(row["Y"]), 0.0)
        for i in range(3):
            key = (element, 3 * (layer - 1) + i + 1)
            wrong = 0.0 if i == 1 else 1e9  # a value at a layer's face must never be taken for its middle
            stress[key] = ((float(row["S11"]) + wrong, float(row["S22"]), 0.0, float(row["S12"])), {name: float(row[name]) for name in INVARIANTS})
            strain[key] = (float(row["E11"]), float(row["E22"]), 0.0, float(row["E12"]))
    reactions = []
    for i, key in enumerate(solution.mesh.node_keys):
        x, y = (float(from_si(v, "length", "mm-MPa")) for v in solution.mesh.xy[i])
        rf = [float(from_si(v, "force", "mm-MPa")) for v in solution.reaction[i, :2]]
        if any(rf):
            reactions.append([str(key[1]), extract.number(x), extract.number(y), extract.number(rf[0]), extract.number(rf[1])])
    data = {"odb": str(folder / "Job-1.odb"), "solver": "Abaqus/Standard 2025", "created": "Thu Nov 12 10:00:00 2026", "step": "Step-1",
            "frame_index": 1, "frame": "Increment      1: Step Time =    1.000", "instance": "COUPON-1", "points": points, "stress": stress,
            "strain": strain, "centroids": centroids, "components": ("S11", "S22", "S33", "S12"),
            "strain_components": ("E11", "E22", "E33", "E12"), "reactions": reactions}
    return SimpleNamespace(folder=folder, odb=folder / "Job-1.odb", deck=deck, data=data, rows=len(rows), layers=layers)


def reader_of(job, seen: list | None = None):
    def read(path, step, frame, instance):
        if seen is not None:
            seen.append((Path(path).name, step, frame, instance))
        return job.data
    return read


# --- stand-ins for Abaqus/CAE's objects: a repository is a dict, a symbolic constant prints as its name --------------------------------

class Constant:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name


class Nodes(list):
    def getBoundingBox(self):  # noqa: N802  Abaqus's own name
        return {"low": (0.0, 0.0, 0.0), "high": (25.0, 250.0, 0.0)}


class Unset:
    """An Abaqus object whose members raise when read."""

    def __getattr__(self, name):
        raise RuntimeError(f"{name} is not available")


def cae_model(broken: bool = False):
    """A model shaped as Abaqus 2025 gave one on the first trial: a symmetric layup listing half its plies, each angle one of Abaqus's
    choices, a region as a tuple, and a displacement's value on the step's states and not on the boundary condition."""
    ply = lambda name, given, value=0.0: SimpleNamespace(plyName=name, material="IM7-8552", thickness=0.18288, numIntPoints=3,  # noqa: E731
                                                         orientationType=Constant(given), orientationValue=value, angle=0.0,
                                                         axis=Constant("AXIS_3"), suppressed=False, region=Unset())
    layup = SimpleNamespace(symmetric=True, elementType=Constant("SHELL"), offsetType=Constant("MIDDLE_SURFACE"),
                            orientation=SimpleNamespace(orientationType=Constant("SYSTEM"), localCsys=3, axis=Constant("AXIS_3")),
                            plies=[ply("PLY-1", "ANGLE_45"), ply("PLY-2", "ANGLE_0"), ply("PLY-3", "ANGLE_NEG45"), ply("PLY-4", "ANGLE_90"),
                                   ply("PLY-5", "SPECIFY_ORIENT", 30.0), ply("PLY-6", "CSYS")])
    part = SimpleNamespace(space=Constant("THREE_D"), type=Constant("DEFORMABLE_BODY"), faces=[1, 2, 3], edges=[0] * 10, vertices=[0] * 8,
                           nodes=Nodes(range(377)), elements=[SimpleNamespace(type=Constant("S4R"))] * 336,
                           features={"Shell planar-1": 1, "Partition face-1": 2}, sets={"Gauge": 1}, surfaces={},
                           compositeLayups={"LAYUP-1": layup}, sectionAssignments=[])
    elastic = SimpleNamespace(type=Constant("LAMINA"), table=((161000.0, 11380.0, 0.32, 5170.0, 5170.0, 3980.0),), failStress=None)
    pull = SimpleNamespace(u1=0.0, u2=1.0, u1State=Constant("UNSET"), u2State=Constant("SET"), amplitudeState=Constant("UNSET"))
    asked = SimpleNamespace(variables=("S", "E", "RF"), variablesState=Constant("SET"), frequency=1)
    step = SimpleNamespace(previous="Initial", nlgeom=Constant("OFF"), timePeriod=1.0, description="",
                           boundaryConditionStates={"Pull": pull}, loadStates={}, fieldOutputRequestStates={"F-Output-1": asked},
                           historyOutputRequestStates=Unset() if broken else {})
    initial = SimpleNamespace(boundaryConditionStates={}, loadStates={}, fieldOutputRequestStates={}, historyOutputRequestStates={})
    bc = SimpleNamespace(createStepName="Step-1", category=Constant("MECHANICAL"), region=("GRIP-TOP", "Assembly", 1, 4, 0))
    model = SimpleNamespace(
        parts={"Coupon": part}, materials={"IM7-8552": SimpleNamespace(elastic=elastic)}, sections={},
        rootAssembly=SimpleNamespace(instances={"Coupon-1": SimpleNamespace(partName="Coupon", dependent=Constant("ON"), nodes=[], elements=[])},
                                     sets={"Top": 1, "Bottom": 2}, surfaces={}, referencePoints={}),
        steps={"Initial": initial, "Step-1": step}, boundaryConditions={"Pull": bc, "Hold": SimpleNamespace(createStepName="Initial")},
        loads={}, constraints={}, fieldOutputRequests={"F-Output-1": SimpleNamespace(sectionPoints=(2, 5, 8), outputAtPlyMid=True)},
        historyOutputRequests={})
    if broken:
        model.constraints = Unset()
    return model


# --- the bundle --------------------------------------------------------------------------------------------------------------------

def test_one_command_writes_a_bundle_the_format_takes_from_the_job_and_its_input_file(connector, job, capsys):
    seen = []
    assert connector.run([str(job.odb), "--units", "mm-MPa", "--coupon", "d3039-im7-8552"], read_job=reader_of(job, seen)) == 0
    said = capsys.readouterr().out
    out = job.folder / "Job-1-anisotropy.zip"
    assert seen == [("Job-1.odb", None, None, None)] and str(out) in said and "the model as built is not in it" in said
    bundle = open_bundle(out)
    assert set(bundle.files) == {"deck", "every_output", "reactions"}
    assert bundle.files["deck"].path == "model/Job-1.inp" and bundle.read("deck") == job.deck.read_bytes()
    m = bundle.manifest
    assert m["units"] == "mm-MPa" and m["job"] == "Job-1" and m["coupon"] == "d3039-im7-8552"
    assert m["written_by"] == {"connector": connector.CONNECTOR, "abaqus": "Abaqus/Standard 2025", "python": connector.abaqus_python()}
    assert m["results"] == {"solver": "Abaqus/Standard 2025", "created": "Thu Nov 12 10:00:00 2026", "step": "Step-1", "frame_index": 1,
                            "frame": "Increment      1: Step Time =    1.000", "instance": "COUPON-1"}
    assert str(job.folder) not in json.dumps(m)  # no path of the user's machine
    table = list(csv.DictReader(bundle.text("every_output").splitlines()))
    assert len(table) == job.rows and {row["Layer"] for row in table} == {str(k) for k in range(1, job.layers + 1)}
    assert all(abs(float(row["S11"])) < 1e8 for row in table)  # each layer's middle point, never a face's value


def test_the_bundle_the_connector_writes_agrees_with_our_run_of_the_same_deck(connector, upload, job, tmp_path):
    out = tmp_path / "sent.zip"
    assert connector.run([str(job.odb), "--units", "mm-MPa", "--out", str(out)], read_job=reader_of(job)) == 0
    held = upload.check(out)
    assert held["in_scope"] and held["model"] is None and held["every_output"]["rows"] == job.rows
    result = upload.compare(out, job.folder / "ours-every-output.csv", job.deck)
    assert result["verdict"] == "agrees" and result["model"]["compared"] == "item by item"
    assert all(c["met"] for c in result["criteria"] if c["judged"])


def test_the_step_frame_and_instance_asked_for_reach_the_odb_reader(connector, job, tmp_path):
    seen = []
    connector.run([str(job.odb), "--units", "mm-MPa", "--out", str(tmp_path / "b.zip"), "--step", "Step-1", "--frame", "1", "--instance", "COUPON-1"],
                  read_job=reader_of(job, seen))
    assert seen == [("Job-1.odb", "Step-1", 1, "COUPON-1")]


def test_with_a_cae_the_model_as_built_and_its_journal_go_in_and_check_counts_them(connector, upload, job, tmp_path, capsys):
    cae = tmp_path / "coupon.cae"
    cae.write_bytes(b"not a .cae: the reader is replaced")
    (tmp_path / "coupon.jnl").write_text("mdb.Model(name='Model-1')\n# never run by us\n", encoding="utf-8")
    asked = []

    def read_model(path, name):
        asked.append((path.name, name, path.resolve() != cae.resolve(), path.read_bytes()))
        path.write_bytes(b"changed, as Abaqus/CAE changes a .cae it opens")
        return connector.model_as_built(cae_model(), "Model-1")

    out = tmp_path / "with-model.zip"
    assert connector.run([str(job.odb), "--units", "mm-MPa", "--cae", str(cae), "--out", str(out)], read_job=reader_of(job), read_model=read_model) == 0
    assert asked == [("coupon.cae", None, True, b"not a .cae: the reader is replaced")]  # a copy, under the file's own name
    assert cae.read_bytes() == b"not a .cae: the reader is replaced"  # the user's own .cae is never opened
    assert "the model as built is not in it" not in capsys.readouterr().out
    bundle = open_bundle(out)
    assert set(bundle.files) == {"deck", "every_output", "reactions", "model", "journal"}
    assert bundle.files["model"].path == "model/Job-1-model.json" and "never run by us" in bundle.text("journal")
    held = upload.check(out)
    assert held["in_scope"]
    assert held["model"] == {"read": True, "model": "Model-1", "read_by": connector.CONNECTOR,
                             "groups": {"parts": 1, "materials": 1, "sections": 0, "steps": 2, "boundary_conditions": 2, "loads": 0,
                                        "constraints": 0, "field_output_requests": 1, "history_output_requests": 0},
                             "layups": [{"name": "LAYUP-1", "plies": 12}], "not_read": []}
    upload.print_check(held)
    assert "the model as built: Model-1: 1 parts, 1 materials" in capsys.readouterr().out


def test_the_model_reader_writes_what_abaqus_gives_as_plain_values_and_names_what_it_could_not_read(connector):
    model = connector.model_as_built(cae_model(broken=True), "Model-1")
    json.dumps(model, allow_nan=False)  # plain values only
    part = model["parts"][0]
    assert part["name"] == "Coupon" and part["space"] == "THREE_D" and part["faces"] == 3 and part["cells"] is None
    assert part["nodes"] == 377 and part["elements"] == 336 and part["element_types"] == ["S4R"]
    assert part["box"] == [[0.0, 0.0, 0.0], [25.0, 250.0, 0.0]] and part["features"] == ["Shell planar-1", "Partition face-1"]
    layup = part["layups"][0]
    assert layup["name"] == "LAYUP-1" and layup["symmetric"] is True and layup["orientation"] == {"orientationType": "SYSTEM", "localCsys": 3, "axis": "AXIS_3"}
    assert layup["plies_through_thickness"] == 12  # six listed, mirrored
    # the angle whichever way Abaqus holds it; a ply turned by a coordinate system has none
    assert [(p["plyName"], p["orientationType"], p.get("rotation_deg")) for p in layup["plies"]] == [
        ("PLY-1", "ANGLE_45", 45.0), ("PLY-2", "ANGLE_0", 0.0), ("PLY-3", "ANGLE_NEG45", -45.0), ("PLY-4", "ANGLE_90", 90.0),
        ("PLY-5", "SPECIFY_ORIENT", 30.0), ("PLY-6", "CSYS", None)]
    assert layup["plies"][0]["thickness"] == 0.18288 and "region" not in layup["plies"][0]  # a member Abaqus will not give is left out
    assert model["materials"] == [{"name": "IM7-8552", "elastic": {"type": "LAMINA", "table": [[161000.0, 11380.0, 0.32, 5170.0, 5170.0, 3980.0]]}}]
    step = model["steps"][1]
    assert {key: step[key] for key in ("name", "previous", "nlgeom", "timePeriod")} == {"name": "Step-1", "previous": "Initial", "nlgeom": "OFF", "timePeriod": 1.0}
    # the pull is on the step's state of the boundary condition, and what is asked for on the step's state of the request
    # and a direction left free is null, not the 0.0 Abaqus holds for it, which would read as held at zero
    assert step["boundary_conditions"] == [{"name": "Pull", "u1": None, "u2": 1.0, "u1State": "UNSET", "u2State": "SET", "amplitudeState": "UNSET"}]
    assert step["field_output_requests"] == [{"name": "F-Output-1", "variables": ["S", "E", "RF"], "variablesState": "SET", "frequency": 1}]
    assert step["loads"] == [] and "history_output_requests" not in step
    assert model["boundary_conditions"][0] == {"name": "Pull", "kind": "SimpleNamespace", "createStepName": "Step-1", "category": "MECHANICAL",
                                               "region": ["GRIP-TOP", "Assembly", 1, 4, 0], "region_set": "GRIP-TOP"}
    assert model["field_output_requests"] == [{"name": "F-Output-1", "kind": "SimpleNamespace", "sectionPoints": [2, 5, 8], "outputAtPlyMid": True}]
    assert model["assembly"]["instances"] == [{"name": "Coupon-1", "nodes": 0, "elements": 0, "partName": "Coupon", "dependent": "ON"}]
    assert "constraints" not in model and model["history_output_requests"] == []
    assert [entry.split(":")[0] for entry in model["not_read"]] == ["steps/Step-1/history_output_requests", "constraints"]
    long = connector.plain(Constant("x" * 1000))
    assert len(long) == connector.TEXT_LIMIT + 4 and connector.plain(float("nan")) is None


def test_a_model_file_of_another_shape_is_said_not_read_and_the_comparison_still_takes_the_bundle(upload, tmp_path):
    for text, reason in (("[1, 2]", "not a model of format 1 (found 'list')"), ('{"model_format": 2}', "found 2"), ("{", "is not JSON")):
        path = tmp_path / "m.json"
        path.write_text(text, encoding="utf-8")
        facts = upload.model_facts(path)
        assert facts["read"] is False and reason in facts["reason"]


# --- refusals ----------------------------------------------------------------------------------------------------------------------

def test_what_cannot_be_packed_is_refused_in_one_line_and_nothing_is_written(connector, job, tmp_path, capsys):
    out = tmp_path / "none.zip"
    alone = tmp_path / "Job-9.odb"
    alone.write_bytes(b"")
    for arguments, reason in (
        ([str(tmp_path / "missing.odb"), "--units", "mm-MPa"], "no ODB at"),
        ([str(job.deck), "--units", "mm-MPa"], "no ODB at"),  # an input file is not an ODB
        ([str(alone), "--units", "mm-MPa"], "no input file at"),
        ([str(job.odb), "--units", "mm-MPa", "--journal", str(tmp_path / "missing.jnl")], "no journal at"),
        ([str(job.odb), "--units", "mm-MPa", "--cae", str(tmp_path / "missing.cae")], "no model file at"),
    ):
        assert connector.run([*arguments, "--out", str(out)], read_job=reader_of(job)) == 2
        assert f"refused: {reason}" in capsys.readouterr().err and not out.exists()
    cae = tmp_path / "coupon.cae"
    cae.write_bytes(b"")
    assert connector.run([str(job.odb), "--units", "mm-MPa", "--cae", str(cae), "--out", str(out)], read_job=reader_of(job)) == 2
    assert "reading a .cae needs Abaqus/CAE: run  abaqus cae noGUI=anisotropy_connector.py" in capsys.readouterr().err and not out.exists()
    assert connector.run([str(job.odb), "--units", "mm-MPa", "--out", str(out)]) == 2  # no stand-in: Abaqus's own modules are not here
    assert "refused: this command runs under Abaqus's own Python" in capsys.readouterr().err and not out.exists()
    assert connector.run([str(job.odb), "--out", str(out)], read_job=reader_of(job)) == 2  # the deck system is stated, never inferred
    assert "--units" in capsys.readouterr().err and not out.exists()


def test_the_odb_readers_own_refusal_is_said_as_a_refusal(connector, job, tmp_path, capsys):
    extract = sys.modules["abaqus_extract_fields"]

    def read(path, step, frame, instance):
        raise extract.ExtractError("frame 1 holds no E; its fields are ['S', 'U']")

    assert connector.run([str(job.odb), "--units", "mm-MPa", "--out", str(tmp_path / "b.zip")], read_job=read) == 2
    assert "refused: frame 1 holds no E" in capsys.readouterr().err


def test_our_arguments_are_found_among_abaqus_caes_own_with_the_two_dashes_or_without(connector):
    ours = ["Job-1.odb", "--units", "mm-MPa", "--cae", "coupon.cae"]
    flags = ["ABQcaeK.exe", "-cae", "-noGUI", "-academic", "TEACHING", "-tmpdir", "C:\\temp", "-lmlog", "ON"]
    assert connector.command_line([*flags, "--", *ours]) == ours
    assert connector.command_line([*flags, *ours]) == ours  # Abaqus 2025's launcher drops the two dashes: ours start at the ODB
    assert connector.command_line(["anisotropy_connector.py", "--units", "m-Pa", "Job-1.odb"]) == ["--units", "m-Pa", "Job-1.odb"]  # abaqus python
    with pytest.raises(connector.Refused, match="give the job's .odb first"):
        connector.command_line([*flags, "--units", "mm-MPa"])


def test_under_abaqus_cae_nothing_ends_unsaid_because_its_exit_code_and_its_window_say_nothing(connector, job, tmp_path, monkeypatch, capfd):
    """Abaqus/CAE without its window writes a script's error in abaqus.rpy only and ends with 0 (the first trial): there the
    connector says every ending on the terminal's own stream itself. Elsewhere an unexpected error is raised as it is."""
    def read(path, step, frame, instance):
        raise RuntimeError("an error nobody planned for")

    arguments = [str(job.odb), "--units", "mm-MPa", "--out", str(tmp_path / "b.zip")]
    with pytest.raises(RuntimeError):
        connector.run(arguments, read_job=read)
    monkeypatch.setitem(sys.modules, "abaqus", SimpleNamespace(mdb=object()))
    assert connector.under_cae()
    capfd.readouterr()
    assert connector.run(arguments, read_job=read) == 2
    said = capfd.readouterr().err
    assert "the connector stopped, and no bundle was written" in said and "RuntimeError: an error nobody planned for" in said
    assert connector.run([str(job.odb), "--out", str(tmp_path / "b.zip")], read_job=reader_of(job)) == 2
    assert "--units" in capfd.readouterr().err
    assert connector.run([str(tmp_path / "missing.odb"), "--units", "mm-MPa"], read_job=reader_of(job)) == 2
    assert "refused: no ODB at" in capfd.readouterr().err
    assert connector.run(arguments, read_job=reader_of(job)) == 0
    assert "bundle version 1 of Job-1" in capfd.readouterr().out and (tmp_path / "b.zip").is_file()


# --- what is handed over -----------------------------------------------------------------------------------------------------------

def test_the_connectors_files_import_nothing_beyond_the_standard_library_and_abaqus(connector):
    allowed = set(sys.stdlib_module_names) | {"abaqus", "abaqusConstants", "abaqusGui", "caeModules", "odbAccess", "abaqus_extract_fields"}
    folders = {"bundle.py": TOOLS.parent / "src" / "anisotropy_fea"}
    for name in connector.FILES:
        tree = ast.parse((folders.get(name, TOOLS) / name).read_text(encoding="utf-8"))
        imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        assert imported <= allowed, (name, imported - allowed)


def test_the_zip_to_hand_over_holds_the_connector_whole_and_it_runs_from_that_folder_alone(connector, upload, job, tmp_path):
    handed = tmp_path / "anisotropy-connector.zip"
    assert upload.main(["connector", "--out", str(handed)]) == 0
    with zipfile.ZipFile(handed) as archive:
        assert sorted(archive.namelist()) == sorted(f"anisotropy-connector/{name}" for name in (*connector.FILES, "README.txt"))
        archive.extractall(tmp_path)
    first = handed.read_bytes()
    upload.main(["connector", "--out", str(handed)])
    assert handed.read_bytes() == first  # the same files give the same zip
    folder = tmp_path / "anisotropy-connector"
    notes = (folder / "README.txt").read_text(encoding="utf-8")
    assert "abaqus python anisotropy_connector.py" in notes and "--watch <the folder your jobs run in>" in notes
    assert "abaqus_plugins in your home" in notes and "Plug-ins > Anisotropy" in notes  # the menu is this same folder, copied there
    before = list(sys.path)
    try:
        alone = load("anisotropy_connector", folder)
        assert alone.here() == folder
        out = tmp_path / "from-the-folder.zip"
        assert alone.run([str(job.odb), "--units", "mm-MPa", "--out", str(out)], read_job=reader_of(job)) == 0
        assert Path(sys.modules["anisotropy_bundle"].__file__).parent == folder  # its own copy of the format, not the repository's
    finally:
        sys.path[:] = before
        load("anisotropy_connector")  # the repository's modules again under their names, for the tests after this one
    assert open_bundle(out).manifest["written_by"]["connector"] == connector.CONNECTOR
