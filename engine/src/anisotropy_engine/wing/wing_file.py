"""A wing as a file: the description and the envelope in the units an engineer works in, and the results back in them.

The engine works in SI (ADR-0002). A wing file states `units`, "SI" or "US", and every value in it
is converted here on the way in; `wing_report` converts the results on the way out. Speeds carry
their own unit, `speed_unit`, because airplanes are flown in several. No value is guessed: a table
or a key the format does not know is refused by name.

| quantity | SI | US |
| --- | --- | --- |
| span, chord, rib spacing, aileron stations, deflection | m | in |
| ply and core thickness | mm | in |
| weight, shear | N | lb |
| moduli / strengths | GPa / MPa | Msi / ksi |
| density | kg/m^3 | lb/in^3 |
| altitude | m | ft |
| speeds | `speed_unit`: m/s, km/h, kt, mph or ft/s | the same |
| moment, torque | N*m | lb*in |
| running load, shear flow | N/m | lb/in |
| bending and torsion stiffness | N*m^2 | lb*in^2 |
| mass | kg | lb |
| spar cap widths | m | in |
| a zone's start and end | a fraction of the half span from the root | the same |
| design rules: least share of each direction, most plies of one angle in a row | % and a count | the same |
| design rules: ply drop ratio, most plies ending at one place | run-out per thickness dropped, and a count | the same |
"""

import dataclasses
import math
import re
import tomllib
from pathlib import Path

import numpy as np

from ..lamina import Lamina, Strengths, strain_limits_from_strengths
from ..layup_rules import RuleLimits, ply_drop_rules
from ..library import library_core, library_material, strength_dataset
from ..units import FOOT, INCH, LBF, POUND_MASS, PSI
from .airfoil import Airfoil, naca4
from .analysis import WingResult
from .description import (
    Aerodynamics, Aileron, CoreMaterial, FlightEnvelope, GustLoadFactors, GustSpeeds, Layup, SparCaps, Speeds, StrengthSource, Wing,
    WingGeometry, WingMaterial, Zone,
)

KNOT = 1852 / 3600  # m/s, exact
SPEED_UNITS = {"m/s": 1.0, "km/h": 1 / 3.6, "kt": KNOT, "mph": 5280 * FOOT / 3600, "ft/s": FOOT}
WING_UNITS = {
    "SI": {"length": (1.0, "m"), "thickness": (1e-3, "mm"), "force": (1.0, "N"), "modulus": (1e9, "GPa"), "stress": (1e6, "MPa"),
           "density": (1.0, "kg/m^3"), "altitude": (1.0, "m"), "moment": (1.0, "N*m"), "running_load": (1.0, "N/m"),
           "stiffness": (1.0, "N*m^2"), "mass": (1.0, "kg"), "deflection": (1e-3, "mm")},
    "US": {"length": (INCH, "in"), "thickness": (INCH, "in"), "force": (LBF, "lb"), "modulus": (1e6 * PSI, "Msi"), "stress": (1e3 * PSI, "ksi"),
           "density": (POUND_MASS / INCH**3, "lb/in^3"), "altitude": (FOOT, "ft"), "moment": (LBF * INCH, "lb*in"),
           "running_load": (LBF / INCH, "lb/in"), "stiffness": (LBF * INCH**2, "lb*in^2"), "mass": (POUND_MASS, "lb"),
           "deflection": (INCH, "in")},
}
STRENGTHS = ("F1t", "F1c", "F2t", "F2c", "F6")


def _table(data: dict, name: str, required: set[str], optional: set[str] = frozenset()) -> dict:
    """A table of the file with exactly the keys the format knows."""
    if name not in data:
        raise ValueError(f"The wing file needs [{name}]")
    table = data[name]
    if not isinstance(table, dict):
        raise ValueError(f"[{name}] must be a table")
    _keys(table, f"[{name}]", required, optional)
    return table


def _keys(table: dict, where: str, required: set[str], optional: set[str] = frozenset()) -> None:
    missing = sorted(required - set(table))
    unknown = sorted(set(table) - required - optional)
    if missing:
        raise ValueError(f"{where} is missing {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{where} has unknown keys {', '.join(unknown)}")


STRENGTH_BASES = ("mean", "B-basis")


def _material(table: dict, si) -> WingMaterial:
    """A library material by its id, or one typed in full. The library's ply thickness or density may be replaced by a typed one.

    `strengths = "B-basis"` takes the strengths from the material's B-basis dataset and everything else from its means (ADR-0126);
    `"mean"`, the default, takes them from the dataset named, or the material's primary one."""
    if "library" in table:
        _keys(table, "[material]", {"library"}, {"dataset", "strengths", "ply_thickness", "density"})
        basis = table.get("strengths", "mean")
        if basis not in STRENGTH_BASES:
            raise ValueError(f'[material] strengths must be "mean" or "B-basis", not {basis!r}')
        if basis != "mean" and "dataset" in table:
            raise ValueError("[material]: give dataset or strengths, not both: the B-basis strengths have a dataset of their own")
        record = library_material(table["library"], table.get("dataset"))
        thickness = si(table["ply_thickness"], "thickness") if "ply_thickness" in table else record.ply_thickness_m
        density = si(table["density"], "density") if "density" in table else record.density_kg_per_m3
        if thickness is None:
            raise ValueError(f"[material]: the library record of {table['library']!r} has no ply thickness; give ply_thickness")
        if density is None:
            raise ValueError(f"[material]: the library record of {table['library']!r} has no density; give density")
        strengths = record if basis == "mean" else library_material(table["library"], strength_dataset(table["library"], basis))
        if strengths.lamina.strengths is None:
            raise ValueError(f"[material]: the library record of {table['library']!r} has no complete strengths")
        sources = tuple(StrengthSource(role=v.role, key=v.key, basis=v.basis, source_value=v.source_value, source_unit=v.source_unit,
                                       page=v.page, url=v.reference_url) for v in strengths.values if v.role in STRENGTHS)
        return WingMaterial(name=record.name, lamina=record.lamina.model_copy(update={"strengths": strengths.lamina.strengths}),
                            ply_thickness_m=thickness, density_kg_m3=density, strength_basis=basis, strength_dataset=strengths.dataset,
                            strength_citation=strengths.citation, strength_sources=sources)
    _keys(table, "[material]", {"name", "E1", "E2", "G12", "nu12", *STRENGTHS, "ply_thickness", "density"})
    lamina = Lamina(E1=si(table["E1"], "modulus"), E2=si(table["E2"], "modulus"), G12=si(table["G12"], "modulus"), nu12=table["nu12"],
                    strengths=Strengths(**{name: si(table[name], "stress") for name in STRENGTHS}))
    return WingMaterial(name=table["name"], lamina=lamina, ply_thickness_m=si(table["ply_thickness"], "thickness"),
                        density_kg_m3=si(table["density"], "density"))


def _airfoil(value) -> Airfoil:
    if isinstance(value, str):
        match = re.fullmatch(r"naca[- ]?(\d{4})", value.strip().lower())
        if not match:
            raise ValueError(f"[geometry] airfoil {value!r}: name a NACA four-digit airfoil such as \"naca-2412\", "
                             "or give a table with name, upper and lower points")
        return naca4(match.group(1))
    if not isinstance(value, dict):
        raise ValueError("[geometry] airfoil must be a name or a table")
    _keys(value, "[geometry.airfoil]", {"name", "upper", "lower"})
    return Airfoil(name=value["name"], upper=tuple(tuple(point) for point in value["upper"]),
                   lower=tuple(tuple(point) for point in value["lower"]))


LAYUP_KEYS = {"core_thickness", "core_density", "core", "core_modulus", "core_shear_modulus", "core_shear_strength", "zones"}


def _core(table: dict, si, name: str) -> tuple[CoreMaterial | None, float | None]:
    """The core's stiffness, from the library by its id or typed (moduli and strength in the stress unit), and its density."""
    typed = [key for key in ("core_modulus", "core_shear_modulus", "core_shear_strength") if key in table]
    density = si(table["core_density"], "density") if "core_density" in table else None
    if "core" in table:
        if typed or density is not None:
            raise ValueError(f"[{name}]: core names a library core, which gives its stiffness and density; "
                             f"remove {', '.join(typed + (['core_density'] if density is not None else []))} or the core")
        record = library_core(table["core"])
        return (CoreMaterial(name=record.name, modulus_Pa=record.modulus_Pa, shear_modulus_Pa=record.shear_modulus_Pa,
                             shear_strength_Pa=record.shear_strength_Pa), record.density_kg_m3)
    if not typed:
        return None, density
    if "core_modulus" not in table or "core_shear_modulus" not in table:
        raise ValueError(f"[{name}]: a typed core needs both core_modulus and core_shear_modulus")
    return (CoreMaterial(name=f"{name} core", modulus_Pa=si(table["core_modulus"], "stress"),
                         shear_modulus_Pa=si(table["core_shear_modulus"], "stress"),
                         shear_strength_Pa=si(table["core_shear_strength"], "stress") if "core_shear_strength" in table else None), density)


def _zones(value, name: str) -> tuple[Zone, ...]:
    """[[<part>.zones]]: each a stretch of the half span, start and end as fractions of it, with its own half stack (ADR-0125)."""
    if not isinstance(value, list) or not all(isinstance(zone, dict) for zone in value):
        raise ValueError(f"[{name}] zones must be a list of tables, each with start, end and half_stack")
    zones = []
    for k, zone in enumerate(value, start=1):
        _keys(zone, f"[{name}] zone {k}", {"start", "end", "half_stack"})
        for key in ("start", "end"):
            if isinstance(zone[key], bool) or not isinstance(zone[key], (int, float)):
                raise ValueError(f"[{name}] zone {k}: {key} is a fraction of the half span, a number from 0 to 1")
        zones.append(Zone(start=zone["start"], end=zone["end"], half_stack_deg=tuple(zone["half_stack"])))
    return tuple(zones)


def _layup(table: dict, material: WingMaterial, si, name: str) -> Layup:
    _keys(table, f"[{name}]", {"half_stack"}, LAYUP_KEYS)
    core, density = _core(table, si, name)
    return Layup(material=material, half_stack_deg=tuple(table["half_stack"]),
                 core_thickness_m=si(table.get("core_thickness", 0.0), "thickness"), core_density_kg_m3=density, core=core,
                 zones=_zones(table["zones"], name) if "zones" in table else ())


def _spar_caps(table: dict, material: WingMaterial, si) -> SparCaps:
    """[spar_caps]: a strip of each skin centred on each web, its width per spar and its own half stack, solid (ADR-0125)."""
    _keys(table, "[spar_caps]", {"front_width", "rear_width", "half_stack"}, {"zones"})
    layup = Layup(material=material, half_stack_deg=tuple(table["half_stack"]),
                  zones=_zones(table["zones"], "spar_caps") if "zones" in table else ())
    return SparCaps(front_width_m=si(table["front_width"], "length"), rear_width_m=si(table["rear_width"], "length"), layup=layup)


def _design_rules(table: dict) -> RuleLimits:
    """[design_rules]: the limits the layups are judged by (ADR-0123, ADR-0125), each optional, the share in percent."""
    limits = {}
    if "min_percent" in table:
        value = table["min_percent"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 25:
            raise ValueError("[design_rules] min_percent is the least share of each of 0, +45, -45 and 90 degrees, above 0 and at most 25 %")
        limits["min_share"] = value / 100
    if "max_in_a_row" in table:
        value = table["max_in_a_row"]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("[design_rules] max_in_a_row is the most plies of one angle next to each other, a whole number of at least 1")
        limits["max_in_a_row"] = value
    if "drop_ratio" in table:
        value = table["drop_ratio"]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 1 <= value <= 200:
            raise ValueError("[design_rules] drop_ratio is the run-out of a ply drop per unit of the thickness it drops, from 1 to 200")
        limits["drop_ratio"] = float(value)
    if "max_dropped" in table:
        value = table["max_dropped"]
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("[design_rules] max_dropped is the most plies that end at one place, both halves counted, a whole number of at least 1")
        limits["max_dropped"] = value
    return RuleLimits(**limits)


def wing_from_dict(data: dict) -> tuple[Wing, FlightEnvelope]:
    """The wing and its envelope in SI from a wing file's contents."""
    _keys(data, "The wing file", {"title", "units", "geometry", "material", "skin", "spar", "aerodynamics", "envelope"},
          {"source", "rib", "design_rules", "spar_caps"})
    if data["units"] not in WING_UNITS:
        raise ValueError(f"units must be one of {tuple(WING_UNITS)}")
    system = WING_UNITS[data["units"]]

    def si(value, kind: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Expected a number, got {value!r}")
        return float(value) * system[kind][0]

    geometry = _table(data, "geometry", {"half_span", "chord", "airfoil", "front_spar", "rear_spar"}, {"rib_spacing"})
    if not isinstance(data["material"], dict):
        raise ValueError("[material] must be a table")
    material = _material(data["material"], si)
    aero = _table(data, "aerodynamics", {"aerodynamic_center", "pitching_moment_coefficient"}, {"lift_curve_slope"})
    wing = Wing(
        name=data["title"],
        geometry=WingGeometry(half_span_m=si(geometry["half_span"], "length"), chord_m=si(geometry["chord"], "length"),
                              airfoil=_airfoil(geometry["airfoil"]), front_spar=geometry["front_spar"], rear_spar=geometry["rear_spar"],
                              rib_spacing_m=si(geometry["rib_spacing"], "length") if "rib_spacing" in geometry else None),
        skin=_layup(_table(data, "skin", {"half_stack"}, LAYUP_KEYS), material, si, "skin"),
        spar=_layup(_table(data, "spar", {"half_stack"}, LAYUP_KEYS), material, si, "spar"),
        aerodynamics=Aerodynamics(aerodynamic_center=aero["aerodynamic_center"],
                                  pitching_moment_coefficient=aero["pitching_moment_coefficient"],
                                  lift_curve_slope_per_rad=aero.get("lift_curve_slope")),
        rib=_layup(_table(data, "rib", {"half_stack"}, LAYUP_KEYS), material, si, "rib") if "rib" in data else None,
        design_rules=_design_rules(_table(data, "design_rules", set(), {"min_percent", "max_in_a_row", "drop_ratio", "max_dropped"}))
        if "design_rules" in data else RuleLimits(),
        spar_caps=_spar_caps(_table(data, "spar_caps", {"front_width", "rear_width", "half_stack"}, {"zones"}), material, si)
        if "spar_caps" in data else None,
    )

    env = _table(data, "envelope", {"gross_weight", "positive_load_factor", "negative_load_factor", "airspeed", "speed_unit", "altitudes",
                                    "ultimate_factor", "criterion"}, {"proof_factor", "f12_star", "strain_limits", "speeds", "gust", "aileron"})
    if env["speed_unit"] not in SPEED_UNITS:
        raise ValueError(f"[envelope] speed_unit must be one of {tuple(SPEED_UNITS)}")
    speed = SPEED_UNITS[env["speed_unit"]]
    speeds_table = env.get("speeds", {})
    _keys(speeds_table, "[envelope.speeds]", set(), set(Speeds.model_fields))
    gust = None
    if "gust" in env:
        table = env["gust"]
        if "cruise_gust_speed" in table or "dive_gust_speed" in table:
            _keys(table, "[envelope.gust]", {"cruise_gust_speed", "dive_gust_speed", "lift_curve_slope_per_rad", "wing_area"})
            gust = GustSpeeds(cruise_gust_speed_m_s=table["cruise_gust_speed"] * speed, dive_gust_speed_m_s=table["dive_gust_speed"] * speed,
                              lift_curve_slope_per_rad=table["lift_curve_slope_per_rad"],
                              wing_area_m2=table["wing_area"] * system["length"][0] ** 2)
        else:
            _keys(table, "[envelope.gust]", set(GustLoadFactors.model_fields))
            gust = GustLoadFactors(**table)
    aileron = None
    if "aileron" in env:
        table = env["aileron"]
        _keys(table, "[envelope.aileron]", {"span_start", "span_end", "down_delta_cl", "down_delta_cm", "up_delta_cl", "up_delta_cm",
                                            "roll_pull_up_fraction"})
        aileron = Aileron(span_start_m=si(table["span_start"], "length"), span_end_m=si(table["span_end"], "length"),
                          **{key: table[key] for key in ("down_delta_cl", "down_delta_cm", "up_delta_cl", "up_delta_cm", "roll_pull_up_fraction")})
    if "strain_limits" in env:
        if env["strain_limits"] != "from-strengths":
            raise ValueError('[envelope] strain_limits may only be "from-strengths"')
        lamina = material.lamina.model_copy(update={"strain_limits": strain_limits_from_strengths(material.lamina)})
        material = material.model_copy(update={"lamina": lamina})
        caps = wing.spar_caps
        wing = wing.model_copy(update={"skin": wing.skin.model_copy(update={"material": material}),
                                       "spar": wing.spar.model_copy(update={"material": material}),
                                       "rib": None if wing.rib is None else wing.rib.model_copy(update={"material": material}),
                                       "spar_caps": None if caps is None else caps.model_copy(
                                           update={"layup": caps.layup.model_copy(update={"material": material})})})
    envelope = FlightEnvelope(
        gross_weight_N=si(env["gross_weight"], "force"), positive_load_factor=env["positive_load_factor"],
        negative_load_factor=env["negative_load_factor"], airspeed=env["airspeed"],
        speeds=Speeds(**{name: value * speed for name, value in speeds_table.items()}),
        altitudes_m=tuple(si(altitude, "altitude") for altitude in env["altitudes"]),
        ultimate_factor=env["ultimate_factor"], proof_factor=env.get("proof_factor"), criterion=env["criterion"],
        f12_star=env.get("f12_star"), gust=gust, aileron=aileron)
    return wing, envelope


def load_wing(path: Path) -> tuple[dict, Wing, FlightEnvelope]:
    """Read a wing file (TOML): its contents as written, and the wing and envelope in SI."""
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    wing, envelope = wing_from_dict(data)
    return data, wing, envelope


def _number(value: float | None, factor: float = 1.0):
    """A result as a plain number in its reporting unit; infinity (an unloaded check) is reported as None."""
    if value is None or not math.isfinite(value):
        return None
    return value / factor


def wing_report(result: WingResult, units: str, speed_unit: str) -> dict:
    """The results as plain numbers in a reporting system: what a page, a table or a file shows."""
    if units not in WING_UNITS:
        raise ValueError(f"units must be one of {tuple(WING_UNITS)}")
    if speed_unit not in SPEED_UNITS:
        raise ValueError(f"speed_unit must be one of {tuple(SPEED_UNITS)}")
    u = WING_UNITS[units]
    section = result.section
    length, force, moment, load = u["length"][0], u["force"][0], u["moment"][0], u["running_load"][0]
    mass = u["mass"][0]
    governing = result.governing
    return {
        "units": {kind: label for kind, (_, label) in u.items()} | {"speed": speed_unit, "frequency": "Hz", "twist": "deg",
                                                                    "dynamic_pressure": "psi" if units == "US" else "Pa"},
        "wing": result.wing.name,
        "material": wing_material(result.wing.skin.material, units),
        "passes": result.passes,
        "seconds": result.seconds,
        "design": {
            "mass": result.mass_kg() / mass, "mass_skins": result.mass_kg("skins") / mass, "mass_caps": result.mass_kg("caps") / mass,
            "mass_spars": result.mass_kg("spars") / mass, "mass_core": result.mass_kg("core") / mass,
            "bending_stiffness": section.EI / u["stiffness"][0], "torsion_stiffness": section.GJ / u["stiffness"][0],
            "first_bending_frequency": result.first_bending_frequency_Hz,
            "skin_modulus": section.skin.Ex / u["modulus"][0], "spar_modulus": section.spar.Ex / u["modulus"][0],
            "skin_shear_modulus": section.skin.Gxy / u["modulus"][0], "spar_shear_modulus": section.spar.Gxy / u["modulus"][0],
            "skin_thickness": section.skin.thickness_m / u["thickness"][0], "spar_thickness": section.spar.thickness_m / u["thickness"][0],
            "skin_buckling_load": section.skin_buckling_load / load, "skin_widths": [w / length for w in section.skin_widths_m],
            "spar_heights": [h / length for h in section.spar_heights_m], "shear_center": section.shear_center_m / length,
            "shear_shares": list(section.shear_shares), "centroid": [section.centroid_x_m / length, section.centroid_m / length],
            "enclosed_area": section.enclosed_area_m2 / length**2,
            "cap_modulus": None if section.cap is None else section.cap.Ex / u["modulus"][0],
            "cap_thickness": None if section.cap is None else section.cap.thickness_m / u["thickness"][0],
            # root to tip, a stretch wherever a layup changes (ADR-0125); the values above are the root's
            "stretches": [{"start": s.segment.start_m / length, "end": s.segment.end_m / length,
                           "bending_stiffness": s.section.EI / u["stiffness"][0], "torsion_stiffness": s.section.GJ / u["stiffness"][0],
                           "shear_center": s.section.shear_center_m / length,
                           "mass_per_length": s.section.mass_per_length_kg_m / (mass / length)} for s in result.stretches],
        },
        "governing": None if governing is None else {
            "case": governing[0].case.number, "label": governing[0].case.label,
            "altitude": governing[0].case.altitude_m / u["altitude"][0], "check": governing[1].name,
            "margin_ultimate": _number(governing[1].margin_ultimate)},
        "cases": [{
            "number": r.case.number, "label": r.case.label, "group": r.case.group, "altitude": r.case.altitude_m / u["altitude"][0],
            "speed": r.case.speed_m_s / SPEED_UNITS[speed_unit], "load_factor": r.case.load_factor, "aileron": r.case.aileron,
            "dynamic_pressure": r.case.dynamic_pressure_Pa / (PSI if units == "US" else 1.0),
            "root_shear": r.root_shear / force, "root_moment": r.root_moment / moment, "root_torque": r.root_torque / moment,
            "tip_deflection": r.tip_deflection / u["deflection"][0], "tip_twist": math.degrees(r.tip_twist),
            "checks": {check.name: {
                "strength_ratio": _number(check.strength_ratio), "margin_ultimate": _number(check.margin_ultimate),
                "margin_proof": _number(check.margin_proof),
                "station": _number(check.station_m, length), "member": check.member, "ply_angle": check.ply_angle_deg, "mode": check.mode,
                "point": None if check.point_m is None else [v / length for v in check.point_m],
            } for check in r.checks},
        } for r in result.cases],
        "aeroelastic": None if result.aeroelastic is None else {
            "divergence_speed": _number(result.aeroelastic.divergence_speed_m_s, SPEED_UNITS[speed_unit]),
            "divergence_dynamic_pressure": _number(result.aeroelastic.divergence_dynamic_pressure_Pa, PSI if units == "US" else 1.0),
            "reversal_speed": _number(result.aeroelastic.reversal_speed_m_s, SPEED_UNITS[speed_unit]),
            "reversal_dynamic_pressure": _number(result.aeroelastic.reversal_dynamic_pressure_Pa, PSI if units == "US" else 1.0),
            "dive_speed": _number(result.aeroelastic.dive_speed_m_s, SPEED_UNITS[speed_unit]),
            "divergence_over_dive": _number(result.aeroelastic.divergence_over_dive),
            "reversal_over_dive": _number(result.aeroelastic.reversal_over_dive),
            # a check that ran and found no speed at all: the wing never diverges, or the aileron never reverses before it does
            "divergence_never": result.aeroelastic.divergence_speed_m_s == math.inf,
            "reversal_never": result.aeroelastic.reversal_speed_m_s == math.inf,
            "needs": list(result.aeroelastic.needs)},
        "not_run": [{"number": n.number, "label": n.label, "altitude": n.altitude_m / u["altitude"][0], "needs": n.needs} for n in result.not_run],
        "rule_limits": {"min_percent": 100 * result.wing.design_rules.min_share, "max_in_a_row": result.wing.design_rules.max_in_a_row,
                        "drop_ratio": result.wing.design_rules.drop_ratio, "max_dropped": result.wing.design_rules.max_dropped},
        "rules": wing_rules(result.wing, units),
    }


def wing_material(material: WingMaterial, units: str = "SI") -> dict:
    """The ply material as a page shows it: its name, the basis of the strengths the margins use (ADR-0126), and each strength in the
    file's stress unit with its basis, page and link. "estimates" names the strengths whose basis is a B-estimate."""
    stress = WING_UNITS[units]["stress"][0]
    strengths = material.lamina.strengths
    by_role = {source.role: source for source in material.strength_sources}
    rows = [{"role": role, "value": getattr(strengths, role) / stress,
             **({} if role not in by_role else {"basis": by_role[role].basis, "key": by_role[role].key, "page": by_role[role].page,
                                                 "url": by_role[role].url, "source_value": by_role[role].source_value,
                                                 "source_unit": by_role[role].source_unit})}
            for role in STRENGTHS]
    return {"name": material.name, "strength_basis": material.strength_basis, "dataset": material.strength_dataset,
            "source": material.strength_citation, "strengths": rows,
            "estimates": [row["role"] for row in rows if row.get("basis") == "B-estimate"]}


def _percent_of_span(fraction: float) -> str:
    return f"{100 * fraction:.1f}".rstrip("0").rstrip(".") + " % of the span"


def wing_rules(wing: Wing, units: str = "SI") -> list[dict]:
    """The design rules of every layup of the wing (ADR-0123), skins, spar webs, spar caps and ribs, as plain values: a warning each,
    never a margin. A part whose layup changes along the span is judged on each stretch, `span` from its start to its end as
    fractions of the half span, and at each change, `at` (ADR-0125), with its run-out in the file's thickness unit."""
    limits, unit = wing.design_rules, WING_UNITS[units]["thickness"]
    members = (("skin", wing.skin), ("spar", wing.spar), ("cap", None if wing.spar_caps is None else wing.spar_caps.layup), ("rib", wing.rib))
    rules = []
    for part, layup in members:
        if layup is None:
            continue
        stretches = layup.stretches()
        for start, end, uniform in stretches:
            rules += [{"part": part, "span": [start, end], "at": None, **dataclasses.asdict(check)} for check in uniform.rules(limits)]
        L = wing.geometry.half_span_m
        for (start, edge, inboard), (_, end, outboard) in zip(stretches, stretches[1:]):
            checks = ply_drop_rules(inboard.half_stack_deg, outboard.half_stack_deg, layup.material.ply_thickness_m,
                                    ((edge - start) * L, (end - edge) * L), _percent_of_span(edge), limits, unit)
            rules += [{"part": part, "span": None, "at": edge, **dataclasses.asdict(check)} for check in checks]
    return rules


VIEW_DIGITS = 4  # significant digits of what a page draws; the numbers it states come from wing_report in full
AIRFOIL_POINTS = 61


def _drawn(values) -> list:
    """Values to draw, to VIEW_DIGITS significant digits; infinity and NaN (an unloaded check) as None."""
    return [None if not math.isfinite(v) else float(f"{v:.{VIEW_DIGITS}g}") for v in np.asarray(values, dtype=float).ravel()]


def _cap_points(section) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Each cap's mid-surface across its web, both halves, fore to aft: (name, x, z)."""
    found = []
    for name in ("upper front spar cap", "lower front spar cap", "upper rear spar cap", "lower rear spar cap"):
        halves = [s for s in section.point_sets if s.label == name]
        if halves:
            x, z = np.concatenate([h.x_m for h in halves]), np.concatenate([h.z_m for h in halves])
            order = np.argsort(x, kind="stable")
            x, z = x[order], z[order]
            keep = np.r_[True, np.diff(x) > 0]  # the point over the web is in both halves
            found.append((name, x[keep], z[keep]))
    return found


def wing_views(result: WingResult, units: str) -> dict:
    """What a page draws of a worked wing, in a reporting system: the airfoil at the root and the box's walls where the hand
    calculation puts them, the spars, the ribs, the shear center and the centroid; for every case, the lowest margin at ultimate
    load of each check along the span, the deflection and twist along it, and the spanwise load and shear flow at every point of
    the walls at the root. Every value is the engine's, rounded to VIEW_DIGITS significant digits for drawing; the numbers a page
    states come from `wing_report`."""
    if units not in WING_UNITS:
        raise ValueError(f"units must be one of {tuple(WING_UNITS)}")
    u = WING_UNITS[units]
    length, load, deflection = u["length"][0], u["running_load"][0], u["deflection"][0]
    wing, section, envelope = result.wing, result.section, result.envelope
    g = wing.geometry
    chord = g.chord_m
    x = (1 - np.cos(np.linspace(0.0, math.pi, AIRFOIL_POINTS))) / 2  # closer at the leading edge, where the outline turns
    heights = np.array([g.airfoil.surface_heights(float(xi)) for xi in x])
    walls = [(name, points, k) for name, points, k in (("upper skin", section.skins, 0), ("lower skin", section.skins, 1),
                                                         ("front web", section.webs, 0), ("rear web", section.webs, 1))]

    def margins(ratio: np.ndarray) -> list:
        return _drawn(ratio / envelope.ultimate_factor - 1)

    cases = []
    for r in result.cases:
        s = r.stations
        moment, shear, torque_flow = float(s.moment[0]), float(s.shear[0]), float(s.shear_flow[0])
        cases.append({
            "number": r.case.number, "altitude": r.case.altitude_m / u["altitude"][0],
            "margins": {"skin plies": margins(s.skin_ratio.min(axis=0)), "spar plies": margins(s.spar_ratio.min(axis=0)),
                        "skin buckling": margins(s.buckling_ratio), "web buckling": margins(s.web_buckling_ratio.min(axis=0))},
            "deflection": _drawn(s.deflection / deflection), "twist": _drawn(np.degrees(s.twist)),
            "root": [{"name": name, "load": _drawn(points.load_per_moment[k] * moment / load),
                      "shear_flow": _drawn((points.flow_per_shear[k] * shear + torque_flow) / load)} for name, points, k in walls],
        })
    return {
        "half_span": g.half_span_m / length, "chord": chord / length,
        "airfoil": {"name": g.airfoil.name, "x": _drawn(x * chord / length), "upper": _drawn(heights[:, 0] * chord / length),
                    "lower": _drawn(heights[:, 1] * chord / length)},
        "walls": [{"name": name, "x": _drawn(points.x_m[k] / length), "z": _drawn(points.z_m[k] / length)} for name, points, k in walls],
        "spars": [v / length for v in section.spar_x_m], "spar_heights": [v / length for v in section.spar_heights_m],
        "shear_center": section.shear_center_m / length, "centroid": [section.centroid_x_m / length, section.centroid_m / length],
        "ribs": [v / length for v in g.rib_stations_m],
        # each spar cap at the root, upper and lower, both halves, as the root's section puts it (ADR-0125)
        "caps": [{"name": name, "x": _drawn(x / length), "z": _drawn(z / length)} for name, x, z in _cap_points(section)],
        "changes": [s.segment.end_m / length for s in result.stretches[:-1]],  # where a layup changes along the span
        "stations": _drawn(result.cases[0].stations.y / length) if result.cases else [],
        "cases": cases,
    }
