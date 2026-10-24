"""A coupon's folder in three parts, team / ours / documents (ADR-0040 amendment 3): where the paths module finds each file, and
the one-time move from the layout before it (tools/migrate_coupon_layout.py), on a made-up coupon in a temporary folder."""

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest

from anisotropy_fea import paths  # where the files live (ADR-0036)

TOOL = Path(__file__).parents[1] / "tools" / "migrate_coupon_layout.py"
NAME = "IM7-UNT-L9"


@pytest.fixture(scope="module")
def migrate():
    spec = importlib.util.spec_from_file_location("migrate_coupon_layout", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str = "x\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "LOCAL", tmp_path)
    monkeypatch.setattr(paths, "MODELS", tmp_path)
    return tmp_path


# --------------------------------------------------------------------------------------------- the paths module

def test_a_coupon_in_three_parts_is_found(local):
    coupon = local / NAME
    write(coupon / "README.md")
    write(coupon / "ours" / f"{NAME}.toml")
    write(coupon / "ours" / "verification" / f"{NAME}-calculix.toml")
    write(coupon / "ours" / "verification" / f"{NAME}-team-summary.toml")
    write(coupon / "ours" / "verification" / "team-comparison.toml")
    write(local / "checks" / "unrelated.toml")  # .local/fea/checks/ holds runs of the checks, no coupon
    assert paths.model_dirs() == [coupon]
    assert coupon / "ours" in paths.test_dirs() and paths.test_name(coupon / "ours") == NAME
    assert paths.records_dir(coupon / "ours") == coupon / "ours" / "verification" and paths.records_dir(paths.CHECKS / "x") == paths.CHECKS / "x" / "records"
    assert paths.team_summary(coupon / "ours") == coupon / "ours" / "verification" / f"{NAME}-team-summary.toml"
    mine = [r for r in paths.all_records() if local in r.parents]
    assert mine == [coupon / "ours" / "verification" / f"{NAME}-calculix.toml"]  # neither the summary nor the manifest is a record
    assert (paths.ours(NAME), paths.verification(NAME), paths.runs(NAME), paths.latex(NAME), paths.team_files(NAME), paths.documents(NAME)) == (
        coupon / "ours", coupon / "ours" / "verification", coupon / "ours" / "runs", coupon / "ours" / "latex", coupon / "team", coupon / "documents")


def test_the_teams_deck_is_the_newest_delivery_that_brought_one(local):
    team = local / NAME / "team"
    assert paths.team_deck(NAME) is None
    first = write(team / "2026-11-02" / "their-model.inp")
    write(team / "2026-11-09" / "2026-11-05_IM7-UNT-L9-audit.xlsx")  # a returned audit brings no deck
    write(team / "2026-11-10" / "rebuilt" / "Job-1.inp")  # nor does a deck rebuilt from our guide
    assert paths.team_deck(NAME) == first
    write(team / "2026-11-12" / "a.inp")
    write(team / "2026-11-12" / "b.inp")
    assert paths.team_deck(NAME) is None  # two decks in the newest delivery: not one deck


# --------------------------------------------------------------------------------------------- the move

def old_coupon(root: Path) -> Path:
    """A coupon folder in the layout before amendment 3, with the relative paths its records and manifest really hold."""
    c = root / NAME
    write(c / "README.md", "# case page\n")
    write(c / f"{NAME}.toml")
    write(c / f"{NAME}-nodal.toml")
    write(c / "decks" / f"{NAME}-nodal-abaqus.inp")
    write(c / "records" / f"{NAME}-calculix.toml", f'spec = "../{NAME}-nodal.toml"\ndeck_kernel = "../decks/{NAME}-nodal-abaqus.inp"\n'
                                                     'conventions = "../../../checks/calculix-conventions.toml"\n')
    write(c / "records" / f"{NAME}-calculix.md")
    write(c / "records" / f"{NAME}-team-summary.toml")
    (c / "comparison" / "team-comparison.toml").parent.mkdir(parents=True)
    (c / "comparison" / "team-comparison.toml").write_bytes(
        ('[team]\r\ndeck = "../from-team/2026-11-02/their-model.inp"\r\nreports = ["../from-team/2026-11-02/results/S22.csv"]\r\n'
         f'[ours]\r\nspec = "../{NAME}.toml"\r\ncalculix_record = "../records/{NAME}-calculix.toml"\r\n').encode("utf-8"))  # CRLF, as Windows wrote it
    write(c / "comparison" / "notes" / "a-note.md")
    write(c / "comparison" / "figures" / "map.png")
    write(c / "our-runs" / "attempt-01_2026-10-21" / "run" / "kernel" / "summary.txt")
    write(c / "documents" / f"{NAME}.tex")
    write(c / "documents" / "figures" / "model.png")
    write(c / "documents" / f"{NAME}.pdf")
    write(c / "documents" / f"2026-10-22_{NAME}.zip")
    write(c / "documents" / f"2026-10-23_{NAME}" / "README.txt")
    write(c / "from-team" / "2026-11-02" / "their-model.inp")
    write(c / "from-team" / "2026-11-02" / "results" / "S22.csv")
    return c


def files(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


def test_the_move_lists_first_then_moves_and_keeps_every_path_reaching_its_file(tmp_path, migrate):
    c = old_coupon(tmp_path)
    before = files(c)
    plan = migrate.plan(c)
    assert files(c) == before  # planning changes nothing
    report = "\n".join(migrate.report(plan))
    assert "move     from-team/" in report and f"stays    documents/{NAME}.pdf" in report and f"stays    documents/2026-10-22_{NAME}.zip" in report
    assert f"documents/2026-10-23_{NAME}" not in report.split("stays")[-1]  # a package is already where it belongs
    assert "../../../checks/calculix-conventions.toml\" reached no file" in report
    migrate.apply(plan)
    assert {p.name for p in c.iterdir()} == {"README.md", "team", "ours", "documents"}
    assert files(c) == {
        "README.md", f"ours/{NAME}.toml", f"ours/{NAME}-nodal.toml", f"ours/decks/{NAME}-nodal-abaqus.inp",
        f"ours/verification/{NAME}-calculix.toml", f"ours/verification/{NAME}-calculix.md", f"ours/verification/{NAME}-team-summary.toml",
        "ours/verification/team-comparison.toml", "ours/verification/notes/a-note.md", "ours/verification/figures/map.png",
        "ours/runs/attempt-01_2026-10-21/run/kernel/summary.txt", f"ours/latex/{NAME}.tex", "ours/latex/figures/model.png",
        f"documents/{NAME}.pdf", f"documents/2026-10-22_{NAME}.zip", f"documents/2026-10-23_{NAME}/README.txt",
        "team/2026-11-02/their-model.inp", "team/2026-11-02/results/S22.csv"}
    manifest = c / "ours" / "verification" / "team-comparison.toml"
    raw = manifest.read_bytes()
    assert b"\r\n" in raw and b'deck = "../../team/2026-11-02/their-model.inp"' in raw and f'calculix_record = "{NAME}-calculix.toml"'.encode() in raw
    data = tomllib.loads(raw.decode("utf-8"))
    for relative in (data["team"]["deck"], *data["team"]["reports"], data["ours"]["spec"], data["ours"]["calculix_record"]):
        assert (manifest.parent / relative).is_file(), relative  # every path reaches its file from the new place
    record = (c / "ours" / "verification" / f"{NAME}-calculix.toml").read_text(encoding="utf-8")
    assert f'spec = "../{NAME}-nodal.toml"' in record and f'deck_kernel = "../decks/{NAME}-nodal-abaqus.inp"' in record  # unchanged: still right
    assert migrate.plan(c).skipped == "already in the new layout"


def test_a_move_onto_an_existing_path_or_an_unknown_entry_stops_before_anything_moves(tmp_path, migrate):
    c = old_coupon(tmp_path)
    write(c / "team" / "stray.txt")
    write(c / "share" / "old.zip")
    before = files(c)
    with pytest.raises(migrate.LayoutError, match="share: not part of either layout.*team exists already"):
        migrate.plan(c)
    assert files(c) == before
