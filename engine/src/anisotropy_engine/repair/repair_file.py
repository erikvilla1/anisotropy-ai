"""A stepped patch repair stated as a table (a TOML file or a dict) in a unit system, and what it works out to in the same
units (ADR-0131).

    units = "mm-MPa"                 # or "SI", "US", "psi": the systems of units.py
    [parent]    library = "im7-8552" (with dataset and ply_thickness if wanted), or name, E1, E2, G12, nu12, ply_thickness;
                layup = [...]        # degrees from the load, bottom face first
    [damage]    diameter             # of the deepest cut
    [steps]     count, length, plies (the plies each step removes; 1 unless said)
    [patch]     optional: a material as in [parent], and layup, deepest ply first. Left out, the patch is the laminate's own
                material in the angles of the plies removed
    [cover]     optional: layup (lowest first) and overlap, how far the cover plies reach past the widest cut
    [adhesive]  shear_modulus, thickness, shear_strength (optional), poisson and peel_strength (optional, for the solve),
                peel_energy and shear_energy (optional, to follow the bond until it lets go)
    [panel]     length (along the load), width
    [applied]   optional: load, per unit width, tension positive

The solve of the slice (ADR-0132) needs more than the hand calculation, and a file that leaves these out is still worked by
hand: in a material's table its constants through the thickness, `nu23` alone for a unidirectional ply (E3 = E2,
G13 = G12, nu13 = nu12 and G23 = E2 / (2 (1 + nu23)) follow) or all of `E3`, `G13`, `G23`, `nu13`, `nu23`; and the
adhesive's `poisson`. The adhesive's `peel_strength`, the stress pulling the patch off that the bond can take (the
adhesive's, or the laminate's own strength through its thickness when that is lower), is optional: with it the solve
judges the peel stress, without it the peel stress is reported and not judged. To follow the bond until it lets go
(ADR-0140) the adhesive needs all of `shear_strength`, `poisson`, `peel_strength` and its two fracture energies,
`peel_energy` and `shear_energy`: the energy it takes to part a unit area of the bond by pulling it open and by sliding it,
in the unit system's force per length (N/mm in "mm-MPa", which is kJ/m^2; N/m in "SI", which is J/m^2; lb/in in "US" and
"psi"). A material typed in full may also state its ply strengths, all of `F1t`, `F1c`, `F2t`, `F2c`, `F6`,
for the check of which ply fails first; a library material brings its own. To follow the plies as they damage (ADR-0141) a
material needs its five strengths and, beside them, its four fracture energies, `fibre_tension_energy`,
`fibre_compression_energy`, `matrix_tension_energy` and `matrix_shear_energy`: the energy it takes to part a unit area of
one crack, in the same unit as the adhesive's.

A patch bonded on top over a hole (ADR-0131 amendment 1) says so and states its patch in full:

    kind = "external"                # "flush", the stepped cut above, unless said
    [damage]    diameter             # of the hole
    [steps]     count, length, plies (the patch plies of each step; 1 unless said)
    [patch]     layup (from the ply on the laminate upward), overlap (how far the shortest plies reach past the hole's
                edge) and shape ("round" or "strip", a band across the panel's width); a material as in [parent] when it
                is not the laminate's
    no [cover]

Nothing is guessed: a missing value, an unknown key or an unknown unit system is refused (ADR-0003).
"""

from __future__ import annotations

from ..lamina import Lamina, Strengths
from ..library import library_material
from ..units import UNIT_SYSTEMS
from .description import PATCH_SHAPES, REPAIR_KINDS, PlyEnergies, Repair, RepairError, RepairMaterial, ThroughThickness, tape_through_thickness
from .lap_file import lap_report
from .patch_lap import lap_steps, repair_lap
from .section import areas, bond_lengths, check_regions, regions, volumes
from .step_lap import Adhesive

TABLES = ("parent", "damage", "steps", "patch", "cover", "adhesive", "panel", "applied")
TYPED_MATERIAL = ("name", "E1", "E2", "G12", "nu12", "ply_thickness")
THROUGH = ("E3", "G13", "G23", "nu13", "nu23")  # a ply's constants through the thickness, for the solve of the slice (ADR-0132)
STRENGTHS = ("F1t", "F1c", "F2t", "F2c", "F6")
# a ply's fracture energies, for following the plies as they damage (ADR-0141): the energy to part a unit area of one crack
ENERGIES = ("fibre_tension_energy", "fibre_compression_energy", "matrix_tension_energy", "matrix_shear_energy")


def _keys(table: object, where: str, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(table, dict):
        raise RepairError(f"The repair needs [{where}], a table of values")
    missing = sorted(required - set(table))
    unknown = sorted(set(table) - required - optional)
    if missing:
        raise RepairError(f"[{where}] is missing: {', '.join(missing)}")
    if unknown:
        raise RepairError(f"[{where}] has values a repair does not read: {', '.join(unknown)}")
    return table


def _through(table: dict, where: str, lamina: Lamina, si) -> ThroughThickness | None:
    """A material's constants through the thickness: none stated, `nu23` alone (a unidirectional ply), or all five."""
    stated = [key for key in THROUGH if key in table]
    if not stated:
        return None
    for key in ("nu13", "nu23"):
        if key in table and (isinstance(table[key], bool) or not isinstance(table[key], (int, float))):
            raise RepairError(f"[{where}]: {key} must be a number, got {table[key]!r}")
    try:
        if stated == ["nu23"]:
            return tape_through_thickness(lamina, table["nu23"])
        if len(stated) == len(THROUGH):
            return ThroughThickness(E3=si(table["E3"], "modulus"), G13=si(table["G13"], "modulus"), G23=si(table["G23"], "modulus"),
                                    nu13=table["nu13"], nu23=table["nu23"])
    except RepairError as error:
        raise RepairError(f"[{where}]: {error}") from error
    raise RepairError(f"[{where}]: through the thickness, give nu23 alone (a unidirectional ply) or all of {', '.join(THROUGH)}; "
                      f"the table gives {', '.join(stated)}")


def _energies(table: dict, where: str, si) -> PlyEnergies | None:
    """A ply's four fracture energies when the table states them. All four or none, as the strengths are."""
    stated = [key for key in ENERGIES if key in table]
    if not stated:
        return None
    if len(stated) != len(ENERGIES):
        raise RepairError(f"[{where}]: give all of the ply's fracture energies {', '.join(ENERGIES)} or none; the table gives "
                          f"{', '.join(stated)}")
    try:
        return PlyEnergies(**{key[: -len("_energy")]: si(table[key], "N", "fracture energy") for key in ENERGIES})
    except RepairError as error:
        raise RepairError(f"[{where}]: {error}") from error


def _material(table: dict, where: str, si) -> RepairMaterial:
    """A library material by its id (its ply thickness may be replaced by a typed one), or one typed in full; either with
    its constants through the thickness when the table states them."""
    if "library" in table:
        try:
            record = library_material(table["library"], table.get("dataset"))
        except ValueError as error:
            raise RepairError(f"[{where}]: {error}") from error
        thickness = si(table["ply_thickness"], "length") if "ply_thickness" in table else record.ply_thickness_m
        if thickness is None:
            raise RepairError(f"[{where}]: the library record of {table['library']!r} has no ply thickness; give ply_thickness")
        name, lamina = record.name, record.lamina
    else:
        strengths = [key for key in STRENGTHS if key in table]
        if strengths and len(strengths) != len(STRENGTHS):
            raise RepairError(f"[{where}]: give all of the ply strengths {', '.join(STRENGTHS)} or none; the table gives {', '.join(strengths)}")
        try:
            lamina = Lamina(E1=si(table["E1"], "modulus"), E2=si(table["E2"], "modulus"), G12=si(table["G12"], "modulus"), nu12=table["nu12"],
                            strengths=Strengths(**{key: si(table[key], "stress") for key in STRENGTHS}) if strengths else None)
        except ValueError as error:
            raise RepairError(f"[{where}]: the ply constants E1, E2, G12 and nu12 and the strengths do not make a material: {error}") from error
        name, thickness = table["name"], si(table["ply_thickness"], "length")
    try:
        return RepairMaterial(name, lamina, thickness, _through(table, where, lamina, si), _energies(table, where, si))
    except RepairError as error:
        raise error if str(error).startswith(f"[{where}]") else RepairError(f"[{where}]: {error}") from error


def _material_keys(table: object, where: str, also: set[str], optional: set[str] = frozenset()) -> dict:
    """The keys of a table that names a material: by the library, or typed in full, never half of each."""
    if isinstance(table, dict) and "library" in table:
        return _keys(table, where, {"library"} | also, {"dataset", "ply_thickness"} | set(THROUGH) | set(ENERGIES) | optional)
    return _keys(table, where, set(TYPED_MATERIAL) | also, set(THROUGH) | set(STRENGTHS) | set(ENERGIES) | optional)


def repair_from_dict(data: dict) -> tuple[Repair, float | None]:
    """The repair a table states, and its load per unit width in N/m when one is stated."""
    if not isinstance(data, dict):
        raise RepairError("A repair is a table of values")
    units = data.get("units")
    if units not in UNIT_SYSTEMS:
        raise RepairError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    unknown = sorted(set(data) - set(TABLES) - {"units", "title", "source", "kind"})
    if unknown:
        raise RepairError(f"The repair has tables it does not read: {', '.join(unknown)}")
    system = UNIT_SYSTEMS[units]

    def si(value, quantity, called=None):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RepairError(f"A {called or (quantity if quantity != 'N' else 'load')} must be a number, got {value!r}")
        return value * system[quantity][0]

    parent = _material_keys(data.get("parent"), "parent", {"layup"})
    damage = _keys(data.get("damage"), "damage", {"diameter"})
    steps = _keys(data.get("steps"), "steps", {"count", "length"}, {"plies"})
    stated = _keys(data.get("adhesive"), "adhesive", {"shear_modulus", "thickness"}, {"shear_strength", "poisson", "peel_strength", "peel_energy", "shear_energy"})
    panel = _keys(data.get("panel"), "panel", {"length", "width"})
    try:
        adhesive = Adhesive(si(stated["shear_modulus"], "stress"), si(stated["thickness"], "length"),
                            si(stated["shear_strength"], "stress") if "shear_strength" in stated else None,
                            poisson_ratio=stated.get("poisson"),
                            peel_strength_pa=si(stated["peel_strength"], "stress") if "peel_strength" in stated else None,
                            peel_energy_j_m2=si(stated["peel_energy"], "N", "fracture energy") if "peel_energy" in stated else None,
                            shear_energy_j_m2=si(stated["shear_energy"], "N", "fracture energy") if "shear_energy" in stated else None)
    except ValueError as error:
        raise RepairError(f"[adhesive]: {error}") from error
    kind = data.get("kind", "flush")
    if kind not in REPAIR_KINDS:
        raise RepairError(f"kind must be one of {', '.join(REPAIR_KINDS)}, got {kind!r}")
    patch_material = patch_angles = None
    patch_overlap, patch_shape = 0.0, "round"
    if kind == "external":
        if "cover" in data:
            raise RepairError("An external patch has no [cover]: its longest plies are its first step")
        patch = data.get("patch")
        if not isinstance(patch, dict):
            raise RepairError("An external repair needs [patch]: its layup, overlap and shape")
        own = {"layup", "overlap", "shape"}
        if set(patch) <= own:  # the laminate's material
            _keys(patch, "patch", own)
        else:
            patch_material = _material(_material_keys(patch, "patch", own), "patch", si)
        if patch["shape"] not in PATCH_SHAPES:
            raise RepairError(f"[patch]: shape must be one of {', '.join(PATCH_SHAPES)}, got {patch['shape']!r}")
        patch_angles, patch_overlap, patch_shape = patch["layup"], si(patch["overlap"], "length"), patch["shape"]
    elif "patch" in data:
        patch = data["patch"]
        if isinstance(patch, dict) and set(patch) == {"layup"}:  # the laminate's material in the patch's own angles
            patch_angles = patch["layup"]
        else:
            patch = _material_keys(patch, "patch", set(), {"layup"})
            patch_material, patch_angles = _material(patch, "patch", si), patch.get("layup")
    cover_angles, cover_overlap = (), 0.0
    if "cover" in data:
        cover = _keys(data["cover"], "cover", {"layup", "overlap"})
        cover_angles, cover_overlap = cover["layup"], si(cover["overlap"], "length")
    load = None
    if "applied" in data:
        load = si(_keys(data["applied"], "applied", {"load"})["load"], "N")
    repair = Repair(
        parent_material=_material(parent, "parent", si), parent_angles=parent["layup"], damage_diameter_m=si(damage["diameter"], "length"),
        steps=steps["count"], step_length_m=si(steps["length"], "length"), plies_per_step=steps.get("plies", 1), adhesive=adhesive,
        panel_length_m=si(panel["length"], "length"), panel_width_m=si(panel["width"], "length"), patch_material=patch_material,
        patch_angles=patch_angles, cover_angles=cover_angles, cover_overlap_m=cover_overlap, kind=kind, patch_overlap_m=patch_overlap,
        patch_shape=patch_shape,
    )
    check_regions(repair)
    return repair, load


def repair_report(repair: Repair, units: str, load_n_per_m: float | None = None) -> dict:
    """What the repair works out to, in a unit system: its sizes, every rectangle of the slice, the areas and volumes of
    each kind of part, the bondline's lengths, the steps of its lap and, when a load is given, the lap's answer."""
    if units not in UNIT_SYSTEMS:
        raise RepairError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    system = UNIT_SYSTEMS[units]
    length, modulus = system["length"][0], system["modulus"][0]
    steps, names, continues = lap_steps(repair)
    report = {
        "units": {"length": system["length"][1], "area": f"{system['length'][1]}^2", "volume": f"{system['length'][1]}^3",
                  "modulus": system["modulus"][1], "force": system["N"][1], "stress": system["stress"][1]},
        "kind": repair.kind,
        "patch_shape": repair.patch_shape,
        "sizes": {
            "thickness": repair.thickness_m / length, "patch_thickness": repair.patch_thickness_m / length,
            "depth": repair.depth_m / length, "through": repair.through,
            "plies_removed": repair.plies_removed, "plies_left": repair.plies - repair.plies_removed,
            "cut_radii": [repair.cut_radius_m(step) / length for step in range(1, repair.steps + 1)],
            "patch_diameter": 2 * repair.patch_radius_m / length, "repair_diameter": 2 * repair.cover_radius_m / length,
        },
        "patch_layup": list(repair.patch_angles),
        "regions": [{"kind": r.kind, "name": r.name, "r0": r.r0 / length, "r1": r.r1 / length, "z0": r.z0 / length, "z1": r.z1 / length,
                     "angle": r.angle_deg, "step": r.step} for r in regions(repair)],
        "areas": {kind: value / length**2 for kind, value in areas(repair).items()},
        "volumes": {kind: value / length**3 for kind, value in volumes(repair).items()},
        "bond_lengths": {name: value / length for name, value in bond_lengths(repair).items()},
        "lap": {
            "ends_at_the_middle": continues,
            "steps": [{"name": name, "length": step.length_m / length, "patch_thickness": step.outer_thickness_m / length,
                       "patch_modulus": step.outer_modulus_pa / modulus, "laminate_thickness": step.inner_thickness_m / length,
                       "laminate_modulus": step.inner_modulus_pa / modulus} for name, step in zip(names, steps)],
        },
    }
    if load_n_per_m is not None:
        report["lap"]["load"] = load_n_per_m / system["N"][0]
        report["lap"]["answer"] = lap_report(repair_lap(repair, load_n_per_m), units)
    return report


def repair_views(repair: Repair, units: str, load_n_per_m: float | None = None, points_per_step: int = 41) -> dict:
    """What a page draws beside the slice's rectangles (ADR-0135), in a unit system: the half panel's length, the lap's reach
    from the repair's middle, every step boundary of the lap and, when a load is given, the hand calculation's shear stress
    in the adhesive and the patch's force along the lap. `r` is the distance from the repair's middle, as in the
    rectangles, so the curve runs from the repair's edge inward; each step has `points_per_step` points with both its ends."""
    if units not in UNIT_SYSTEMS:
        raise RepairError(f"units must be one of {', '.join(UNIT_SYSTEMS)}, got {units!r}")
    system = UNIT_SYSTEMS[units]
    length, stress, force = system["length"][0], system["stress"][0], system["N"][0]
    steps, names, _ = lap_steps(repair)
    outer = repair.patch_radius_m if repair.external else repair.cover_radius_m
    boundaries, r = [{"name": "Edge of the repair", "r": outer / length}], outer
    for name, step in zip(names, steps):
        r -= step.length_m
        boundaries.append({"name": name, "r": (r if r > 1e-9 * outer else 0.0) / length})  # the steps' sum ends at the middle but for rounding
    views = {"half_length": repair.panel_length_m / 2 / length, "outer": outer / length, "boundaries": boundaries}
    if load_n_per_m is not None:
        x, shear, patch_force = repair_lap(repair, load_n_per_m).distribution(points_per_step)
        views["lap"] = {"r": [max(float(outer - value), 0.0) / length for value in x], "shear": [float(value) / stress for value in shear],
                        "patch_force": [float(value) / force for value in patch_force]}
    return views


def solve_needs(repair: Repair, load_n_per_m: float | None = None) -> list[dict]:
    """What the solve of the slice (ADR-0132) still needs that the hand calculation does not, each with the place in the
    repair file where it is stated and the need in words, to follow "needs"; empty when the slice can be solved."""
    needs = []

    def through(material: RepairMaterial, table: str, whose: str) -> None:
        if material.through is None:
            needs.append({"path": f"{table}.nu23", "words": f"{whose} constants through the thickness: nu23 for a unidirectional ply, or all of "
                                                            f"{', '.join(THROUGH)}"})

    through(repair.parent_material, "parent", "the laminate ply's")
    if repair.patch_material is not repair.parent_material:
        through(repair.patch_material, "patch", "the patch ply's")
    if repair.adhesive.poisson_ratio is None:
        needs.append({"path": "adhesive.poisson", "words": "the adhesive's Poisson's ratio"})
    if load_n_per_m is None or load_n_per_m == 0:
        needs.append({"path": "applied.load", "words": "a load per unit width that is not zero"})
    return needs


def ply_needs(repair: Repair) -> list[dict]:
    """What following the plies as they damage (ADR-0141) still needs, as `solve_needs` words it; empty when they can be
    followed. It needs what following the bond does, and of every ply material its five strengths and its four fracture
    energies."""
    needs = bond_needs(repair)
    materials = [(repair.parent_material, "parent", "the laminate ply's")]
    if repair.patch_material is not repair.parent_material:
        materials.append((repair.patch_material, "patch", "the patch ply's"))
    for material, table, whose in materials:
        if material.lamina.strengths is None:
            needs.append({"path": f"{table}.F1t", "words": f"{whose} strengths, all of {', '.join(STRENGTHS)}"})
        if material.energies is None:
            needs.append({"path": f"{table}.{ENERGIES[0]}", "words": f"{whose} fracture energies, all of {', '.join(ENERGIES)}"})
    return needs


def bond_needs(repair: Repair) -> list[dict]:
    """What following the bond until it lets go (ADR-0140) still needs, as `solve_needs` words it; empty when it can be
    followed. It needs what the solve of the slice does, but no load (the load is what it finds), and the adhesive's six
    numbers whole: its two strengths and its two fracture energies beside the stiffness."""
    needs = solve_needs(repair, 1.0)
    adhesive = repair.adhesive
    for value, key, words in ((adhesive.shear_strength_pa, "shear_strength", "the adhesive's shear strength"),
                              (adhesive.peel_strength_pa, "peel_strength", "the bond's peel strength"),
                              (adhesive.peel_energy_j_m2, "peel_energy", "the bond's fracture energy in peel"),
                              (adhesive.shear_energy_j_m2, "shear_energy", "the bond's fracture energy in shear")):
        if value is None:
            needs.append({"path": f"adhesive.{key}", "words": words})
    return needs
