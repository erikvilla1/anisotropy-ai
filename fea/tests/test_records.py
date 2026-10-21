"""Comparison records: the kernel reproduces every committed record, and the record machinery refuses what it should (ADR-0030)."""

import tomllib
from pathlib import Path

import pytest

from anisotropy_fea.compare import RecordError, compare_record, format_record, load_record, record_disagreements, validate_record
from anisotropy_fea import paths  # where the files live (ADR-0036)

RECORDS = paths.CHECKS / "unnotched-im7-8552" / "records"  # the first record
COMMITTED = paths.all_records()


@pytest.mark.parametrize("path", COMMITTED, ids=[p.stem for p in COMMITTED])
def test_the_kernel_reproduces_the_record(path):
    record = load_record(path)
    problems = record_disagreements(record)
    assert not problems, f"{record['title']}\n" + "\n".join(problems)


def test_there_is_a_record():
    assert COMMITTED


def test_the_first_record_covers_reactions_displacements_strain_and_every_ply():
    record = load_record(RECORDS / "unnotched-im7-8552-nodal-calculix.toml")
    comparisons, problems = compare_record(record)
    assert not problems and len(comparisons) >= 50
    keys = {c.key.split("[")[0] for c in comparisons}
    assert keys == {"rf", "u", "strain", "ply_stress_local", "ply_strain_local"}
    plies = record["expected"]["ply_stress_local"]["Coupon-1.626"]
    assert list(plies) == [str(k) for k in range(1, 9)]
    worst = max(abs(c.engine - c.expected) / c.allowed for c in comparisons)
    assert worst < 1.0


def test_the_floor_rule_judges_small_components_against_their_group():
    record = load_record(RECORDS / "unnotched-im7-8552-nodal-calculix.toml")
    comparisons, _ = compare_record(record)
    (tiny,) = [c for c in comparisons if c.key == "ply_stress_local[Coupon-1.626][2][2]"]  # tau_12 of a 0 ply at the centre: roundoff-sized
    assert abs(tiny.expected) < 1.0 and tiny.allowed > 0.03 * abs(tiny.expected)  # judged against 2 % of the ~1180 MPa group, not against itself


def test_a_changed_deck_is_noticed(tmp_path):
    source = RECORDS / "unnotched-im7-8552-nodal-calculix.toml"
    record = tomllib.loads(source.read_text(encoding="utf-8"))
    record["_dir"] = str(RECORDS)
    record["deck_reference_sha256"] = "0" * 64
    with pytest.raises(RecordError, match="was made from"):
        validate_record(record)


def test_incomplete_or_wrong_records_are_refused():
    record = tomllib.loads((RECORDS / "unnotched-im7-8552-nodal-calculix.toml").read_text(encoding="utf-8"))
    record["_dir"] = str(RECORDS)
    for key, value, message in (("solver", {**record["solver"], "name": "nastran"}, "calculix or abaqus"),
                                ("solver", {k: v for k, v in record["solver"].items() if k != "run_by"}, "needs 'run_by'"),
                                ("expected", {**record["expected"], "floor": 1.5}, "floor must be"),
                                ("expected", {**record["expected"], "stress": {"*": [0.0, 0.0, 0.0]}}, "not a result group")):
        broken = {**record, key: value}
        with pytest.raises((RecordError, ValueError), match=message):
            validate_record(broken)
    with pytest.raises(RecordError, match="needs 'deck_reference'"):
        validate_record({k: v for k, v in record.items() if k != "deck_reference"})


def test_format_record_round_trips():
    record = tomllib.loads((RECORDS / "unnotched-im7-8552-nodal-calculix.toml").read_text(encoding="utf-8"))
    again = tomllib.loads(format_record(record))
    assert again == record
