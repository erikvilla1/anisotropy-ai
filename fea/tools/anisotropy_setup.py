"""Set this PC up for Anisotropy, once (ADR-0094 amendment 1). Run it with Abaqus's own Python from the connector's folder, or
double-click "Set up Anisotropy", which runs exactly this:

    abaqus python anisotropy_setup.py
    abaqus python anisotropy_setup.py --remove      takes all of it away again

It does three things, for this Windows user alone and without administrator's rights, and says each:

1. copies the connector's files to `abaqus_plugins/anisotropy` in the home directory, so Abaqus/CAE shows Plug-ins > Anisotropy the
   next time it starts;
2. registers the link type `anisotropy://` for this user (under HKEY_CURRENT_USER\\Software\\Classes), so a click on Send to Abaqus on
   the site starts `anisotropy_link.py` there. The command it registers names a Python program directly, never a batch file and never
   the command interpreter, because a link is text from a web page; the Python is one found beside Abaqus and tried here first;
3. writes where Abaqus's own command is to `.anisotropy/machine.json` in the home directory, so the link can start Abaqus/CAE.

It does not connect this PC to an account and sends nothing: Connect this PC on the site does that, and asks first.

The standard library only, Python 3.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FILES = ("anisotropy_connector.py", "bundle.py", "abaqus_every_output.py", "abaqus_extract_fields.py", "anisotropy_menu.py", "anisotropy_plugin.py",
         "anisotropy_link.py", "anisotropy_start.py", "anisotropy_setup.py")
PLUGINS = "abaqus_plugins"
FOLDER = "anisotropy"
SCHEME = "anisotropy"
CLASS_KEY = "Software\\Classes\\" + SCHEME
COMMAND_KEY = CLASS_KEY + "\\shell\\open\\command"
PROBE = "import ssl, json, ctypes, urllib.request; print('anisotropy-ok')"  # what the link's helper needs of a Python
PROBE_TIMEOUT_S = 120.0
MACHINE_FILE = "machine.json"
KEY_FILE = "upload-key.txt"
NOT_IN_A_COMMAND = '"%\r\n'  # a path with one of these is not put into the registered command


class NotDone(Exception):
    """The setup cannot go on; the message says why and what to do."""


def here() -> Path:
    return Path(__file__).resolve().parent


def plugin_folder() -> Path:
    return Path.home() / PLUGINS / FOLDER


def state_folder() -> Path:
    return Path.home() / ".anisotropy"


def copy_files(source: Path, target: Path) -> list:
    """The connector's files in the folder Abaqus/CAE reads plug-ins from. Running the setup from that folder copies nothing."""
    missing = [name for name in FILES if not (source / name).is_file()]
    if missing:
        raise NotDone(f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not beside the setup: unzip the whole connector and run the setup from its folder")
    if source.resolve() == target.resolve():
        return []
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(str(source / name), str(target / name))
    return list(FILES)


def candidates(executable: str) -> list:
    """Python programs to try for the link, the one running this first, then the ones Abaqus installs beside it."""
    found = [Path(executable)]
    for parent in list(Path(executable).resolve().parents)[:6]:
        for pattern in ("tools/SMApy/python*/python.exe", "code/bin/SMAPython.exe"):
            try:
                found += sorted(parent.glob(pattern))
            except OSError:
                continue
    seen, ordered = set(), []
    for path in found:
        if str(path).lower() not in seen and path.suffix.lower() == ".exe" and path.is_file():
            seen.add(str(path).lower())
            ordered.append(path)
    return ordered


def works(python: Path, flags: list, run=subprocess.run) -> bool:
    """Whether this Python, started on its own as Windows will start it for a link, has what the helper needs."""
    try:
        done = run([str(python), *flags, "-c", PROBE], capture_output=True, text=True, timeout=PROBE_TIMEOUT_S, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and "anisotropy-ok" in (done.stdout or "")


def link_python(executable: str, run=subprocess.run) -> tuple:
    """(the Python, its flags) for the link's command: isolated from the environment where that works."""
    for python in candidates(executable):
        for flags in (["-I"], []):
            if works(python, flags, run):
                return python, flags
    raise NotDone("no Python beside Abaqus could be started on its own, so the site's links were not registered. The menu in Abaqus/CAE "
                  "is installed and works without them")


def link_command(python: Path, flags: list, helper: Path) -> str:
    """What Windows runs for a link: the Python, the helper, and the link as one quoted word. No batch file and no shell."""
    for path in (python, helper):
        if any(c in str(path) for c in NOT_IN_A_COMMAND):
            raise NotDone(f"the path {path} holds a character that cannot go into a registered command; install the connector under a plainer path")
    return " ".join([f'"{python}"', *flags, f'"{helper}"', '"%1"'])


def register(command: str, registry) -> None:
    """The link type for this user: HKEY_CURRENT_USER alone, which needs no administrator."""
    with registry.CreateKey(registry.HKEY_CURRENT_USER, CLASS_KEY) as key:
        registry.SetValueEx(key, "", 0, registry.REG_SZ, "URL:Anisotropy")
        registry.SetValueEx(key, "URL Protocol", 0, registry.REG_SZ, "")
    with registry.CreateKey(registry.HKEY_CURRENT_USER, COMMAND_KEY) as key:
        registry.SetValueEx(key, "", 0, registry.REG_SZ, command)


def unregister(registry) -> bool:
    """Take the link type away again; whether there was one."""
    there = False
    for name in (COMMAND_KEY, CLASS_KEY + "\\shell\\open", CLASS_KEY + "\\shell", CLASS_KEY):
        try:
            registry.DeleteKey(registry.HKEY_CURRENT_USER, name)
            there = True
        except OSError:
            continue
    return there


def keep_abaqus(folder: Path, which=shutil.which) -> str:
    """Where Abaqus's command is, kept for the link's helper beside what the machine is connected to."""
    found = which("abaqus") or ""
    path = folder / MACHINE_FILE
    try:
        with io.open(str(path), encoding="utf-8") as handle:
            facts = json.load(handle)
    except (OSError, ValueError):
        facts = {}
    facts = facts if isinstance(facts, dict) else {}
    if found:
        facts["abaqus"] = found
    folder.mkdir(parents=True, exist_ok=True)
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(facts, handle, indent=1, sort_keys=True)
        handle.write("\n")
    return found


def windows_registry():
    if os.name != "nt":
        return None
    import winreg
    return winreg


def set_up(say=print, source: Path | None = None, target: Path | None = None, state: Path | None = None, registry=None, executable: str | None = None,
           run=subprocess.run, which=shutil.which) -> int:
    source, target, state = source or here(), target or plugin_folder(), state or state_folder()
    try:
        copied = copy_files(source, target)
        say(f"1. The menu: {len(copied) or len(FILES)} files {'copied to' if copied else 'are in'} {target}. Start Abaqus/CAE again and look under Plug-ins > Anisotropy.")
        if registry is None:
            say("2. The site's links: not registered, because they are for Windows. On this machine use the menu in Abaqus/CAE.")
        else:
            python, flags = link_python(executable or sys.executable, run)
            register(link_command(python, flags, target / "anisotropy_link.py"), registry)
            say(f"2. The site's links: anisotropy:// now starts the helper in that folder with {python}, for this Windows user alone.")
        abaqus = keep_abaqus(state, which)
        say(f"3. Abaqus's command: {abaqus}." if abaqus else "3. Abaqus's command was not found on PATH. Send to Abaqus on the site will say so; the menu in Abaqus/CAE works without it.")
        say("")
        say("Done. Next, on a run's page on the site: First time on this PC, Connect this PC. Then Send to Abaqus.")
    except NotDone as exc:
        say(f"not set up: {exc}")
        return 1
    return 0


def remove(say=print, target: Path | None = None, state: Path | None = None, registry=None) -> int:
    target, state = target or plugin_folder(), state or state_folder()
    if registry is not None:
        say("The site's links: " + ("no longer registered." if unregister(registry) else "were not registered."))
    gone = 0
    for name in FILES:
        try:
            (target / name).unlink()
            gone += 1
        except OSError:
            continue
    try:
        target.rmdir()
    except OSError:
        pass  # something of the user's own is in it
    say(f"The menu: {gone} files removed from {target}.")
    had_key = (state / KEY_FILE).is_file()
    for name in (KEY_FILE, MACHINE_FILE):
        try:
            (state / name).unlink()
        except OSError:
            continue
    say("This PC's upload key: deleted here. Cancel it on the site too, on a run's page under Send straight from Abaqus." if had_key
        else "This PC held no upload key.")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv not in ([], ["--remove"]):
        print("anisotropy_setup.py takes nothing, or --remove")
        return 2
    return remove(registry=windows_registry()) if argv else set_up(registry=windows_registry())


if __name__ == "__main__":
    sys.exit(main())
