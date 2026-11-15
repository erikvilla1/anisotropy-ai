"""The setup of a PC (ADR-0094 amendment 1): `tools/anisotropy_setup.py` copies the connector where Abaqus/CAE reads plug-ins,
registers the link type for the user alone with a command that names a Python program and the helper and nothing a shell reads, and
keeps where Abaqus's command is. The registry is a stand-in that records what was written; no Python is started."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_anisotropy_connector import TOOLS, connector, load  # noqa: F401


class Registry:
    """winreg, as far as the setup uses it: every key of HKEY_CURRENT_USER and its values, in a dict."""

    HKEY_CURRENT_USER, REG_SZ = "HKCU", 1

    def __init__(self):
        self.keys = {}

    def CreateKey(self, root, name):  # noqa: N802  winreg's own names
        assert root == self.HKEY_CURRENT_USER
        self.keys.setdefault(name, {})
        return Key(name)

    def SetValueEx(self, key, value, reserved, kind, data):  # noqa: N802
        assert kind == self.REG_SZ
        self.keys[key.name][value] = data

    def DeleteKey(self, root, name):  # noqa: N802
        if name not in self.keys:
            raise FileNotFoundError(name)
        if any(other.startswith(name + "\\") for other in self.keys):
            raise PermissionError("the key has subkeys")
        del self.keys[name]


class Key:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def setup(connector):  # noqa: F811
    module = load("anisotropy_setup")
    assert module.FILES == connector.FILES  # what is installed is what is handed over
    return module


@pytest.fixture
def folder(connector, tmp_path):  # noqa: F811
    """The connector's folder as unzipped."""
    there = tmp_path / "unzipped"
    there.mkdir()
    for name in connector.FILES:
        source = (TOOLS.parent / "src" / "anisotropy_fea" if name == "bundle.py" else TOOLS) / name
        (there / name).write_bytes(source.read_bytes())
    return there


def python_at(tmp_path: Path, name: str = "python.exe") -> Path:
    path = tmp_path / "SIMULIA" / "win_b64" / "tools" / "SMApy" / "python3.10" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"MZ")
    return path


def runs(ok=lambda command: True):
    started = []

    def run(command, **more):
        started.append(command)
        return SimpleNamespace(returncode=0 if ok(command) else 1, stdout="anisotropy-ok\n" if ok(command) else "")
    return run, started


def test_the_setup_copies_the_menu_registers_the_link_for_the_user_alone_and_keeps_where_abaqus_is(setup, folder, tmp_path):
    registry, said, python = Registry(), [], python_at(tmp_path)
    target, state = tmp_path / "home" / "abaqus_plugins" / "anisotropy", tmp_path / "home" / ".anisotropy"
    run, started = runs()
    assert setup.set_up(said.append, folder, target, state, registry, str(python), run, lambda name: "C:\\SIMULIA\\Commands\\abaqus.BAT") == 0
    assert sorted(p.name for p in target.iterdir()) == sorted(setup.FILES)
    assert registry.keys == {"Software\\Classes\\anisotropy": {"": "URL:Anisotropy", "URL Protocol": ""},
                             "Software\\Classes\\anisotropy\\shell\\open\\command": {"": f'"{python}" -I "{target / "anisotropy_link.py"}" "%1"'}}
    assert started == [[str(python), "-I", "-c", setup.PROBE]]  # the Python was tried on its own before it was registered
    assert json.loads((state / "machine.json").read_text()) == {"abaqus": "C:\\SIMULIA\\Commands\\abaqus.BAT"}
    assert said[0].startswith(f"1. The menu: {len(setup.FILES)} files copied to {target}") and "for this Windows user alone" in said[1] and "Connect this PC" in said[-1]

    (state / "machine.json").write_text(json.dumps({"address": "https://anisotropy.example/api", "owner": "engineer@example.com"}))
    assert setup.set_up(said.append, target, target, state, registry, str(python), run, lambda name: "D:\\abaqus.bat") == 0  # again, from the installed folder
    assert json.loads((state / "machine.json").read_text()) == {"address": "https://anisotropy.example/api", "owner": "engineer@example.com", "abaqus": "D:\\abaqus.bat"}


def test_the_registered_command_names_a_program_never_a_batch_file_and_a_python_that_fails_alone_is_not_registered(setup, folder, tmp_path):
    target, state = tmp_path / "home" / "abaqus_plugins" / "anisotropy", tmp_path / "home" / ".anisotropy"
    launcher = tmp_path / "SIMULIA" / "Commands" / "abaqus.bat"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("@echo off\n")
    assert setup.candidates(str(launcher)) == []  # a batch file would hand the link to the command interpreter
    python = python_at(tmp_path)
    beside = python.parents[3] / "code" / "bin" / "SMAPython.exe"
    beside.parent.mkdir(parents=True)
    beside.write_bytes(b"MZ")
    assert setup.candidates(str(beside)) == [beside, python]
    windowless = python.with_name("pythonw.exe")
    windowless.write_bytes(b"MZ")
    assert setup.candidates(str(beside)) == [windowless, beside, python]  # no console flashes at a click when the windowless one works
    windowless.unlink()

    registry, said = Registry(), []
    run, started = runs(lambda command: command[0] == str(python) and "-I" not in command)  # only the second, and only without -I
    assert setup.set_up(said.append, folder, target, state, registry, str(beside), run, lambda name: None) == 0
    assert registry.keys["Software\\Classes\\anisotropy\\shell\\open\\command"][""] == f'"{python}" "{target / "anisotropy_link.py"}" "%1"'
    assert [c[:2] for c in started] == [[str(beside), "-I"], [str(beside), "-c"], [str(python), "-I"], [str(python), "-c"]]
    assert "Abaqus's command was not found on PATH" in said[2]

    registry, said = Registry(), []
    assert setup.set_up(said.append, folder, target, state, registry, str(beside), runs(lambda command: False)[0], lambda name: None) == 1
    assert registry.keys == {} and "no Python beside Abaqus could be started on its own" in said[-1] and (target / "anisotropy_menu.py").is_file()
    for bad in ('C:\\Users\\a"b\\python.exe', "C:\\Users\\100%\\python.exe"):
        with pytest.raises(setup.NotDone, match="cannot go into a registered command"):
            setup.link_command(Path(bad), ["-I"], target / "anisotropy_link.py")


def test_without_windows_the_menu_is_installed_and_no_link_is_registered_and_a_folder_missing_a_file_is_refused(setup, folder, tmp_path):
    target, state, said = tmp_path / "home" / "abaqus_plugins" / "anisotropy", tmp_path / "home" / ".anisotropy", []
    assert setup.set_up(said.append, folder, target, state, None, "python", None, lambda name: "/opt/abaqus/Commands/abaqus") == 0
    assert "not registered, because they are for Windows" in said[1] and (target / "anisotropy_plugin.py").is_file()
    (folder / "bundle.py").unlink()
    said = []
    assert setup.set_up(said.append, folder, tmp_path / "other", state, Registry(), "python", None, lambda name: None) == 1
    assert said == ["not set up: bundle.py is not beside the setup: unzip the whole connector and run the setup from its folder"] and not (tmp_path / "other").exists()


def test_remove_takes_the_link_the_menu_and_the_key_away_and_leaves_what_is_the_users(setup, folder, tmp_path):
    registry, python = Registry(), python_at(tmp_path)
    target, state = tmp_path / "home" / "abaqus_plugins" / "anisotropy", tmp_path / "home" / ".anisotropy"
    assert setup.set_up(lambda line: None, folder, target, state, registry, str(python), runs()[0], lambda name: "abaqus.bat") == 0
    (state / "upload-key.txt").write_text("anisotropy_upload_" + "k" * 43 + "\n")
    (state / "connector.json").write_text(json.dumps({"units": "m-Pa", "address": "https://anisotropy.example/api", "token_file": str(state / "upload-key.txt")}))
    (target / "my-notes.txt").write_text("mine")
    for name in ("messages-0123456789abcdef.txt", "messages-0123456789abcdef.window"):  # what a window started from the site left
        (state / name).write_text("")
    (target / "__pycache__").mkdir()
    for name in ("anisotropy_link.cpython-310.pyc", "anisotropy_menu.cpython-310.pyc"):  # what Python compiled of our files
        (target / "__pycache__" / name).write_bytes(b"")
    said = []
    assert setup.remove(said.append, target, state, registry) == 0
    assert registry.keys == {} and [p.name for p in target.iterdir()] == ["my-notes.txt"]
    assert not (state / "upload-key.txt").exists() and not (state / "machine.json").exists() and sorted(p.name for p in state.iterdir()) == ["connector.json"]
    assert json.loads((state / "connector.json").read_text()) == {"units": "m-Pa", "address": "", "token_file": ""}  # the deleted key's file is no longer offered
    assert said[0] == "The site's links: no longer registered." and "Cancel it on the site too" in said[2]
    said = []
    assert setup.remove(said.append, target, state, registry) == 0
    assert said == ["The site's links: were not registered.", f"The menu: 0 files removed from {target}.", "This PC held no upload key."]
    assert setup.main(["--help"]) == 2


def test_a_double_click_ends_in_a_box_that_says_it_is_set_up_and_what_comes_next_or_why_not(setup, capsys):
    told = []
    tell = lambda text, error=False: told.append((text, error))  # noqa: E731

    def done(say, registry=None):
        for line in ("1. The menu: 9 files copied.", "2. The site's links: registered.", "3. Abaqus's command: C:\\SIMULIA\\Commands\\abaqus.BAT.", "", "Done."):
            say(line)
        return 0
    assert setup.main(["--box"], tell, done) == 0
    assert told == [(setup.SET_UP + "\n\n" + setup.NEXT, False)] and "Connect this PC" in setup.NEXT and "Send to Abaqus" in setup.NEXT
    assert "1. The menu: 9 files copied." in capsys.readouterr().out  # the console still has every line

    def no_abaqus(say, registry=None):
        say("1. The menu: 9 files copied.")
        say(setup.NO_ABAQUS)
        return 0
    assert setup.main(["--box"], tell, no_abaqus) == 0
    assert told[-1] == (setup.SET_UP + "\n\nAbaqus's command was not found on PATH. Send to Abaqus on the site will say so; the menu in Abaqus/CAE works without it.\n\n" + setup.NEXT, False)

    def stopped(say, registry=None):
        say("1. The menu: 9 files copied.")
        say("not set up: no Python beside Abaqus could be started on its own")
        return 1
    assert setup.main(["--box"], tell, stopped) == 1
    assert told[-1] == (setup.NOT_SET_UP + "\n\nNo Python beside Abaqus could be started on its own", True)  # the reason once, not the console's first words again

    assert setup.main([], tell, done) == 0 and len(told) == 3  # from a command window: the lines, and no box
    removed = []
    assert setup.main(["--remove"], tell, done, lambda registry=None: removed.append(1) or 0) == 0 and removed == [1] and len(told) == 3
    assert setup.main(["--box", "--remove"], tell, done) == 2
    assert setup.box("here, without Windows, nothing is shown") is False

