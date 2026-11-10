"""tools/migrate_angles.py (ADR-0065): a spec written before the convention is restated from the length axis with the same fibres, once."""

import importlib.util
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.spec import fibre_angles, parse_spec, spec_plies, to_si

TOOL = Path(__file__).parents[1] / "tools" / "migrate_angles.py"
NODAL = paths.spec_path("unnotched-im7-8552-nodal").read_text(encoding="utf-8").replace("\r\n", "\n")
OLD = re.sub(r"angles_from = \"length\"[^\n]*\n", "", NODAL)  # the public spec as it was written before ADR-0065


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("migrate_angles", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_rewritten_spec_states_the_same_fibres_from_the_length_axis(tool):
    assert "angles_from" not in OLD
    rewritten, before, after = tool.migrate_text(OLD, date(2026, 11, 8))
    assert before == [45, 0, -45, 90] and after == [-45, 90, 45, 0]
    assert 'angles = [-45, 90, 45, 0]\nangles_from = "length"  # counted from the coupon\'s length axis' in rewritten
    assert rewritten.endswith("# Migrated on 2026-11-08 by fea/tools/migrate_angles.py (ADR-0065): the angles were [45, 0, -45, 90] counted from x, "
                              "across the width; they are now stated from the coupon's length axis, the same fibres.\n")
    migrated = to_si(parse_spec(rewritten))
    assert fibre_angles(migrated) == [45, 0, -45, 90, 90, -45, 0, 45]  # the fibres the old spec meant, counted from x
    assert [p.angle_deg for p in spec_plies(migrated)] == [45, 0, -45, 90, 90, -45, 0, 45]
    # nothing but the two lines and the trailing comment changed
    kept = [line for line in rewritten.splitlines() if not line.startswith(("angles", "# Migrated"))]
    assert kept == [line for line in OLD.splitlines() if not line.startswith("angles")]


@pytest.mark.parametrize("angles, expected", [
    ("[0]", "[90]"), ("[90]", "[0]"), ("[45, -45]", "[-45, 45]"), ("[0, 90, 90, 0]", "[90, 0, 0, 90]"), ("[22.5, -67.5]", "[-67.5, 22.5]"),
    ("[180, -90, 270]", "[90, 0, 0]"),
])
def test_every_angle_turns_by_minus_90_into_the_half_open_range(tool, angles, expected):
    rewritten, _, _ = tool.migrate_text(OLD.replace("angles = [45, 0, -45, 90]", f"angles = {angles}"), date(2026, 11, 8))
    assert f"angles = {expected}\n" in rewritten


def test_a_spec_already_under_the_convention_is_refused_and_so_is_one_without_a_layup(tool):
    with pytest.raises(tool.MigrationError, match="already states layup.angles_from"):
        tool.migrate_text(NODAL)
    with pytest.raises(tool.MigrationError, match="no \\[layup\\] table"):
        tool.migrate_text(OLD.replace("[layup]", "[stack]"))
    with pytest.raises(tool.MigrationError, match="other than numbers"):
        tool.migrate_text(OLD.replace("angles = [45, 0, -45, 90]", 'angles = ["a"]'))


def test_the_command_rewrites_in_place_keeps_crlf_and_the_dry_run_writes_nothing(tmp_path):
    spec = tmp_path / "old.toml"
    spec.write_bytes(OLD.replace("\n", "\r\n").encode("utf-8"))
    dry = subprocess.run([sys.executable, str(TOOL), "--dry-run", str(spec)], capture_output=True, text=True, encoding="utf-8")
    assert dry.returncode == 0 and "angles [45, 0, -45, 90] -> [-45, 90, 45, 0]" in dry.stdout and "dry run" in dry.stdout
    assert spec.read_bytes() == OLD.replace("\n", "\r\n").encode("utf-8")
    done = subprocess.run([sys.executable, str(TOOL), str(spec)], capture_output=True, text=True, encoding="utf-8")
    assert done.returncode == 0 and "angles_from = \"length\" added" in done.stdout
    raw = spec.read_bytes()
    assert b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b"")  # the file keeps its CRLF line endings
    assert b'angles = [-45, 90, 45, 0]\r\nangles_from = "length"' in raw and raw.endswith(b"the same fibres.\r\n")
    again = subprocess.run([sys.executable, str(TOOL), str(spec)], capture_output=True, text=True, encoding="utf-8")
    assert again.returncode == 1 and "already states layup.angles_from" in again.stderr and spec.read_bytes() == raw
    assert to_si(parse_spec(raw.decode("utf-8"))).layup.angles == [-45.0, 90.0, 45.0, 0.0]
