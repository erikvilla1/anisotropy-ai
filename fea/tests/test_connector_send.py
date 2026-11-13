"""The connector sending its bundle (ADR-0094, step 5): `tools/anisotropy_connector.py --send` against a server on this machine that
plays the API's one route. The ODB reader is replaced as in test_anisotropy_connector.py; the request itself is the real one, over a
socket. No Abaqus runs here: sending from Abaqus's own Python is checked on the founder's machine."""

from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from test_anisotropy_connector import connector, job, reader_of  # noqa: F401  the fixtures of the connector's own tests

TOKEN = "anisotropy_upload_" + "k" * 43
UPLOAD = {"id": "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", "bundle_bytes": 1, "bundle_sha256": "ab" * 32, "verdict": "agrees",
          "job_id": "7d0c7b0a-55aa-4f0e-9a3c-0a8f0e1b2c33", "not_compared": None}


class Site:
    """A server on this machine that keeps every request it gets and answers each with what the test set."""

    def __init__(self, status=201, body=None, headers=None):
        self.status, self.body, self.headers, self.requests = status, json.dumps(UPLOAD if body is None else body).encode() if not isinstance(body, bytes) else body, headers or {}, []
        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                data = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                site.requests.append({"method": "POST", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": data})
                self.send_response(site.status)
                for name, value in site.headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(site.body)))
                self.end_headers()
                self.wfile.write(site.body)

            do_GET = do_POST  # noqa: N815  a redirect followed would arrive as a GET

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.address = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def site():
    made = []

    def make(**options) -> Site:
        made.append(Site(**options))
        return made[-1]
    yield make
    for one in made:
        one.close()


@pytest.fixture
def token_file(tmp_path):
    path = tmp_path / "token.txt"
    path.write_text(TOKEN + "\n", encoding="utf-8")
    return path


def command(job, out, *more) -> list[str]:  # noqa: F811
    return [str(job.odb), "--units", "mm-MPa", "--coupon", "d3039-im7-8552", "--out", str(out), *more]


def test_send_posts_the_bundle_with_the_token_and_says_what_the_site_answered(connector, job, site, token_file, tmp_path, capsys):  # noqa: F811
    api, out = site(), tmp_path / "Job-1-anisotropy.zip"
    assert connector.run(command(job, out, "--send", api.address + "/api/", "--token-file", str(token_file), "--our-run", UPLOAD["job_id"]),
                         read_job=reader_of(job)) == 0
    (request,) = api.requests
    assert request["path"] == f"/api/v1/connector/uploads?job_id={UPLOAD['job_id']}"
    assert request["headers"]["authorization"] == f"Bearer {TOKEN}" and request["headers"]["content-type"] == "application/zip"
    assert request["headers"]["user-agent"] == connector.CONNECTOR and request["body"] == out.read_bytes()  # the bundle as written, and nothing else
    said = capsys.readouterr()
    assert f"sent: upload {UPLOAD['id']}, yours alone" in said.out and f"Agrees with ours: beside the run {UPLOAD['job_id']}" in said.out
    assert TOKEN not in said.out + said.err and TOKEN[-8:] not in said.out + said.err  # the token is never printed


def test_the_token_comes_from_the_environment_when_no_file_is_named_and_an_upload_not_compared_says_why(connector, job, site, tmp_path, monkeypatch, capsys):  # noqa: F811
    api = site(body={**UPLOAD, "verdict": None, "job_id": None, "not_compared": "you have no finished run of d3039-im7-8552 here"})
    monkeypatch.setenv(connector.TOKEN_VARIABLE, f"  {TOKEN}  ")
    assert connector.run(command(job, tmp_path / "b.zip", "--send", api.address), read_job=reader_of(job)) == 0
    assert api.requests[0]["path"] == "/v1/connector/uploads" and api.requests[0]["headers"]["authorization"] == f"Bearer {TOKEN}"
    assert "not compared yet: you have no finished run of d3039-im7-8552 here" in capsys.readouterr().out


def test_what_sending_needs_is_judged_before_the_odb_is_read(connector, job, site, token_file, tmp_path, monkeypatch, capsys):  # noqa: F811
    api, out, seen = site(), tmp_path / "none.zip", []
    monkeypatch.delenv(connector.TOKEN_VARIABLE, raising=False)
    other = tmp_path / "other.txt"
    other.write_text("a password, not a token", encoding="utf-8")
    for more, reason in (
        (["--send", api.address], "--send needs your upload token"),
        (["--send", api.address, "--token-file", str(tmp_path / "missing.txt")], "no token file at"),
        (["--send", api.address, "--token-file", str(other)], "the file other.txt does not hold an upload token"),
        (["--send", "http://example.com/api", "--token-file", str(token_file)], "--send takes an https address"),
        (["--send", "example.com/api", "--token-file", str(token_file)], "--send takes the address of Anisotropy's API"),
        (["--send", api.address + "/api?x=1", "--token-file", str(token_file)], "--send takes the address of Anisotropy's API"),
        (["--send", "https://someone:secret@example.com/api", "--token-file", str(token_file)], "--send takes the address of Anisotropy's API"),
    ):
        assert connector.run(command(job, out, *more), read_job=reader_of(job, seen)) == 2
        said = capsys.readouterr().err
        assert f"refused: {reason}" in said and "a password" not in said and "secret" not in said and not out.exists()
    assert seen == [] and api.requests == []
    assert connector.run(command(job, out, "--token-file", str(token_file)), read_job=reader_of(job, seen)) == 2  # a token with nowhere to send it
    assert "--token-file and --our-run go with --send" in capsys.readouterr().err and seen == []


@pytest.mark.parametrize("answer, said", [
    ({"status": 401, "body": {"detail": "the request carries none that stands"}}, "not sent: the site refused it (401): the request carries none that stands"),
    ({"status": 422, "body": {"detail": "Not a bundle this version takes"}}, "not sent: the site refused it (422): Not a bundle this version takes"),
    ({"status": 503, "body": b"<html>bad gateway</html>"}, "not sent: the site refused it (503). The bundle is written"),
    ({"status": 201, "body": b"<html>welcome</html>"}, "not sent: the address answered, and not as Anisotropy's API does"),
])
def test_a_bundle_the_site_does_not_take_stays_on_the_disk_and_the_reason_is_said(connector, job, site, token_file, tmp_path, capsys, answer, said):  # noqa: F811
    api, out = site(**answer), tmp_path / "Job-1-anisotropy.zip"
    assert connector.run(command(job, out, "--send", api.address, "--token-file", str(token_file)), read_job=reader_of(job)) == 1
    err = capsys.readouterr().err
    assert said in err and f"The bundle is written: {out}" in err and out.is_file() and TOKEN not in err


def test_a_redirect_is_not_followed_so_the_token_goes_nowhere_else(connector, job, site, token_file, tmp_path, capsys):  # noqa: F811
    elsewhere = site()
    api = site(status=302, body=b"", headers={"Location": elsewhere.address + "/cdn-cgi/access/login"})
    out = tmp_path / "Job-1-anisotropy.zip"
    assert connector.run(command(job, out, "--send", api.address, "--token-file", str(token_file)), read_job=reader_of(job)) == 1
    assert "not sent: the address answered with a redirect (302), as a sign-in page does" in capsys.readouterr().err
    assert len(api.requests) == 1 and elsewhere.requests == [] and out.is_file()


def test_an_address_nothing_answers_at_is_said(connector, job, token_file, tmp_path, capsys):  # noqa: F811
    with socket.socket() as probe:  # a port nothing listens on
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    out = tmp_path / "Job-1-anisotropy.zip"
    assert connector.run(command(job, out, "--send", f"http://127.0.0.1:{port}", "--token-file", str(token_file)), read_job=reader_of(job)) == 1
    assert "not sent: the address did not answer" in capsys.readouterr().err and out.is_file()


def test_the_address_is_the_apis_with_the_connectors_route(connector):  # noqa: F811
    assert connector.send_address("https://studio.example.com/api") == "https://studio.example.com/api/v1/connector/uploads"
    assert connector.send_address(" https://studio.example.com/api/ ", "a b") == "https://studio.example.com/api/v1/connector/uploads?job_id=a+b"
    assert connector.send_address("http://localhost:8000") == "http://localhost:8000/v1/connector/uploads"
    for bad in ("ftp://example.com", "https://", "http://10.0.0.5:8000", "https://example.com/api#x"):
        with pytest.raises(connector.Refused):
            connector.send_address(bad)
