"""The quality checks of one coupon run, as the rows of its QA record, and the run's verdict (ADR-0137).

A check is one row: its layer (data, physics, fea, output, software), its id and the version of its rule, its verdict (pass, warn,
block), its label and message in the words a customer reads, the values it measured, and the decision record or clause behind it.
The run's verdict follows from its rows alone: "blocked" when a check blocks, "needs engineer" when one warns, "ready" when every
check passes, "unchecked" when there are none.

This first step writes the checks a run already makes into the record, and changes no run: the setup checklist (ADR-0051), the second
solver's comparison (ADR-0030) and the mesh study (ADR-0068). A run reaches its result only past the setup check, so of these only a
setup item can block, and a run it blocks is refused before its result; the comparison and the study warn. Every number here is read
from what the run computed; nothing is computed again.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .case_pages import reaction_row, record_rows

LAYERS = ("data", "physics", "fea", "output", "software")
VERDICTS = ("pass", "warn", "block")
RUN_VERDICTS = ("blocked", "needs engineer", "ready", "unchecked")
VERSION = 1  # the rules' version: a check whose rule changes raises it, so an old row says which rule judged it

SETUP_STATE = {"pass": "pass", "warn": "warn", "pending": "warn", "fail": "block", "missing": "block"}  # checks.STATES to a verdict
SETUP = {  # the checklist's items (checks.ITEMS) as checks: layer, id, the record or clause behind it
    "identity": ("data", "DATA-IDENTITY", "ADR-0051"),
    "units": ("data", "DATA-UNITS", "ADR-0002"),
    "geometry": ("data", "DATA-GEOMETRY", "ADR-0003"),
    "standard": ("data", "DATA-STANDARD", "ADR-0072"),
    "material": ("data", "DATA-MATERIAL", "ADR-0003"),
    "laminate": ("data", "DATA-LAMINATE", "ADR-0003"),
    "constraints": ("physics", "PHYS-SUPPORTS", "ADR-0051"),
    "load": ("data", "DATA-LOAD", "ADR-0003"),
    "mesh": ("fea", "FEA-MESH-QUALITY", "ADR-0051"),
    "criterion": ("data", "DATA-CRITERION", "ADR-0051"),
    "probes": ("data", "DATA-PROBES", "ADR-0051"),
    "solver": ("software", "SW-SOLVER-READY", "ADR-0030"),
    "document": ("output", "OUT-REPORT-READY", "ADR-0064"),
}
SECOND_SOLVER = ("fea", "FEA-SECOND-SOLVER", "ADR-0030")
MESH_STUDY = ("fea", "FEA-MESH-CONVERGED", "ADR-0068")
MESH_WORDS = {"reaction": "the reaction", "gauge_strain": "the strain in the gauge section", "plies": "the plies' shear stress",
              "peaks": "the peak fibre stresses", "fpf": "the first-ply failure load", "fpf_gauge": "the first-ply failure load in the gauge section"}


class QAError(ValueError):
    """A check that cannot be written as asked."""


def check(layer: str, check_id: str, verdict: str, label: str, message: str, evidence: dict[str, Any] | None = None, basis: str = "") -> dict[str, Any]:
    """One row of the QA record, refused when its layer or verdict is not one of the record's."""
    if layer not in LAYERS:
        raise QAError(f"a check's layer is one of {', '.join(LAYERS)}, not {layer!r}")
    if verdict not in VERDICTS:
        raise QAError(f"a check's verdict is one of {', '.join(VERDICTS)}, not {verdict!r}")
    return {"layer": layer, "check": check_id, "version": VERSION, "verdict": verdict, "label": label, "message": message,
            "evidence": evidence or {}, "basis": basis}


def setup_checks(checklist: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The setup checklist's items as checks; one warning when the run had none (a run started by a coupon's name)."""
    if checklist is None:
        return [check("data", "DATA-SETUP", "warn", "Setup check", "This run started from a stored coupon, so its setup was not checked again.",
                      {}, "ADR-0051")]
    out = []
    for item in checklist.get("items", []):
        state = item.get("state")
        if state not in SETUP_STATE:
            raise QAError(f"the setup item {item.get('id')!r} has the state {state!r}")
        layer, check_id, basis = SETUP.get(item["id"], ("data", "DATA-" + str(item["id"]).upper(), "ADR-0051"))
        out.append(check(layer, check_id, SETUP_STATE[state], item.get("label", item["id"]), item.get("message", ""),
                         {"state": state, "rows": list(item.get("rows", []))}, basis))
    return out


def second_solver_check(record: Path | None) -> dict[str, Any]:
    """Whether every value compared with the second solver agrees within the record's tolerance: pass, or warn with how many do not."""
    layer, check_id, basis = SECOND_SOLVER
    label = "Second solver agrees"
    if record is None or not record.is_file():
        return check(layer, check_id, "warn", label, "The second solver's comparison was not written, so this result is not cross-checked.", {}, basis)
    _, rows, data = record_rows(record)
    expected = data["expected"]
    agree, compared = sum(row.agrees for row in rows), len(rows)
    evidence: dict[str, Any] = {"agree": agree, "compared": compared, "tolerance": expected["tolerance"], "floor": expected.get("floor", 0.0)}
    reaction = reaction_row(rows)
    if reaction is not None and reaction[0].reference != 0:
        row, sign = reaction
        evidence["reaction"] = {"ours": sign * row.kernel, "second_solver": sign * row.reference,  # in the load's sense, as the tables print it
                                "difference": sign * (row.kernel - row.reference) / abs(row.reference)}
    percent = f"{100 * expected['tolerance']:g} %"
    if compared and agree == compared:
        return check(layer, check_id, "pass", label, f"All {compared} compared values agree with the second solver within {percent}.", evidence, basis)
    return check(layer, check_id, "warn", label, f"{agree} of {compared} compared values agree with the second solver within {percent}; "
                 "an engineer should look at the others before this result is used.", evidence, basis)


def mesh_check(study: dict[str, Any] | None) -> dict[str, Any]:
    """Whether the answer settles as the mesh is refined: pass when every quantity the study follows moved by less than its limit on the
    last refinement, warn otherwise or when there was no study."""
    layer, check_id, basis = MESH_STUDY
    label = "Mesh converged"
    if study is None:
        return check(layer, check_id, "warn", label, "The mesh study did not run, so the answer's dependence on the mesh is unknown.", {}, basis)
    if not study.get("studied"):
        return check(layer, check_id, "warn", label, f"The mesh was not studied: {study.get('reason', 'no reason given')}.",
                     {"studied": False}, basis)
    settled = {key: bool(value) for key, value in study.get("settled", {}).items()}
    limit = study.get("settled_below")
    evidence = {"studied": True, "settled": settled, "settled_below": limit}
    within = f"{100 * limit:g} %" if isinstance(limit, (int, float)) and math.isfinite(limit) else "its limit"
    moving = [MESH_WORDS.get(key, key.replace("_", " ")) for key, ok in settled.items() if not ok]
    if settled and not moving:
        return check(layer, check_id, "pass", label, f"Every quantity followed changed by less than {within} on the last refinement.", evidence, basis)
    if not settled:
        return check(layer, check_id, "warn", label, "The mesh study gave no quantities to compare.", evidence, basis)
    return check(layer, check_id, "warn", label, "Still changing by more than " + within + " on the last refinement: " + ", ".join(moving) + ".",
                 evidence, basis)


def run_checks(checklist: dict[str, Any] | None, record: Path | None, study: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Every check of a run that reached its result, in the record's order: the setup, the second solver, the mesh."""
    return [*setup_checks(checklist), second_solver_check(record), mesh_check(study)]


def run_verdict(checks: list[dict[str, Any]]) -> str:
    """The run's verdict from its checks alone."""
    verdicts = {c["verdict"] for c in checks}
    if not checks:
        return "unchecked"
    if "block" in verdicts:
        return "blocked"
    if "warn" in verdicts:
        return "needs engineer"
    return "ready"


def qa_record(checks: list[dict[str, Any]]) -> dict[str, Any]:
    """The run's QA file: its checks, their counts and its verdict."""
    counts = {verdict: sum(c["verdict"] == verdict for c in checks) for verdict in VERDICTS}
    return {"version": VERSION, "verdict": run_verdict(checks), "counts": counts, "checks": checks}
