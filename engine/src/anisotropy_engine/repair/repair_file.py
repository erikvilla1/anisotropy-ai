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
    [adhesive]  shear_modulus, thickness, shear_strength (optional)
    [panel]     length (along the load), width
    [applied]   optional: load, per unit width, tension positive

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

from ..lamina import Lamina
from ..library import library_material
from ..units import UNIT_SYSTEMS
from .description import PATCH_SHAPES, REPAIR_KINDS, Repair, RepairError, RepairMaterial
from .lap_file import lap_report
from .patch_lap import lap_steps, repair_lap
from .section import areas, bond_lengths, check_regions, regions, volumes
from .step_lap import Adhesive

TABLES = ("parent", "damage", "steps", "patch", "cover", "adhesive", "panel", "applied")
TYPED_MATERIAL = ("name", "E1", "E2", "G12", "nu12", "ply_thickness")


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


def _material(table: dict, where: str, si) -> RepairMaterial:
    """A library material by its id (its ply thickness may be replaced by a typed one), or one typed in full."""
    if "library" in table:
        try:
            record = library_material(table["library"], table.get("dataset"))
        except ValueError as error:
            raise RepairError(f"[{where}]: {error}") from error
        thickness = si(table["ply_thickness"], "length") if "ply_thickness" in table else record.ply_thickness_m
        if thickness is None:
            raise RepairError(f"[{where}]: the library record of {table['library']!r} has no ply thickness; give ply_thickness")
        return RepairMaterial(record.name, record.lamina, thickness)
    try:
        lamina = Lamina(E1=si(table["E1"], "modulus"), E2=si(table["E2"], "modulus"), G12=si(table["G12"], "modulus"), nu12=table["nu12"])
    except ValueError as error:
        raise RepairError(f"[{where}]: the ply constants E1, E2, G12 and nu12 do not make a material: {error}") from error
    return RepairMaterial(table["name"], lamina, si(table["ply_thickness"], "length"))


def _material_keys(table: object, where: str, also: set[str], optional: set[str] = frozenset()) -> dict:
    """The keys of a table that names a material: by the library, or typed in full, never half of each."""
    if isinstance(table, dict) and "library" in table:
        return _keys(table, where, {"library"} | also, {"dataset", "ply_thickness"} | optional)
    return _keys(table, where, set(TYPED_MATERIAL) | also, optional)


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

    def si(value, quantity):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RepairError(f"A {quantity if quantity != 'N' else 'load'} must be a number, got {value!r}")
        return value * system[quantity][0]

    parent = _material_keys(data.get("parent"), "parent", {"layup"})
    damage = _keys(data.get("damage"), "damage", {"diameter"})
    steps = _keys(data.get("steps"), "steps", {"count", "length"}, {"plies"})
    stated = _keys(data.get("adhesive"), "adhesive", {"shear_modulus", "thickness"}, {"shear_strength"})
    panel = _keys(data.get("panel"), "panel", {"length", "width"})
    try:
        adhesive = Adhesive(si(stated["shear_modulus"], "stress"), si(stated["thickness"], "length"),
                            si(stated["shear_strength"], "stress") if "shear_strength" in stated else None)
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
