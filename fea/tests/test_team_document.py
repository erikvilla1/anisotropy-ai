"""The team comparison document and share folder, docs/models/team.py (ADR-0035), built from committed fixtures in a temporary folder."""

import subprocess
import sys
import zipfile
from pathlib import Path

from test_equivalence import FIXTURE_SPEC, GRIPS_FIXTURE
from test_side_by_side import kernel_reports

ROOT = Path(__file__).parents[2]
BUILD = ROOT / "docs/models/team.py"
RECORD = ROOT / "fea/validation/records/unnotched-im7-8552-nodal-calculix.toml"
LIBRARY_SPEC = FIXTURE_SPEC.replace("E1 = 162095.74\nE2 = 8963.18\nG12 = 4688.43\nnu12 = 0.316\nF1t = 2558.51\nF1c = 1731.48\nF2t = 64.05\nF2c = 285.72\nF6 = 91.15\n",
                                    'library = "im7-8552"\ndataset = "ncamp-im7-8552-2019-rtd-measured-v1"\n')


def manifest(tmp: Path, share: str) -> Path:
    (tmp / "team").mkdir(exist_ok=True)
    (tmp / "ours").mkdir(exist_ok=True)
    deck = tmp / "team" / GRIPS_FIXTURE.name
    deck.write_bytes(GRIPS_FIXTURE.read_bytes())
    reports = kernel_reports(GRIPS_FIXTURE, tmp / "team")
    (tmp / "ours" / "grips-coupon.toml").write_text(LIBRARY_SPEC, encoding="utf-8")
    (tmp / "ours" / "twin-ccx.frd").write_text("results placeholder\n", encoding="utf-8")
    path = tmp / "team-comparison.toml"
    path.write_text("\n".join([
        'name = "grips"', 'title = "Grips fixture"', 'units = "mm-MPa"', "node_tolerance = 1e-5", "agreement = 0.01", "edge_band = 10.0", "map_layer = 10",
        f'share = "{share}"', "[locations]", '"centre" = [2.5, 45.0]',
        "[team]", f'deck = "team/{deck.name}"', 'solver = "a fixture"', 'run_by = "the test"', 'run_date = "2026-10-20"',
        "reports = [" + ", ".join(f'"team/{p.name}"' for p in reports) + "]",
        "[ours]", 'spec = "ours/grips-coupon.toml"', f'calculix_record = "{RECORD.as_posix()}"', 'calculix_results = "ours/twin-ccx.frd"',
    ]) + "\n", encoding="utf-8")
    return path


def run(path: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(BUILD), str(path), "--no-pdf"], capture_output=True, text=True, cwd=ROOT)


def test_the_document_and_the_share_folder_are_built(tmp_path):
    path = manifest(tmp_path, "share/grips")
    result = run(path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "items the same" in result.stdout and "16 elements matched" in result.stdout
    tex = (tmp_path / "report" / "grips-comparison" / "grips-comparison.tex").read_text(encoding="utf-8")
    for label in ("sec:models", "sec:material", "sec:results", "sec:reading", "sec:open", "sec:files"):
        assert rf"\label{{{label}}}" in tex
    assert "No reading has been written yet" in tex and r"\begin{quote}" in tex
    share = tmp_path / "share" / "grips"
    expected = ["README.txt", "1-team-model/coupon-2x8-grips-im7-8552.inp", "2-our-model/abaqus/grips-coupon-abaqus.inp",
                "2-our-model/calculix/unnotched-im7-8552-nodal-ccx.inp", "2-our-model/calculix/twin-ccx.frd", "2-our-model/spec/grips-coupon.toml",
                "3-material/im7-8552.csv", "4-results/ours-S11.csv", "4-results/ours-S22.csv", "4-results/ours-Mises.csv", "4-results/team-vs-ours.csv",
                "4-results/ours-all-plies.csv"]
    for name in expected:
        assert (share / name).is_file(), name
    assert (share / "4-results/ours-S22.csv").read_text(encoding="utf-8").splitlines()[0] == \
        (tmp_path / "team/Test_S22.csv").read_text(encoding="utf-8").splitlines()[0]  # the team's columns, in the team's order
    with zipfile.ZipFile(tmp_path / "share" / "grips.zip") as zf:
        assert {f"grips/{name}" for name in expected} <= set(zf.namelist())
    assert run(path).returncode == 0  # a second build replaces the folder it wrote


def test_a_folder_the_script_did_not_write_is_never_replaced(tmp_path):
    foreign = tmp_path / "share" / "theirs"
    foreign.mkdir(parents=True)
    (foreign / "notes.txt").write_text("keep me\n", encoding="utf-8")
    result = run(manifest(tmp_path, "share/theirs"))
    assert result.returncode != 0 and "was not written by this script" in result.stdout + result.stderr
    assert (foreign / "notes.txt").read_text(encoding="utf-8") == "keep me\n"


SHARE = ROOT / "docs/models/share.py"


def share_manifest(tmp: Path, folder: str) -> Path:
    frd = tmp / "twin.frd"
    frd.write_text("results placeholder\n", encoding="utf-8")
    path = tmp / "models.toml"
    path.write_text("\n".join([
        'name = "models"', 'title = "Two coupons"', 'units = "mm-MPa"', f'share = "{(tmp / folder).as_posix()}"',
        "[[models]]", 'test = "tension-coupon"', 'spec = "fea/validation/specs/tension-coupon-x840-coupling.toml"',
        'record = "fea/validation/records/tension-coupon-x840-nodal-calculix.toml"', f'results = "{frd.as_posix()}"',
        "[[models]]", 'test = "unnotched-im7"', 'spec = "fea/validation/specs/unnotched-im7-8552-nodal.toml"',
        'record = "fea/validation/records/unnotched-im7-8552-nodal-calculix.toml"', f'results = "{frd.as_posix()}"',
    ]) + "\n", encoding="utf-8")
    return path


def test_our_models_are_written_to_one_folder_and_zipped(tmp_path):
    result = subprocess.run([sys.executable, str(SHARE), str(share_manifest(tmp_path, "share/models")), "--no-pdf"], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    share = tmp_path / "share" / "models"
    for name in ("README.txt", "1-tension-coupon/abaqus/tension-coupon-x840-coupling-abaqus.inp", "1-tension-coupon/calculix/tension-coupon-x840-nodal-ccx.inp",
                 "1-tension-coupon/calculix/twin.frd", "1-tension-coupon/spec/tension-coupon-x840-nodal.toml", "2-unnotched-im7/spec/unnotched-im7-8552-nodal.toml",
                 "material/x840-z60-pw.csv", "material/im7-8552.csv"):
        assert (share / name).is_file(), name
    readme = (share / "README.txt").read_text(encoding="utf-8")
    assert "69 of 69 compared values agree" in readme and "59 of 59 compared values agree" in readme
    deck = (share / "1-tension-coupon/abaqus/tension-coupon-x840-coupling-abaqus.inp").read_text(encoding="utf-8")
    assert deck == (ROOT / "fea/validation/decks/generated/tension-coupon-x840-coupling-abaqus.inp").read_text(encoding="utf-8").replace("\r\n", "\n")
    with zipfile.ZipFile(tmp_path / "share" / "models.zip") as zf:
        assert "models/material/x840-z60-pw.csv" in zf.namelist()
    foreign = tmp_path / "theirs"
    foreign.mkdir()
    (foreign / "keep.txt").write_text("keep\n", encoding="utf-8")
    refused = subprocess.run([sys.executable, str(SHARE), str(share_manifest(tmp_path, "theirs")), "--no-pdf"], capture_output=True, text=True, cwd=ROOT)
    assert refused.returncode != 0 and (foreign / "keep.txt").exists()
