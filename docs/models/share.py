"""Each coupon's model in a zip the team can open, written into that coupon's documents/ folder (ADR-0035, ADR-0040).

Every folder under `fea/models/` is one coupon, named by its designation (ADR-0038), found by convention: the spec
`<coupon>.toml` (the team's build, the deck they import), its twin's record `records/<coupon>-calculix.toml`, and the
twin spec the record names. For each coupon the zip `.local/fea/<coupon>/documents/<today>_<coupon>-model.zip` holds the
Abaqus deck to import, the CalculiX twin's deck, both specs, the library record of the material, and the document of its
CalculiX record; its README gives the coupon's identity card. No CalculiX results go in: the team runs our decks themselves.

From the repository root:

    uv run --project fea python docs/models/share.py                      # every coupon
    uv run --project fea python docs/models/share.py X840PW-UNT-L1 --root <folder> --no-pdf

Every deck is regenerated from its spec and must equal the committed one.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from datetime import date
from pathlib import Path

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
from anisotropy_fea import paths  # noqa: E402
from anisotropy_fea.compare import load_record  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.report import comparison_rows  # noqa: E402
from anisotropy_fea.spec import coupon_card, load_spec, spec_material  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402


def model_coupons(names: list[str] | None) -> list[str]:
    """The coupon folders under fea/models/, all or the ones named, each with its spec and record present."""
    found = sorted(d.name for d in paths.MODELS.iterdir() if d.is_dir() and (d / f"{d.name}.toml").is_file())
    if names:
        unknown = sorted(set(names) - set(found))
        if unknown:
            raise SystemExit(f"no model folder for {unknown}; the models are {found}")
        found = [n for n in found if n in names]
    for name in found:
        record = paths.MODELS / name / "records" / f"{name}-calculix.toml"
        if not record.is_file():
            raise SystemExit(f"{name}: no CalculiX record {record.relative_to(ROOT).as_posix()}")
    return found


def fill(folder: Path, coupon: str, pdf: bool, documents_dir: Path) -> None:
    spec_path = paths.MODELS / coupon / f"{coupon}.toml"
    record_path = paths.MODELS / coupon / "records" / f"{coupon}-calculix.toml"
    spec = load_spec(spec_path)
    card = dict(coupon_card(spec))
    if not card:
        raise SystemExit(f"{spec_path.relative_to(ROOT).as_posix()} has no [coupon] table: every model names its coupon (ADR-0038)")
    text = write_abaqus(build_model(spec))
    committed = paths.deck_path(spec_path, "abaqus")
    if not committed.is_file() or committed.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
        raise SystemExit(f"{committed.relative_to(ROOT).as_posix()} is not what the generator writes from {spec_path.name} today; "
                         "run fea/tools/regenerate_decks.py first")
    record = load_record(record_path)
    ccx_deck = (record_path.parent / record["deck_reference"]).resolve()
    twin_spec = (record_path.parent / record["spec"]).resolve()
    for sub in ("abaqus", "calculix", "spec", "material"):
        (folder / sub).mkdir(parents=True)
    (folder / "abaqus" / committed.name).write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(ccx_deck, folder / "calculix" / ccx_deck.name)
    shutil.copy2(spec_path, folder / "spec" / spec_path.name)
    if twin_spec != spec_path:
        shutil.copy2(twin_spec, folder / "spec" / twin_spec.name)
    if spec.material.library is not None:
        lib = library_material(spec.material.library, spec.material.dataset)
        team.write_material_csv(folder / "material" / f"{lib.material_id}.csv", lib, spec_material(spec), "mm-MPa")
    if pdf:
        document = documents.build(record_path, documents_dir / "latex" / record_path.stem, True, False, False)
        if document.suffix == ".pdf":
            shutil.copy2(document, folder / document.name)
    rows, problems = comparison_rows(record)
    lines = [team.README_MARK, f"{card['Coupon']}, {card['Test']}: our model, built the team's way (coupled tabs, the team's names)", "",
             *[f"{label + ':':14} {value}" for label, value in card.items()],
             f"{'CalculiX:':14} {record['solver']['version']} against our kernel, {sum(r.agrees for r in rows)} of {len(rows)} compared values agree"
             + (f"; {len(problems)} problems" if problems else ""), "",
             f"Built {date.today().isoformat()} by docs/models/share.py (anisotropy-fea {fea_version}, commit {team.git_commit()}).",
             "Numbers are in mm, MPa and N.", "",
             "  abaqus/     the deck to open in Abaqus/CAE (File, Import, Model; this click path is not checked by us), the team's build",
             "  calculix/   the CalculiX twin (grips as direct constraints); PrePoMax: File, Import, then run it",
             "  spec/       the specs our generator builds both decks from",
             "  material/   the library record of the material: every value, its unit, basis and source page, and the source",
             "  *.pdf       the comparison of CalculiX against our kernel on this model, with a step-by-step rebuild guide"]
    (folder / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build(coupon: str, root: Path, pdf: bool) -> Path:
    """The coupon's zip, `<root>/<coupon>/documents/<today>_<coupon>-model.zip`."""
    documents_dir = root / coupon / paths.DOCUMENTS
    archive = team.dated(documents_dir / f"{coupon}-model.zip")
    archive = team.write_zip(archive, f"{coupon}-model", lambda folder: fill(folder, coupon, pdf, documents_dir))
    print(f"{coupon}: zipped to {archive}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("coupons", nargs="*", help="model folders to zip; default every folder under fea/models/")
    parser.add_argument("--root", type=Path, default=paths.LOCAL, help="the folder holding one folder per coupon (default .local/fea)")
    parser.add_argument("--no-pdf", action="store_true", help="leave out the comparison document")
    args = parser.parse_args()
    for coupon in model_coupons(args.coupons or None):
        build(coupon, args.root, pdf=not args.no_pdf)


if __name__ == "__main__":
    main()
