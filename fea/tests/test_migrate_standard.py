"""tools/migrate_standard.py (ADR-0072): a spec whose standard is free text is restated with "none" and keeps the old words in size_from,
so the form's Standard list can reopen it; a spec already on the list is left as it is."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from anisotropy_fea.spec import parse_spec

from public_coupon import PUBLIC_COUPON

TOOL = Path(__file__).parents[1] / "tools" / "migrate_standard.py"
FREE_TEXT = PUBLIC_COUPON.replace('standard = "none"', 'standard = "ASTM D3039 proportions"')


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("migrate_standard", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_free_text_becomes_none_and_the_words_stay_in_size_from(tool):
    assert parse_spec(FREE_TEXT).coupon.standard == "ASTM D3039 proportions"  # it loads and runs as it is; only the form refuses it
    rewritten, old = tool.migrate_text(FREE_TEXT, date(2026, 11, 8))
    spec = parse_spec(rewritten)
    assert old == "ASTM D3039 proportions" and spec.coupon.standard == "none"
    assert spec.coupon.size_from == "the public IM7/8552 check fea/checks/unnotched-im7-8552/; stated before as: ASTM D3039 proportions"
    assert rewritten.endswith("it is now \"none\" and the old words close size_from.\n") and "Migrated on 2026-11-08" in rewritten
    unchanged = [line for line in FREE_TEXT.splitlines() if "standard =" not in line and "size_from =" not in line]
    assert all(line in rewritten.splitlines() for line in unchanged)


def test_a_spec_on_the_list_is_left_alone(tool, tmp_path):
    assert tool.migrate_text(PUBLIC_COUPON) is None
    path = tmp_path / "spec.toml"
    path.write_bytes(PUBLIC_COUPON.encode("utf-8"))
    assert tool.migrate_file(path, dry_run=False).endswith("standard already on the list, left as it is") and path.read_bytes() == PUBLIC_COUPON.encode("utf-8")


def test_a_dry_run_writes_nothing_and_line_endings_are_kept(tool, tmp_path):
    path = tmp_path / "spec.toml"
    crlf = FREE_TEXT.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(crlf)
    assert "(dry run, nothing written)" in tool.migrate_file(path, dry_run=True) and path.read_bytes() == crlf
    tool.migrate_file(path, dry_run=False)
    text = path.read_bytes().decode("utf-8")
    assert "\n" not in text.replace("\r\n", "") and parse_spec(text.replace("\r\n", "\n")).coupon.standard == "none"


def test_a_spec_without_a_coupon_table_is_refused(tool):
    with pytest.raises(tool.MigrationError, match="no \\[coupon\\] table"):
        tool.migrate_text("title = \"x\"\n")
