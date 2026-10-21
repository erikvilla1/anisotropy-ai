"""Our models in one folder the team can open, zipped beside itself (ADR-0035, amendment 2).

For each coupon in the manifest: the Abaqus deck to import (the team's build, coupled grips, the team's names), the
CalculiX twin with its results for PrePoMax, both specs, and the comparison document of its CalculiX record. The library
record of every material the models use is written once. This is for coupons the team has not built yet as much as for the
ones they have; a coupon the team did build also gets the side-by-side comparison of `docs/models/team.py`.

From the repository root:

    uv run --project fea python docs/models/share.py docs/models/our-models.toml

The manifest (format in `Manifest` below; every key required; paths relative to the repository root) names the folder and,
per model, the coupled spec, the CalculiX record of its nodal twin and that run's `.frd`. Every deck is regenerated from its
spec and must equal the committed one. The folder goes under `.local/` because the `.frd` files and PDFs are build outputs;
the decks and specs are also committed, so anyone with the repository has them.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tempfile
import tomllib
import zipfile
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


team = load_module("anisotropy_models_team", HERE / "team.py")
documents = load_module("anisotropy_models_build", HERE / "build.py")

from anisotropy_engine.library import library_material  # noqa: E402
from anisotropy_fea import __version__ as fea_version  # noqa: E402
from anisotropy_fea.compare import load_record  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.report import comparison_rows  # noqa: E402
from anisotropy_fea.spec import load_spec, spec_material  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Model(Record):
    test: str  # the test name, as the local folders use it
    spec: str  # the coupled spec: the deck the team imports
    record: str  # the committed CalculiX record of its nodal twin
    results: str  # that CalculiX run's .frd


class Manifest(Record):
    name: str
    title: str
    units: str
    share: str
    models: list[Model]


def load_manifest(path: Path) -> Manifest:
    try:
        manifest = Manifest(**tomllib.loads(path.read_text(encoding="utf-8")))
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise SystemExit(f"{path}: {exc}") from None
    if manifest.units not in team.UNITS or not manifest.models:
        raise SystemExit(f"{path}: units must be one of {list(team.UNITS)} and at least one model is needed")
    return manifest


def existing(relative: str, what: str, root: Path) -> Path:
    path = (root / relative).resolve()
    if not path.exists():
        raise SystemExit(f"{what} not found: {path}")
    return path


def build(manifest_path: Path, pdf: bool, root: Path = ROOT) -> Path:
    m = load_manifest(manifest_path)
    share = (root / m.share).resolve()
    if share.exists():
        readme = share / "README.txt"
        if not readme.exists() or not readme.read_text(encoding="utf-8").startswith(team.README_MARK):
            raise SystemExit(f"{share} exists and was not written by this script; choose another share folder")
        shutil.rmtree(share)
    share.mkdir(parents=True)
    lines = [team.README_MARK, f"{m.title}", "",
             f"Built {date.today().isoformat()} by docs/models/share.py (anisotropy-fea {fea_version}, commit {team.git_commit()}).",
             f"Numbers are in {', '.join(team.UNITS[m.units])}. Each folder is one coupon:", "",
             "  abaqus/    the deck to open in Abaqus/CAE (File, Import, Model; this click path is not checked by us), the team's build",
             "  calculix/  the CalculiX twin (grips as direct constraints) and its results; PrePoMax: File, Import the .inp, File, Open the .frd",
             "  spec/      the specs our generator builds both decks from",
             "  *.pdf      the comparison of CalculiX against our kernel on that model, with a step-by-step rebuild guide", ""]
    materials: dict[tuple[str, str | None], tuple] = {}
    for k, model in enumerate(m.models, start=1):
        spec_path = existing(model.spec, "spec", root)
        record_path = existing(model.record, "record", root)
        results_path = existing(model.results, "CalculiX results", root)
        spec = load_spec(spec_path)
        text = write_abaqus(build_model(spec))
        committed = team.fea_paths.deck_path(spec_path, "abaqus")
        if committed.exists() and committed.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            raise SystemExit(f"{committed} is not what the generator writes from {spec_path.name} today; regenerate it first")
        record = load_record(record_path)
        ccx_deck = (record_path.parent / record["deck_reference"]).resolve()
        twin_spec = (record_path.parent / record["spec"]).resolve()
        folder = share / f"{k}-{model.test}"
        for sub in ("abaqus", "calculix", "spec"):
            (folder / sub).mkdir(parents=True)
        (folder / "abaqus" / f"{spec_path.stem}-abaqus.inp").write_text(text, encoding="utf-8", newline="\n")
        shutil.copy2(ccx_deck, folder / "calculix" / ccx_deck.name)
        shutil.copy2(results_path, folder / "calculix" / results_path.name)
        shutil.copy2(spec_path, folder / "spec" / spec_path.name)
        if twin_spec != spec_path:
            shutil.copy2(twin_spec, folder / "spec" / twin_spec.name)
        rows, problems = comparison_rows(record)
        if pdf:
            with tempfile.TemporaryDirectory() as tmp:
                document = documents.build(record_path, Path(tmp), True, False, False)
                if document.suffix == ".pdf":
                    shutil.copy2(document, folder / f"{record_path.stem}.pdf")
        material = spec.material
        materials[(material.library, material.dataset)] = (material, spec)
        lines.append(f"{folder.name}/  {spec.title}")
        lines.append(f"    CalculiX {record['solver']['version']} against our kernel: {sum(r.agrees for r in rows)} of {len(rows)} compared values agree"
                     + (f"; {len(problems)} problems" if problems else ""))
    (share / "material").mkdir()
    lines += ["", "material/  the library record of each material the models use: every value, its unit, basis and source page, and the source"]
    for (library, dataset), (_, spec) in materials.items():
        if library is None:
            continue
        lib = library_material(library, dataset)
        team.write_material_csv(share / "material" / f"{lib.material_id}.csv", lib, spec_material(spec), m.units)
    (share / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    archive = share.parent / f"{share.name}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(share.rglob("*")):
            if path.is_file():
                zf.write(path, Path(share.name) / path.relative_to(share))
    print(f"{len(m.models)} models written to {share} and zipped to {archive}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("manifest", type=Path, help="the share manifest (TOML)")
    parser.add_argument("--no-pdf", action="store_true", help="leave out the comparison documents")
    args = parser.parse_args()
    build(args.manifest, pdf=not args.no_pdf)


if __name__ == "__main__":
    main()
