"""The three tools of a round trip through Abaqus (ADR-0094, step 4): `tools/abaqus_tools.py` with Abaqus replaced by a stand-in
that leaves the files Abaqus leaves. Its build writes the input file our own writer gives for the model, its run writes a status file,
and its send is the real connector with the two readers that need Abaqus replaced, as in test_anisotropy_connector.py. No Abaqus runs
here: the commands themselves are checked on the founder's machine."""

from __future__ import annotations

import ast
import contextlib
import copy
import json
import re
import sys
from pathlib import Path

import pytest

from anisotropy_fea.femodel import build_model
from anisotropy_fea.spec import load_spec
from anisotropy_fea.write_abaqus import write_abaqus

from test_anisotropy_connector import SPEC, TOOLS, cae_model, connector, job, load, reader_of  # noqa: F401  the fixtures are used by name

COUPON = "IM7-UNT-L1"


@pytest.fixture(scope="module")
def tools():
    before = list(sys.path)
    yield load("abaqus_tools")
    sys.path[:] = before


class StandIn:
    """Abaqus as these tools start it: one command, some files left in the work folder, exit code 0 whatever happened."""

    def __init__(self, tools, connector, data, silent: str | None = None, sta: str | None = None):
        self.tools, self.connector, self.data, self.silent, self.sta, self.calls = tools, connector, data, silent, sta, []
        self.model = build_model(load_spec(SPEC))

    def __call__(self, argv, folder, timeout_s):
        kind = "run" if argv[1].startswith("job=") else "build" if argv[2].endswith("-build.py") else "send"
        self.calls.append((kind, list(argv), Path(folder), timeout_s))
        if kind == self.silent:
            (folder / "abaqus.rpy").write_text("# -*- coding: mbcs -*-\nNameError: name 'mdb' is not defined\n", encoding="utf-8")
            return self.tools.Done(0, "")
        if kind == "build":
            script = (folder / argv[2].split("=", 1)[1]).read_text(encoding="utf-8")
            job_name = re.search(r"^JOB = '(.+)'$", script, re.M).group(1)
            (folder / argv[4].split("=", 1)[1]).write_bytes(b"not a .cae: Abaqus is replaced")
            (folder / f"{job_name}.inp").write_text(write_abaqus(self.model), encoding="utf-8", newline="\n")
            return self.tools.Done(0, f"built: model {job_name}")
        if kind == "run":
            job_name = argv[1].split("=", 1)[1]
            assert argv[2] == f"input={job_name}.inp" and (folder / f"{job_name}.inp").is_file()
            (folder / f"{job_name}.odb").write_bytes(b"not an ODB: Abaqus is replaced")
            (folder / f"{job_name}.sta").write_text(self.sta or " THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n", encoding="utf-8")
            return self.tools.Done(0, f"Abaqus JOB {job_name} COMPLETED")
        with contextlib.chdir(folder):  # the connector is given bare names, as Abaqus gives them from the work folder
            self.connector.run(argv[4:], read_job=lambda path, step, frame, instance: self.data,
                               read_model=lambda path, name: self.connector.model_as_built(cae_model(), "Model-1"))
        return self.tools.Done(0, "")


@pytest.fixture()
def abaqus(tmp_path):
    command = tmp_path / "abaqus.bat"
    command.write_text("the command is replaced\n", encoding="utf-8")
    return command


def args(command: str, folder: Path, abaqus: Path, *extra: str) -> list[str]:
    return [command, str(SPEC), "--folder", str(folder), "--abaqus", str(abaqus), *extra]


def test_three_tools_take_a_coupon_through_abaqus_and_back_and_the_record_lists_each_call(tools, connector, job, abaqus, tmp_path, capsys):
    folder = tmp_path / "work"
    stand_in = StandIn(tools, connector, job.data)
    code = tools.main(args("plan", folder, abaqus, "--tools", "build", "run", "send", "--chosen-by", "template",
                           "--asked", "build this coupon in Abaqus and compare"), runner=stand_in)
    printed = capsys.readouterr()
    assert code == 0, printed.err
    assert "Agrees with ours" in printed.out and "build: done" in printed.out and "send: done" in printed.out
    # each command is fixed: Abaqus's own words, and names our code derived from the spec, as bare names in the one folder
    assert [(kind, argv) for kind, argv, _, _ in stand_in.calls] == [
        ("build", [str(abaqus), "cae", f"noGUI={COUPON}-build.py", "--", f"save={COUPON}.cae"]),
        ("run", [str(abaqus), f"job={COUPON}", f"input={COUPON}.inp", "interactive", "ask_delete=OFF", "cpus=1"]),
        ("send", [str(abaqus), "cae", f"noGUI={TOOLS / 'anisotropy_connector.py'}", "--", f"{COUPON}.odb", "--units", "mm-MPa", "--coupon", COUPON,
                  "--cae", f"{COUPON}.cae"])]
    assert all(where == folder.resolve() for _, _, where, _ in stand_in.calls)
    record = json.loads((folder / "abaqus-tools.json").read_text(encoding="utf-8"))
    assert record["coupon"] == COUPON and record["units"] == "mm-MPa" and record["spec"]["name"] == SPEC.name and len(record["spec"]["sha256"]) == 64
    assert [(c["tool"], c["outcome"], c["chosen_by"], c["asked"]) for c in record["calls"]] == [
        (tool, "done", "template", "build this coupon in Abaqus and compare") for tool in ("build", "run", "send")]
    assert [c["command"] for c in record["calls"]] == [argv for _, argv, _, _ in stand_in.calls]
    for entry in record["calls"]:
        assert entry["started"].endswith("Z") and entry["seconds"] >= 0 and entry["files"]
        assert all(len(facts["sha256"]) == 64 and facts["bytes"] > 0 for facts in entry["files"].values())
    assert set(record["calls"][0]["files"]) == {f"{COUPON}-build.py", f"{COUPON}.cae", f"{COUPON}.inp"}
    assert record["calls"][0]["facts"]["elements"] == 1488 and record["calls"][0]["facts"]["plies"] == 8
    sent = record["calls"][2]
    assert sent["verdict"] == "agrees" and sent["facts"]["model_as_built"] and sent["facts"]["rows"] == job.rows
    assert set(sent["files"]) == {f"{COUPON}-anisotropy.zip", f"{COUPON}-comparison.json", "ours/ours-every-output.csv", f"ours/{COUPON}-abaqus.inp"}
    comparison = json.loads((folder / f"{COUPON}-comparison.json").read_text(encoding="utf-8"))
    assert comparison["verdict"] == "agrees" and comparison["model"]["same"] is True
    assert tools.main(["state", str(SPEC), "--folder", str(folder)]) == 0 and "the round trip is done" in capsys.readouterr().out


def test_the_state_names_what_is_done_and_what_a_chooser_is_told(tools, tmp_path, capsys):
    assert tools.main(["state", str(SPEC), "--folder", str(tmp_path / "empty"), "--json"]) == 0
    told = json.loads(capsys.readouterr().out)
    assert told["state"] == {"built": False, "ran": False, "sent": False, "next": "build"} and told["coupon"] == COUPON
    assert [tool["name"] for tool in told["tools"]] == ["build", "run", "send"] and all(tool["description"] for tool in told["tools"])
    assert not (tmp_path / "empty").exists()  # asking changes nothing


def test_a_chain_with_a_gap_or_a_step_already_done_is_refused_whole_and_nothing_runs(tools, connector, job, abaqus, tmp_path, capsys):
    folder = tmp_path / "work"
    stand_in = StandIn(tools, connector, job.data)
    assert tools.main(args("plan", folder, abaqus, "--tools", "build", "send"), runner=stand_in) == 2
    assert "send: needs run first" in capsys.readouterr().err and stand_in.calls == [] and not folder.exists()
    assert tools.main(args("run", folder, abaqus), runner=stand_in) == 2 and "run: needs build first" in capsys.readouterr().err
    assert tools.main(args("build", folder, abaqus), runner=stand_in) == 0
    before = {path.name: path.read_bytes() for path in folder.iterdir() if path.suffix in (".cae", ".inp", ".py")}
    assert tools.main(args("plan", folder, abaqus, "--tools", "build", "run"), runner=stand_in) == 2
    assert "build: already done in this folder" in capsys.readouterr().err and [kind for kind, *_ in stand_in.calls] == ["build"]
    assert {path.name: path.read_bytes() for path in folder.iterdir() if path.suffix in (".cae", ".inp", ".py")} == before
    assert tools.plan_problems(["mesh"], tools.state_of(tools.session_of(SPEC, folder)[0])) == ["'mesh' is not one of the tools: build, run, send"]
    assert tools.plan_problems([], {"built": False, "ran": False, "sent": False}) == ["no tool was chosen"]
    with pytest.raises(SystemExit):  # the command line takes the three names and no other
        tools.main(args("plan", folder, abaqus, "--tools", "build; del"), runner=stand_in)


def test_abaqus_cae_ending_with_nothing_written_is_a_refusal_with_its_replay_file_and_the_chain_stops(tools, connector, job, abaqus, tmp_path, capsys):
    folder = tmp_path / "work"
    stand_in = StandIn(tools, connector, job.data, silent="build")
    assert tools.main(args("plan", folder, abaqus, "--tools", "build", "run", "send"), runner=stand_in) == 2
    said = capsys.readouterr().err
    assert f"Abaqus/CAE ended without writing {COUPON}.cae and {COUPON}.inp" in said and "abaqus.rpy: NameError: name 'mdb' is not defined" in said
    assert [kind for kind, *_ in stand_in.calls] == ["build"]  # exit code 0 is not taken for a model
    record = json.loads((folder / "abaqus-tools.json").read_text(encoding="utf-8"))
    assert [(c["tool"], c["outcome"]) for c in record["calls"]] == [("build", "refused")] and record["calls"][0]["problems"]


def test_a_job_abaqus_did_not_complete_is_refused_with_what_abaqus_wrote(tools, connector, job, abaqus, tmp_path, capsys):
    folder = tmp_path / "work"
    stand_in = StandIn(tools, connector, job.data, sta=" THE ANALYSIS HAS NOT BEEN COMPLETED\n")
    assert tools.main(args("plan", folder, abaqus, "--tools", "build", "run", "send"), runner=stand_in) == 2
    assert "The analysis has not been completed" in capsys.readouterr().err and [kind for kind, *_ in stand_in.calls] == ["build", "run"]
    assert tools.state_of(tools.session_of(SPEC, folder)[0]) == {"built": True, "ran": False, "sent": False, "next": "run"}


def test_a_bundle_that_differs_from_ours_ends_with_exit_code_one_and_says_where(tools, connector, job, abaqus, tmp_path, capsys):
    data = copy.deepcopy(job.data)
    for (element, point), (components, invariants) in list(data["stress"].items()):
        if point % 3 == 2:  # every layer's middle point: S11 two percent off
            data["stress"][(element, point)] = ((components[0] * 1.02, *components[1:]), invariants)
    folder = tmp_path / "work"
    assert tools.main(args("plan", folder, abaqus, "--tools", "build", "run", "send"), runner=StandIn(tools, connector, data)) == 1
    printed = capsys.readouterr().out
    assert "Differs from ours" in printed and "NOT MET" in printed
    record = json.loads((folder / "abaqus-tools.json").read_text(encoding="utf-8"))
    assert record["calls"][2]["outcome"] == "done" and record["calls"][2]["verdict"] == "differs"  # the tool did its work: the answer is the verdict


def test_what_could_not_go_into_a_command_is_refused_before_anything_is_started(tools, connector, job, abaqus, tmp_path, monkeypatch, capsys):
    stand_in = StandIn(tools, connector, job.data)
    assert tools.main(args("build", tmp_path / "a&b", abaqus), runner=stand_in) == 2
    assert "holds &" in capsys.readouterr().err
    assert tools.main(args("build", tmp_path / "work", tmp_path / "missing.bat"), runner=stand_in) == 2
    assert "Abaqus command not found" in capsys.readouterr().err
    monkeypatch.setattr(tools, "find_abaqus", lambda abaqus: None)
    assert tools.main(["build", str(SPEC), "--folder", str(tmp_path / "work")], runner=stand_in) == 2
    assert "Abaqus not found" in capsys.readouterr().err
    assert [path.name for path in (tmp_path / "work").iterdir()] == ["abaqus-tools.json"]  # the refusals are recorded, and nothing else is written
    assert [c["outcome"] for c in json.loads((tmp_path / "work" / "abaqus-tools.json").read_text(encoding="utf-8"))["calls"]] == ["refused", "refused"]
    assert tools.main(["state", str(tmp_path / "no-such.toml"), "--folder", str(tmp_path / "work")]) == 2
    monkeypatch.setattr(tools, "cae_facts", lambda model: {"model": "IM7 & del", "job": "ok", "units": "mm-MPa", "element": "S4"})
    assert tools.main(args("build", tmp_path / "work", abaqus), runner=stand_in) == 2
    assert "the model name 'IM7 & del' cannot go into a command" in capsys.readouterr().err and stand_in.calls == []


def test_the_tools_start_abaqus_without_a_shell_and_run_no_text(tools):
    tree = ast.parse((TOOLS / "abaqus_tools.py").read_text(encoding="utf-8"))
    names = {node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "") for node in ast.walk(tree) if isinstance(node, ast.Call)}
    assert not names & {"system", "popen", "Popen", "exec", "eval", "check_output", "check_call", "getoutput"}
    keywords = [(k.arg, getattr(k.value, "value", None)) for node in ast.walk(tree) if isinstance(node, ast.Call) for k in node.keywords]
    assert ("shell", True) not in keywords
