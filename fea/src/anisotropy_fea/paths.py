"""Where the finite element files live: one folder per test, in the repository and on the founder's machine (ADR-0036).

    .local/fea/<coupon>/      one folder per coupon, named by it (ADR-0040), git-ignored and never committed (ADR-0042), in
                              three parts beside its case page, README.md (ADR-0040 amendment 3):
      team/<date>/            everything the team sent, as received; also a returned audit form and rebuilt/ (a deck rebuilt
                              from our guide)
      ours/                   everything we built: the spec(s), decks/, verification/ (the CalculiX record, the team
                              comparison, notes and figures, each record with its reading), runs/ (one folder per try,
                              ADR-0039), latex/ (the .tex and figures of the coupon document)
      documents/              the packages that go out, one per delivery: <date>_<coupon>/ (ADR-0043)
    fea/checks/<test>/        the public proofs, committed (the IM7/8552 regression set, the isotropic Kirsch plate): a spec at
                              the root, decks/, records/
    fea/checks/cases/         validation cases: a deck, expected numbers, a source, a tolerance
    fea/checks/decks/         the tiny hand-made decks the cases and tests read

A test folder is a check's folder or a coupon's ours/. A spec is a TOML file at its root; its generated decks are
`decks/<spec stem>-abaqus.inp` and `decks/<spec stem>-ccx.inp`; its records are in `records/` (a check) or `verification/`
(a coupon), each with a reading `<record>.md` beside it. A coupon the team built also has there the team comparison's
manifest and `<coupon>-team-summary.toml`, its figures (ADR-0039); neither is a record. On a machine without `.local/` (CI)
there are no coupons, only the checks. Tools and tests take every location from here, so a later move changes this module
and nothing else. The paths are those of the source tree: the package is used from the repository, never from an installed
copy.
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
RUBRIC = ROOT / "docs" / "audit" / "rubric.toml"  # what every coupon audit checks (ADR-0043)
NOT_TESTS = {"cases", "decks", "checks"}  # folders that hold no test of their own: under checks/, and .local/fea/checks/ (local runs of the checks)
TEAM_FILES, OURS, DOCUMENTS = "team", "ours", "documents"  # a coupon's three parts (ADR-0040 amendment 3)
VERIFICATION, RUNS, LATEX = "verification", "runs", "latex"  # inside ours/
MANIFEST = "team-comparison.toml"  # the team comparison's manifest, in ours/verification/ (ADR-0035); not a record
TEAM_SUMMARY = "-team-summary"  # stem suffix of the team comparison's figures (ADR-0039); not a record

DECK_KINDS = ("abaqus", "ccx")


def model_dirs() -> list[Path]:
    """Every coupon on this machine: a folder under .local/fea/ holding `ours/<folder>.toml`, sorted by name; none on CI."""
    return [d for d in sorted(MODELS.iterdir()) if d.is_dir() and (d / OURS / f"{d.name}.toml").is_file()] if MODELS.is_dir() else []


def test_dirs() -> list[Path]:
    """Every test folder, sorted by path: a check's folder (committed) and a coupon's ours/ (local), each with a spec at its root."""
    checks = [d for d in CHECKS.iterdir() if d.is_dir() and d.name not in NOT_TESTS and any(d.glob("*.toml"))] if CHECKS.is_dir() else []
    coupons = [d / OURS for d in MODELS.iterdir() if d.is_dir() and any((d / OURS).glob("*.toml"))] if MODELS.is_dir() else []
    return sorted(checks + coupons)


def test_name(test_dir: Path) -> str:
    """The name a test folder's files carry: the check's folder name, or the coupon's for its ours/."""
    test_dir = Path(test_dir)
    return test_dir.parent.name if test_dir.name == OURS else test_dir.name


def records_dir(test_dir: Path) -> Path:
    """Where a test folder's records are: `records/` in a check, `verification/` in a coupon's ours/."""
    test_dir = Path(test_dir)
    return test_dir / (VERIFICATION if test_dir.name == OURS else "records")


def all_specs() -> list[Path]:
    """Every spec on this machine, the checks' and the local coupons', sorted by path."""
    return sorted(spec for d in test_dirs() for spec in d.glob("*.toml"))


def all_records() -> list[Path]:
    """Every comparison record on this machine, sorted by path; a team summary and a team comparison's manifest are not records."""
    return sorted(record for d in test_dirs() for record in records_dir(d).glob("*.toml")
                  if not record.stem.endswith(TEAM_SUMMARY) and record.name != MANIFEST)


def team_summary(test_dir: Path) -> Path:
    """Where the team comparison's figures for a test folder are written: `<test>-team-summary.toml` among its records."""
    return records_dir(test_dir) / f"{test_name(test_dir)}{TEAM_SUMMARY}.toml"


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
    """The coupon's folder on the founder's machine (git-ignored): README.md, team/, ours/, documents/ (ADR-0040, ADR-0042)."""
    return LOCAL / name


def team_files(name: str) -> Path:
    """What the team sent for a coupon, one dated folder per delivery, as received."""
    return LOCAL / name / TEAM_FILES


def ours(name: str) -> Path:
    """Everything we built for a coupon: the spec(s), decks/, verification/, runs/, latex/."""
    return LOCAL / name / OURS


def verification(name: str) -> Path:
    """How our model of a coupon was checked: the CalculiX record, the team comparison, notes and figures."""
    return ours(name) / VERIFICATION


def runs(name: str) -> Path:
    """Our runs of a coupon, one attempt-NN_<date>/ folder per try (ADR-0039)."""
    return ours(name) / RUNS


def latex(name: str) -> Path:
    """The coupon document's source: <coupon>.tex and the figures/ it uses; the PDF is built into the package."""
    return ours(name) / LATEX


def team_deck(name: str) -> Path | None:
    """The team's deck of a coupon: the one .inp at the top of the newest team/<date>/ folder that holds one; None where there is
    none (CI) or that folder holds more than one. A folder that brought only a returned audit form, or a rebuilt/ deck, is
    passed over. Found by place, so committed code never names the team's files (ADR-0042)."""
    received = team_files(name)
    dated = sorted((d for d in received.iterdir() if d.is_dir()), reverse=True) if received.is_dir() else []
    for folder in dated:
        decks = sorted(folder.glob("*.inp"))
        if decks:
            return decks[0] if len(decks) == 1 else None
    return None


def documents(name: str) -> Path:
    """Where a coupon's packages go, one dated folder per delivery: the PDF, the audit form, the decks and the material."""
    return LOCAL / name / DOCUMENTS
