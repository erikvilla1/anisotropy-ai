"""A composite wing from one description: section, flight load cases and the hand calculation (ADR-0115)."""

from .airfoil import Airfoil, naca4
from .analysis import CaseResult, Check, WingResult, analyze_wing
from .description import (
    Aerodynamics, Aileron, FlightEnvelope, GustLoadFactors, GustSpeeds, Layup, Speeds, Wing, WingGeometry, WingMaterial,
)
from .loads import CaseNotRun, LoadCase, flight_cases, span_loads
from .section import BoxSection, box_section
from .wing_file import load_wing, wing_from_dict, wing_report

__all__ = [
    "Aerodynamics", "Aileron", "Airfoil", "BoxSection", "CaseNotRun", "CaseResult", "Check", "FlightEnvelope", "GustLoadFactors",
    "GustSpeeds", "Layup", "LoadCase", "Speeds", "Wing", "WingGeometry", "WingMaterial", "WingResult", "analyze_wing", "box_section",
    "flight_cases", "load_wing", "naca4", "span_loads", "wing_from_dict", "wing_report",
]
