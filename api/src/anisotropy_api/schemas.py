"""Explicit JSON contracts for forward and prescribed-curvature laminate analysis."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, PositiveFloat, model_validator

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.response import Loads


class Contract(BaseModel):
    """Reject unknown fields, non-finite numbers, and string/bool-to-number coercion."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class MaterialInput(Contract):
    """Explicit elastic constants and a caller-supplied citation, not a verified dataset."""

    E1_pa: PositiveFloat
    E2_pa: PositiveFloat
    G12_pa: PositiveFloat
    nu12: float
    source_reference: Annotated[str, Field(min_length=1, pattern=r"\S")]

    def to_engine(self) -> Lamina:
        """Map API field names to the engine's existing validated material model."""
        return Lamina(E1=self.E1_pa, E2=self.E2_pa, G12=self.G12_pa, nu12=self.nu12)

    @model_validator(mode="after")
    def validate_compliance(self) -> Self:
        """Reuse the engine's physical input check instead of copying its equation."""
        try:
            self.to_engine()
        except (OverflowError, ZeroDivisionError) as exc:
            raise ValueError("Elastic constants exceed the supported numerical range") from exc
        return self


class PlyInput(Contract):
    """Plies arrive bottom face first; angles are counterclockwise from x to fibers."""

    angle_deg: float
    thickness_m: PositiveFloat


class LoadInput(Contract):
    """Every component is required, including explicit zeros. All loads are per width."""

    Nx: float = Field(description="Axial force resultant, N/m")
    Ny: float = Field(description="Transverse force resultant, N/m")
    Nxy: float = Field(description="Shear force resultant, N/m")
    Mx: float = Field(description="Bending moment resultant, N*m/m")
    My: float = Field(description="Bending moment resultant, N*m/m")
    Mxy: float = Field(description="Twisting moment resultant, N*m/m")

    def to_engine(self) -> Loads:
        """Pass all six supplied components to the engine without adding defaults."""
        return Loads(**self.model_dump())


class AnalysisRequest(Contract):
    """SI_BASE means Pa, m, N/m and N*m/m; it is not the calculator's SI display scale."""

    unit_system: Literal["SI_BASE"]
    material: MaterialInput
    plies: Annotated[list[PlyInput], Field(min_length=1)]
    loads: LoadInput


Vector3 = Annotated[list[FiniteFloat], Field(min_length=3, max_length=3)]
Matrix3 = Annotated[list[Vector3], Field(min_length=3, max_length=3)]


class AnalysisResponse(Contract):
    """Engine results in base units, with the accepted inputs echoed for inspection."""

    engine_version: str
    inputs: AnalysisRequest
    A_N_per_m: Matrix3
    B_N: Matrix3
    D_N_m: Matrix3
    midplane_strain: Vector3 = Field(description="[epsilon_x, epsilon_y, gamma_xy]; engineering shear")
    curvature_per_m: Vector3 = Field(description="[kappa_x, kappa_y, kappa_xy], 1/m")


class ForceInput(Contract):
    """Only known force resultants are accepted; moments are outputs of this operation."""

    Nx: float = Field(description="Axial force resultant, N/m")
    Ny: float = Field(description="Transverse force resultant, N/m")
    Nxy: float = Field(description="Shear force resultant, N/m")


class PrescribedCurvatureRequest(Contract):
    """Known forces and prescribed curvature; solve for all three moments and strains.

    Explicitly declaring bottom_to_top makes the caller responsible for resolving
    the stacking convention. Reversing the stack reverses flattening moment signs.
    """

    unit_system: Literal["SI_BASE"]
    stacking_order: Literal["bottom_to_top"]
    material: MaterialInput
    plies: Annotated[list[PlyInput], Field(min_length=1)]
    forces: ForceInput
    prescribed_curvature_per_m: Vector3 = Field(
        description="[kappa_x, kappa_y, kappa_xy], 1/m, with engineering twist convention. Enter [0,0,0] to enforce flatness.",
    )


class VerificationResponse(Contract):
    """Forward-solve residuals and componentwise numerical tolerances, not validation against experiments."""

    passed: Literal[True]
    recovered_midplane_strain: Vector3
    recovered_curvature_per_m: Vector3
    strain_residual: Vector3
    curvature_residual_per_m: Vector3
    strain_allowed_error: Vector3
    curvature_allowed_error_per_m: Vector3


class PrescribedCurvatureResponse(Contract):
    """Required applied moment resultants, not the opposite reactions on a fixture.

    Axes x/y, engineering shear/twist, CCW angles from x to fibers, and bottom-first
    plies follow ADR-0004. No thermal/moisture effects or support/fixture design.
    """

    analysis_type: Literal["prescribed_curvature"]
    engine_version: str
    inputs: PrescribedCurvatureRequest
    A_N_per_m: Matrix3
    B_N: Matrix3
    D_N_m: Matrix3
    midplane_strain: Vector3
    moments_N_m_per_m: Vector3 = Field(description="Required [Mx, My, Mxy] applied to the laminate, N*m/m")
    verification: VerificationResponse
