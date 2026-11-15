"""Set this PC up for Anisotropy, once (ADR-0094 amendment 1). Run it with Abaqus's own Python from the connector's folder, or
double-click "Set up Anisotropy", which runs exactly this:

    abaqus python anisotropy_setup.py
    abaqus python anisotropy_setup.py --box         the same, and a box of Windows's own says how it ended (what the double-click runs)
    abaqus python anisotropy_setup.py --remove      takes all of it away again

Before anything else it checks every file beside it against `SHA256SUMS.txt`, the list the connector's zip carries, and stops when one
is missing or does not match: a folder that was unzipped in part, or mixed with the files of another version, is not installed. Then
it does three things, for this Windows user alone and without administrator's rights, and says each:

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

import hashlib
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
SUMS = "SHA256SUMS.txt"  # in the connector's zip: `<SHA-256>  <name>` for every other file in it
NOT_IN_A_COMMAND = '"%\r\n'  # a path with one of these is not put into the registered command
TITLE = "Anisotropy"
NO_ABAQUS = "3. Abaqus's command was not found on PATH. Send to Abaqus on the site will say so; the menu in Abaqus/CAE works without it."
SET_UP = "Anisotropy is set up on this PC."
NEXT = ("Next, on a run's page on the site: open First time on this PC and click Connect this PC. After that, Send to Abaqus starts "
        "Abaqus with the run's coupon built.")
NOT_SET_UP = "Anisotropy was not set up on this PC."


class NotDone(Exception):
    """The setup cannot go on; the message says why and what to do."""


def here() -> Path:
    return Path(__file__).resolve().parent


def plugin_folder() -> Path:
    return Path.home() / PLUGINS / FOLDER


def state_folder() -> Path:
    return Path.home() / ".anisotropy"


def verify(source: Path) -> int:
    """Check the connector's folder against the list of checksums its zip carries: every file the setup installs is on the list and
    has that SHA-256, and so has every other file of the list that is in the folder (the installed folder holds the Python files and
    the list alone). Returns how many files were checked; `NotDone` says which one failed. This is a check against a damaged or
    mixed-up folder, not a signature: who made the zip is checked on the zip's own checksum."""
    again = "Download the connector again, unzip all of it into a new folder, and run the setup from there"
    try:
        with io.open(str(source / SUMS), encoding="utf-8") as handle:
            lines = [line.rstrip("\r\n") for line in handle if line.strip()]
    except OSError:
        raise NotDone(f"{SUMS} is not beside the setup, so its files cannot be checked. {again}") from None
    listed = {}
    for line in lines:
        digest, _, name = line.partition("  ")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest) or not name or "/" in name or "\\" in name or name in listed:
            raise NotDone(f"{SUMS} is not a list of checksums this setup can read. {again}")
        listed[name] = digest
    checked = 0
    for name in sorted(set(FILES) | set(listed)):
        if name not in listed:
            raise NotDone(f"{SUMS} does not name {name}, so this is not a whole connector. {again}")
        try:
            with io.open(str(source / name), "rb") as handle:
                found = hashlib.sha256(handle.read()).hexdigest()
        except OSError:
            if name in FILES:
                raise NotDone(f"{name} is missing from the connector's folder. {again}") from None
            continue  # the README, this note or the batch file: not installed, and not needed to be here
        if found != listed[name]:
            raise NotDone(f"{name} is not the file this connector was made with (its checksum differs from {SUMS}). {again}")
        checked += 1
    return checked


def copy_files(source: Path, target: Path) -> list:
    """The connector's files in the folder Abaqus/CAE reads plug-ins from. Running the setup from that folder copies nothing."""
    missing = [name for name in FILES if not (source / name).is_file()]
    if missing:
        raise NotDone(f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} not beside the setup: unzip the whole connector and run the setup from its folder")
    if source.resolve() == target.resolve():
        return []
    target.mkdir(parents=True, exist_ok=True)
    for name in (*FILES, SUMS):  # the list goes with them, so the installed folder can be checked again
        shutil.copyfile(str(source / name), str(target / name))
    return list(FILES)


def candidates(executable: str) -> list:
    """Python programs to try for the link: first the windowless one Abaqus installs, so no console flashes at a click (the helper
    asks and answers in boxes), then the one running this, then the others beside it."""
    found, later = [], [Path(executable)]
    for parent in list(Path(executable).resolve().parents)[:6]:
        for pattern, into in (("tools/SMApy/python*/pythonw.exe", found), ("tools/SMApy/python*/python.exe", later), ("code/bin/SMAPython.exe", later)):
            try:
                into += sorted(parent.glob(pattern))
            except OSError:
                continue
    found += later
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


def forget_key_file(state: Path) -> None:
    """The menu's kept answers no longer name the key's file that was just deleted, or the address it was for; the units stay."""
    path = state / "connector.json"
    try:
        with io.open(str(path), encoding="utf-8") as handle:
            answers = json.load(handle)
    except (OSError, ValueError):
        return
    if not isinstance(answers, dict) or answers.get("token_file") != str(state / KEY_FILE):
        return  # a key's file the user named themselves is theirs
    answers.update(address="", token_file="")
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(answers, handle, indent=1, sort_keys=True)
        handle.write("\n")


def windows_registry():
    if os.name != "nt":
        return None
    import winreg
    return winreg


def set_up(say=print, source: Path | None = None, target: Path | None = None, state: Path | None = None, registry=None, executable: str | None = None,
           run=subprocess.run, which=shutil.which) -> int:
    source, target, state = source or here(), target or plugin_folder(), state or state_folder()
    try:
        say(f"0. The files: {verify(source)} checked against {SUMS}.")
        copied = copy_files(source, target)
        say(f"1. The menu: {len(copied) or len(FILES)} files {'copied to' if copied else 'are in'} {target}. Start Abaqus/CAE again and look under Plug-ins > Anisotropy.")
        if registry is None:
            say("2. The site's links: not registered, because they are for Windows. On this machine use the menu in Abaqus/CAE.")
        else:
            python, flags = link_python(executable or sys.executable, run)
            register(link_command(python, flags, target / "anisotropy_link.py"), registry)
            say(f"2. The site's links: anisotropy:// now starts the helper in that folder with {python}, for this Windows user alone.")
        abaqus = keep_abaqus(state, which)
        say(f"3. Abaqus's command: {abaqus}." if abaqus else NO_ABAQUS)
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
        (target / SUMS).unlink()
    except OSError:
        pass
    cache = target / "__pycache__"  # what Python compiled of our files; anything else in it is not ours and keeps the folder
    for name in FILES:
        for compiled in (list(cache.glob(Path(name).stem + ".*.pyc")) if cache.is_dir() else []):
            try:
                compiled.unlink()
            except OSError:
                continue
    for folder in (cache, target):
        try:
            folder.rmdir()
        except OSError:
            pass  # something of the user's own is in it
    say(f"The menu: {gone} files removed from {target}.")
    had_key = (state / KEY_FILE).is_file()
    for name in (KEY_FILE, MACHINE_FILE):
        try:
            (state / name).unlink()
        except OSError:
            continue
    for left in (list(state.glob("messages-*")) if state.is_dir() else []):  # what a window started from the site left for its message area
        try:
            left.unlink()
        except OSError:
            continue
    forget_key_file(state)
    say("This PC's upload key: deleted here. Cancel it on the site too, on a run's page under Send straight from Abaqus." if had_key
        else "This PC held no upload key.")
    return 0


def box(text: str, error: bool = False) -> bool:
    """A box of Windows's own with the text, in front of the other windows; whether one was shown. A double-click on the setup ends
    in a console window that closes at a key, which told its first user nothing (2026-11-14)."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, TITLE, (0x10 if error else 0x40) | 0x10000 | 0x40000)
    except Exception:  # noqa: BLE001  no box on this machine: the lines in the console are the answer
        return False
    return True


def ending(code: int, said: list) -> str:
    """How the setup ended, in the few words a box holds: that it is done and what comes next, or the reason it is not."""
    if code != 0:
        why = [line[len("not set up: "):] for line in said if line.startswith("not set up: ")][-1:]  # the reason, without the console's own first words
        return "\n\n".join([NOT_SET_UP, *[line[:1].upper() + line[1:] for line in why]])
    return "\n\n".join([SET_UP, *[line[3:] for line in said if line == NO_ABAQUS], NEXT])


def main(argv=None, tell=box, set_up=set_up, remove=remove) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv not in ([], ["--remove"], ["--box"]):
        print("anisotropy_setup.py takes nothing, --box or --remove")
        return 2
    if argv == ["--remove"]:
        return remove(registry=windows_registry())
    said = []

    def say(line):
        said.append(line)
        print(line)
    code = set_up(say, registry=windows_registry())
    if argv:
        tell(ending(code, said), error=code != 0)
    return code


if __name__ == "__main__":
    sys.exit(main())
