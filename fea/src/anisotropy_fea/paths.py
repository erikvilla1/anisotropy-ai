"""Where the finite element files live: one folder per test, in the repository and on the founder's machine (ADR-0036).

    fea/models/<coupon>/      the models we show the team, named by the coupon (ADR-0040): the spec(s) at the folder root,
                              decks/, records/, README.md (the case page)
    fea/checks/<test>/        the same shape for the proofs that are not team models (the public IM7/8552 regression set,
                              the isotropic Kirsch plate)
    fea/checks/cases/         validation cases: a deck, expected numbers, a source, a tolerance
    fea/checks/decks/         the tiny hand-made decks the cases and tests read
    .local/fea/<coupon>/      the same name locally (ADR-0040): from-team/ (as received), our-runs/ (one folder per try, ADR-0039),
                              comparison/ (what we compare with), documents/ (every PDF, its LaTeX and the zips to send)

A spec is a TOML file at the root of a test folder; its generated decks are `decks/<spec stem>-abaqus.inp` and
`decks/<spec stem>-ccx.inp`; its records are `records/*.toml`, each with a reading `records/<record>.md`. A model the team
built also has `records/<test>-team-summary.toml`, the team comparison in figures (ADR-0039), which is not a record. Tools and tests
take every location from here, so a later move changes this module and nothing else. The paths are those of the source
tree: the package is used from the repository, never from an installed copy.
"""

from __future__ import annotations

from pathlib import Path

FEA = Path(__file__).resolve().parents[2]  # fea/
ROOT = FEA.parent  # the repository
MODELS = FEA / "models"
CHECKS = FEA / "checks"
CASES = CHECKS / "cases"
CHECK_DECKS = CHECKS / "decks"
CONVENTIONS = CHECKS / "calculix-conventions.toml"
LOCAL = ROOT / ".local" / "fea"
NOT_TESTS = {"cases", "decks"}  # folders under checks/ that hold no test of their own
TEAM_FILES, RUNS, COMPARISON, DOCUMENTS = "from-team", "our-runs", "comparison", "documents"  # a coupon's local folders (ADR-0040)
TEAM_SUMMARY = "-team-summary"  # stem suffix of the team comparison's figures in records/ (ADR-0039); not a comparison record

DECK_KINDS = ("abaqus", "ccx")


def test_dirs() -> list[Path]:
    """Every test folder: a folder under models/ or checks/ with at least one spec at its root, sorted by path."""
    dirs = [d for base in (MODELS, CHECKS) if base.is_dir() for d in sorted(base.iterdir())
            if d.is_dir() and d.name not in NOT_TESTS and any(d.glob("*.toml"))]
    return sorted(dirs)


def all_specs() -> list[Path]:
    """Every committed spec, sorted by path."""
    return sorted(spec for d in test_dirs() for spec in d.glob("*.toml"))


def all_records() -> list[Path]:
    """Every committed comparison record, sorted by path; the team summaries are not records."""
    return sorted(record for d in test_dirs() for record in (d / "records").glob("*.toml") if not record.stem.endswith(TEAM_SUMMARY))


def team_summary(test_dir: Path) -> Path:
    """Where the team comparison's figures for a model folder are committed: `records/<test>-team-summary.toml`."""
    return Path(test_dir) / "records" / f"{Path(test_dir).name}{TEAM_SUMMARY}.toml"


def spec_path(name: str) -> Path:
    """The committed spec with this stem, wherever its test folder is."""
    found = [spec for spec in all_specs() if spec.stem == name]
    if len(found) != 1:
        raise FileNotFoundError(f"no single committed spec named {name!r} ({len(found)} found)")
    return found[0]


def deck_path(spec: Path, kind: str) -> Path:
    """Where the deck the generator writes from `spec` is committed: `decks/<stem>-abaqus.inp` or `decks/<stem>-ccx.inp`."""
    if kind not in DECK_KINDS:
        raise ValueError(f"deck kind must be one of {DECK_KINDS}")
    return Path(spec).parent / "decks" / f"{Path(spec).stem}-{kind}.inp"


def check_deck(name: str) -> Path:
    """A hand-made deck under checks/decks/, by file name."""
    return CHECK_DECKS / name


def local_test(name: str) -> Path:
    """The coupon's folder on the founder's machine (git-ignored): from-team/, our-runs/, comparison/, documents/ (ADR-0040)."""
    return LOCAL / name


def documents(name: str) -> Path:
    """Where every document of a coupon goes: its PDFs on top, their LaTeX in latex/<document>/, and the zips to send."""
    return LOCAL / name / DOCUMENTS
