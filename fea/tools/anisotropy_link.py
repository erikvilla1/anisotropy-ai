"""What a click on Anisotropy's site does on this machine (ADR-0094 amendment 1). The site's page opens a link that starts with
`anisotropy://`; Windows hands the link to this file (`anisotropy_setup.py` registers that, for this user alone), and this file does
one of two things and nothing else:

    anisotropy://pair?code=<a one-time code>&site=<the address of Anisotropy's API>
        Connect this PC: the code, made a moment ago by the page of a signed-in user, is swapped for an upload key of this machine's
        own. First the site is asked whose account the code is for, and the user is asked, in a box that names the site and the
        account, whether to connect. Only a yes swaps the code. The key is written to `.anisotropy/upload-key.txt` in the home
        directory and is never shown, printed or put on a command line.

    anisotropy://open?run=<the id of a finished run>
        Send to Abaqus: the build script of that run, which must be a run of the connected account, is fetched with the key, written
        to `Anisotropy/<coupon>/` in the home directory, and Abaqus/CAE is started there with the coupon built, as a model to edit.
        When its job completes, the results go back to the run by themselves (`anisotropy_menu.py`).

Any web page can open such a link, so a link is read as hostile text:

- it is one of the two shapes above, to the character: a code of ours, a run's id, an https address; anything else is refused;
- nothing from a link is run, and nothing from a link reaches a command line: Abaqus is started as `abaqus cae
  script=anisotropy-start.py` in the coupon's folder, the same words every time;
- the key goes only to the address this machine was connected to, which only a yes in the box sets or changes; an open link carries
  no address;
- a redirect is an answer and is never followed, and a build script is run only when our writer wrote it (its first lines say so).

The standard library only, Python 3. Run as `python anisotropy_link.py <link>`; Abaqus's own Python is enough.
"""

from __future__ import annotations

import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HELPER = "anisotropy-link 0.6.0"
SCHEME = "anisotropy"
MAX_LINK = 600
CODE = re.compile(r"anisotropy_pair_[A-Za-z0-9_-]{43}")
RUN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
LINK_TEXT = re.compile(r"[A-Za-z0-9:/?&=%._~-]+")  # every character a link of ours can hold: no space, quote, or anything a shell reads
SITE_TEXT = re.compile(r"https?://[A-Za-z0-9:/._-]{1,200}")  # an address as a link may state it: no name or password, no ? and no #
HOST = re.compile(r"[a-z0-9]([a-z0-9.-]*[a-z0-9])?")
SITE_PATH = re.compile(r"(/[A-Za-z0-9._-]+)*/?")
COUPON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")
TOKEN_PREFIX = "anisotropy_upload_"
PAIR_ROUTE = "/v1/connector/pair"
RUNS_ROUTE = "/v1/connector/runs"
THIS_MACHINE = ("localhost", "127.0.0.1")
MARK = "# Built by anisotropy_fea "  # in the first lines of every build script (`write_cae_script`)
HEAD_LINES = 4
MAX_SCRIPT_BYTES = 2 * 1024 * 1024
TIMEOUT_S = 30.0
KEY_FILE = "upload-key.txt"
MACHINE_FILE = "machine.json"  # the address this machine is connected to, whose account, and where Abaqus's command is
ANSWERS_FILE = "connector.json"  # what the menu in Abaqus/CAE offers the next time (`anisotropy_menu.py`)
START_SCRIPT = "anisotropy_start.py"  # beside this file; copied into the coupon's folder under the name Abaqus is started with
START_NAME = "anisotropy-start.py"
START_FACTS = "anisotropy-start.json"
SESSION = "ANISOTROPY_SESSION"  # in the environment of the Abaqus/CAE started here: a name of that one window's own (`start`)
TITLE = "Anisotropy"


class NotDone(Exception):
    """What the link asked cannot be done; the message says why and what to do."""


def here() -> Path:
    return Path(__file__).resolve().parent


def state_folder() -> Path:
    return Path.home() / ".anisotropy"


def work_folder() -> Path:
    return Path.home() / "Anisotropy"


# ------------------------------------------------------------------------------------------------------- reading a link

def site_address(site: str) -> str:
    """The address of Anisotropy's API as a link or a file states it, checked and without its last slash. https only, apart from this
    machine itself, because the requests carry the key."""
    refused = NotDone("the link does not name an address of Anisotropy's API")
    if not isinstance(site, str) or SITE_TEXT.fullmatch(site) is None:
        raise refused
    parts = urllib.parse.urlsplit(site)
    try:
        port = parts.port
    except ValueError:
        raise refused from None
    host = parts.hostname or ""
    if (parts.scheme not in ("http", "https") or HOST.fullmatch(host) is None or parts.netloc.lower() not in (host, f"{host}:{port}")
            or parts.query or parts.fragment or SITE_PATH.fullmatch(parts.path) is None):
        raise refused
    if parts.scheme == "http" and host not in THIS_MACHINE:
        raise NotDone("the link names an address that is not https: the key must not cross a network in the clear")
    return f"{parts.scheme}://{parts.netloc.lower()}{parts.path.rstrip('/')}"


def read_link(text: str) -> dict:
    """A link as the two things it may ask: {"what": "pair", "code", "site"} or {"what": "open", "run"}. Refused otherwise."""
    refused = NotDone("this is not a link Anisotropy's site makes, so nothing was done")
    if not isinstance(text, str) or not 0 < len(text) <= MAX_LINK or LINK_TEXT.fullmatch(text) is None:
        raise refused
    parts = urllib.parse.urlsplit(text)
    if parts.scheme != SCHEME or parts.netloc not in ("pair", "open") or parts.path not in ("", "/") or parts.fragment:
        raise refused
    try:
        asked = urllib.parse.parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True, max_num_fields=2)
    except ValueError:
        raise refused from None
    names = sorted(name for name, _ in asked)
    wanted = dict(asked)
    if parts.netloc == "open":
        if names != ["run"] or RUN.fullmatch(wanted["run"]) is None:
            raise refused
        return {"what": "open", "run": wanted["run"]}
    if names != ["code", "site"] or CODE.fullmatch(wanted["code"]) is None:
        raise refused
    return {"what": "pair", "code": wanted["code"], "site": site_address(wanted["site"])}


# ------------------------------------------------------------------------------------------------------- what this machine keeps

def read_json(path: Path) -> dict:
    try:
        with io.open(str(path), encoding="utf-8") as handle:
            found = json.load(handle)
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def write_json(path: Path, facts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with io.open(str(path), "w", encoding="utf-8", newline="\n") as handle:
        json.dump(facts, handle, indent=1, sort_keys=True)
        handle.write("\n")


def machine(folder: Path | None = None) -> dict:
    """What this machine is connected to: {"address", "owner"} once a yes connected it, and {"abaqus"} once set up."""
    return read_json((folder or state_folder()) / MACHINE_FILE)


def key_of(folder: Path | None = None) -> str:
    """The upload key this machine was given; refused with what to do when there is none. Never printed."""
    path = (folder or state_folder()) / KEY_FILE
    try:
        with io.open(str(path), encoding="utf-8-sig") as handle:
            key = handle.read().strip()
    except OSError:
        key = ""
    if not key.startswith(TOKEN_PREFIX) or len(key.split()) != 1:
        raise NotDone("this PC is not connected to your account yet: click Connect this PC on the run's page, then Send to Abaqus again")
    return key


def keep_key(key: str, folder: Path) -> Path:
    """Write the key in the home directory, as a new file that replaces the old one whole. On Windows the file has the folder's
    own permissions, which keep a home directory to its user; elsewhere it is made for the owner alone."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / KEY_FILE
    fresh = folder / (KEY_FILE + ".new")
    if fresh.exists():
        fresh.unlink()
    handle = os.open(str(fresh), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as out:
        out.write(key + "\n")
    os.replace(str(fresh), str(path))
    return path


# ------------------------------------------------------------------------------------------------------- asking the site

class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an answer, not a place to go: the key and the code are for the address named and no other."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def call(request, timeout: float):
    """(status, body, headers) of the request as sent, without following a redirect; at most MAX_SCRIPT_BYTES of the body and one more."""
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_SCRIPT_BYTES + 1), dict(response.headers.items())
    except urllib.error.HTTPError as answer:
        return answer.code, answer.read(MAX_SCRIPT_BYTES + 1), dict(answer.headers.items())


def detail_of(body: bytes) -> str:
    """What the API said in a refusal, as one line; nothing when the body is not its JSON (a sign-in page, a proxy's own page)."""
    try:
        detail = json.loads(body.decode("utf-8")).get("detail")
    except (ValueError, AttributeError, UnicodeDecodeError):
        return ""
    return " ".join(detail.split())[:400] if isinstance(detail, str) else ""


def asked(caller, request) -> tuple:
    """The site's answer, or `NotDone` in a person's words when it did not answer or answered as a sign-in page does."""
    try:
        status, body, headers = caller(request, TIMEOUT_S)
    except (urllib.error.URLError, OSError) as exc:
        raise NotDone(f"the site did not answer: {getattr(exc, 'reason', exc)}. Check the connection and click again") from None
    if 300 <= status < 400:
        raise NotDone("the site answered with its sign-in page: it does not take this from a PC yet. Nothing was sent or changed")
    return status, body, {name.lower(): value for name, value in headers.items()}


def pair_request(site: str, code: str, look: bool, name: str = ""):
    body = {"code": code, "look": True} if look else {"code": code, "name": name}
    return urllib.request.Request(site + PAIR_ROUTE, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "User-Agent": HELPER})


def script_request(site: str, run: str, key: str):
    return urllib.request.Request(f"{site}{RUNS_ROUTE}/{run}/build-script", method="GET", headers={
        "Authorization": f"Bearer {key}", "Accept": "text/x-python", "User-Agent": HELPER})


# ------------------------------------------------------------------------------------------------------- Connect this PC

def host_of(address: str) -> str:
    return urllib.parse.urlsplit(address).netloc


def machine_name() -> str:
    """The name the key carries in the list on the site, so its owner knows which PC to cancel."""
    try:
        node = socket.gethostname()  # not platform.node(), which starts the command interpreter on Windows to ask for its version
    except OSError:
        node = ""
    name = "".join(c for c in node if c.isalnum() or c in "-_.")[:60]
    return name or "a connected PC"


def question(site: str, owner: str, now: dict) -> str:
    """What the box asks before anything is swapped: the site and the account by name."""
    lines = ["Connect Abaqus on this PC to Anisotropy?", "", f"Site:  {host_of(site)}", f"Account:  {owner}", "",
             "After a yes, a click on the site opens your runs in Abaqus on this PC, and a model opened that way sends its results back "
             "to this account when its job completes.", "",
             "Say yes only if you clicked Connect this PC on that site a moment ago and this is your account."]
    if now.get("address") and (now.get("address") != site or now.get("owner") != owner):
        lines += ["", f"This PC is now connected to {host_of(now['address'])} as {now.get('owner') or 'an account'}. A yes replaces that."]
    return "\n".join(lines)


def pair(link: dict, confirm, caller=call, folder: Path | None = None, name: str | None = None) -> dict:
    """Swap the link's code for a key of this machine's own, after the user's yes. Returns {"address", "owner"}."""
    folder = folder or state_folder()
    site, code = link["site"], link["code"]
    status, body, _ = asked(caller, pair_request(site, code, look=True))
    owner = None
    if status == 200:
        try:
            owner = json.loads(body.decode("utf-8")).get("owner")
        except (ValueError, AttributeError, UnicodeDecodeError):
            owner = None
    if status != 200 or not isinstance(owner, str) or not owner.strip() or len(owner) > 400:
        said = detail_of(body)
        raise NotDone(f"{host_of(site)} did not take the code ({status})" + (f": {said}" if said else ": is this Anisotropy's address?"))
    owner = " ".join(owner.split())
    now = machine(folder)
    if not confirm(question(site, owner, now)):
        raise NotDone("not connected: you said no, and nothing was changed. The code on the page ends by itself in a few minutes")
    status, body, _ = asked(caller, pair_request(site, code, look=False, name=name if name is not None else machine_name()))
    try:
        answer = json.loads(body.decode("utf-8")) if status == 200 else {}
    except (ValueError, UnicodeDecodeError):
        answer = {}
    key = answer.get("token") if isinstance(answer, dict) else None
    if not isinstance(key, str) or not key.startswith(TOKEN_PREFIX) or len(key.split()) != 1 or " ".join(str(answer.get("owner")).split()) != owner:
        said = detail_of(body)
        raise NotDone(f"{host_of(site)} did not connect this PC ({status})" + (f": {said}" if said else ""))
    path = keep_key(key, folder)
    write_json(folder / MACHINE_FILE, {**now, "address": site, "owner": owner})
    answers = read_json(folder / ANSWERS_FILE)
    write_json(folder / ANSWERS_FILE, {"units": answers.get("units", "") if isinstance(answers.get("units"), str) else "",
                                       "address": site, "token_file": str(path)})
    return {"address": site, "owner": owner}


# ------------------------------------------------------------------------------------------------------- Send to Abaqus

def is_ours(text: str) -> bool:
    """Whether the script's first lines say that Anisotropy's build-script writer wrote it."""
    return any(line.startswith(MARK) for line in text.splitlines()[:HEAD_LINES])


def abaqus_command(now: dict, which=shutil.which) -> str:
    """Abaqus's own command on this machine: where the setup found it, or on PATH."""
    kept = now.get("abaqus")
    if isinstance(kept, str) and kept and Path(kept).is_file():
        return kept
    found = which("abaqus")
    if not found:
        raise NotDone("Abaqus's command was not found on this PC. Run the setup again from the connector's folder (Set up Anisotropy), "
                      "or open the build script by hand: Plug-ins > Anisotropy > Open from Anisotropy")
    return found


def start(command: str, folder: Path):
    """Abaqus/CAE with its window, in the coupon's folder, running the start script there. The same words every time: nothing from a
    link or from the site is on this command line. On Windows Abaqus's command is a batch file and stays until the window ends; it
    is started with no console of its own, since a detached one left a terminal window open for as long as Abaqus ran (the
    eleventh trial). The window and its kernel are given one name of their own in the environment, made here and said to nobody, so
    that the window shows what its own kernel's job-completed callback says and no other window's (`anisotropy_menu.hand_over`)."""
    more = {"env": dict(os.environ, **{SESSION: secrets.token_hex(8)})}
    if os.name == "nt":
        more["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen([command, "cae", f"script={START_NAME}"], cwd=str(folder), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, close_fds=True, **more)


def open_run(link: dict, caller=call, folder: Path | None = None, work: Path | None = None, starter=start, which=shutil.which) -> dict:
    """Fetch the run's build script with this machine's key and start Abaqus/CAE with the coupon built. Returns {"coupon", "folder"}."""
    folder = folder or state_folder()
    now = machine(folder)
    key = key_of(folder)
    try:
        site = site_address(now.get("address") if isinstance(now.get("address"), str) else "")
    except NotDone:
        raise NotDone("this PC is not connected to your account yet: click Connect this PC on the run's page, then Send to Abaqus again") from None
    command = abaqus_command(now, which)
    status, body, headers = asked(caller, script_request(site, link["run"], key))
    if status == 401:
        raise NotDone("the site no longer takes this PC's key (it was cancelled, or the site does not take keys from a PC yet). Click "
                      "Connect this PC on the run's page, then Send to Abaqus again")
    if status != 200:
        said = detail_of(body)
        raise NotDone(f"the site did not give the run's build script ({status})" + (f": {said}" if said else ""))
    if len(body) > MAX_SCRIPT_BYTES:
        raise NotDone("the site's answer is larger than any build script, so it was not kept")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    if not is_ours(text):
        raise NotDone("the site's answer is not a build script Anisotropy wrote, so it was not run")
    coupon = headers.get("x-anisotropy-coupon", "")
    coupon = coupon if COUPON.fullmatch(coupon) is not None else "coupon"
    target = (work or work_folder()) / coupon
    target.mkdir(parents=True, exist_ok=True)
    script = target / f"{coupon}-build.py"
    with io.open(str(script), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    source = here() / START_SCRIPT
    if not source.is_file():
        raise NotDone(f"{START_SCRIPT} is not beside the helper: keep the connector's files together in one folder, or run the setup again")
    shutil.copyfile(str(source), str(target / START_NAME))
    write_json(target / START_FACTS, {"script": str(script), "run": link["run"], "coupon": coupon, "connector": str(here())})
    starter(command, target)
    return {"coupon": coupon, "folder": target}


# ------------------------------------------------------------------------------------------------------- saying and asking

def box(text: str, ask: bool = False, error: bool = False) -> bool:
    """A box of Windows's own with the text; with `ask`, Yes or No, No first. Without Windows, the terminal."""
    if os.name == "nt":
        try:
            import ctypes
            style = (0x04 | 0x20 | 0x100 if ask else 0x10 if error else 0x40) | 0x10000 | 0x40000  # yes/no, question, No first | to the front, on top
            return ctypes.windll.user32.MessageBoxW(None, text, TITLE, style) == 6
        except Exception:  # noqa: BLE001  no box on this machine: the terminal asks
            pass
    print(text)
    if not ask:
        return True
    try:
        return input("Type yes to connect, anything else to leave it: ").strip().lower() == "yes"
    except EOFError:
        return False


def main(argv=None, confirm=None, tell=None, caller=call, folder: Path | None = None, work: Path | None = None, starter=start,
         which=shutil.which) -> int:
    argv = sys.argv[1:] if argv is None else argv
    confirm = confirm or (lambda text: box(text, ask=True))
    tell = tell or (lambda text, error=False: box(text, error=error))
    try:
        if len(argv) != 1:
            raise NotDone("this helper takes one link from Anisotropy's site and nothing else")
        link = read_link(argv[0])
        if link["what"] == "pair":
            done = pair(link, confirm, caller, folder)
            tell(f"This PC is connected to {host_of(done['address'])} as {done['owner']}.\n\nGo back to the run's page and click Send to Abaqus.")
        else:
            done = open_run(link, caller, folder, work, starter, which)
            print(f"Abaqus/CAE is starting with {done['coupon']} in {done['folder']}")
    except NotDone as exc:
        tell(f"Anisotropy: {exc}", error=True)
        return 1
    except Exception as exc:  # noqa: BLE001  nothing leaves a click unsaid, and no traceback names the key
        tell(f"Anisotropy: the helper stopped ({type(exc).__name__}). Nothing was sent. Click again, or use the menu in Abaqus", error=True)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
