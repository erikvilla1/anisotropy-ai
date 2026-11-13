"""The exchange bundle with Abaqus, version 1 (ADR-0094): one zip that a connector writes under the user's own Abaqus and our tools read.

    manifest.json                        what the bundle holds: the format's version, the unit system as stated, who wrote it and when,
                                         and each file with its size and SHA-256
    model/<job>.inp                      "deck": the input file Abaqus solved (required)
    results/<job>-every-output.csv       "every_output": every element and ply in `tools/abaqus_every_output.py`'s columns (required)
    results/<job>-every-output-RF.csv    "reactions": the reaction at every node that carries one
    model/<job>-model.json               "model": the model as built in Abaqus/CAE, read from the .cae (a later step writes it)
    model/<job>.jnl                      "journal": Abaqus/CAE's journal, kept as text

A bundle is data. Nothing in it is ever executed: a journal or a script is stored and read as text. `open_bundle` checks the whole
bundle before anything is read from it and refuses it with every reason at once (ADR-0003): a file the manifest does not list, a path
that leaves the bundle, a size or a digest that does not match, a key this version does not know, a unit system a deck is not written
in. `write_bundle` writes one from files on disk, the same bytes for the same files, and reads it back before it returns.

The standard library only, and nothing newer than Python 3.10: the connector runs this file under Abaqus's own Python (Abaqus 2024 or
later), where our package and numpy are not installed.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

BUNDLE_VERSION = 1
MANIFEST = "manifest.json"
UNITS = ("mm-MPa", "m-Pa")  # the systems a deck is written in (`anisotropy_fea.units.DECK_UNIT_SYSTEMS`; a test keeps the two equal)
# role -> (required, the folder `write_bundle` puts it in, the endings it may have)
ROLES = {
    "deck": (True, "model", (".inp",)),
    "every_output": (True, "results", (".csv",)),
    "reactions": (False, "results", (".csv",)),
    "model": (False, "model", (".json",)),
    "journal": (False, "model", (".jnl", ".rpy", ".txt")),
}
MANIFEST_KEYS = ("bundle_version", "created", "units", "written_by", "job", "coupon", "results", "files")
REQUIRED_KEYS = ("bundle_version", "created", "units", "written_by", "files")
WRITTEN_BY_KEYS = ("connector", "abaqus", "python")
# where the results were read in the ODB; no path on the user's machine is carried
RESULTS_KEYS = ("solver", "created", "step", "frame_index", "frame", "instance")
MAX_BYTES = 256 * 1024 * 1024  # the files of one bundle, unpacked; the size of a real job's bundle is not measured yet (ADR-0094)
MAX_MANIFEST_BYTES = 64 * 1024
CREATED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")  # UTC, to the second
NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9 ._()+-]{0,119}$")  # a file's own name inside the bundle
SHA256 = re.compile(r"^[0-9a-f]{64}$")
EPOCH = (1980, 1, 1, 0, 0, 0)  # every member's time in the zip: the same files give the same bundle


class BundleRefused(ValueError):
    """The bundle breaks the format; `problems` lists every reason found."""

    def __init__(self, source, problems):
        self.source = str(source)
        self.problems = tuple(problems)
        super().__init__(f"{self.source}: " + "; ".join(self.problems))


@dataclass(frozen=True)
class BundleFile:
    role: str
    path: str  # inside the bundle, with forward slashes
    bytes: int
    sha256: str


@dataclass(frozen=True)
class Bundle:
    source: Path
    sha256: str  # of the zip itself: the bundle's identity
    manifest: dict
    files: dict  # role -> BundleFile

    @property
    def units(self) -> str:
        return self.manifest["units"]

    def read(self, role: str) -> bytes:
        """One file's bytes, checked again against the manifest as they are read."""
        entry = self.files[role]
        with zipfile.ZipFile(str(self.source)) as archive:
            data = archive.read(entry.path)
        if len(data) != entry.bytes or hashlib.sha256(data).hexdigest() != entry.sha256:
            raise BundleRefused(self.source, [f"{entry.path} changed since the bundle was checked"])
        return data

    def text(self, role: str) -> str:
        """One file as text. A journal may hold bytes that are not UTF-8 (a path on the user's machine); they are replaced, not refused."""
        return self.read(role).decode("utf-8-sig", errors="replace" if role == "journal" else "strict")

    def extract(self, folder) -> dict:
        """Write every listed file under `folder` at its path in the bundle; role -> the file written."""
        out = {}
        for role, entry in self.files.items():
            target = Path(folder).joinpath(*PurePosixPath(entry.path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(self.read(role))
            out[role] = target
        return out


def file_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_problem(name: str):
    """Why a member's path may not be in a bundle, or None: every part a plain name, forward slashes, at most one folder deep."""
    if "\\" in name or name.startswith("/") or name.endswith("/"):
        return "is not a plain relative path with forward slashes"
    parts = name.split("/")
    if len(parts) > 2:
        return "lies more than one folder deep"
    for part in parts:
        if part in ("", ".", "..") or not NAME.match(part) or part.endswith((".", " ")):
            return f"has a part that is not a plain file name ({part!r})"
    return None


def _manifest_problems(manifest) -> list:
    """Every way the manifest breaks version 1, apart from the files' own bytes."""
    if not isinstance(manifest, dict):
        return ["manifest.json is not a JSON object"]
    problems = []
    version = manifest.get("bundle_version")
    if type(version) is not int or version != BUNDLE_VERSION:
        return [f"bundle_version is {version!r}; this reader takes version {BUNDLE_VERSION} only"]
    for key in REQUIRED_KEYS:
        if key not in manifest:
            problems.append(f"manifest.json has no {key}")
    for key in manifest:
        if key not in MANIFEST_KEYS:
            problems.append(f"manifest.json has a key version {BUNDLE_VERSION} does not know: {key}")
    if "created" in manifest and not (isinstance(manifest["created"], str) and CREATED.match(manifest["created"])):
        problems.append(f"created is {manifest['created']!r}, not a UTC time written as 2026-11-12T21:36:00Z")
    if "units" in manifest and manifest["units"] not in UNITS:
        problems.append(f"units is {manifest['units']!r}; a deck is written in one of {', '.join(UNITS)}, and nothing is inferred from the numbers")
    written_by = manifest.get("written_by")
    if "written_by" in manifest:
        if not isinstance(written_by, dict) or not isinstance(written_by.get("connector"), str) or not written_by.get("connector"):
            problems.append("written_by does not name the connector that wrote the bundle")
        else:
            for key, value in written_by.items():
                if key not in WRITTEN_BY_KEYS:
                    problems.append(f"written_by has a key version {BUNDLE_VERSION} does not know: {key}")
                elif value is not None and not isinstance(value, str):
                    problems.append(f"written_by.{key} is not text")
    for key in ("job", "coupon"):
        if manifest.get(key) is not None and not (isinstance(manifest[key], str) and len(manifest[key]) <= 200):
            problems.append(f"{key} is not a text of at most 200 characters")
    results = manifest.get("results")
    if results is not None:
        if not isinstance(results, dict):
            problems.append("results is not an object")
        else:
            for key, value in results.items():
                if key not in RESULTS_KEYS:
                    problems.append(f"results has a key version {BUNDLE_VERSION} does not know: {key}")
                elif not isinstance(value, (str, int)) or isinstance(value, bool):
                    problems.append(f"results.{key} is neither text nor a whole number")
    files = manifest.get("files")
    if "files" in manifest:
        if not isinstance(files, dict):
            return problems + ["files is not an object of roles"]
        for role, (required, _, _) in ROLES.items():
            if required and role not in files:
                problems.append(f"files has no {role}: a bundle needs {', '.join(r for r, rule in ROLES.items() if rule[0])}")
        seen = {}
        for role, entry in files.items():
            if role not in ROLES:
                problems.append(f"files has a role version {BUNDLE_VERSION} does not know: {role}")
                continue
            if not isinstance(entry, dict) or set(entry) != {"path", "bytes", "sha256"}:
                problems.append(f"files.{role} must give path, bytes and sha256, and nothing else")
                continue
            path, size, digest = entry["path"], entry["bytes"], entry["sha256"]
            if not isinstance(path, str) or path_problem(path) or path == MANIFEST:
                why = "is not text" if not isinstance(path, str) else "is the manifest's own name" if path == MANIFEST else path_problem(path)
                problems.append(f"files.{role}: the path {path!r} {why}")
            else:
                if not path.lower().endswith(ROLES[role][2]):
                    problems.append(f"files.{role}: {path} does not end in {' or '.join(ROLES[role][2])}")
                if path.lower() in seen:
                    problems.append(f"files.{role} and files.{seen[path.lower()]} name the same file, {path}")
                seen[path.lower()] = role
            if type(size) is not int or size < 0:
                problems.append(f"files.{role}: bytes is not a whole number of bytes")
            if not isinstance(digest, str) or not SHA256.match(digest):
                problems.append(f"files.{role}: sha256 is not 64 lower-case hexadecimal digits")
    return problems


def open_bundle(path, max_bytes: int = MAX_BYTES) -> Bundle:
    """Check a bundle whole and return it, or refuse it with every reason (`BundleRefused`). Nothing is unpacked to disk."""
    path = Path(path)
    if not path.is_file():
        raise BundleRefused(path, ["no such file"])
    if not zipfile.is_zipfile(str(path)):
        raise BundleRefused(path, ["not a zip file"])
    problems = []
    try:
        archive = zipfile.ZipFile(str(path))
    except (zipfile.BadZipFile, OSError) as exc:
        raise BundleRefused(path, [f"the zip cannot be read: {exc}"]) from None
    with archive:
        members = {}
        for info in archive.infolist():
            if info.is_dir():
                continue  # a folder's own entry holds nothing
            name = info.filename
            if name in members:
                problems.append(f"{name} is in the zip twice")
            members[name] = info
            if info.flag_bits & 0x1:
                problems.append(f"{name} is encrypted")
            if stat.S_ISLNK(info.external_attr >> 16):
                problems.append(f"{name} is a link, not a file")
            why = path_problem(name)
            if why:
                problems.append(f"the member {name!r} {why}")
        total = sum(info.file_size for info in members.values())
        if total > max_bytes:
            problems.append(f"the files unpack to {total} bytes, more than the {max_bytes} a bundle may hold")
        if MANIFEST not in members:
            raise BundleRefused(path, problems + [f"no {MANIFEST} at the top of the zip"])
        if members[MANIFEST].file_size > MAX_MANIFEST_BYTES:
            raise BundleRefused(path, problems + [f"{MANIFEST} is larger than {MAX_MANIFEST_BYTES} bytes"])
        if problems:
            raise BundleRefused(path, problems)  # nothing is read from a zip whose members are not plain files
        try:
            manifest = json.loads(archive.read(MANIFEST).decode("utf-8-sig"))
        except (ValueError, zipfile.BadZipFile) as exc:
            raise BundleRefused(path, [f"{MANIFEST} is not JSON in UTF-8: {exc}"]) from None
        problems += _manifest_problems(manifest)
        entries = manifest.get("files") if isinstance(manifest, dict) and isinstance(manifest.get("files"), dict) else {}
        files, listed = {}, set()
        for role, entry in entries.items():
            if role not in ROLES or not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                continue  # already a problem above
            name = entry["path"]
            listed.add(name)
            if name not in members:
                problems.append(f"files.{role}: {name} is not in the zip")
                continue
            if type(entry.get("bytes")) is not int or not isinstance(entry.get("sha256"), str):
                continue
            try:
                data = archive.read(name)
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                problems.append(f"{name} cannot be read from the zip: {exc}")
                continue
            if len(data) != entry["bytes"]:
                problems.append(f"{name} holds {len(data)} bytes; the manifest says {entry['bytes']}")
            elif hashlib.sha256(data).hexdigest() != entry["sha256"]:
                problems.append(f"{name} does not match its SHA-256 in the manifest: the file changed after the bundle was written")
            elif role != "journal":
                try:
                    data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    problems.append(f"{name} is not text in UTF-8")
            files[role] = BundleFile(role=role, path=name, bytes=entry["bytes"], sha256=entry["sha256"])
        for name in sorted(set(members) - listed - {MANIFEST}):
            problems.append(f"{name} is in the zip and not in the manifest")
    if problems:
        raise BundleRefused(path, problems)
    return Bundle(source=path, sha256=file_sha256(path), manifest=manifest, files=files)


def write_bundle(out, files: dict, units: str, connector: str, abaqus=None, python=None, job=None, coupon=None, results=None,
                 created=None) -> Bundle:
    """Write a version 1 bundle to `out` from files on disk (`files`: role -> path) and return it as read back. The file names are kept;
    `created` is a UTC time written as 2026-11-12T21:36:00Z, now when not given. Refuses what `open_bundle` would refuse."""
    out = Path(out)
    problems = []
    for role, (required, _, _) in ROLES.items():
        if required and role not in files:
            problems.append(f"no {role} given")
    for role, source in files.items():
        if role not in ROLES:
            problems.append(f"{role} is not a role of version {BUNDLE_VERSION}")
        elif not Path(source).is_file():
            problems.append(f"{role}: no file at {source}")
    if problems:
        raise BundleRefused(out, problems)
    created = created or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest = {"bundle_version": BUNDLE_VERSION, "created": created, "units": units,
                "written_by": {"connector": connector, "abaqus": abaqus, "python": python}, "job": job, "coupon": coupon, "files": {}}
    if results is not None:
        manifest["results"] = {key: results[key] for key in RESULTS_KEYS if key in results}
    payload = {}
    for role in ROLES:
        if role not in files:
            continue
        data = Path(files[role]).read_bytes()
        name = f"{ROLES[role][1]}/{Path(files[role]).name}"
        manifest["files"][role] = {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        payload[name] = data
    problems = _manifest_problems(manifest)
    if problems:
        raise BundleRefused(out, problems)
    payload[MANIFEST] = (json.dumps(manifest, indent=1, sort_keys=True) + "\n").encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(out), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(payload):
            info = zipfile.ZipInfo(name, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, payload[name])
    return open_bundle(out)
