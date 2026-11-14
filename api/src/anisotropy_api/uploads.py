"""Uploads from Abaqus (ADR-0094, part 6 and step 5): a bundle a user sends from their own Abaqus is checked, stored under a prefix of
its own, and put beside a run of ours. Nothing here computes a result.

- The bundle is judged by `fea/tools/abaqus_upload.py check`, the command of step 1, started as every tool of the fea package is. One
  that breaks the format is refused with every reason and nothing is stored (ADR-0003). Nothing in a bundle is ever executed.
- It is stored as one object, `uploads/<upload id>/bundle.zip`: in the bucket when the settings name one, in a folder of the local disk
  otherwise. Its row (`records.UploadRow`) names its owner. Only the owner reads it, compares it and deletes it; a founder named in the
  settings also sees it (part 6). To anyone else it does not exist.
- The comparison is `abaqus_upload.py compare` beside a finished coupon job's own files, taken from that job's package: its
  `4-results/ours-every-output.csv` with the JSON beside it, and its deck. The verdict and every number are that command's (ADR-0001).
  No run record is written for it: the run records are read by every signed-in user, and an upload is private, so the upload's own
  row is its receipt.
- The comparison as a document (step 7) is `docs/models/upload.py`, written from the comparison the row keeps and from nothing else,
  when its owner first asks for it. It is kept beside the bundle, under the upload's own prefix, and never in the run's files, which
  every signed-in user reads.
- The connector sends with a token its owner created. The token is shown once and only its SHA-256 is kept; a cancelled token is
  refused. Nothing of an upload goes to the assistant's model provider (part 6).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .coupon_jobs import FEA, REPO, CouponJobs, Job, repository_path
from .storage import ObjectStore

TOOL = FEA / "tools" / "abaqus_upload.py"
DOCUMENT_TOOL = REPO / "docs" / "models" / "upload.py"  # the comparison as a document (ADR-0094 step 7)
LOCAL_UPLOADS = REPO / ".local" / "abaqus"  # the folder store's root when no bucket is named: .local/abaqus/uploads/<id>/bundle.zip
MAX_BUNDLE_BYTES = 50 * 1024 * 1024  # the zip as sent; the first real job's bundle (1488 elements, 8 plies) unpacks to 2.2 MB (ADR-0094)
MAX_UPLOADS = 100  # stored uploads per person; one more is refused until one is deleted
MAX_TOKENS = 10  # tokens per person that are not cancelled
TOKEN_PREFIX = "anisotropy_upload_"
CHECK_TIMEOUT_S = 120.0
COMPARE_TIMEOUT_S = 240.0
DOCUMENT_TIMEOUT_S = 180.0
OURS = ("4-results", "ours-every-output.csv")
OUR_DECKS = ("2-our-model", "abaqus")
OUR_DECK_ENDING = "-abaqus.inp"
CONNECTOR_NAME = "anisotropy-connector.zip"


class UploadRefused(Exception):
    """The bundle breaks the format; `problems` lists every reason. Nothing was stored."""

    def __init__(self, problems):
        self.problems = [str(problem) for problem in problems]
        super().__init__("; ".join(self.problems))


class ToolFailed(RuntimeError):
    """The fea package's command could not run or gave no answer."""


class NotCompared(Exception):
    """No comparison was made, and why: no run of ours to stand beside, or a run whose files are gone."""


# ------------------------------------------------------------------------------------------------------------- the tokens

def new_token() -> tuple[str, str, str]:
    """A fresh token, its SHA-256, and its last four characters. The token is 256 random bits; only the digest is kept."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return token, token_digest(token), token[-4:]


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def bearer(header: str | None) -> str | None:
    """The token of an `Authorization: Bearer <token>` header, when it has the shape of one of ours; None otherwise."""
    scheme, _, token = (header or "").strip().partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token.startswith(TOKEN_PREFIX) or len(token) > 200:
        return None
    return token


# ------------------------------------------------------------------------------------------------------------- the command

def tool_command() -> list[str] | None:
    """`uv run --project fea python fea/tools/abaqus_upload.py`, or None when uv is not on PATH."""
    uv = shutil.which("uv")
    return None if uv is None else [uv, "run", "--project", str(FEA), "python", str(TOOL)]


def document_command() -> list[str] | None:
    """`uv run --project fea python docs/models/upload.py`, or None when uv is not on PATH."""
    uv = shutil.which("uv")
    return None if uv is None else [uv, "run", "--project", str(FEA), "python", str(DOCUMENT_TOOL)]


class Uploads:
    """The store the bundles go to and the command that judges them. `command` is the tool's command line without its arguments, and
    `writer` the same for the command that writes a comparison's document."""

    def __init__(self, store: ObjectStore, command: list[str] | None, founders: frozenset[str] = frozenset(), scratch: Path | None = None,
                 writer: list[str] | None = None):
        self.store = store
        self.command = command
        self.writer = writer if writer is not None else document_command()
        self.founders = founders
        self.scratch = scratch or Path(tempfile.gettempdir()) / "anisotropy-uploads"
        self._connector: Path | None = None  # the connector's zip, once this process has written it

    def sees_all(self, user_email: str | None) -> bool:
        """Whether the requester is a founder, who also sees every upload (ADR-0094 part 6). Only a signed-in email can be one."""
        return user_email is not None and user_email.strip().lower() in self.founders

    def folder(self) -> tempfile.TemporaryDirectory:
        self.scratch.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(prefix="upload-", dir=self.scratch, ignore_cleanup_errors=True)

    def _run(self, args: list[str], answer: Path, timeout_s: float, command: list[str] | None = None) -> dict:
        """The command, waited for; its answer is the JSON it wrote, whatever its exit code said (0, 1 and 2 are all answers). The
        bundle's command unless `command` names another of the fea environment."""
        command = command if command is not None else self.command
        if command is None:
            raise ToolFailed("uv is not on PATH; a bundle is judged by fea/tools/abaqus_upload.py through `uv run --project fea`")
        env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
        try:
            done = subprocess.run([*command, *args, "--json", str(answer)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  cwd=FEA, env={**env, "PYTHONIOENCODING": "utf-8"}, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            raise ToolFailed(f"the bundle's command did not answer in {timeout_s:g} s") from None
        except OSError as exc:
            raise ToolFailed(f"the bundle's command could not run: {exc}") from exc
        try:
            return json.loads(answer.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
            raise ToolFailed("the bundle's command failed: " + (" | ".join(tail) or f"exit code {done.returncode}")) from None

    def connector(self) -> Path:
        """The connector's files as one zip to hand to a user of Abaqus (`abaqus_upload.py connector`), written once per process: the
        same files give the same bytes."""
        if self._connector is not None and self._connector.is_file():
            return self._connector
        if self.command is None:
            raise ToolFailed("uv is not on PATH; the connector's zip is written by fea/tools/abaqus_upload.py through `uv run --project fea`")
        made = self.scratch / "connector" / CONNECTOR_NAME  # written again by each process: a file left by an older one may be an older connector
        made.parent.mkdir(parents=True, exist_ok=True)
        with self.folder() as folder:
            fresh = Path(folder) / CONNECTOR_NAME
            env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
            try:
                done = subprocess.run([*self.command, "connector", "--out", str(fresh)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                                      cwd=FEA, env={**env, "PYTHONIOENCODING": "utf-8"}, timeout=CHECK_TIMEOUT_S, check=False)
            except (subprocess.TimeoutExpired, OSError) as exc:
                raise ToolFailed(f"the connector's zip could not be written: {exc}") from exc
            if done.returncode != 0 or not fresh.is_file():
                tail = (done.stderr or done.stdout).strip().splitlines()[-3:]
                raise ToolFailed("the connector's zip was not written: " + (" | ".join(tail) or f"exit code {done.returncode}"))
            os.replace(fresh, made)  # whole or not there: two requests at once write the same bytes
        self._connector = made
        return made

    def check(self, bundle: Path) -> dict:
        """What the bundle holds and whether the comparison takes it (`abaqus_upload.py check`). Raises `UploadRefused` for a file that
        is not a bundle of version 1."""
        found = self._run(["check", str(bundle)], bundle.with_name("check.json"), CHECK_TIMEOUT_S)
        if found.get("verdict") == "refused":
            raise UploadRefused(found.get("problems") or ["the bundle was refused"])
        if not isinstance(found.get("bundle"), dict) or "in_scope" not in found:
            raise ToolFailed("the bundle's command answered without the bundle's facts")
        return found

    def compare(self, bundle: Path, ours_csv: Path, our_deck: Path) -> dict:
        """The bundle beside a run of ours (`abaqus_upload.py compare`): the result with its verdict, `refused` with the reasons when
        the comparison does not take the pair."""
        found = self._run(["compare", str(bundle), "--ours", str(ours_csv), "--our-deck", str(our_deck)], bundle.with_name("comparison.json"),
                          COMPARE_TIMEOUT_S)
        if found.get("verdict") not in ("agrees", "differs", "incomplete", "refused"):
            raise ToolFailed("the bundle's command answered without a verdict")
        return found

    def document(self, comparison: dict, folder: Path, *, upload: str, run: str | None = None, compared: str | None = None) -> Path:
        """The comparison as a PDF in `folder` (`docs/models/upload.py`, ADR-0094 step 7), written from the comparison alone. Raises
        `NotCompared` when no document can be written from it (a comparison that was refused, or one an older command wrote), and
        `ToolFailed` when the document could not be compiled."""
        if self.writer is None:
            raise ToolFailed("uv is not on PATH; the document is written by docs/models/upload.py through `uv run --project fea`")
        source = folder / "comparison.json"
        source.write_text(json.dumps(comparison), encoding="utf-8")
        args = [str(source), "--out", str(folder / "document"), "--upload", upload]
        args += (["--run", run] if run else []) + (["--compared", compared] if compared else [])
        found = self._run(args, folder / "document.json", DOCUMENT_TIMEOUT_S, command=self.writer)
        if not found.get("written"):
            raise NotCompared(str(found.get("reason") or "no document can be written from this comparison"))
        written = Path(str(found["written"]))
        if not found.get("pdf") or written.suffix != ".pdf" or not written.is_file() or written.stat().st_size == 0:
            raise ToolFailed("the document was not compiled: " + str(found.get("reason") or "no PDF was written"))
        return written


# ------------------------------------------------------------------------------------------------------------- a run of ours

def _from_archive(archive: Path, root: Path) -> None:
    """The three files the comparison reads, out of a package's zip and nothing else: a member is taken only when its path under the
    package's own folder is one of them, and it is written at that path under `root`."""
    with zipfile.ZipFile(archive) as package:
        for info in package.infolist():
            tail = PurePosixPath(info.filename).parts[1:]
            wanted = (tail in (OURS, (OURS[0], PurePosixPath(OURS[1]).with_suffix(".json").name))
                      or (len(tail) == 3 and tail[:2] == OUR_DECKS and tail[2].endswith(OUR_DECK_ENDING) and tail[2] not in (".", "..")))
            if info.is_dir() or not wanted:
                continue
            target = root.joinpath(*tail)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.read(info))


def ours_of(jobs: CouponJobs, job: Job, folder: Path) -> tuple[Path, Path]:
    """A finished job's own files for the comparison: its every-output file (the JSON beside it) and its deck, from the package folder
    when this disk has it, else from the package's zip in the object store. Raises `NotCompared` with the reason."""
    outputs = (job.outcome or {}).get("outputs") or {}
    package = repository_path(outputs["package"]).resolve() if "package" in outputs else None
    here = package is not None and package.is_dir() and (  # the same rule as a job's files: under the repository or the job's folder
        package.is_relative_to(REPO.resolve()) or (job.folder is not None and package.is_relative_to(job.folder.resolve())))
    if here:
        root = package
    elif jobs.store is not None and "package" in job.stored:
        archive = folder / "package.zip"
        jobs.store.get(job.stored["package"], archive)
        root = folder / "package"
        _from_archive(archive, root)
    else:
        raise NotCompared(f"the package of coupon job {job.id} is no longer there, so its files cannot stand beside the upload")
    ours = root.joinpath(*OURS)
    decks = sorted(root.joinpath(*OUR_DECKS).glob(f"*{OUR_DECK_ENDING}")) if root.joinpath(*OUR_DECKS).is_dir() else []
    if not ours.is_file() or not ours.with_suffix(".json").is_file():
        raise NotCompared(f"the package of coupon job {job.id} has no {'/'.join(OURS)} with its JSON: that run is not one the comparison covers")
    if len(decks) != 1:
        raise NotCompared(f"the package of coupon job {job.id} holds {len(decks)} decks for Abaqus under {'/'.join(OUR_DECKS)}; the comparison needs one")
    return ours, decks[0]
