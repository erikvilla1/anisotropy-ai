"""Lamina elastic constants from fiber and matrix constants and the fiber volume ratio (micromechanics).

Continuous aligned fibers, perfect bonding, a transversely isotropic fiber and an isotropic matrix. The models
are the mechanics-of-materials ones and the Halpin-Tsai interpolation of Daniel and Ishai, chapter 3 (2nd ed.,
2006, pp. 46-57), plus the combined series-parallel model for a square fiber array derived in the theory file.
Every model choice is stated by the caller (ADR-0003): the transverse and shear models and, for Halpin-Tsai,
the parameter xi. SI units inside (ADR-0002).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveFloat, field_validator

from .lamina import Lamina, Strengths, ThermalExpansion

E2Model = Literal["series", "series_constrained", "halpin_tsai", "combination_square"]
G12Model = Literal["series", "halpin_tsai", "combination_square"]
E2_MODELS: tuple[str, ...] = ("series", "series_constrained", "halpin_tsai", "combination_square")
G12_MODELS: tuple[str, ...] = ("series", "halpin_tsai", "combination_square")


class Fiber(BaseModel):
    """A transversely isotropic fiber: axial modulus E1, transverse modulus E2, axial shear modulus G12, Poisson's ratio nu12 (Pa)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    E1: PositiveFloat
    E2: PositiveFloat
    G12: PositiveFloat
    nu12: float

    @field_validator("nu12")
    @classmethod
    def _poisson_range(cls, value: float) -> float:
        if not math.isfinite(value) or not -1.0 < value < 0.5:
            raise ValueError("fiber nu12 must be a finite number between -1 and 0.5")
        return value

    @classmethod
    def isotropic(cls, E: float, nu: float) -> "Fiber":
        """An isotropic fiber (glass): E1 = E2 = E and G12 = E / (2 (1 + nu))."""
        return cls(E1=E, E2=E, G12=E / (2.0 * (1.0 + nu)), nu12=nu)


class Matrix(BaseModel):
    """An isotropic matrix: Young's modulus E (Pa) and Poisson's ratio nu; its shear modulus follows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    E: PositiveFloat
    nu: float

    @field_validator("nu")
    @classmethod
    def _poisson_range(cls, value: float) -> float:
        if not math.isfinite(value) or not -1.0 < value < 0.5:
            raise ValueError("matrix nu must be a finite number between -1 and 0.5")
        return value

    @property
    def G(self) -> float:
        """Shear modulus of the isotropic matrix, E / (2 (1 + nu))."""
        return self.E / (2.0 * (1.0 + self.nu))


def _check_volume_ratio(Vf: float) -> float:
    if not math.isfinite(Vf) or not 0.0 < Vf < 1.0:
        raise ValueError(f"fiber volume ratio Vf must lie strictly between 0 and 1, got {Vf}")
    return float(Vf)


def rule_of_mixtures(Pf: float, Pm: float, Vf: float) -> float:
    """Parallel (Voigt) model, equal strain in fiber and matrix: P = Vf Pf + Vm Pm. Used for E1 and nu12."""
    Vf = _check_volume_ratio(Vf)
    return Vf * Pf + (1.0 - Vf) * Pm


def series_model(Pf: float, Pm: float, Vf: float) -> float:
    """Series (Reuss) model, equal stress in fiber and matrix: 1 / P = Vf / Pf + Vm / Pm. Used for E2 and G12."""
    Vf = _check_volume_ratio(Vf)
    if Pf <= 0 or Pm <= 0:
        raise ValueError("the series model needs positive fiber and matrix constants")
    return 1.0 / (Vf / Pf + (1.0 - Vf) / Pm)


def constrained_matrix_modulus(matrix: Matrix) -> float:
    """The matrix modulus with the fibers preventing its contraction along them: E'_m = E_m / (1 - nu_m^2)."""
    return matrix.E / (1.0 - matrix.nu**2)


def halpin_tsai(Pf: float, Pm: float, Vf: float, xi: float) -> float:
    """Halpin-Tsai interpolation: eta = (Pf - Pm) / (Pf + xi Pm), P = Pm (1 + xi eta Vf) / (1 - eta Vf).

    xi is the reinforcing-efficiency parameter the caller states: 0 gives the series model, large values the
    parallel model; Daniel and Ishai quote 1 to 2 for E2 and 1 for G12 of common fiber composites.
    """
    Vf = _check_volume_ratio(Vf)
    if not math.isfinite(xi) or xi < 0.0:
        raise ValueError(f"Halpin-Tsai xi must be a finite number, zero or positive, got {xi}")
    if Pf <= 0 or Pm <= 0:
        raise ValueError("Halpin-Tsai needs positive fiber and matrix constants")
    eta = (Pf - Pm) / (Pf + xi * Pm)
    return Pm * (1.0 + xi * eta * Vf) / (1.0 - eta * Vf)


def combination_square_array(Pf: float, Pm: float, Vf: float) -> float:
    """Combined series-parallel model for a square array of square fibers.

    The unit cell of side L holds a fiber of side a, so Vf = (a / L)^2 and sqrt(Vf) = a / L. The column that
    contains the fiber acts in series (fiber fraction sqrt(Vf), matrix fraction 1 - sqrt(Vf)) and sits in parallel
    with the pure-matrix columns, which take the fraction 1 - sqrt(Vf) of the width:
    P = Pm (1 - sqrt(Vf)) + sqrt(Vf) * Pf Pm / (Pm sqrt(Vf) + Pf (1 - sqrt(Vf))).
    """
    Vf = _check_volume_ratio(Vf)
    if Pf <= 0 or Pm <= 0:
        raise ValueError("the combination model needs positive fiber and matrix constants")
    side = math.sqrt(Vf)
    series_column = Pf * Pm / (Pm * side + Pf * (1.0 - side))
    return Pm * (1.0 - side) + side * series_column


@dataclass(frozen=True)
class MicromechanicsResult:
    """Lamina constants (Pa) with the models that produced them, and the Lamina the laminate code uses."""

    fiber: Fiber
    matrix: Matrix
    Vf: float
    E1: float
    E2: float
    G12: float
    nu12: float
    E2_model: str
    G12_model: str
    xi_E2: float | None
    xi_G12: float | None
    lamina: Lamina

    @property
    def Vm(self) -> float:
        return 1.0 - self.Vf

    @property
    def nu21(self) -> float:
        return self.lamina.nu21


def lamina_from_constituents(fiber: Fiber, matrix: Matrix, Vf: float, E2_model: E2Model, G12_model: G12Model,
                             xi_E2: float | None = None, xi_G12: float | None = None,
                             strengths: Strengths | None = None, thermal_expansion: ThermalExpansion | None = None) -> MicromechanicsResult:
    """The lamina's E1, E2, G12 and nu12 from its constituents and the stated models.

    E1 and nu12 always come from the rule of mixtures. E2 comes from the model named: the series model, the series
    model with the constrained matrix modulus, Halpin-Tsai with the stated xi_E2, or the square-array combination
    model. G12 likewise from the series model, Halpin-Tsai with xi_G12, or the combination model with the fiber's
    axial shear modulus and the matrix shear modulus. A Halpin-Tsai model without its xi is refused; an xi given
    for another model is refused too, so the record of a case says exactly what was used. Strengths and expansion
    coefficients are not predicted here; when given they are attached to the lamina as measured values.
    """
    Vf = _check_volume_ratio(Vf)
    if E2_model not in E2_MODELS:
        raise ValueError(f"E2_model must be one of {E2_MODELS}, got {E2_model!r}")
    if G12_model not in G12_MODELS:
        raise ValueError(f"G12_model must be one of {G12_MODELS}, got {G12_model!r}")
    for name, model, xi in (("xi_E2", E2_model, xi_E2), ("xi_G12", G12_model, xi_G12)):
        if model == "halpin_tsai" and xi is None:
            raise ValueError(f"{name} is required with the halpin_tsai model (Daniel and Ishai quote 1 to 2 for E2 and 1 for G12); it is never assumed")
        if model != "halpin_tsai" and xi is not None:
            raise ValueError(f"{name} belongs to the halpin_tsai model only; the {model!r} model has no parameter")
    E1 = rule_of_mixtures(fiber.E1, matrix.E, Vf)
    nu12 = rule_of_mixtures(fiber.nu12, matrix.nu, Vf)
    if E2_model == "series":
        E2 = series_model(fiber.E2, matrix.E, Vf)
    elif E2_model == "series_constrained":
        E2 = series_model(fiber.E2, constrained_matrix_modulus(matrix), Vf)
    elif E2_model == "halpin_tsai":
        E2 = halpin_tsai(fiber.E2, matrix.E, Vf, xi_E2)
    else:
        E2 = combination_square_array(fiber.E2, matrix.E, Vf)
    if G12_model == "series":
        G12 = series_model(fiber.G12, matrix.G, Vf)
    elif G12_model == "halpin_tsai":
        G12 = halpin_tsai(fiber.G12, matrix.G, Vf, xi_G12)
    else:
        G12 = combination_square_array(fiber.G12, matrix.G, Vf)
    lamina = Lamina(E1=E1, E2=E2, G12=G12, nu12=nu12, strengths=strengths, thermal_expansion=thermal_expansion)
    return MicromechanicsResult(fiber=fiber, matrix=matrix, Vf=Vf, E1=E1, E2=E2, G12=G12, nu12=nu12, E2_model=E2_model, G12_model=G12_model,
                                xi_E2=xi_E2, xi_G12=xi_G12, lamina=lamina)
