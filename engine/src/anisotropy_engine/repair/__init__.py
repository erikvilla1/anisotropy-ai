"""A bonded repair worked by hand: the stepped lap between a patch and the laminate it covers (ADR-0130), and a stepped patch
repair described by a few numbers, flush in a stepped cut or bonded on top over a hole, with the slice through it and the lap it
makes (ADR-0131 and its amendment 1); and the plies and the adhesive of that slice as solids, for its finite element solve
(ADR-0132)."""

from .description import Repair, RepairError, RepairMaterial, ThroughThickness, tape_through_thickness
from .lap_file import lap_from_dict, lap_report
from .patch_lap import lap_steps, repair_lap, shared_stiffnesses, stretching_matrix
from .repair_file import repair_from_dict, repair_report
from .section import Region, areas, bond_lengths, check_regions, region_at, regions, volumes
from .solid import FarField, adhesive_stiffness, far_field, plane_stress_stiffness, ply_axis_stress, ply_compliance, ply_stiffness, turned_stiffness
from .step_lap import (
    Adhesive, Step, StepLap, boundary_forces, double_lap_strength, elastic_limit_load, long_overlap_strength, step_constants, step_lap,
)

__all__ = [
    "Adhesive", "FarField", "Region", "Repair", "RepairError", "RepairMaterial", "Step", "StepLap", "ThroughThickness", "adhesive_stiffness", "areas",
    "bond_lengths", "boundary_forces", "check_regions", "double_lap_strength", "elastic_limit_load", "far_field", "lap_from_dict", "lap_report",
    "lap_steps", "long_overlap_strength", "plane_stress_stiffness", "ply_axis_stress", "ply_compliance", "ply_stiffness", "region_at", "regions",
    "repair_from_dict", "repair_lap", "repair_report", "shared_stiffnesses", "step_constants", "step_lap", "stretching_matrix",
    "tape_through_thickness", "turned_stiffness", "volumes",
]
