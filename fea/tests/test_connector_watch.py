"""The connector's watched folder (ADR-0094, step 8): `tools/anisotropy_connector.py --watch <folder>` deals with each job as it
finishes there. A job is the files Abaqus leaves: `<job>.odb`, `<job>.inp`, a `.sta` whose last line is Abaqus's own ending, and a
`.lck` while it runs. The ODB reader is replaced as in test_anisotropy_connector.py and the site is the server of
test_connector_send.py. No Abaqus runs here: the watch under `abaqus python` is checked on the founder's machine."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from test_anisotropy_connector import connector, job, reader_of  # noqa: F401  the fixtures of the connector's own tests
from test_connector_send import TOKEN, site, token_file  # noqa: F401

COMPLETED = " THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n"
STEPS = " SUMMARY OF JOB INFORMATION:\n STEP  INC ATT SEVERE EQUIL TOTAL  TOTAL      STEP       INC OF       DOF    IF\n    1     1   1     0     1     1  1.00       1.00       1.000\n"


def put(folder: Path, job, name: str, ending: str | None = COMPLETED, locked: bool = False) -> Path:  # noqa: F811
    """A job named `name` in the folder, as Abaqus leaves it: finished (`ending`), still running (`locked`, or a `.sta` with no
    ending yet), or an ODB with no status file (`ending` None)."""
    shutil.copyfile(job.odb, folder / f"{name}.odb")
    shutil.copyfile(job.deck, folder / f"{name}.inp")
    if ending is not None:
        (folder / f"{name}.sta").write_text(STEPS + ending, encoding="utf-8")
    if locked:
        (folder / f"{name}.lck").write_text("", encoding="utf-8")
    return folder / f"{name}.odb"


def record_of(folder: Path) -> dict:
    return json.loads((folder / "anisotropy-watch.json").read_text(encoding="utf-8"))["jobs"]


def test_one_look_takes_each_finished_job_once_and_says_why_it_leaves_the_others(connector, job, tmp_path, capsys):  # noqa: F811
    put(tmp_path, job, "Done-1")
    put(tmp_path, job, "Running-1", locked=True)
    put(tmp_path, job, "Starting-1", ending="")
    put(tmp_path, job, "Failed-1", ending=" THE ANALYSIS HAS NOT BEEN COMPLETED\n")
    put(tmp_path, job, "Copied-1", ending=None)
    seen = []
    command = ["--watch", str(tmp_path), "--units", "mm-MPa", "--existing", "--once"]
    assert connector.run(command, read_job=reader_of(job, seen)) == 1  # one job Abaqus did not complete
    said = capsys.readouterr()
    assert f"watching {tmp_path} for jobs that finish, once; each bundle is written beside its ODB and nothing is sent" in said.out
    assert [name for name, *_ in seen] == ["Done-1.odb"] and (tmp_path / "Done-1-anisotropy.zip").is_file()
    assert "bundle version 1 of Done-1, in mm-MPa" in said.out
    assert "Failed-1: Abaqus did not complete the analysis, so there is nothing to send" in said.err
    assert "Copied-1: no Copied-1.sta beside the ODB, so the watch cannot tell that the job finished here" in said.err
    assert sorted(p.name for p in tmp_path.glob("*-anisotropy.zip")) == ["Done-1-anisotropy.zip"]
    record = record_of(tmp_path)
    assert {name: entry["state"] for name, entry in record.items()} == {"Done-1": "written", "Failed-1": "not completed", "Copied-1": "not taken"}
    assert record["Done-1"]["bundle"] == "Done-1-anisotropy.zip" and len(record["Done-1"]["bundle_sha256"]) == 64
    assert not (tmp_path / "anisotropy-watch.json.new").exists()

    # the same folder again: nothing is read and nothing is said twice; the running jobs are still waited for
    assert connector.run(command, read_job=reader_of(job, seen)) == 0
    said = capsys.readouterr()
    assert len(seen) == 1 and "Failed-1" not in said.err and "Copied-1" not in said.err

    # the two that were running finish, and one job is run again: its ODB is another one, so it is taken again
    (tmp_path / "Running-1.lck").unlink()
    (tmp_path / "Starting-1.sta").write_text(STEPS + COMPLETED, encoding="utf-8")
    again = tmp_path / "Done-1.odb"
    again.write_bytes(again.read_bytes() + b" run again")
    assert connector.run(command, read_job=reader_of(job, seen)) == 0
    assert sorted(name for name, *_ in seen[1:]) == ["Done-1.odb", "Running-1.odb", "Starting-1.odb"]
    assert {name: entry["state"] for name, entry in record_of(tmp_path).items()} == {
        "Done-1": "written", "Running-1": "written", "Starting-1": "written", "Failed-1": "not completed", "Copied-1": "not taken"}


def test_jobs_finished_before_the_watch_are_left_alone_and_one_that_finishes_during_it_is_sent(connector, job, site, token_file, tmp_path, capsys):  # noqa: F811
    folder = tmp_path / "jobs"
    folder.mkdir()
    put(folder, job, "Old-1")
    put(folder, job, "New-1", locked=True)
    there = site()
    looks = []

    def sleep(seconds):
        """What happens between two looks: the running job finishes, then the user presses Ctrl+C."""
        looks.append(seconds)
        if len(looks) == 1:
            (folder / "New-1.lck").unlink()
        if len(looks) == 3:
            raise KeyboardInterrupt

    args = connector.parse(["--watch", str(folder), "--units", "mm-MPa", "--coupon", "d3039-im7-8552", "--every", "2", "--send", there.address,
                            "--token-file", str(token_file)])
    url, token = connector.send_address(args.send), connector.token_of(args.token_file)
    seen = []
    assert connector.watch(args, url, token, reader_of(job, seen), sleep=sleep) == 0
    said = capsys.readouterr()
    assert looks == [2.0, 2.0, 2.0] and [name for name, *_ in seen] == ["New-1.odb"]
    assert f"every 2 s; each bundle is sent to {there.address}. End with Ctrl+C" in said.out
    assert "1 job had finished before the watch started and is left alone: Old-1. Add --existing to take them too" in said.out
    assert "sent: upload 0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11, yours alone" in said.out and "the watch has ended" in said.out
    assert len(there.requests) == 1 and there.requests[0]["path"] == "/v1/connector/uploads"
    assert there.requests[0]["body"] == (folder / "New-1-anisotropy.zip").read_bytes()
    record = record_of(folder)
    assert record["Old-1"]["state"] == "before the watch" and not (folder / "Old-1-anisotropy.zip").exists()
    assert record["New-1"]["state"] == "sent" and record["New-1"]["upload"] == "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11" and record["New-1"]["verdict"] == "agrees"
    kept = (folder / "anisotropy-watch.json").read_text(encoding="utf-8")
    assert TOKEN not in kept and TOKEN not in said.out + said.err  # the token is in the request and nowhere else

    # the next watch of the folder knows both: the old job is not "before" anything new, and nothing is sent again
    assert connector.run(["--watch", str(folder), "--units", "mm-MPa", "--once", "--send", there.address, "--token-file", str(token_file)],
                         read_job=reader_of(job, seen)) == 0
    assert len(there.requests) == 1 and len(seen) == 1 and "left alone" not in capsys.readouterr().out


def test_a_job_that_cannot_be_bundled_or_sent_is_said_and_written_down_and_the_watch_goes_on(connector, job, site, token_file, tmp_path, capsys):  # noqa: F811
    put(tmp_path, job, "A-no-deck")
    (tmp_path / "A-no-deck.inp").unlink()
    put(tmp_path, job, "B-fine")
    there = site(status=413, body={"detail": "A bundle is at most 50 MB as sent"})
    command = ["--watch", str(tmp_path), "--units", "mm-MPa", "--existing", "--once", "--send", there.address, "--token-file", str(token_file)]
    assert connector.run(command, read_job=reader_of(job)) == 1
    said = capsys.readouterr()
    assert "A-no-deck: refused: no input file at" in said.err
    assert "not sent: the site refused it (413): A bundle is at most 50 MB as sent. The bundle is written:" in said.err
    record = record_of(tmp_path)
    assert record["A-no-deck"]["state"] == "refused" and record["B-fine"]["state"] == "not sent"
    assert record["B-fine"]["said"] == "the site refused it (413): A bundle is at most 50 MB as sent" and (tmp_path / "B-fine-anisotropy.zip").is_file()

    def stops(path, step, frame, instance):
        raise RuntimeError("an error nobody planned for")
    put(tmp_path, job, "C-stops")
    assert connector.run(command, read_job=stops) == 1  # A and B are not tried again; C's own trouble is its own
    said = capsys.readouterr()
    assert "C-stops: the connector stopped on this job" in said.err and "RuntimeError: an error nobody planned for" in said.err
    assert "A-no-deck" not in said.err and len(there.requests) == 1
    assert record_of(tmp_path)["C-stops"]["state"] == "refused"


def test_the_watch_is_asked_for_in_one_way_and_refuses_what_it_cannot_do(connector, job, tmp_path, monkeypatch, capsys):  # noqa: F811
    for command, words in (([], "give one finished job's .odb, or --watch <folder>"),
                           ([str(job.odb), "--watch", str(tmp_path)], "give one finished job's .odb, or --watch <folder>"),
                           ([str(job.odb), "--once"], "--every, --existing and --once go with --watch"),
                           (["--watch", str(tmp_path), "--cae", "model.cae"], "--cae names one job's files and cannot go with --watch"),
                           (["--watch", str(tmp_path), "--out", "b.zip", "--inp", "a.inp"], "--inp, --out name one job's files and cannot go with --watch"),
                           (["--watch", str(tmp_path), "--every", "0.2"], "--every takes a number of seconds, 1 or more")):
        assert connector.run([*command, "--units", "mm-MPa"]) == 2
        assert words in capsys.readouterr().err
    assert connector.run(["--watch", str(tmp_path / "missing"), "--units", "mm-MPa", "--once"]) == 2
    assert "refused: no folder at" in capsys.readouterr().err
    (tmp_path / "anisotropy-watch.json").write_text("not ours", encoding="utf-8")
    assert connector.run(["--watch", str(tmp_path), "--units", "mm-MPa", "--once"]) == 2
    assert "is not the watch's own record: move it away" in capsys.readouterr().err
    os.remove(tmp_path / "anisotropy-watch.json")
    monkeypatch.setitem(__import__("sys").modules, "abaqus", type("abaqus", (), {"mdb": object()}))  # Abaqus/CAE's kernel
    assert connector.run(["--watch", str(tmp_path), "--units", "mm-MPa", "--once"]) == 2


def test_where_a_job_stands_is_read_from_the_end_of_its_status_file(connector, job, tmp_path):  # noqa: F811
    odb = put(tmp_path, job, "Long-1", ending="")
    assert connector.job_state(odb) == "running"
    with (tmp_path / "Long-1.sta").open("a", encoding="utf-8") as handle:
        handle.write("    1     2   1     0     1     2  1.00       1.00       0.1\n" * 400 + COMPLETED)  # the ending is far past the first lines
    assert connector.job_state(odb) == "completed"
    (tmp_path / "Long-1.lck").write_text("", encoding="utf-8")
    assert connector.job_state(odb) == "running"  # a lock is Abaqus still holding the ODB, whatever the status file says
    assert connector.job_state(put(tmp_path, job, "Copied-1", ending=None)) == "no status file"
