"""A bonded repair worked by hand: the stepped lap between a patch and the laminate it covers (ADR-0130), and a stepped patch
repair described by a few numbers, with the slice through it and the lap it makes (ADR-0131)."""

from .description import Repair, RepairError, RepairMaterial
from .lap_file import lap_from_dict, lap_report
from .patch_lap import lap_steps, repair_lap, shared_stiffnesses, stretching_matrix
from .repair_file import repair_from_dict, repair_report
from .section import Region, areas, bond_lengths, check_regions, region_at, regions, volumes
from .step_lap import (
    Adhesive, Step, StepLap, boundary_forces, double_lap_strength, elastic_limit_load, long_overlap_strength, step_constants, step_lap,
)

__all__ = [
    "Adhesive", "Region", "Repair", "RepairError", "RepairMaterial", "Step", "StepLap", "areas", "bond_lengths", "boundary_forces", "check_regions",
    "double_lap_strength", "elastic_limit_load", "lap_from_dict", "lap_report", "lap_steps", "long_overlap_strength", "region_at", "regions",
    "repair_from_dict", "repair_lap", "repair_report", "shared_stiffnesses", "step_constants", "step_lap", "stretching_matrix", "volumes",
]
