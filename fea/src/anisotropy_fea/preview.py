"""What the studio draws before a coupon is solved (ADR-0051): the mesh, its named sets, what is held and what is loaded, the plies,
the material and the probes, as one JSON-ready dict in the spec's units.

Everything here is read from the model `femodel.build_model` made; nothing is computed beyond unit conversion and counting. The
browser draws it and never changes it: a change goes back through the values file and the checks.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .femodel import FEModel
from .quality import QualityField, quality_summary
from .spec import TEST_CODES, coupon_card, full_angles, layup_text, spec_ply_thickness
from .units import UNIT_LABEL, from_si

DOF_WORDS = {1: "x", 2: "y", 3: "z", 4: "rotation about x", 5: "rotation about y", 6: "rotation about z"}


def _coupled_set(model: FEModel, target: str) -> tuple[str, str | None]:
    """The coupon node set a boundary or load acts on, and the reference point it acts through, if any."""
    for coupling in model.couplings:
        if coupling.reference_set == target:
            return coupling.node_set, target
    return target, None


def preview_data(model: FEModel, quality: QualityField | None = None) -> dict[str, Any]:
    spec, mesh, units = model.spec, model.mesh, model.spec.units
    length = lambda v: from_si(float(v), "length", units)  # noqa: E731
    stress = lambda v: None if v is None else from_si(float(v), "stress", units)  # noqa: E731
    g, loading, material = spec.geometry, spec.loading, model.material
    corners = mesh.corners
    thickness_m = sum(ply.thickness_m for ply in model.section.plies)
    sets = model.node_sets
    held = []
    for boundary in model.boundaries:
        if boundary.value != 0.0:
            continue  # the moving grip's prescribed value is the loading, listed below
        node_set, through = _coupled_set(model, boundary.target)
        held.append({"set": node_set, "through": through, "dofs": list(range(boundary.dof_first, boundary.dof_last + 1)),
                     "directions": [DOF_WORDS[d] for d in range(boundary.dof_first, boundary.dof_last + 1)], "nodes": int(sets[node_set].size)})
    if loading.control == "displacement":
        moving = next(b for b in model.boundaries if b.value != 0.0)
        node_set, through = _coupled_set(model, moving.target)
        value, unit = length(moving.value), UNIT_LABEL[units]["length"]
        dof = moving.dof_first
    else:
        targets = {load.target for load in model.loads}
        through = next((t for t in targets if any(c.reference_set == t for c in model.couplings)), None)
        node_set = _coupled_set(model, through)[0] if through else "Grip-Top"
        value, unit = from_si(sum(load.value for load in model.loads), "force", units), UNIT_LABEL[units]["force"]
        dof = next(iter(model.loads)).dof
    loaded = {"set": node_set, "through": through, "control": loading.control, "dof": dof, "direction": ("+" if value >= 0 else "-") + DOF_WORDS[dof],
              "value": value, "unit": unit, "nodes": int(sets[node_set].size)}
    z = -thickness_m / 2
    plies = []
    for k, ply in enumerate(model.section.plies, start=1):
        plies.append({"index": k, "angle": ply.angle_deg, "thickness": length(ply.thickness_m), "z_bottom": length(z), "z_top": length(z + ply.thickness_m),
                      "material": ply.material})
        z += ply.thickness_m
    strengths = None if material.strengths is None else {role: stress(getattr(material.strengths, role)) for role in ("F1t", "F1c", "F2t", "F2c", "F6")}
    centroids = mesh.centroids()
    probes = {"nodes": {name: {"index": int(i), "xy": [length(mesh.xy[i, 0]), length(mesh.xy[i, 1])]} for name, i in model.probe_nodes.items()},
              "elements": {name: {"index": int(e), "xy": [length(centroids[e, 0]), length(centroids[e, 1])]} for name, e in model.probe_elements.items()}}
    geometry = {"length": length(g.length), "width": length(g.width), "tab_length": length(g.tab_length or 0.0),
                "hole_diameter": None if g.hole_diameter is None else length(g.hole_diameter), "thickness": length(thickness_m)}
    for key in ("span", "overhang", "load_span"):
        value_ = getattr(g, key)
        geometry[key] = None if value_ is None else length(value_)
    data: dict[str, Any] = {
        "units": units, "labels": UNIT_LABEL[units],
        "coupon": {"designation": spec.coupon.designation if spec.coupon else None, "title": spec.title, "kind": spec.kind,
                   "test": TEST_CODES[spec.kind][1], "card": [list(row) for row in coupon_card(spec)], "layup": layup_text(spec)},
        "geometry": geometry,
        "mesh": {"nodes": [[length(x), length(y)] for x, y in mesh.xy], "quads": corners.tolist(), "node_sets": {name: idx.tolist() for name, idx in sets.items()},
                 "element_sets": {name: idx.tolist() for name, idx in model.element_sets.items()},
                 "order": mesh.order, "mesher": mesh.mesher, "node_count": mesh.node_count, "element_count": mesh.element_count},
        "held": held, "loaded": loaded,
        "plies": plies,
        "material": {"name": material.name, "source": material.source, "rights": material.rights, "E1": stress(material.E1), "E2": stress(material.E2),
                     "G12": stress(material.G12), "nu12": material.nu12, "G13": stress(material.G13), "G23": stress(material.G23),
                     "strengths": strengths, "f12_star": material.f12_star, "criteria": list(spec.output.fpf_criteria),
                     "citation_lines": list(material.citation_lines), "ply_thickness": length(spec_ply_thickness(spec)), "plies": len(full_angles(spec))},
        "probes": probes,
    }
    if quality is not None:
        data["quality"] = {"summary": quality_summary(quality),
                           "per_element": {name: np.round(getattr(quality, name), 6).tolist()
                                           for name in ("aspect_ratio", "min_angle_deg", "max_angle_deg", "jacobian_ratio")}}
    return data
