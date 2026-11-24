"""The quality checks of a coupon run and its verdict (ADR-0137): the setup items as checks, the second solver's comparison and the mesh
study, each with its layer, id, verdict and evidence, in the words a customer reads."""

from __future__ import annotations

from pathlib import Path

import pytest

from anisotropy_fea import paths
from anisotropy_fea.case_pages import record_rows
from anisotropy_fea.qa import (LAYERS, SETUP, VERDICTS, QAError, check, mesh_check, qa_record, run_checks, run_verdict, second_solver_check,
                               setup_checks)

RECORD = paths.FEA / "checks" / "d3039-im7-8552" / "records" / "d3039-im7-8552-calculix.toml"  # a public check record
FORBIDDEN = ("CalculiX", "kernel", "engine", "record", "ADR-")  # what a customer never reads in a check's words (ADR-0091)


def item(id_: str, state: str, message: str = "fine") -> dict:
    return {"id": id_, "label": id_.title(), "state": state, "message": message, "rows": ["Width"], "requirements": []}


def test_each_setup_state_becomes_a_verdict_and_each_item_a_layer():
    states = {"units": "pass", "geometry": "warn", "material": "pending", "laminate": "fail", "load": "missing"}
    checks = setup_checks({"items": [item(k, v) for k, v in states.items()]})
    assert [c["verdict"] for c in checks] == ["pass", "warn", "warn", "block", "block"]
    assert [c["check"] for c in checks] == ["DATA-UNITS", "DATA-GEOMETRY", "DATA-MATERIAL", "DATA-LAMINATE", "DATA-LOAD"]
    assert checks[0]["evidence"] == {"state": "pass", "rows": ["Width"]} and checks[0]["label"] == "Units" and checks[0]["basis"] == "ADR-0002"
    assert all(layer in LAYERS for layer, _, _ in SETUP.values())
    assert setup_checks({"items": [item("something_new", "pass")]})[0]["check"] == "DATA-SOMETHING_NEW"  # a later item still has a row


def test_a_run_without_its_checklist_is_said_so_and_a_state_the_checklist_never_gives_is_refused():
    (only,) = setup_checks(None)
    assert only["verdict"] == "warn" and only["check"] == "DATA-SETUP"
    with pytest.raises(QAError, match="state 'maybe'"):
        setup_checks({"items": [item("units", "maybe")]})


def test_a_check_keeps_to_the_records_layers_and_verdicts():
    with pytest.raises(QAError, match="layer"):
        check("physics-ish", "X", "pass", "X", "")
    with pytest.raises(QAError, match="verdict"):
        check("data", "X", "fail", "X", "")
    assert set(VERDICTS) == {"pass", "warn", "block"}


def test_the_second_solver_check_counts_what_the_record_counts():
    result = second_solver_check(RECORD)
    _, rows, data = record_rows(RECORD)
    agree = sum(r.agrees for r in rows)
    assert result["evidence"]["agree"] == agree and result["evidence"]["compared"] == len(rows)
    assert result["evidence"]["tolerance"] == data["expected"]["tolerance"]
    assert result["verdict"] == ("pass" if agree == len(rows) else "warn") and result["check"] == "FEA-SECOND-SOLVER" and result["layer"] == "fea"
    reaction = result["evidence"]["reaction"]
    assert reaction["difference"] == pytest.approx((reaction["ours"] - reaction["second_solver"]) / abs(reaction["second_solver"]))


def test_no_second_solver_and_no_mesh_study_warn():
    assert second_solver_check(None)["verdict"] == "warn" and second_solver_check(Path("no-such.toml"))["verdict"] == "warn"
    assert mesh_check(None)["verdict"] == "warn"
    not_studied = mesh_check({"studied": False, "reason": "the study covers gripped in-plane coupons"})
    assert not_studied["verdict"] == "warn" and "gripped in-plane" in not_studied["message"]


def test_the_mesh_check_passes_only_when_every_quantity_settled():
    settled = {"reaction": True, "gauge_strain": True, "plies": True, "peaks": True, "fpf": True, "fpf_gauge": True}
    assert mesh_check({"studied": True, "settled": settled, "settled_below": 0.01})["verdict"] == "pass"
    moving = mesh_check({"studied": True, "settled": {**settled, "peaks": False}, "settled_below": 0.01})
    assert moving["verdict"] == "warn" and "peak fibre stresses" in moving["message"] and "1 %" in moving["message"]
    assert moving["evidence"]["settled"]["peaks"] is False
    assert mesh_check({"studied": True, "settled": {}, "settled_below": 0.01})["verdict"] == "warn"


def test_the_verdict_follows_from_the_checks_alone():
    ok = check("data", "A", "pass", "A", "")
    assert run_verdict([]) == "unchecked" and run_verdict([ok]) == "ready"
    assert run_verdict([ok, check("fea", "B", "warn", "B", "")]) == "needs engineer"
    assert run_verdict([ok, check("fea", "B", "warn", "B", ""), check("data", "C", "block", "C", "")]) == "blocked"


def test_a_runs_record_holds_its_checks_counts_and_verdict_in_a_customers_words():
    checklist = {"items": [item(k, "pass") for k in SETUP]}
    study = {"studied": True, "settled": {"reaction": True}, "settled_below": 0.01}
    record = qa_record(run_checks(checklist, RECORD, study))
    assert len(record["checks"]) == len(SETUP) + 2 and sum(record["counts"].values()) == len(record["checks"])
    assert record["verdict"] == run_verdict(record["checks"]) and record["version"] == 1
    for c in record["checks"][-2:]:  # the words this module writes; the setup items' words are the checklist's own
        assert not any(term in c["message"] or term in c["label"] for term in FORBIDDEN), c
