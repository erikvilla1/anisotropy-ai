"""Our models in one zip the team can open (ADR-0035, ADR-0036).

Every folder under `fea/models/` is one coupon and goes in, found by convention: the spec `<test>.toml` (the team's
build, the deck they import), its twin's record `records/<test>-calculix.toml`, and the twin spec the record names. A new
test folder joins the zip by itself. Each coupon's folder in the zip is named by its designation (ADR-0038), for example
X840PW-UNT-L1/, and holds the Abaqus deck to import, the CalculiX twin's deck, both specs and the comparison document of
its CalculiX record; the README gives each coupon's identity card. The library record of every material is written once.
No CalculiX results go in: the team runs our decks themselves.

From the repository root:

    uv run --project fea python docs/models/share.py                       # every model, to .local/fea/share/<today>_our-models.zip
    uv run --project fea python docs/models/share.py tension-coupon --out <zip> --no-pdf

Every deck is regenerated from its spec and must equal the committed one.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
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
from anisotropy_fea.spec import coupon_card, load_spec, spec_material  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402

DEFAULT_ZIP = paths.LOCAL / "share" / "our-models.zip"
TITLE = "Our coupon models, built the team's way (coupled tabs, the team's names), one folder per coupon, named by its designation"


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
             "Numbers are in mm, MPa and N. A coupon's name reads <material>-<test>-<layup>:", "",
             "Each folder is one coupon:", "",
             "  abaqus/    the deck to open in Abaqus/CAE (File, Import, Model; this click path is not checked by us), the team's build",
             "  calculix/  the CalculiX twin (grips as direct constraints); PrePoMax: File, Import, then run it",
             "  spec/      the specs our generator builds both decks from",
             "  *.pdf      the comparison of CalculiX against our kernel on that model, with a step-by-step rebuild guide", ""]
    materials, codes = {}, ({}, {}, {})  # material, test and layup codes, each with its meaning
    for test in tests:
        spec_path = paths.MODELS / test / f"{test}.toml"
        record_path = paths.MODELS / test / "records" / f"{test}-calculix.toml"
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
        out = folder / card["Coupon"]
        for part, kind, meaning in zip(card["Coupon"].split("-"), codes, (card["Material"].split(" (")[0], card["Test"], card["Layup"].split(",")[0])):
            kind[part] = meaning
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
        lines.append(f"{out.name}/  {card['Test']} (test folder {test})")
        lines += [f"    {label + ':':14} {value}" for label, value in card.items() if label not in ("Coupon", "Test")]
        lines.append(f"    {'CalculiX:':14} {record['solver']['version']} against our kernel, {sum(r.agrees for r in rows)} of {len(rows)} compared values agree"
                     + (f"; {len(problems)} problems" if problems else ""))
        lines.append("")
    legend = lines.index("Each folder is one coupon:") - 1
    lines[legend:legend] = [f"  {code:8} {meaning}" for kind in codes for code, meaning in sorted(kind.items())]
    (folder / "material").mkdir()
    lines += ["material/  the library record of each material the models use: every value, its unit, basis and source page, and the source"]
    for (library, dataset), spec in materials.items():
        if library is not None:
            lib = library_material(library, dataset)
            team.write_material_csv(folder / "material" / f"{lib.material_id}.csv", lib, spec_material(spec), "mm-MPa")
    (folder / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def build(out: Path, pdf: bool, names: list[str] | None = None) -> Path:
    if out.suffix != ".zip":
        raise SystemExit(f"--out must name a .zip file, not {out.name}")
    tests = model_tests(names)
    folder = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", out.stem)  # the folder inside the zip carries no date
    archive = team.write_zip(out, folder, lambda folder_path: fill(folder_path, tests, pdf))
    print(f"{len(tests)} models zipped to {archive}")
    return archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("tests", nargs="*", help="model folders to include; default every folder under fea/models/")
    parser.add_argument("--out", type=Path, default=None, help="the zip to write (default .local/fea/share/<today>_our-models.zip)")
    parser.add_argument("--no-pdf", action="store_true", help="leave out the comparison documents")
    args = parser.parse_args()
    build(args.out or team.dated(DEFAULT_ZIP), pdf=not args.no_pdf, names=args.tests or None)


if __name__ == "__main__":
    main()
