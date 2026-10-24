"""Where the finite element files live: one folder per test, in the repository and on the founder's machine (ADR-0036).

    .local/fea/<coupon>/      our models of the team's coupons, named by the coupon (ADR-0040), git-ignored and never committed
                              (ADR-0042): the spec(s) at the folder root, decks/, records/, README.md (the case page), and beside
                              them from-team/ (as received), our-runs/ (one folder per try, ADR-0039), comparison/ (what we
                              compare with), documents/ (every PDF, its LaTeX and the zips to send)
    fea/checks/<test>/        the same shape, committed, for the public proofs (the IM7/8552 regression set, the isotropic
                              Kirsch plate)
    fea/checks/cases/         validation cases: a deck, expected numbers, a source, a tolerance
    fea/checks/decks/         the tiny hand-made decks the cases and tests read

A spec is a TOML file at the root of a test folder; its generated decks are `decks/<spec stem>-abaqus.inp` and
`decks/<spec stem>-ccx.inp`; its records are `records/*.toml`, each with a reading `records/<record>.md`. A model the team
built also has `records/<test>-team-summary.toml`, the team comparison in figures (ADR-0039), which is not a record. On a
machine without `.local/` (CI) there are no models, only the checks. Tools and tests take every location from here, so a
later move changes this module and nothing else. The paths are those of the source tree: the package is used from the
repository, never from an installed copy.
"""

from __future__ import annotations

from pathlib import Path

FEA = Path(__file__).resolve().parents[2]  # fea/
ROOT = FEA.parent  # the repository
LOCAL = ROOT / ".local" / "fea"
MODELS = LOCAL  # the coupon models live in the coupons' local folders (ADR-0042)
CHECKS = FEA / "checks"
CASES = CHECKS / "cases"
CHECK_DECKS = CHECKS / "decks"
CONVENTIONS = CHECKS / "calculix-conventions.toml"
NOT_TESTS = {"cases", "decks", "checks"}  # folders that hold no test of their own: under checks/, and .local/fea/checks/ (local runs of the checks)
TEAM_FILES, RUNS, COMPARISON, DOCUMENTS = "from-team", "our-runs", "comparison", "documents"  # a coupon's local folders (ADR-0040)
TEAM_SUMMARY = "-team-summary"  # stem suffix of the team comparison's figures in records/ (ADR-0039); not a comparison record

DECK_KINDS = ("abaqus", "ccx")


def model_dirs() -> list[Path]:
    """Every coupon model on this machine: a folder under .local/fea/ holding `<folder>.toml`, sorted by name; none on CI."""
    return [d for d in sorted(MODELS.iterdir()) if d.is_dir() and (d / f"{d.name}.toml").is_file()] if MODELS.is_dir() else []


def test_dirs() -> list[Path]:
    """Every test folder: a coupon model (local) or a check (committed) with at least one spec at its root, sorted by path."""
    dirs = [d for base in (MODELS, CHECKS) if base.is_dir() for d in sorted(base.iterdir())
            if d.is_dir() and d.name not in NOT_TESTS and any(d.glob("*.toml"))]
    return sorted(dirs)


def all_specs() -> list[Path]:
    """Every spec on this machine, the checks' and the local models', sorted by path."""
    return sorted(spec for d in test_dirs() for spec in d.glob("*.toml"))


def all_records() -> list[Path]:
    """Every comparison record on this machine, sorted by path; the team summaries are not records."""
    return sorted(record for d in test_dirs() for record in (d / "records").glob("*.toml") if not record.stem.endswith(TEAM_SUMMARY))


def team_summary(test_dir: Path) -> Path:
    """Where the team comparison's figures for a model folder are written: `records/<test>-team-summary.toml`."""
    return Path(test_dir) / "records" / f"{Path(test_dir).name}{TEAM_SUMMARY}.toml"


def spec_path(name: str) -> Path:
    """The spec with this stem, wherever its test folder is."""
    found = [spec for spec in all_specs() if spec.stem == name]
    if len(found) != 1:
        raise FileNotFoundError(f"no single spec named {name!r} ({len(found)} found)")
    return found[0]


def deck_path(spec: Path, kind: str) -> Path:
    """Where the deck the generator writes from `spec` is kept: `decks/<stem>-abaqus.inp` or `decks/<stem>-ccx.inp`."""
    if kind not in DECK_KINDS:
        raise ValueError(f"deck kind must be one of {DECK_KINDS}")
    return Path(spec).parent / "decks" / f"{Path(spec).stem}-{kind}.inp"


def check_deck(name: str) -> Path:
    """A hand-made deck under checks/decks/, by file name."""
    return CHECK_DECKS / name


def local_test(name: str) -> Path:
    """The coupon's folder on the founder's machine (git-ignored): its model, from-team/, our-runs/, comparison/, documents/ (ADR-0040, ADR-0042)."""
    return LOCAL / name


def team_deck(name: str) -> Path | None:
    """The team's deck of a coupon: the one .inp in its newest from-team/<date>/ folder; None where there is no such folder
    (CI) or the folder holds no single deck. Found by place, so committed code never names the team's files (ADR-0042)."""
    received = LOCAL / name / TEAM_FILES
    dated = sorted(d for d in received.iterdir() if d.is_dir()) if received.is_dir() else []
    decks = sorted(dated[-1].glob("*.inp")) if dated else []
    return decks[0] if len(decks) == 1 else None


def documents(name: str) -> Path:
    """Where a coupon's document is built: <coupon>.tex and <coupon>.pdf side by side, the figures/ they use, and the zip to send."""
    return LOCAL / name / DOCUMENTS
