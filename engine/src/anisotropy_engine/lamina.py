"""Stiffness and strength of a single orthotropic ply (lamina) under plane stress.

Axis 1 is the fiber direction, axis 2 is transverse in-plane. Shear uses
engineering strain gamma12 = 2 * epsilon12. All moduli and strengths are in Pa.
"""

import numpy as np
from pydantic import BaseModel, ConfigDict, PositiveFloat, model_validator


class Strengths(BaseModel):
    """In-plane ply strengths in Pa, Daniel & Ishai notation (F6 is in-plane shear).

    Compressive strengths are positive magnitudes.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    F1t: PositiveFloat
    F1c: PositiveFloat
    F2t: PositiveFloat
    F2c: PositiveFloat
    F6: PositiveFloat


class Lamina(BaseModel):
    """In-plane elastic constants of one ply in Pa, plus strengths when failure checks are needed."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    E1: PositiveFloat
    E2: PositiveFloat
    G12: PositiveFloat
    nu12: float
    strengths: Strengths | None = None

    @property
    def nu21(self) -> float:
        """Minor Poisson ratio from reciprocity: nu21 / E2 = nu12 / E1."""
        return self.nu12 * self.E2 / self.E1

    @model_validator(mode="after")
    def _positive_compliance(self) -> "Lamina":
        if 1 - self.nu12 * self.nu21 <= 0:
            raise ValueError("Elastic constants violate positive compliance: need nu12**2 < E1/E2")
        return self


def reduced_stiffness(ply: Lamina) -> np.ndarray:
    """Plane-stress reduced stiffness Q: [sigma1, sigma2, tau12] = Q @ [eps1, eps2, gamma12]."""
    d = 1 - ply.nu12 * ply.nu21
    q12 = ply.nu12 * ply.E2 / d
    return np.array([
        [ply.E1 / d, q12, 0.0],
        [q12, ply.E2 / d, 0.0],
        [0.0, 0.0, ply.G12],
    ])
