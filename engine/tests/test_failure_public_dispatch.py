"""The per-face criterion dispatch is public so a finite element kernel can check a ply state it computed (ADR-0029)."""

import numpy as np
import pytest

from anisotropy_engine import failure
from anisotropy_engine.failure import check_criterion, face_strength_ratio, max_stress_ratio, tsai_hill_ratio
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import PlySurface

MATERIAL = Lamina(E1=162e9, E2=9e9, G12=4.7e9, nu12=0.316, strengths=Strengths(F1t=2558e6, F1c=1731e6, F2t=64e6, F2c=286e6, F6=91e6))
ZERO = np.zeros(3)


def surface(stress_12):
    return PlySurface(0, 0.0, 0.0, ZERO, ZERO, ZERO, np.asarray(stress_12, dtype=float))


def test_public_names_are_the_earlier_private_ones():
    assert failure._face_ratio is face_strength_ratio
    assert failure._check_criterion is check_criterion


def test_face_strength_ratio_with_nothing_held_equals_the_single_state_ratios():
    stress = [800e6, 30e6, -20e6]
    assert face_strength_ratio("max_stress", MATERIAL, surface(ZERO), surface(stress), None) == max_stress_ratio(np.array(stress), MATERIAL.strengths)
    ratio, mode = face_strength_ratio("tsai_hill", MATERIAL, surface(ZERO), surface(stress), None)
    assert ratio == pytest.approx(tsai_hill_ratio(np.array(stress), MATERIAL.strengths)) and mode == "interactive"


def test_check_criterion_refuses_what_the_plies_cannot_be_checked_by():
    plies = [Ply(material=MATERIAL, angle_deg=0.0, thickness_m=1e-4)]
    check_criterion(plies, "max_stress", None)
    with pytest.raises(ValueError, match="Unknown criterion"):
        check_criterion(plies, "hashin", None)
    with pytest.raises(ValueError, match="needs an explicit f12_star"):
        check_criterion(plies, "tsai_wu", None)
    with pytest.raises(ValueError, match="no strain limits"):
        check_criterion(plies, "max_strain", None)
    bare = [Ply(material=Lamina(E1=162e9, E2=9e9, G12=4.7e9, nu12=0.316), angle_deg=0.0, thickness_m=1e-4)]
    with pytest.raises(ValueError, match="have no strengths"):
        check_criterion(bare, "max_stress", None)
