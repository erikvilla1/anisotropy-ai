"""The team comparison and the share zips, docs/models/team.py and docs/models/share.py (ADR-0035, ADR-0036), built in a temporary folder."""

import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

from test_equivalence import FIXTURE_SPEC, GRIPS_FIXTURE
from test_side_by_side import kernel_reports

ROOT = Path(__file__).parents[2]
BUILD = ROOT / "docs/models/team.py"
SHARE = ROOT / "docs/models/share.py"
RECORD = ROOT / "fea/checks/unnotched-im7-8552/records/unnotched-im7-8552-nodal-calculix.toml"
CARD = """[coupon]
designation = "IM7-UNT-L9"
standard = "none"
size_from = "the grips fixture"
team_model = "the grips fixture deck"
test_data = "none"
"""
LIBRARY_SPEC = FIXTURE_SPEC.replace("E1 = 162095.74\nE2 = 8963.18\nG12 = 4688.43\nnu12 = 0.316\nF1t = 2558.51\nF1c = 1731.48\nF2t = 64.05\nF2c = 285.72\nF6 = 91.15\n",
                                    'library = "im7-8552"\ndataset = "ncamp-im7-8552-2019-rtd-measured-v1"\n')
NAMED_SPEC = LIBRARY_SPEC.replace('title = "The grips fixture as a spec"', 'title = "IM7-UNT-L9, unnotched tension: the grips fixture as a spec"', 1) \
    .replace("[geometry]", CARD + "[geometry]", 1)


def manifest(tmp: Path, zip_name: str, spec: str = NAMED_SPEC) -> Path:
    (tmp / "team").mkdir(exist_ok=True)
    (tmp / "ours").mkdir(exist_ok=True)
    deck = tmp / "team" / GRIPS_FIXTURE.name
    deck.write_bytes(GRIPS_FIXTURE.read_bytes())
    reports = kernel_reports(GRIPS_FIXTURE, tmp / "team")
    (tmp / "ours" / "grips-coupon.toml").write_text(spec, encoding="utf-8")
    path = tmp / "team-comparison.toml"
    path.write_text("\n".join([
        'name = "grips"', 'units = "mm-MPa"', "node_tolerance = 1e-5", "agreement = 0.01", "edge_band = 10.0", "map_layer = 10",
        f'zip = "{zip_name}"', "[locations]", '"centre" = [2.5, 45.0]',
        "[team]", f'deck = "team/{deck.name}"', 'solver = "a fixture"', 'run_by = "the test"', 'run_date = "2026-10-20"',
        "reports = [" + ", ".join(f'"team/{p.name}"' for p in reports) + "]",
        "[ours]", 'spec = "ours/grips-coupon.toml"', f'calculix_record = "{RECORD.as_posix()}"',
    ]) + "\n", encoding="utf-8")
    return path


def run(script: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *arguments, "--no-pdf"], capture_output=True, text=True, cwd=ROOT)


def test_the_document_and_the_zip_are_built(tmp_path):
    path = manifest(tmp_path, "share/grips-comparison.zip")
    result = run(BUILD, str(path))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "items the same" in result.stdout and "16 elements matched" in result.stdout
    tex = (tmp_path / "report" / "grips-comparison" / "grips-comparison.tex").read_text(encoding="utf-8")
    for label in ("sec:models", "sec:material", "sec:results", "sec:reading", "sec:open", "sec:files"):
        assert rf"\label{{{label}}}" in tex
    assert "IM7-UNT-L9" in tex and "Unnotched tension coupon" in tex  # the coupon's name is the title (ADR-0038)
    assert "No reading has been written yet" in tex and r"\begin{quote}" in tex
    expected = ["README.txt", "1-team-model/coupon-2x8-grips-im7-8552.inp", "2-our-model/abaqus/grips-coupon-abaqus.inp",
                "2-our-model/calculix/unnotched-im7-8552-nodal-ccx.inp", "2-our-model/spec/grips-coupon.toml",
                "3-material/im7-8552.csv", "4-results/ours-S11.csv", "4-results/ours-S22.csv", "4-results/ours-Mises.csv", "4-results/team-vs-ours.csv",
                "4-results/ours-all-plies.csv"]
    archive = tmp_path / "share" / f"{date.today().isoformat()}_grips-comparison.zip"  # dated (ADR-0039)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert {f"grips/{name}" for name in expected} <= names
        assert not any(name.endswith(".frd") for name in names)  # no CalculiX results in a team zip (ADR-0036)
        ours = zf.read("grips/4-results/ours-S22.csv").decode("utf-8").splitlines()[0]
        readme = zf.read("grips/README.txt").decode("utf-8").splitlines()
    assert readme[1] == "IM7-UNT-L9, unnotched tension: the team's Abaqus model and ours" and "Test data:     none" in readme
    assert ours == (tmp_path / "team/Test_S22.csv").read_text(encoding="utf-8").splitlines()[0]  # the team's columns, in the team's order
    assert not (tmp_path / "share" / "grips").exists()  # no unzipped copy is kept
    assert run(BUILD, str(path)).returncode == 0  # a second build replaces the zip it wrote
    summary = (tmp_path / "ours" / "records" / "ours-team-summary.toml").read_text(encoding="utf-8")  # the figures beside our records (ADR-0039)
    assert 'coupon = "IM7-UNT-L9"' in summary and "[equivalence]" in summary and "[[agreement]]" in summary


def test_a_comparison_names_its_coupon(tmp_path):
    result = run(BUILD, str(manifest(tmp_path, "share/grips-comparison.zip", spec=LIBRARY_SPEC)))
    assert result.returncode != 0 and "has no [coupon] table" in result.stdout + result.stderr


def test_a_zip_the_project_did_not_write_is_never_replaced(tmp_path):
    (tmp_path / "share").mkdir()
    foreign = tmp_path / "share" / f"{date.today().isoformat()}_theirs.zip"  # the name the build would write today
    with zipfile.ZipFile(foreign, "w") as zf:
        zf.writestr("theirs/notes.txt", "keep me\n")
    result = run(BUILD, str(manifest(tmp_path, "share/theirs.zip")))
    assert result.returncode != 0 and "was not written by this project" in result.stdout + result.stderr
    with zipfile.ZipFile(foreign) as zf:
        assert zf.namelist() == ["theirs/notes.txt"]


def test_our_models_are_zipped_by_convention(tmp_path):
    archive = tmp_path / "our-models.zip"
    result = run(SHARE, "tension-coupon", "compression-coupon", "--out", str(archive))  # structured meshes: no Gmsh needed (the manual job has none)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 models zipped" in result.stdout
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        for name in ("README.txt", "X840PW-UNC-L1/abaqus/compression-coupon-abaqus.inp", "X840PW-UNC-L1/calculix/compression-coupon-nodal-ccx.inp",
                     "X840PW-UNT-L1/abaqus/tension-coupon-abaqus.inp", "X840PW-UNT-L1/spec/tension-coupon-nodal.toml", "material/x840-z60-pw.csv"):
            assert f"our-models/{name}" in names, name
        assert not any(name.endswith(".frd") for name in names)
        readme = zf.read("our-models/README.txt").decode("utf-8")
        deck = zf.read("our-models/X840PW-UNT-L1/abaqus/tension-coupon-abaqus.inp").decode("utf-8")
    assert readme.count("69 of 69 compared values agree") == 2
    assert "X840PW-UNT-L1/  unnotched tension (test folder tension-coupon)" in readme  # each folder is named by its coupon (ADR-0038)
    assert "  L1       [0/45/-45/45/0]s" in readme and "  UNC      unnotched compression" in readme  # the key, from the coupons zipped
    assert deck == (ROOT / "fea/models/tension-coupon/decks/tension-coupon-abaqus.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    unknown = run(SHARE, "no-such-coupon", "--out", str(tmp_path / "x.zip"))
    assert unknown.returncode != 0 and "no model folder" in unknown.stdout + unknown.stderr
