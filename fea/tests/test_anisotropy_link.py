"""The helper behind the site's links (ADR-0094 amendment 1): `tools/anisotropy_link.py` reads an `anisotropy://` link as hostile
text, connects this machine only after the user's yes to a box that names the site and the account, keeps the key in the home
directory and never says it, and opens a run by fetching its build script with the key and starting Abaqus/CAE with the same words
every time. The site is a stand-in that records each request; Abaqus is never started and no box of Windows is drawn."""

from __future__ import annotations

import importlib.util
import json
import urllib.error
from pathlib import Path

import pytest

from test_anisotropy_connector import TOOLS

SITE = "https://anisotropy.example/api"
CODE = "anisotropy_pair_" + "c_-" * 14 + "c"
KEY = "anisotropy_upload_" + "k" * 43
RUN = "0123abcd-0123-4abc-8def-0123456789ab"
OWNER = "engineer@example.com"
SCRIPT = "# The coupon D3039-CHECK as a native Abaqus/CAE model.\n# Built by anisotropy_fea 0.1.0 from D3039-CHECK\nMODEL = 'D3039-CHECK'\n"
PAIR_LINK = f"anisotropy://pair?code={CODE}&site=https%3A%2F%2Fanisotropy.example%2Fapi"
OPEN_LINK = f"anisotropy://open?run={RUN}"


@pytest.fixture
def link():
    spec = importlib.util.spec_from_file_location("anisotropy_link_under_test", TOOLS / "anisotropy_link.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Site:
    """Anisotropy's API as the helper meets it: one code of one owner, one run with its build script, every request recorded."""

    def __init__(self, owner=OWNER, script=SCRIPT, coupon="D3039-CHECK"):
        self.owner, self.script, self.coupon, self.requests, self.swapped = owner, script, coupon, [], False

    def __call__(self, request, timeout):
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        self.requests.append((request.get_method(), request.full_url, dict(request.header_items()), body))
        if request.full_url == SITE + "/v1/connector/pair":
            if body["code"] != CODE or self.swapped:
                return 401, json.dumps({"detail": "This code is not one of ours, was used already, or is older than 10 minutes."}).encode(), {}
            if body.get("look"):
                return 200, json.dumps({"owner": self.owner, "token": None}).encode(), {}
            self.swapped = True
            return 200, json.dumps({"owner": self.owner, "token": KEY, "token_id": "t", "name": body["name"]}).encode(), {}
        if request.full_url == f"{SITE}/v1/connector/runs/{RUN}/build-script":
            if dict(request.header_items()).get("Authorization") != f"Bearer {KEY}":
                return 401, b'{"detail": "no token that stands"}', {}
            return 200, self.script.encode("utf-8"), {"X-Anisotropy-Coupon": self.coupon, "Content-Type": "text/x-python"}
        return 404, b'{"detail": "No run of yours"}', {}


def said(texts):
    return lambda text, error=False: texts.append((text, error))


# ------------------------------------------------------------------------------------------------------- a link is hostile text

def test_a_link_is_one_of_two_shapes_to_the_character(link):
    assert link.read_link(PAIR_LINK) == {"what": "pair", "code": CODE, "site": SITE}
    assert link.read_link(f"anisotropy://pair/?site=https%3A%2F%2FAnisotropy.example%2Fapi%2F&code={CODE}") == {"what": "pair", "code": CODE, "site": SITE}
    assert link.read_link(OPEN_LINK) == {"what": "open", "run": RUN} and link.read_link(f"anisotropy://open/?run={RUN}")["run"] == RUN
    assert link.read_link(f"anisotropy://pair?code={CODE}&site=http%3A%2F%2Flocalhost%3A8000")["site"] == "http://localhost:8000"
    for text in ("", "anisotropy://", "anisotropy:open?run=" + RUN, "https://open?run=" + RUN, "ANISOTROPY://open?run=" + RUN.upper(),
                 f"anisotropy://open?run={RUN}&run={RUN}", f"anisotropy://open?run={RUN}&site=https%3A%2F%2Fevil.example",
                 f"anisotropy://open?run={RUN}#x", f"anisotropy://open/x?run={RUN}", f"anisotropy://open?run={RUN[:-1]}", f"anisotropy://open?run={RUN}0",
                 f"anisotropy://open?run={RUN}%0A", f"anisotropy://open?run={RUN} --replay x", f'anisotropy://open?run={RUN}" & calc & "',
                 f"anisotropy://open?run={RUN}&&calc", f"anisotropy://open?run=..%2F..%2Fx", f"anisotropy://run?run={RUN}",
                 f"anisotropy://user@open?run={RUN}", f"anisotropy://open:80?run={RUN}", f"anisotropy://pair?code={CODE}",
                 f"anisotropy://pair?code={CODE[:-1]}&site=https%3A%2F%2Fanisotropy.example",
                 f"anisotropy://pair?code={KEY}&site=https%3A%2F%2Fanisotropy.example", f"anisotropy://pair?code={CODE}&site=https%3A%2F%2Fa.example&name=x",
                 OPEN_LINK + "&" * 600, None, 7):
        with pytest.raises(link.NotDone, match="not a link Anisotropy's site makes"):
            link.read_link(text)
    for site in ("", "http%3A%2F%2Fanisotropy.example", "https%3A%2F%2Fuser%40anisotropy.example", "https%3A%2F%2Fanisotropy.example%2Fapi%3Fx%3D1",
                 "https%3A%2F%2Fanisotropy.example%2Fapi%22%20%26%20calc", "file%3A%2F%2F%2Fc%3A%2Fx"):
        with pytest.raises(link.NotDone, match="address"):  # a code of ours beside an address that is not one
            link.read_link(f"anisotropy://pair?code={CODE}&site={site}")


def test_the_address_in_a_link_is_https_with_no_name_no_question_and_nothing_a_shell_reads(link):
    assert link.site_address("https://anisotropy.dev/api/") == "https://anisotropy.dev/api" and link.site_address("http://127.0.0.1:8000") == "http://127.0.0.1:8000"
    for site in ("http://anisotropy.dev/api", "http://192.168.1.4:8000"):
        with pytest.raises(link.NotDone, match="not https"):
            link.site_address(site)
    for site in ("ftp://anisotropy.dev", "https://", "https://user@anisotropy.dev/api", "https://user:pw@anisotropy.dev", "https://anisotropy.dev/api?x=1",
                 "https://anisotropy.dev/api#x", "https://anisotropy.dev/a b", "https://anisotropy.dev/api\n", "https://anisotropy.dev:port/api",
                 "https://anisotropy.dev:99999/api", "https://anisotropy.dev/api/../x/%2e", "https://anisotropy.dev\\@evil.example", "https://[::1]/api",
                 "https://anisotropy.dev&calc", "https://-x-/api", " https://anisotropy.dev", "https://anisotropy.dev/" + "a" * 300, "", None):
        with pytest.raises(link.NotDone):
            link.site_address(site)


# ------------------------------------------------------------------------------------------------------- Connect this PC

def test_a_yes_to_the_box_that_names_the_site_and_the_account_connects_this_machine_and_the_key_is_never_said(link, tmp_path, capsys):
    site, asked, texts, home = Site(), [], [], tmp_path / "home" / ".anisotropy"
    assert link.main([PAIR_LINK], confirm=lambda text: asked.append(text) or True, tell=said(texts), caller=site, folder=home) == 0
    assert len(asked) == 1 and "Site:  anisotropy.example" in asked[0] and f"Account:  {OWNER}" in asked[0] and "replaces" not in asked[0]
    assert [(m, u, b.get("look", False)) for m, u, _h, b in site.requests] == [("POST", SITE + "/v1/connector/pair", True), ("POST", SITE + "/v1/connector/pair", False)]
    assert all("Authorization" not in headers for _m, _u, headers, _b in site.requests) and site.requests[1][3]["name"]
    assert (home / "upload-key.txt").read_text(encoding="utf-8") == KEY + "\n"
    assert json.loads((home / "machine.json").read_text()) == {"address": SITE, "owner": OWNER}
    assert json.loads((home / "connector.json").read_text()) == {"units": "", "address": SITE, "token_file": str(home / "upload-key.txt")}
    assert texts == [(f"This PC is connected to anisotropy.example as {OWNER}.\n\nGo back to the run's page and click Open in Abaqus.", False)]
    everything = capsys.readouterr()
    assert KEY not in everything.out + everything.err + repr(texts) + repr(asked) + (home / "machine.json").read_text() + (home / "connector.json").read_text()
    assert CODE not in repr(texts) + repr(asked)


def test_a_no_swaps_nothing_and_changes_nothing(link, tmp_path):
    site, texts, home = Site(), [], tmp_path / ".anisotropy"
    assert link.main([PAIR_LINK], confirm=lambda text: False, tell=said(texts), caller=site, folder=home) == 1
    assert len(site.requests) == 1 and site.requests[0][3] == {"code": CODE, "look": True} and not site.swapped and not home.exists()
    assert texts[0][1] is True and "you said no, and nothing was changed" in texts[0][0]


def test_a_code_the_site_refuses_asks_nothing_and_a_site_that_is_not_ours_connects_nothing(link, tmp_path):
    home, asked = tmp_path / ".anisotropy", []

    def confirm(text):
        asked.append(text)
        return True

    used = Site()
    used.swapped = True
    texts = []
    assert link.main([PAIR_LINK], confirm=confirm, tell=said(texts), caller=used, folder=home) == 1
    assert asked == [] and "did not take the code (401): This code is not one of ours" in texts[0][0]
    answers = {"a sign-in page": (302, b"", {"Location": "https://login.example"}), "a page": (200, b"<html>hello</html>", {}), "no owner": (200, b'{"owner": ""}', {}),
               "a list": (200, b"[1]", {}), "an error": (500, b"oops", {})}
    for name, answer in answers.items():
        texts = []
        assert link.main([PAIR_LINK], confirm=confirm, tell=said(texts), caller=lambda request, timeout, a=answer: a, folder=home) == 1, name
        assert asked == [] and texts[0][1] is True and not home.exists(), name

    def down(request, timeout):
        raise urllib.error.URLError("no route to host")

    texts = []
    assert link.main([PAIR_LINK], confirm=confirm, tell=said(texts), caller=down, folder=home) == 1
    assert "the site did not answer: no route to host" in texts[0][0] and asked == []

    class Changed(Site):  # the account changes between the look and the swap, or the swap gives no key of ours
        def __call__(self, request, timeout):
            status, body, headers = super().__call__(request, timeout)
            answer = json.loads(body)
            if answer.get("token"):
                answer.update(self.change)
            return status, json.dumps(answer).encode(), headers

    for change in ({"owner": "someone-else@example.com"}, {"token": "not a key"}, {"token": KEY + " and more"}):
        other, texts = Changed(), []
        other.change = change
        assert link.main([PAIR_LINK], confirm=lambda text: True, tell=said(texts), caller=other, folder=home) == 1
        assert "did not connect this PC" in texts[0][0] and not (home / "upload-key.txt").exists() and not (home / "machine.json").exists()


def test_a_second_link_for_another_site_or_account_says_what_it_replaces_and_only_a_yes_replaces_it(link, tmp_path):
    home, asked = tmp_path / ".anisotropy", []
    assert link.main([PAIR_LINK], confirm=lambda text: True, tell=said([]), caller=Site(), folder=home) == 0
    link.write_json(home / "machine.json", {**link.machine(home), "abaqus": "C:/SIMULIA/Commands/abaqus.bat"})
    other = Site(owner="someone-else@example.com")
    assert link.main([PAIR_LINK], confirm=lambda text: asked.append(text) or False, tell=said([]), caller=other, folder=home) == 1
    assert f"This PC is now connected to anisotropy.example as {OWNER}. A yes replaces that." in asked[0]
    assert link.machine(home)["owner"] == OWNER and (home / "upload-key.txt").read_text() == KEY + "\n"
    assert link.main([PAIR_LINK], confirm=lambda text: True, tell=said([]), caller=other, folder=home) == 0
    assert link.machine(home) == {"address": SITE, "owner": "someone-else@example.com", "abaqus": "C:/SIMULIA/Commands/abaqus.bat"}  # the setup's fact stands


# ------------------------------------------------------------------------------------------------------- Open in Abaqus

def connected(link, home: Path, abaqus: Path) -> None:
    assert link.main([PAIR_LINK], confirm=lambda text: True, tell=said([]), caller=Site(), folder=home) == 0
    abaqus.write_text("@echo off\n", encoding="utf-8")
    link.write_json(home / "machine.json", {**link.machine(home), "abaqus": str(abaqus)})


def test_open_fetches_the_owners_build_script_with_the_key_and_starts_abaqus_with_the_same_words_every_time(link, tmp_path, capsys):
    home, work, site, started, texts = tmp_path / ".anisotropy", tmp_path / "Anisotropy", Site(), [], []
    connected(link, home, tmp_path / "abaqus.bat")
    assert link.main([OPEN_LINK], tell=said(texts), caller=site, folder=home, work=work, starter=lambda command, folder: started.append((command, folder))) == 0
    assert texts == [] and started == [(str(tmp_path / "abaqus.bat"), work / "D3039-CHECK")]
    method, url, headers, body = site.requests[-1]
    assert (method, url, body) == ("GET", f"{SITE}/v1/connector/runs/{RUN}/build-script", None) and headers["Authorization"] == f"Bearer {KEY}"
    folder = work / "D3039-CHECK"
    assert (folder / "D3039-CHECK-build.py").read_text(encoding="utf-8") == SCRIPT
    assert (folder / "anisotropy-start.py").read_text(encoding="utf-8") == (TOOLS / "anisotropy_start.py").read_text(encoding="utf-8")
    assert json.loads((folder / "anisotropy-start.json").read_text()) == {
        "script": str(folder / "D3039-CHECK-build.py"), "run": RUN, "coupon": "D3039-CHECK", "connector": str(TOOLS)}
    assert KEY not in capsys.readouterr().out + (folder / "anisotropy-start.json").read_text()


def test_the_command_that_starts_abaqus_holds_nothing_from_the_link_or_the_site(link, tmp_path, monkeypatch):
    seen = {}

    class Started:
        def __init__(self, command, **more):
            seen.update(command=command, **more)

    monkeypatch.setattr(link.subprocess, "Popen", Started)
    link.start("C:/SIMULIA/Commands/abaqus.bat", tmp_path)
    assert seen["command"] == ["C:/SIMULIA/Commands/abaqus.bat", "cae", "script=anisotropy-start.py"] and seen["cwd"] == str(tmp_path)
    assert "shell" not in seen and "creationflags" not in seen  # here, without Windows
    monkeypatch.setattr(link.os, "name", "nt")
    monkeypatch.setattr(link.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(link.subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200, raising=False)
    monkeypatch.setattr(link.subprocess, "DETACHED_PROCESS", 0x8, raising=False)
    link.start("C:/SIMULIA/Commands/abaqus.bat", tmp_path)
    assert seen["creationflags"] == 0x08000000 | 0x200  # no console of its own, and not detached: that left a terminal window open (the eleventh trial)


def test_open_does_nothing_on_a_machine_that_is_not_connected_and_runs_nothing_that_is_not_ours(link, tmp_path):
    home, work, started = tmp_path / ".anisotropy", tmp_path / "Anisotropy", []

    def opened(site, **more):
        texts = []
        code = link.main([OPEN_LINK], tell=said(texts), caller=site, folder=home, work=work, starter=lambda command, folder: started.append(folder), **more)
        return code, texts[0][0] if texts else ""

    never = Site()
    code, text = opened(never)
    assert code == 1 and "not connected to your account yet: click Connect this PC" in text and never.requests == []  # no key, so nothing is asked
    connected(link, home, tmp_path / "abaqus.bat")
    for site, why in ((Site(script="import os\nos.system('calc')\n"), "not a build script Anisotropy wrote"),
                      (Site(script="x" * (link.MAX_SCRIPT_BYTES + 5)), "larger than any build script"),
                      (lambda request, timeout: (404, b'{"detail": "No run of yours"}', {}), "did not give the run's build script (404): No run of yours"),
                      (lambda request, timeout: (401, b"{}", {}), "no longer takes this PC's key"),
                      (lambda request, timeout: (302, b"", {"Location": "https://evil.example"}), "its sign-in page")):
        code, text = opened(site)
        assert code == 1 and why in text and started == [] and not work.exists(), why
    code, text = opened(Site(coupon="..\\..\\Startup\\x"))  # a coupon's name that is not a plain name is not a folder's name
    assert code == 0 and started == [work / "coupon"] and (work / "coupon" / "coupon-build.py").is_file()
    link.write_json(home / "machine.json", {"address": SITE, "owner": OWNER})
    code, text = opened(Site(), which=lambda name: None)
    assert code == 1 and "Abaqus's command was not found on this PC" in text
    link.write_json(home / "machine.json", {"address": "https://anisotropy.example/api?x", "owner": OWNER, "abaqus": str(tmp_path / "abaqus.bat")})
    assert opened(Site())[0] == 1  # an address this helper would not have written is not used


def test_anything_else_on_the_command_line_does_nothing(link, tmp_path):
    for argv in ([], [OPEN_LINK, "--replay"], ["--help"], [OPEN_LINK, PAIR_LINK]):
        texts = []
        assert link.main(argv, tell=said(texts), caller=Site(), folder=tmp_path / "none", starter=None) == 1 and texts[0][1] is True
    assert not (tmp_path / "none").exists()
