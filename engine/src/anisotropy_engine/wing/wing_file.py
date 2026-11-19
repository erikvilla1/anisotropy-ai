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
"""

import math
import re
import tomllib
from pathlib import Path

from ..lamina import Lamina, Strengths, strain_limits_from_strengths
from ..library import library_core, library_material
from ..units import FOOT, INCH, LBF, POUND_MASS, PSI
from .airfoil import Airfoil, naca4
from .analysis import WingResult
from .description import (
    Aerodynamics, Aileron, CoreMaterial, FlightEnvelope, GustLoadFactors, GustSpeeds, Layup, Speeds, Wing, WingGeometry, WingMaterial,
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


def _material(table: dict, si) -> WingMaterial:
    """A library material by its id, or one typed in full. The library's ply thickness or density may be replaced by a typed one."""
    if "library" in table:
        _keys(table, "[material]", {"library"}, {"dataset", "ply_thickness", "density"})
        record = library_material(table["library"], table.get("dataset"))
        thickness = si(table["ply_thickness"], "thickness") if "ply_thickness" in table else record.ply_thickness_m
        density = si(table["density"], "density") if "density" in table else record.density_kg_per_m3
        if thickness is None:
            raise ValueError(f"[material]: the library record of {table['library']!r} has no ply thickness; give ply_thickness")
        if density is None:
            raise ValueError(f"[material]: the library record of {table['library']!r} has no density; give density")
        if record.lamina.strengths is None:
            raise ValueError(f"[material]: the library record of {table['library']!r} has no complete strengths")
        return WingMaterial(name=record.name, lamina=record.lamina, ply_thickness_m=thickness, density_kg_m3=density)
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


LAYUP_KEYS = {"core_thickness", "core_density", "core", "core_modulus", "core_shear_modulus", "core_shear_strength"}


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


def _layup(table: dict, material: WingMaterial, si, name: str) -> Layup:
    _keys(table, f"[{name}]", {"half_stack"}, LAYUP_KEYS)
    core, density = _core(table, si, name)
    return Layup(material=material, half_stack_deg=tuple(table["half_stack"]),
                 core_thickness_m=si(table.get("core_thickness", 0.0), "thickness"), core_density_kg_m3=density, core=core)


def wing_from_dict(data: dict) -> tuple[Wing, FlightEnvelope]:
    """The wing and its envelope in SI from a wing file's contents."""
    _keys(data, "The wing file", {"title", "units", "geometry", "material", "skin", "spar", "aerodynamics", "envelope"}, {"source", "rib"})
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
        wing = wing.model_copy(update={"skin": wing.skin.model_copy(update={"material": material}),
                                       "spar": wing.spar.model_copy(update={"material": material}),
                                       "rib": None if wing.rib is None else wing.rib.model_copy(update={"material": material})})
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
    governing = result.governing
    return {
        "units": {kind: label for kind, (_, label) in u.items()} | {"speed": speed_unit, "frequency": "Hz", "twist": "deg",
                                                                    "dynamic_pressure": "psi" if units == "US" else "Pa"},
        "wing": result.wing.name,
        "passes": result.passes,
        "seconds": result.seconds,
        "design": {
            "mass": section.mass_kg / u["mass"][0], "mass_skins": section.mass_skins_kg / u["mass"][0],
            "mass_spars": section.mass_spars_kg / u["mass"][0], "mass_core": section.mass_core_kg / u["mass"][0],
            "bending_stiffness": section.EI / u["stiffness"][0], "torsion_stiffness": section.GJ / u["stiffness"][0],
            "first_bending_frequency": section.first_bending_frequency_Hz,
            "skin_modulus": section.skin.Ex / u["modulus"][0], "spar_modulus": section.spar.Ex / u["modulus"][0],
            "skin_shear_modulus": section.skin.Gxy / u["modulus"][0], "spar_shear_modulus": section.spar.Gxy / u["modulus"][0],
            "skin_thickness": section.skin.thickness_m / u["thickness"][0], "spar_thickness": section.spar.thickness_m / u["thickness"][0],
            "skin_buckling_load": section.skin_buckling_load / load, "skin_width": section.skin_width_m / length,
            "spar_heights": [h / length for h in section.spar_heights_m], "shear_center": section.shear_center_m / length,
            "shear_shares": list(section.shear_shares),
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
    }
