"""A bonded repair worked by hand: the stepped lap between a patch and the laminate it covers (ADR-0130), and a stepped patch
repair described by a few numbers, flush in a stepped cut or bonded on top over a hole, with the slice through it and the lap it
makes (ADR-0131 and its amendment 1); and the plies and the adhesive of that slice as solids, for its finite element solve
(ADR-0132); and what a page draws of a repair and what a solve of its slice still needs (ADR-0135); and one change to a repair previewed on a copy,
and one quantity swept with the repair worked by hand at every value (ADR-0136)."""

from .changes import RepairChange, change_repair, preview_change
from .description import Repair, RepairError, RepairMaterial, ThroughThickness, tape_through_thickness
from .lap_file import lap_from_dict, lap_report
from .patch_lap import lap_steps, repair_lap, shared_stiffnesses, stretching_matrix
from .repair_file import bond_needs, repair_from_dict, repair_report, repair_views, solve_needs
from .section import Region, areas, bond_lengths, check_regions, region_at, regions, volumes
from .solid import FarField, adhesive_stiffness, far_field, plane_stress_stiffness, ply_axis_stress, ply_compliance, ply_stiffness, turned_stiffness
from .sweeps import RepairSweep, pick_check, sweep_repair
from .step_lap import (
    Adhesive, Step, StepLap, boundary_forces, double_lap_strength, elastic_limit_load, long_overlap_strength, step_constants, step_lap,
)

__all__ = [
    "Adhesive", "FarField", "Region", "Repair", "RepairChange", "RepairError", "RepairMaterial", "RepairSweep", "Step", "StepLap", "ThroughThickness", "adhesive_stiffness", "areas",
    "bond_lengths", "boundary_forces", "change_repair", "check_regions", "double_lap_strength", "elastic_limit_load", "far_field", "lap_from_dict", "lap_report",
    "lap_steps", "long_overlap_strength", "pick_check", "plane_stress_stiffness", "ply_axis_stress", "ply_compliance", "ply_stiffness", "preview_change", "region_at", "regions",
    "repair_from_dict", "repair_lap", "repair_report", "repair_views", "shared_stiffnesses", "solve_needs", "step_constants", "step_lap",
    "stretching_matrix", "sweep_repair", "tape_through_thickness", "turned_stiffness", "volumes",
]
