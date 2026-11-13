"""The Anisotropy menu in Abaqus/CAE (ADR-0094, step 8): `tools/anisotropy_plugin.py` registers two entries and
`tools/anisotropy_menu.py` is what they do. Abaqus's modules are replaced: the registration is recorded, the input boxes answer what a
test sets, the session's model database is the stand-in of test_anisotropy_connector.py, and the build script runs against the
recorder of test_write_cae_script.py. No Abaqus runs here: that Abaqus/CAE lists the entries and that its own input boxes and model
objects are these is checked on the founder's machine."""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from anisotropy_fea.bundle import open_bundle
from anisotropy_fea.write_cae_script import write_cae_script
from test_anisotropy_connector import TOOLS, cae_model, connector, job, load, reader_of  # noqa: F401
from test_connector_send import TOKEN, site, token_file  # noqa: F401
from test_connector_watch import put
from test_write_cae_script import Recorder, calls
from test_write_cae_script import model as coupon  # noqa: F401  the public D3039 check as a model


@pytest.fixture
def menu(monkeypatch, tmp_path):
    """The menu's module with the user's home in a folder of the test, and its own connector loaded fresh."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    (tmp_path / "home" / "Downloads").mkdir(parents=True)
    before = list(sys.path)
    spec = importlib.util.spec_from_file_location("anisotropy_menu", TOOLS / "anisotropy_menu.py")  # the name Abaqus/CAE imports it under
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop("anisotropy_connector_of_the_menu", None)
    sys.path[:] = before


def abaqus_of(monkeypatch, text: str = "", answers=None, mdb=None, session=None, taken=None) -> SimpleNamespace:
    """Abaqus's modules for one click: the input boxes give `answers` (None is Cancel) and keep what they were asked; `mdb` and
    `session` are given, or recorders that write every call to `log`."""
    log, asked = [], []
    abaqus, constants, cae, mesh, regions = (ModuleType(n) for n in ("abaqus", "abaqusConstants", "caeModules", "mesh", "regionToolset"))
    abaqus.mdb = mdb if mdb is not None else Recorder(log, "mdb", taken or {})
    abaqus.session = session if session is not None else Recorder(log, "session", taken or {})

    def get_input(prompt, default=""):
        asked.append((prompt, default))
        return answers(default) if callable(answers) else answers

    def get_inputs(fields, label="", dialogTitle=""):  # noqa: N803  Abaqus's own name
        asked.append((tuple(fields), label, dialogTitle))
        return answers(dict(fields)) if callable(answers) else answers
    abaqus.getInput, abaqus.getInputs = get_input, get_inputs
    for node in ast.walk(ast.parse(text)):  # a symbolic constant stands for its own name
        if isinstance(node, ast.Name) and node.id.isupper():
            setattr(constants, node.id, node.id)
    mesh.ElemType = Recorder(log, "mesh.ElemType", taken or {})
    regions.Region = Recorder(log, "regionToolset.Region", taken or {})
    for module in (abaqus, constants, cae, mesh, regions):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    return SimpleNamespace(log=log, asked=asked)


def session_of(job_name: str, model_name: str = "IM7-UNT-L1", saved: str = "", shown=None, description: str = ""):
    """A session of Abaqus/CAE with one job created for one model, beside Abaqus's own empty Model-1. `description` is the model's:
    the build script writes its own there, and a model drawn by hand has none."""
    model = cae_model()
    model.description = description
    mdb = SimpleNamespace(jobs={job_name: SimpleNamespace(model=model_name)}, models={"Model-1": SimpleNamespace(), model_name: model},
                          pathName=saved)
    session = SimpleNamespace(currentViewportName="Viewport: 1", viewports={"Viewport: 1": SimpleNamespace(displayedObject=shown)})
    return mdb, session


# --- the registration ----------------------------------------------------------------------------------------------------------------

def test_the_plugin_file_registers_two_entries_under_one_menu_and_each_calls_a_function_the_module_has(menu, monkeypatch):
    registered = []
    toolset = SimpleNamespace(registerKernelMenuButton=lambda **named: registered.append(named))
    gui = ModuleType("abaqusGui")
    gui.getAFXApp = lambda: SimpleNamespace(getAFXMainWindow=lambda: SimpleNamespace(getPluginToolset=lambda: toolset))
    monkeypatch.setitem(sys.modules, "abaqusGui", gui)
    plugin = load("anisotropy_plugin")
    assert [entry["buttonText"] for entry in registered] == ["Anisotropy|Open from Anisotropy...", "Anisotropy|Send to Anisotropy..."]
    for entry in registered:
        assert entry["moduleName"] == "anisotropy_menu" and entry["functionName"].endswith("()")
        assert callable(getattr(menu, entry["functionName"][:-2]))  # what Abaqus/CAE's kernel will call: anisotropy_menu.<function>()
        assert entry["author"] == "Anisotropy" and entry["description"] and set(entry) == {"buttonText", "moduleName", "functionName", "author", "version", "description"}
    assert plugin.VERSION == menu.connector().CONNECTOR.split()[-1]  # the menu and the connector are handed over as one version
    # Abaqus/CAE finds a plug-in by its file's name, and imports it in its window's process, where our other modules are not
    tree = ast.parse((TOOLS / "anisotropy_plugin.py").read_text(encoding="utf-8"))
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)} | {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
    assert imported == {"abaqusGui"} and (TOOLS / "anisotropy_plugin.py").name.endswith("_plugin.py")


# --- Open from Anisotropy --------------------------------------------------------------------------------------------------------------

def test_open_offers_the_newest_build_script_and_builds_it_in_the_session_saving_nothing(menu, coupon, monkeypatch, tmp_path, capsys):  # noqa: F811
    text = write_cae_script(coupon)
    downloads = tmp_path / "home" / "Downloads"
    older, newer = downloads / "old-coupon-build.py", downloads / "IM7-UNT-L1-build.py"
    for age, path in ((200, older), (100, newer)):
        path.write_text(text, encoding="utf-8")
        os.utime(path, (path.stat().st_atime - age, path.stat().st_mtime - age))
    (downloads / "someone-elses-build.py").write_text("print('not ours')\n", encoding="utf-8")  # newest, and never offered
    assert menu.build_scripts([downloads, tmp_path / "missing"]) == [newer, older]
    monkeypatch.chdir(tmp_path)
    there = abaqus_of(monkeypatch, text, answers=lambda default: default)  # OK on what is offered
    menu.open_from_anisotropy()
    assert there.asked == [(menu.OPEN_PROMPT, str(newer))]
    assert [kwargs["name"] for _, kwargs in calls(there.log, "Model")] == ["IM7-UNT-L1"] and calls(there.log, "Job")
    assert not calls(there.log, "saveAs") and not calls(there.log, "writeInput") and not calls(there.log, "save")
    assert [kwargs for _, kwargs in calls(there.log, "setValues") if "displayedObject" in kwargs]  # the new model is put on the screen
    assert "built: model IM7-UNT-L1" in capsys.readouterr().out


def test_open_runs_only_a_script_anisotropy_wrote_and_says_every_other_ending(menu, coupon, monkeypatch, tmp_path, capsys):  # noqa: F811
    text = write_cae_script(coupon)
    ours = tmp_path / "IM7-UNT-L1-build.py"
    ours.write_text(text, encoding="utf-8")
    other = tmp_path / "other.py"
    other.write_text("open('ran.txt', 'w').write('this must never run')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    there = abaqus_of(monkeypatch, text, answers=None)  # Cancel
    menu.open_from_anisotropy()
    assert there.asked == [(menu.OPEN_PROMPT, str(ours))] and there.log == [] and capsys.readouterr().out == ""

    for answer, words in ((f'"{other}"', "other.py is not a build script Anisotropy wrote, so this entry does not run it"),
                          (str(tmp_path / "missing-build.py"), "not opened: no file at"), ("  ", "not opened: name the build script")):
        there = abaqus_of(monkeypatch, text, answers=answer)
        menu.open_from_anisotropy()
        assert words in capsys.readouterr().out and there.log == [] and not (tmp_path / "ran.txt").exists()

    # the script's own refusal, a model of that name already in the session, is said in its words and nothing is built
    there = abaqus_of(monkeypatch, text, answers=str(ours), taken={"mdb.models": ["IM7-UNT-L1"]})
    menu.open_from_anisotropy()
    assert "not built: a model named IM7-UNT-L1 is already in this session" in capsys.readouterr().out and not calls(there.log, "Model")


# --- Send to Anisotropy ----------------------------------------------------------------------------------------------------------------

def test_send_writes_the_bundle_with_the_model_open_in_the_session_and_reads_a_copy_of_the_odb(menu, job, monkeypatch, tmp_path, capsys):  # noqa: F811
    odb = put(tmp_path, job, "Job-1")
    cae = tmp_path / "coupon.cae"
    cae.write_bytes(b"the user's own model")
    cae.with_suffix(".jnl").write_text("# -*- coding: mbcs -*-\nfrom part import *\n", encoding="utf-8")
    mdb, session = session_of("Job-1", saved=str(cae), shown=SimpleNamespace(path=str(odb)))
    monkeypatch.chdir(tmp_path)
    seen = []

    def read(path, step, frame, instance):
        seen.append((Path(path), Path(path).is_file(), Path(path).read_bytes() == odb.read_bytes()))
        return job.data
    monkeypatch.setattr(menu, "reading_a_copy", lambda _none, original=menu.reading_a_copy: original(read))
    there = abaqus_of(monkeypatch, answers=lambda fields: tuple(fields.values()), mdb=mdb, session=session)  # OK on what is offered
    menu.send_to_anisotropy()
    fields, label, title = there.asked[0]
    assert title == "Send to Anisotropy" and label == menu.SEND_LABEL
    assert fields == ((menu.ODB_FIELD, str(odb)), (menu.UNITS_FIELD, "mm-MPa"), (menu.ADDRESS_FIELD, ""), (menu.KEY_FIELD, ""))
    said = capsys.readouterr().out  # the message area
    assert f"{tmp_path / 'Job-1-anisotropy.zip'}: bundle version 1 of Job-1, in mm-MPa" in said and "SHA-256 " in said
    assert "abaqus cae noGUI" not in said and "not in the file" not in said
    bundle = open_bundle(tmp_path / "Job-1-anisotropy.zip")
    assert set(bundle.files) == {"deck", "every_output", "reactions", "model", "journal"}
    built = json.loads(bundle.text("model"))
    assert built["model"] == "IM7-UNT-L1" and [part["name"] for part in built["parts"]] == ["Coupon"]  # the job's model, not the empty Model-1
    assert bundle.manifest["written_by"]["connector"] == menu.connector().CONNECTOR
    (copied, was_there, same), = seen
    assert copied != odb and copied.name == "Job-1.odb" and was_there and same and not copied.exists()  # a copy, read, then gone
    assert cae.read_bytes() == b"the user's own model"
    kept = json.loads((tmp_path / "home" / ".anisotropy" / "connector.json").read_text(encoding="utf-8"))
    assert kept == {"units": "mm-MPa", "address": "", "token_file": ""}
    assert menu.connector().LISTENER is None  # the connector's lines go back to where they went


def test_send_posts_with_the_key_from_its_file_and_offers_the_answers_again_never_the_key(menu, job, site, token_file, monkeypatch, tmp_path, capsys):  # noqa: F811
    work = tmp_path / "work"
    work.mkdir()
    put(work, job, "Old-1")
    odb = put(work, job, "Job-7")  # the newest finished job in the work directory is offered when no ODB is on the screen
    put(work, job, "Running-1", locked=True)
    os.utime(work / "Old-1.odb", (1_000_000_000, 1_000_000_000))
    mdb, session = session_of("Another-job")
    monkeypatch.chdir(work)
    monkeypatch.setattr(menu, "reading_a_copy", lambda _none, original=menu.reading_a_copy: original(reader_of(job)))
    there_site = site()
    there = abaqus_of(monkeypatch, mdb=mdb, session=session,
                      answers=lambda fields: (fields[menu.ODB_FIELD], " m-Pa ", there_site.address, f'"{token_file}"'))
    menu.send_to_anisotropy()
    assert there.asked[0][0][0] == (menu.ODB_FIELD, str(odb))
    said = capsys.readouterr().out
    assert "the model as built is not in the file: this session has no job named Job-7" in said
    assert "sent: upload 0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11, yours alone" in said and "Agrees with ours" in said
    request, = there_site.requests
    assert request["headers"]["authorization"] == f"Bearer {TOKEN}" and request["body"] == (work / "Job-7-anisotropy.zip").read_bytes()
    assert set(open_bundle(work / "Job-7-anisotropy.zip").files) == {"deck", "every_output", "reactions"} and open_bundle(work / "Job-7-anisotropy.zip").manifest["units"] == "m-Pa"
    settings = tmp_path / "home" / ".anisotropy" / "connector.json"
    assert json.loads(settings.read_text(encoding="utf-8")) == {"units": "m-Pa", "address": there_site.address, "token_file": str(token_file)}
    assert TOKEN not in settings.read_text(encoding="utf-8") and TOKEN not in said

    there = abaqus_of(monkeypatch, mdb=mdb, session=session, answers=(None, None, None, None))  # Cancel, as Abaqus gives it
    menu.send_to_anisotropy()
    assert there.asked[0][0][1:] == ((menu.UNITS_FIELD, "m-Pa"), (menu.ADDRESS_FIELD, there_site.address), (menu.KEY_FIELD, str(token_file)))
    assert len(there_site.requests) == 1 and capsys.readouterr().out == ""


def test_send_says_every_refusal_in_the_message_area_and_keeps_no_answer_that_was_refused(menu, job, site, token_file, monkeypatch, tmp_path, capsys):  # noqa: F811
    odb = put(tmp_path, job, "Job-1")
    mdb, session = session_of("Job-1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANISOTROPY_UPLOAD_TOKEN", raising=False)
    monkeypatch.setattr(menu, "reading_a_copy", lambda _none, original=menu.reading_a_copy: original(reader_of(job)))
    settings = tmp_path / "home" / ".anisotropy" / "connector.json"
    for answers, words in ((("", "mm-MPa", "", ""), "refused: name the finished job's ODB"),
                           ((str(odb), "inches", "", ""), "refused: the units are one of mm-MPa or m-Pa"),
                           ((str(tmp_path / "missing.odb"), "mm-MPa", "", ""), "refused: no ODB at"),
                           ((str(odb), "mm-MPa", "http://example.com/api", str(token_file)), "refused: --send takes an https address"),
                           ((str(odb), "mm-MPa", "https://example.com/api", str(tmp_path / "no-key.txt")), "refused: no token file at"),
                           ((str(odb), "mm-MPa", "https://example.com/api", ""), "refused: --send needs your upload token")):
        abaqus_of(monkeypatch, mdb=mdb, session=session, answers=answers)
        menu.send_to_anisotropy()
        assert words in capsys.readouterr().out
        assert not settings.exists() and not (tmp_path / "Job-1-anisotropy.zip").exists() and menu.connector().LISTENER is None

    # the site's refusal: the file is written, the reason is said, and the answers are kept for the next try
    there_site = site(status=401, body={"detail": "This upload token is not one of ours, or it was cancelled"})
    abaqus_of(monkeypatch, mdb=mdb, session=session, answers=(str(odb), "mm-MPa", there_site.address, str(token_file)))
    menu.send_to_anisotropy()
    assert "not sent: the site refused it (401): This upload token is not one of ours, or it was cancelled. The bundle is written:" in capsys.readouterr().out
    assert (tmp_path / "Job-1-anisotropy.zip").is_file() and settings.is_file()

    # an error nobody planned for is shown whole, and nothing is raised into Abaqus/CAE
    def stops(path, step, frame, instance):
        raise RuntimeError("an error nobody planned for")
    monkeypatch.setattr(menu, "reading_a_copy", lambda _none: stops)
    abaqus_of(monkeypatch, mdb=mdb, session=session, answers=(str(odb), "mm-MPa", "", ""))
    menu.send_to_anisotropy()
    said = capsys.readouterr().out
    assert "Send to Anisotropy stopped:" in said and "RuntimeError: an error nobody planned for" in said and menu.connector().LISTENER is None


def test_a_model_the_build_script_made_names_its_coupon_and_units_and_one_drawn_by_hand_names_none(menu, coupon, job, site, token_file, monkeypatch, tmp_path, capsys):  # noqa: F811
    """The loop with nothing typed: the build script writes the coupon's name and the units on the model it makes, and Send reads
    them there. The description is the one the writer puts in the script, so the two cannot drift apart unseen."""
    written = ast.literal_eval(next(line.split(" = ", 1)[1] for line in write_cae_script(coupon).splitlines() if line.startswith("DESCRIPTION = ")))
    odb = put(tmp_path, job, "IM7-UNT-L1")
    shown = SimpleNamespace(path=str(odb))
    mdb, session = session_of("IM7-UNT-L1", description=written, shown=shown)
    assert menu.built_as(mdb, "IM7-UNT-L1") == {"coupon": "IM7-UNT-L1", "units": "mm-MPa"}
    assert menu.built_as(mdb, "Model-1") == {} and menu.built_as(mdb, None) == {} and menu.built_as(SimpleNamespace(), "IM7-UNT-L1") == {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(menu, "reading_a_copy", lambda _none, original=menu.reading_a_copy: original(reader_of(job)))
    menu.keep_answers({"units": "m-Pa", "address": "", "token_file": ""})  # the last time's units are not this model's
    there_site = site()
    there = abaqus_of(monkeypatch, mdb=mdb, session=session,
                      answers=lambda fields: (fields[menu.ODB_FIELD], fields[menu.UNITS_FIELD], there_site.address, str(token_file)))
    menu.send_to_anisotropy()
    assert there.asked[0][0][1] == (menu.UNITS_FIELD, "mm-MPa")  # the model's own units are offered
    said = capsys.readouterr().out
    assert "this model was built from Anisotropy's coupon IM7-UNT-L1: the site puts the file beside your newest finished run of it" in said
    assert "note:" not in said and "sent: upload" in said
    assert open_bundle(tmp_path / "IM7-UNT-L1-anisotropy.zip").manifest["coupon"] == "IM7-UNT-L1"

    # other units than the model's are said, and the file says what the user stated
    abaqus_of(monkeypatch, mdb=mdb, session=session, answers=(str(odb), "m-Pa", "", ""))
    menu.send_to_anisotropy()
    said = capsys.readouterr().out
    assert "note: the build script made this model in mm-MPa and you stated m-Pa" in said and "newest finished run" not in said
    assert open_bundle(tmp_path / "IM7-UNT-L1-anisotropy.zip").manifest["units"] == "m-Pa"

    # a model drawn by hand, or one whose description was changed, names no coupon: the file goes without one and nothing is said of it
    for description in ("", "My own coupon, built by anisotropy_fea"):
        mdb, session = session_of("IM7-UNT-L1", description=description, shown=shown)
        abaqus_of(monkeypatch, mdb=mdb, session=session, answers=(str(odb), "mm-MPa", "", ""))
        menu.send_to_anisotropy()
        assert "coupon" not in capsys.readouterr().out and open_bundle(tmp_path / "IM7-UNT-L1-anisotropy.zip").manifest["coupon"] is None


def test_the_model_is_the_one_the_job_was_created_for_and_the_journal_is_the_saved_models(menu, tmp_path):
    mdb, _ = session_of("Job-1", model_name="Coupon-A")
    assert menu.model_of(mdb, "Job-1") == "Coupon-A" and menu.model_of(mdb, "job-1") is None and menu.model_of(mdb, "Job-2") is None
    mdb.jobs["Job-3"] = SimpleNamespace(model="A model since deleted")
    assert menu.model_of(mdb, "Job-3") is None and menu.model_of(SimpleNamespace(), "Job-1") is None
    assert menu.journal_of(mdb) is None  # a session that was never saved has no journal of its own beside a .cae
    saved = tmp_path / "coupon.cae"
    mdb.pathName = str(saved)
    assert menu.journal_of(mdb) is None
    saved.with_suffix(".jnl").write_text("# journal\n", encoding="utf-8")
    assert menu.journal_of(mdb) == saved.with_suffix(".jnl")
    session = SimpleNamespace(currentViewportName="V", viewports={"V": SimpleNamespace(displayedObject=SimpleNamespace(name="Part-1"))})
    assert menu.shown_odb(session) == "" and menu.shown_odb(SimpleNamespace()) == ""  # a part on the screen, or no viewport at all
    assert menu.kept_answers(tmp_path / "none.json") == {}
    (tmp_path / "bad.json").write_text('["units"]', encoding="utf-8")
    assert menu.kept_answers(tmp_path / "bad.json") == {}
