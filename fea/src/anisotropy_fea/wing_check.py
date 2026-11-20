"""A wing's finite element check, as a job runs it (ADR-0119): the model of ADR-0117 built from the wing file's description,
solved under the flight loads and for its first modes, and set beside the hand calculation of the same description, every
number in the wing file's own units.

The skins count between the spars only (`skins="box"`), as the hand calculation counts them, so the two answer the same
question; until the description says whether the skin ahead of and behind the box is structure or a fairing, that is the
comparison a person can act on. The checks are read outboard of the root zone (one web height, `wing_model.root_zone`), where
the clamp does not raise the stresses; the root's own values are kept beside them.

    python -m anisotropy_fea.wing_check wing.json --out DIR --result outcome.json --progress progress.json [--mesh 40]

writes DIR/wing-check.json, and, like fea/tools/run_coupon.py, the progress after every stage and the outcome at the end: `done`
with the file, `refused` with the reason when the description cannot be read or modelled, `stopped` with the reason when the
solver fails. A wing file is read as JSON (the page's description) or TOML (a wing file as saved).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from anisotropy_engine.wing import analyze_wing, wing_from_dict
from anisotropy_engine.wing.aeroelastic import divergence_dynamic_pressure, equivalent_airspeed
from anisotropy_engine.wing.analysis import WingResult
from anisotropy_engine.wing.description import FlightEnvelope, Wing
from anisotropy_engine.wing.flutter import TypicalSection
from anisotropy_engine.wing.section import box_section
from anisotropy_engine.wing.wing_file import SPEED_UNITS, WING_UNITS

from .wing_model import (
    MM, FeBuckling, FeCase, FeCheck, FeSection, ModeResults, WingModel, WingModelError, _outboard_ratio, buckling_cases, build_wing_model, fe_cases,
    fe_section, flutter_by_altitude, panel_buckling, root_zone, run_modes, run_wing_model, typical_section,
)
from .wing_shape import ShapeError

STAGES = ("build", "solve", "modes")  # the progress's steps: the model, the flight loads, the modes with flutter and buckling
ELEMENT_SIZE_MM = 40.0  # ADR-0117's mesh study: the example's margins move by less than 0.01 from 40 mm to 20 mm
SKINS = "box"
REPORT = "wing-check.json"
OUTPUT_KEY = "wing_check"  # the key the outcome lists the report under, as a coupon run lists its files


class Unchecked(ValueError):
    """The description cannot be checked: it does not read, cannot be modelled, or states no flight case."""


def _finite(value: float | None, factor: float = 1.0) -> float | None:
    return None if value is None or not math.isfinite(value) else value / factor


@dataclass(frozen=True)
class Solved:
    """A wing's finite element check in SI, before it is reported: the hand calculation, the model's cases, its modes, the wing as
    the beam the model behaves as, and the panel that buckles first under the hardest cases."""

    wing: Wing
    envelope: FlightEnvelope
    hand: WingResult
    model: WingModel
    equations: int | None
    static_seconds: float
    cases: list[FeCase]
    root_zone_m: float
    modes: ModeResults
    section: FeSection
    divergence_eas_m_s: float | None  # the model's divergence speed, equivalent airspeed; None without a lift curve slope
    strip: TypicalSection | None
    buckling: list[FeBuckling]
    seconds: float


def solve_check(wing: Wing, envelope: FlightEnvelope, *, element_size_m: float = ELEMENT_SIZE_MM * MM, workdir: Path | None = None,
                threads: int = 1, on_stage: Callable[[str], None] | None = None) -> Solved:
    """Build the wing's model, solve it under the flight loads and for its first modes, and work the hand calculation beside it.
    Unchecked when the wing cannot be modelled or states no flight case."""
    stage = on_stage or (lambda _: None)
    started = time.monotonic()
    hand = analyze_wing(wing, envelope)
    if not hand.cases:
        raise Unchecked("No flight case can be checked: every case waits for a speed the wing file does not give")
    stage("build")
    try:
        model = build_wing_model(wing, envelope, element_size_m, skins=SKINS)
    except (WingModelError, ShapeError) as error:
        raise Unchecked(str(error)) from error
    stage("solve")
    folder = None if workdir is None else Path(workdir)
    results = run_wing_model(model, folder, threads=threads)
    cases = fe_cases(model, results, box_section(wing).shear_center_m)
    stage("modes")
    modes = run_modes(model, folder, threads=threads)
    section = fe_section(model, results)
    divergence = None
    slope = wing.aerodynamics.lift_curve_slope_per_rad
    if slope is not None:
        arm = section.shear_center_m - wing.aerodynamics.aerodynamic_center * wing.geometry.chord_m
        divergence = equivalent_airspeed(divergence_dynamic_pressure(section.torsion_stiffness, wing.geometry.half_span_m, wing.geometry.chord_m, arm, slope))
    return Solved(wing, envelope, hand, model, results.equations, results.solve_seconds, cases, root_zone(model), modes, section, divergence,
                  typical_section(model, section, modes), panel_buckling(model, results, buckling_cases(model)), time.monotonic() - started)


def check_report(solved: Solved, units: str, speed_unit: str) -> dict:
    """The check as plain numbers in a reporting system (the shape `wing_report` uses): the model, the lowest margins by the model
    and by the hand calculation outboard of the root zone and the model's at the root, every case side by side, the modes, the wing
    as a beam, divergence, flutter and the panel that buckles first."""
    if units not in WING_UNITS or speed_unit not in SPEED_UNITS:
        raise Unchecked(f"units must be one of {tuple(WING_UNITS)} and speed_unit one of {tuple(SPEED_UNITS)}")
    u = WING_UNITS[units]
    length, deflection, altitude, speed = u["length"][0], u["deflection"][0], u["altitude"][0], SPEED_UNITS[speed_unit]
    hand, envelope, zone, ultimate = solved.hand, solved.envelope, solved.root_zone_m, solved.envelope.ultimate_factor
    by_case = {(c.case.number, c.case.altitude_m): c for c in hand.cases}

    def where(case: FeCase, check: FeCheck) -> dict:
        return {"case": case.case.number, "label": case.case.label, "altitude": case.case.altitude_m / altitude, "check": check.name,
                "margin_ultimate": _finite(check.margin_ultimate), "part": check.part, "station": _finite(check.station_m, length),
                "chord": _finite(check.chord_m, length), "ply_angle": check.ply_angle_deg, "mode": check.mode}

    rows, hand_lowest = [], None
    for c in solved.cases:
        h = by_case[(c.case.number, c.case.altitude_m)]
        st = h.stations
        checks = {check.name: check.margin_ultimate for check in c.checks}
        hand_skin = _outboard_ratio(st.y, st.skin_ratio, zone) / ultimate - 1
        hand_spar = _outboard_ratio(st.y, st.spar_ratio, zone) / ultimate - 1
        for name, value in (("skin plies", hand_skin), ("spar plies", hand_spar)):
            if hand_lowest is None or value < hand_lowest["margin_ultimate"]:
                hand_lowest = {"case": c.case.number, "label": c.case.label, "altitude": c.case.altitude_m / altitude, "check": name,
                               "margin_ultimate": value}
        rows.append({
            "number": c.case.number, "label": c.case.label, "altitude": c.case.altitude_m / altitude,
            "tip_deflection": {"hand": h.tip_deflection / deflection, "fe": c.tip_deflection_m / deflection},
            "tip_twist": {"hand": math.degrees(h.tip_twist), "fe": math.degrees(c.tip_twist_rad)},
            "skin": {"hand": _finite(hand_skin), "fe": _finite(checks.get("skin plies"))},
            "spar": {"hand": _finite(hand_spar), "fe": _finite(checks.get("spar plies"))},
            "rib": _finite(checks.get("rib plies")), "core": _finite(checks.get("core shear")),
            "root": {"hand": _finite(min(ch.margin_ultimate for ch in h.checks if ch.name in ("skin plies", "spar plies"))),
                     "fe": _finite(min(ch.margin_ultimate for ch in c.root_checks))},
        })
    worst = min(solved.cases, key=lambda c: c.governing.margin_ultimate)
    at_root = min(solved.cases, key=lambda c: min(ch.margin_ultimate for ch in c.root_checks))
    bending = next((m for m in solved.modes.modes if m.kind == "bending"), None)
    flutter = None
    if solved.strip is not None:
        required = envelope.speeds.flutter
        flutter = {"required": _finite(required, speed), "airspeed": envelope.airspeed, "bending_frequency": solved.strip.bending_frequency_Hz,
                   "torsion_frequency": solved.strip.torsion_frequency_Hz, "altitudes": [
                       {"altitude": at / altitude, "speed": _finite(v, speed), "frequency": _finite(result.frequency_Hz) if math.isfinite(v) else None,
                        "times_required": None if required is None or not math.isfinite(v) else v / required}
                       for at, result, v in flutter_by_altitude(solved.strip, envelope)]}
    buckling = []
    for b in solved.buckling:
        hand_checks = {ch.name: ch for ch in by_case[(b.case.number, b.case.altitude_m)].checks}
        buckling.append({"case": b.case.number, "label": b.case.label, "altitude": b.case.altitude_m / altitude, "part": b.part,
                         "station": b.station_m / length, "factor": b.factor, "margin_ultimate": _finite(b.margin_ultimate),
                         "hand_skin": _finite(hand_checks["skin buckling"].margin_ultimate),
                         "hand_web": _finite(hand_checks["web buckling"].margin_ultimate)})
    section, model = solved.section, solved.model
    return {
        "wing": solved.wing.name,
        "strength_basis": solved.wing.skin.material.strength_basis,  # the strengths both margins use (ADR-0126)
        "units": {kind: u[kind][1] for kind in ("length", "thickness", "deflection", "stiffness", "altitude", "mass")}
        | {"speed": speed_unit, "frequency": "Hz", "twist": "deg", "mass_per_length": f"{u['mass'][1]}/{u['length'][1]}"},
        "model": {"elements": int(model.mesh.elements.shape[0]), "nodes": int(model.mesh.nodes.shape[0]),
                  "element_size": model.element_size_m / u["thickness"][0], "skins": model.skins, "equations": solved.equations},
        "seconds": {"build": round(model.build_seconds, 2), "static": round(solved.static_seconds, 2), "modes": round(solved.modes.solve_seconds, 2),
                    "total": round(solved.seconds, 2)},
        "root_zone": zone / length,
        "lowest": where(worst, worst.governing),
        "lowest_hand": hand_lowest,
        "lowest_root": where(at_root, min(at_root.root_checks, key=lambda ch: ch.margin_ultimate)),
        "cases": rows,
        "not_run": len(hand.not_run),
        "modes": [{"number": m.number, "frequency": m.frequency_Hz, "kind": m.kind, "part": m.part} for m in solved.modes.modes],
        "beam": {"shear_center": {"hand": hand.section.shear_center_m / length, "fe": section.shear_center_m / length},
                 "torsion_stiffness": {"hand": hand.section.GJ / u["stiffness"][0], "fe": section.torsion_stiffness / u["stiffness"][0]},
                 "first_bending_frequency": {"hand": hand.section.first_bending_frequency_Hz, "fe": None if bending is None else bending.frequency_Hz},
                 "mass_per_length": section.mass_per_length_kg_m / (u["mass"][0] / length), "center_of_mass": section.center_of_mass_m / length},
        "divergence_speed": None if solved.divergence_eas_m_s is None else {
            "hand": None if hand.aeroelastic is None else _finite(hand.aeroelastic.divergence_speed_m_s, speed),
            "fe": _finite(solved.divergence_eas_m_s, speed)},
        "flutter": flutter,
        "buckling": buckling,
    }


def check_wing(wing: Wing, envelope: FlightEnvelope, units: str, speed_unit: str, **options) -> dict:
    """`solve_check` reported by `check_report`: the check of one wing in its file's units."""
    if units not in WING_UNITS or speed_unit not in SPEED_UNITS:
        raise Unchecked(f"units must be one of {tuple(WING_UNITS)} and speed_unit one of {tuple(SPEED_UNITS)}")
    return check_report(solve_check(wing, envelope, **options), units, speed_unit)


def headline(report: dict) -> str:
    """The check in one line, for the outcome and the run record."""
    fe, hand = report["lowest"], report["lowest_hand"]
    return (f"Lowest margin outboard of the root {fe['margin_ultimate']:+.3f} by the finite element model, {hand['margin_ultimate']:+.3f} by the "
            f"hand calculation; case {fe['case']} ({fe['label']}), {fe['check']}, {fe['part']}")


def read_description(path: Path) -> dict:
    """A wing file as the engine reads it: JSON (the page's description) or TOML."""
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix.lower() == ".json" else tomllib.loads(text)


def _write(path: Path, payload: dict) -> None:
    """A JSON file written whole: to a neighbour first, then moved into place, so a reader never sees half of it."""
    draft = path.with_name(path.name + ".draft")
    draft.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    os.replace(draft, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m anisotropy_fea.wing_check",
                                     description="Check a wing file with its finite element model, beside its hand calculation (ADR-0119).")
    parser.add_argument("wing_file", type=Path, help="the wing's description: .json, or a .toml wing file")
    parser.add_argument("--out", type=Path, required=True, help="folder for the model's files and wing-check.json")
    parser.add_argument("--result", type=Path, required=True, help="the outcome, written at the end")
    parser.add_argument("--progress", type=Path, required=True, help="the stage, rewritten after every step")
    parser.add_argument("--mesh", type=float, default=ELEMENT_SIZE_MM, help=f"element size in mm (default {ELEMENT_SIZE_MM:g})")
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    done: list[str] = []
    timings: dict[str, float] = {}
    clock = {"stage": None, "at": time.monotonic()}

    def progress(stage: str | None) -> None:
        now = time.monotonic()
        if clock["stage"] is not None:
            done.append(clock["stage"])
            timings[f"{clock['stage']}_s"] = round(now - clock["at"], 1)
        clock.update(stage=stage, at=now)
        _write(args.progress, {"stage": stage, "done": list(done), "stages": list(STAGES), "outputs": {}, "coupon": None, "attempt": None,
                               "timings": dict(timings)})

    def end(status: str, message: str, outputs: dict | None = None) -> int:
        progress(None)
        _write(args.result, {"status": status, "message": message, "result": message if status == "done" else None, "coupon": None,
                             "attempt": None, "outputs": outputs or {}, "documents": None})
        print(f"{status}: {message}", flush=True)
        return 0 if status == "done" else 2

    progress(None)
    try:  # the engine's own reader decides what a wing is, as for the hand calculation (ADR-0118)
        data = read_description(args.wing_file)
        wing, envelope = wing_from_dict(data)
    except (ValueError, TypeError, KeyError, tomllib.TOMLDecodeError) as error:  # JSONDecodeError and pydantic's are ValueErrors
        return end("refused", (str(error).splitlines() or [type(error).__name__])[0])
    try:
        report = check_wing(wing, envelope, data["units"], data["envelope"]["speed_unit"], element_size_m=args.mesh * MM,
                            workdir=args.out, threads=args.threads, on_stage=progress)
    except Unchecked as error:
        return end("refused", str(error))
    except Exception as error:  # the solver, the disk or a fault of ours: the job ends with the cause, which stays in its log and row
        return end("stopped", f"The finite element model could not be solved: {(str(error).splitlines() or [type(error).__name__])[0]}")
    report_path = args.out / REPORT
    _write(report_path, report)
    return end("done", headline(report), {OUTPUT_KEY: str(report_path.resolve())})


if __name__ == "__main__":
    raise SystemExit(main())
