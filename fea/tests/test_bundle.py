"""The exchange bundle with Abaqus, version 1 (ADR-0094): what `write_bundle` writes reads back, the same files give the same bytes, and
`open_bundle` refuses a bundle that breaks the format with every reason at once. The module runs under a Python with nothing installed,
as the connector will run it under Abaqus's own."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from anisotropy_fea import bundle as bundle_module
from anisotropy_fea.bundle import BUNDLE_VERSION, MANIFEST, UNITS, BundleRefused, open_bundle, path_problem, write_bundle
from anisotropy_fea.units import DECK_UNIT_SYSTEMS

CREATED = "2026-11-12T21:36:00Z"
DECK = "*Heading\n** a deck\n*Node\n1, 0., 0., 0.\n"
CSV = "Element,Layer\n1,1\n"


@pytest.fixture
def sources(tmp_path):
    folder = tmp_path / "job"
    folder.mkdir()
    (folder / "Job-1.inp").write_text(DECK, encoding="utf-8", newline="\n")
    (folder / "Job-1-every-output.csv").write_text(CSV, encoding="utf-8", newline="\n")
    (folder / "Job-1-every-output-RF.csv").write_text("Node,X,Y,RF1,RF2\n", encoding="utf-8", newline="\n")
    (folder / "Job-1.jnl").write_bytes(b"# -*- coding: mbcs -*-\nmdb.Model(name='C:\\\\temp\\\\caf\xe9')\n")
    return {"deck": folder / "Job-1.inp", "every_output": folder / "Job-1-every-output.csv",
            "reactions": folder / "Job-1-every-output-RF.csv", "journal": folder / "Job-1.jnl"}


def written(tmp_path, sources, name="bundle.zip", **changes):
    arguments = {"units": "mm-MPa", "connector": "test 1", "abaqus": "Abaqus/Standard 2025", "python": "3.10.5", "job": "Job-1",
                 "created": CREATED, "results": {"step": "Step-1", "frame_index": 1, "odb": "C:/temp/Job-1.odb"}}
    arguments.update(changes)
    return write_bundle(tmp_path / name, sources, **arguments)


def zipped(path: Path, manifest, members: dict[str, bytes]) -> Path:
    """A zip made by hand: the manifest as given (a dict, bytes, or None for none) and the members as given."""
    with zipfile.ZipFile(path, "w") as archive:
        if manifest is not None:
            archive.writestr(MANIFEST, manifest if isinstance(manifest, bytes) else json.dumps(manifest))
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def entry(data: bytes, path: str) -> dict:
    return {"path": path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def good_manifest() -> tuple[dict, dict[str, bytes]]:
    deck, rows = DECK.encode(), CSV.encode()
    manifest = {"bundle_version": 1, "created": CREATED, "units": "mm-MPa", "written_by": {"connector": "test 1"},
                "files": {"deck": entry(deck, "model/Job-1.inp"), "every_output": entry(rows, "results/Job-1-every-output.csv")}}
    return manifest, {"model/Job-1.inp": deck, "results/Job-1-every-output.csv": rows}


def problems_of(path: Path, **options) -> tuple[str, ...]:
    with pytest.raises(BundleRefused) as refused:
        open_bundle(path, **options)
    return refused.value.problems


def test_a_written_bundle_reads_back_with_every_file_under_its_role_and_its_digest(tmp_path, sources):
    bundle = written(tmp_path, sources)
    assert bundle.manifest["bundle_version"] == BUNDLE_VERSION == 1 and bundle.units == "mm-MPa"
    assert {role: f.path for role, f in bundle.files.items()} == {
        "deck": "model/Job-1.inp", "every_output": "results/Job-1-every-output.csv", "reactions": "results/Job-1-every-output-RF.csv",
        "journal": "model/Job-1.jnl"}
    for role, source in sources.items():
        assert bundle.read(role) == source.read_bytes() and bundle.files[role].sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert bundle.manifest["written_by"] == {"connector": "test 1", "abaqus": "Abaqus/Standard 2025", "python": "3.10.5"}
    assert bundle.manifest["results"] == {"step": "Step-1", "frame_index": 1}  # no path on the user's machine is carried
    assert bundle.sha256 == hashlib.sha256((tmp_path / "bundle.zip").read_bytes()).hexdigest()
    extracted = bundle.extract(tmp_path / "out")
    assert extracted["deck"] == tmp_path / "out" / "model" / "Job-1.inp" and extracted["deck"].read_text(encoding="utf-8") == DECK


def test_the_same_files_give_the_same_bundle_byte_for_byte(tmp_path, sources):
    assert written(tmp_path, sources, "a.zip").sha256 == written(tmp_path, sources, "b.zip").sha256
    assert written(tmp_path, sources, "c.zip", created="2026-11-12T21:36:01Z").sha256 != written(tmp_path, sources, "a.zip").sha256


def test_a_journal_is_text_whatever_its_bytes_and_nothing_in_the_module_runs_a_file(tmp_path, sources):
    text = written(tmp_path, sources).text("journal")
    assert text.startswith("# -*- coding: mbcs -*-") and "mdb.Model" in text and "\ufffd" in text  # the byte that is not UTF-8, replaced
    tree = ast.parse(Path(bundle_module.__file__).read_text(encoding="utf-8"))
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not called & {"exec", "eval", "compile", "__import__"}
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported <= set(sys.stdlib_module_names) and not imported & {"subprocess", "importlib", "runpy", "pickle", "marshal", "os"}


def test_the_module_runs_with_the_standard_library_alone_as_the_connector_will_run_it(tmp_path, sources):
    script = ("import sys; sys.path.insert(0, sys.argv[1]); import bundle; "
              "b = bundle.write_bundle(sys.argv[2], {'deck': sys.argv[3], 'every_output': sys.argv[4]}, 'm-Pa', 'connector 1'); "
              "print(bundle.open_bundle(sys.argv[2]).units, len(b.files))")
    done = subprocess.run([sys.executable, "-I", "-S", "-c", script, str(Path(bundle_module.__file__).parent), str(tmp_path / "plain.zip"),
                           str(sources["deck"]), str(sources["every_output"])], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["m-Pa", "2"]


def test_the_unit_systems_are_the_ones_a_deck_is_written_in():
    assert set(UNITS) == set(DECK_UNIT_SYSTEMS)


def test_a_good_bundle_made_by_hand_is_taken(tmp_path):
    manifest, members = good_manifest()
    assert set(open_bundle(zipped(tmp_path / "good.zip", manifest, members)).files) == {"deck", "every_output"}


def test_what_is_not_a_bundle_is_refused(tmp_path):
    assert problems_of(tmp_path / "missing.zip") == ("no such file",)
    (tmp_path / "text.zip").write_text("not a zip", encoding="utf-8")
    assert problems_of(tmp_path / "text.zip") == ("not a zip file",)
    _, members = good_manifest()
    assert problems_of(zipped(tmp_path / "bare.zip", None, members)) == ("no manifest.json at the top of the zip",)
    assert "not JSON" in problems_of(zipped(tmp_path / "broken.zip", b"{", members))[0]
    assert problems_of(zipped(tmp_path / "list.zip", b"[]", members))[0] == "manifest.json is not a JSON object"


def test_another_version_is_refused_before_anything_else_is_read(tmp_path):
    manifest, members = good_manifest()
    manifest.update(bundle_version=2, units="furlongs")
    assert problems_of(zipped(tmp_path / "v2.zip", manifest, members)) == ("bundle_version is 2; this reader takes version 1 only",)
    manifest["bundle_version"] = True
    assert "bundle_version is True" in problems_of(zipped(tmp_path / "bool.zip", manifest, members))[0]


def test_a_manifest_that_breaks_the_format_is_refused_with_every_reason_at_once(tmp_path):
    manifest, members = good_manifest()
    manifest.update(units="in-psi", created="yesterday", owner="someone", written_by={"connector": "", "host": "pc"}, job=7,
                    results={"odb": "C:/temp/Job-1.odb", "frame_index": 1.5})
    manifest["files"]["every_output"]["sha256"] = "ABC"
    manifest["files"]["script"] = entry(b"print(1)", "model/run.py")
    del manifest["files"]["deck"]
    problems = problems_of(zipped(tmp_path / "bad.zip", manifest, members))
    for expected in ("units is 'in-psi'; a deck is written in one of mm-MPa, m-Pa, and nothing is inferred from the numbers",
                     "created is 'yesterday', not a UTC time written as 2026-11-12T21:36:00Z",
                     "manifest.json has a key version 1 does not know: owner",
                     "written_by does not name the connector that wrote the bundle",
                     "job is not a text of at most 200 characters",
                     "results has a key version 1 does not know: odb",
                     "results.frame_index is neither text nor a whole number",
                     "files has no deck: a bundle needs deck, every_output",
                     "files has a role version 1 does not know: script",
                     "files.every_output: sha256 is not 64 lower-case hexadecimal digits",
                     "model/Job-1.inp is in the zip and not in the manifest"):
        assert expected in problems, (expected, problems)


@pytest.mark.parametrize("name, why", [
    ("../Job-1.inp", "has a part that is not a plain file name ('..')"),
    ("/etc/Job-1.inp", "is not a plain relative path with forward slashes"),
    ("model\\Job-1.inp", "is not a plain relative path with forward slashes"),
    ("a/b/Job-1.inp", "lies more than one folder deep"),
    ("model/.inp", "has a part that is not a plain file name ('.inp')"),
    ("C:/Job-1.inp", "has a part that is not a plain file name ('C:')"),
])
def test_a_path_that_could_leave_the_bundle_is_refused_in_the_zip_and_in_the_manifest(tmp_path, name, why):
    assert path_problem(name) == why
    manifest, members = good_manifest()
    deck = members.pop("model/Job-1.inp")
    manifest["files"]["deck"] = entry(deck, name)
    problems = problems_of(zipped(tmp_path / "path.zip", manifest, {**members, name: deck}))
    assert problems == (f"the member {name!r} {why}",)  # nothing is read from a zip whose members are not plain files
    assert path_problem("model/Job_1 (2).inp") is None and path_problem("manifest.json") is None


def test_a_file_that_does_not_match_its_manifest_is_refused(tmp_path):
    manifest, members = good_manifest()
    members["results/Job-1-every-output.csv"] = CSV.replace("1,1", "1,2").encode()
    assert problems_of(zipped(tmp_path / "changed.zip", manifest, members)) == (
        "results/Job-1-every-output.csv does not match its SHA-256 in the manifest: the file changed after the bundle was written",)
    manifest, members = good_manifest()
    members["model/Job-1.inp"] += b"*End\n"
    assert problems_of(zipped(tmp_path / "longer.zip", manifest, members)) == ("model/Job-1.inp holds 44 bytes; the manifest says 39",)
    manifest, members = good_manifest()
    del members["model/Job-1.inp"]
    assert problems_of(zipped(tmp_path / "gone.zip", manifest, members)) == ("files.deck: model/Job-1.inp is not in the zip",)


def test_a_wrong_ending_a_file_named_twice_bytes_that_are_not_text_and_a_bundle_too_large_are_refused(tmp_path):
    manifest, members = good_manifest()
    data = members.pop("model/Job-1.inp")
    manifest["files"]["deck"] = entry(data, "model/Job-1.py")
    assert problems_of(zipped(tmp_path / "ending.zip", manifest, {**members, "model/Job-1.py": data})) == (
        "files.deck: model/Job-1.py does not end in .inp",)
    manifest, members = good_manifest()
    manifest["files"]["reactions"] = dict(manifest["files"]["every_output"])
    assert problems_of(zipped(tmp_path / "twice.zip", manifest, members)) == (
        "files.reactions and files.every_output name the same file, results/Job-1-every-output.csv",)
    manifest, members = good_manifest()
    members["model/Job-1.inp"] = b"*Heading\n\xff\xfe\n"
    manifest["files"]["deck"] = entry(members["model/Job-1.inp"], "model/Job-1.inp")
    assert problems_of(zipped(tmp_path / "bytes.zip", manifest, members)) == ("model/Job-1.inp is not text in UTF-8",)
    manifest, members = good_manifest()
    assert "more than the 50 a bundle may hold" in problems_of(zipped(tmp_path / "large.zip", manifest, members), max_bytes=50)[0]


def test_a_link_in_the_zip_is_refused(tmp_path):
    manifest, members = good_manifest()
    path = zipped(tmp_path / "link.zip", manifest, members)
    with zipfile.ZipFile(path, "a") as archive:
        info = zipfile.ZipInfo("model/passwd.inp")
        info.external_attr = (0o120777 << 16)
        archive.writestr(info, "/etc/passwd")
    assert problems_of(path) == ("model/passwd.inp is a link, not a file",)


def test_writing_refuses_what_reading_would_refuse(tmp_path, sources):
    with pytest.raises(BundleRefused, match="no every_output given"):
        write_bundle(tmp_path / "x.zip", {"deck": sources["deck"]}, "mm-MPa", "test 1")
    with pytest.raises(BundleRefused, match="units is 'in-psi'"):
        written(tmp_path, sources, units="in-psi")
    with pytest.raises(BundleRefused, match="script is not a role of version 1"):
        write_bundle(tmp_path / "x.zip", {**sources, "script": sources["deck"]}, "mm-MPa", "test 1")
    renamed = sources["deck"].with_name("Job-1.txt")
    renamed.write_text(DECK, encoding="utf-8")
    with pytest.raises(BundleRefused, match="model/Job-1.txt does not end in .inp"):
        write_bundle(tmp_path / "x.zip", {**sources, "deck": renamed}, "mm-MPa", "test 1")
    assert not (tmp_path / "x.zip").exists()
