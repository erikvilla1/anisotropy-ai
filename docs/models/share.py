"""Our models in one zip the team can open (ADR-0035, ADR-0036).

Every folder under `fea/models/` is one coupon and goes in, found by convention: the spec `<test>.toml` (the team's
build, the deck they import), its twin's record `records/<test>-calculix.toml`, and the twin spec the record names. A new
test folder joins the zip by itself. For each coupon the zip holds the Abaqus deck to import, the CalculiX twin's deck,
both specs and the comparison document of its CalculiX record; the library record of every material is written once.
No CalculiX results go in: the team runs our decks themselves.

From the repository root:

    uv run --project fea python docs/models/share.py                       # every model, to .local/fea/share/our-models.zip
    uv run --project fea python docs/models/share.py tension-coupon --out <zip> --no-pdf

Every deck is regenerated from its spec and must equal the committed one.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tempfile
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
from anisotropy_fea.spec import load_spec, spec_material  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402

DEFAULT_ZIP = paths.LOCAL / "share" / "our-models.zip"
TITLE = "Our coupon models, built the team's way: X840-Z60, [0/45/-45/45/0]s, coupled tabs, the team's names"


def model_tests(names: list[str] | None) -> list[str]:
    """The test folders under fea/models/, all or the ones named, each with its spec and record present."""
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


def fill(folder: Path, tests: list[str], pdf: bool) -> None:
    lines = [team.README_MARK, TITLE, "",
             f"Built {date.today().isoformat()} by docs/models/share.py (anisotropy-fea {fea_version}, commit {team.git_commit()}).",
             "Numbers are in mm, MPa and N. Each folder is one coupon:", "",
             "  abaqus/    the deck to open in Abaqus/CAE (File, Import, Model; this click path is not checked by us), the team's build",
             "  calculix/  the CalculiX twin (grips as direct constraints); PrePoMax: File, Import, then run it",
             "  spec/      the specs our generator builds both decks from",
             "  *.pdf      the comparison of CalculiX against our kernel on that model, with a step-by-step rebuild guide", ""]
    materials = {}
    for k, test in enumerate(tests, start=1):
        spec_path = paths.MODELS / test / f"{test}.toml"
        record_path = paths.MODELS / test / "records" / f"{test}-calculix.toml"
        spec = load_spec(spec_path)
        text = write_abaqus(build_model(spec))
        committed = paths.deck_path(spec_path, "abaqus")
        if not committed.is_file() or committed.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            raise SystemExit(f"{committed.relative_to(ROOT).as_posix()} is not what the generator writes from {spec_path.name} today; "
                             "run fea/tools/regenerate_decks.py first")
        record = load_record(record_path)
        ccx_deck = (record_path.parent / record["deck_reference"]).resolve()
        twin_spec = (record_path.parent / record["spec"]).resolve()
        out = folder / f"{k}-{test}"
        for sub in ("abaqus", "calculix", "spec"):
            (out / sub).mkdir(parents=True)
        (out / "abaqus" / committed.name).write_text(text, encoding="utf-8", newline="\n")
        shutil.copy2(ccx_deck, out / "calculix" / ccx_deck.name)
        shutil.copy2(spec_path, out / "spec" / spec_path.name)
        if twin_spec != spec_path:
            shutil.copy2(twin_spec, out / "spec" / twin_spec.name)
        rows, problems = comparison_rows(record)
        if pdf:
            with tempfile.TemporaryDirectory() as tmp:
                document = documents.build(record_path, Path(tmp), True, False, False)
                if document.suffix == ".pdf":
                    shutil.copy2(document, out / f"{record_path.stem}.pdf")
        materials[(spec.material.library, spec.material.dataset)] = spec
        lines.append(f"{out.name}/  {spec.title}")
        lines.append(f"    CalculiX {record['solver']['version']} against our kernel: {sum(r.agrees for r in rows)} of {len(rows)} compared values agree"
                     + (f"; {len(problems)} problems" if problems else ""))
    (folder / "material").mkdir()
    lines += ["", "material/  the library record of each material the models use: every value, its unit, basis and source page, and the source"]
    for (library, dataset), spec in materials.items():
        if library is not None:
            lib = library_material(library, dataset)
            team.write_material_csv(folder / "material" / f"{lib.material_id}.csv", lib, spec_material(spec), "mm-MPa")
    (folder / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build(out: Path, pdf: bool, names: list[str] | None = None) -> Path:
    if out.suffix != ".zip":
        raise SystemExit(f"--out must name a .zip file, not {out.name}")
    tests = model_tests(names)
    archive = team.write_zip(out, out.stem, lambda folder: fill(folder, tests, pdf))
    print(f"{len(tests)} models zipped to {archive}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tests", nargs="*", help="model folders to include; default every folder under fea/models/")
    parser.add_argument("--out", type=Path, default=DEFAULT_ZIP, help="the zip to write (default .local/fea/share/our-models.zip)")
    parser.add_argument("--no-pdf", action="store_true", help="leave out the comparison documents")
    args = parser.parse_args()
    build(args.out, pdf=not args.no_pdf, names=args.tests or None)


if __name__ == "__main__":
    main()
