"""examples/build_model.py run as a program, its output piped as Windows pipes it."""

import os
import subprocess
import sys
from pathlib import Path

from anisotropy_fea import paths  # where the files live (ADR-0036)

SCRIPT = Path(__file__).parents[1] / "examples/build_model.py"


def test_the_report_prints_through_a_cp1252_pipe(tmp_path):
    # The library's AS4/3501 gives its expansion coefficients in 10⁻⁶ units, which cp1252 (Windows's code page for piped and
    # redirected output) cannot encode. The report quotes them, so a piped run crashed after writing every file.
    text = paths.spec_path("unnotched-im7-8552-nodal").read_text(encoding="utf-8")
    text = text.replace('library = "im7-8552"\ndataset = "ncamp-im7-8552-2019-rtd-measured-v1"', 'library = "as4-3501"')
    text = text.replace('ply_thickness = "library"', "ply_thickness = 0.125")  # that dataset gives no thickness
    assert 'library = "as4-3501"' in text and "ply_thickness = 0.125" in text
    spec = tmp_path / "as4-coupon.toml"
    spec.write_text(text, encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}  # what a Windows pipe gets, on any platform
    env.pop("PYTHONUTF8", None)
    result = subprocess.run([sys.executable, str(SCRIPT), str(spec), "--out", str(tmp_path / "out"), "--no-solve"], capture_output=True, env=env)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert "10⁻⁶" in result.stdout.decode("utf-8")
