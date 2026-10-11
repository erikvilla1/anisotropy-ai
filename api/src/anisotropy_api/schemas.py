"""Explicit JSON contracts for forward and prescribed-curvature laminate analysis."""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Discriminator, Field, FiniteFloat, PositiveFloat, Tag, model_validator

from anisotropy_engine.lamina import Lamina
from anisotropy_engine.library import LibraryMaterial, library_material
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


class LibraryMaterialInput(Contract):
    """A dataset of the cited material library (ADR-0020); the engine resolves and cites it."""

    library_id: Annotated[str, Field(min_length=1, pattern=r"\S")]
    dataset_id: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None

    def resolve(self) -> LibraryMaterial:
        return library_material(self.library_id, self.dataset_id)

    def to_engine(self) -> Lamina:
        return self.resolve().lamina

    @model_validator(mode="after")
    def validate_dataset(self) -> Self:
        """Unknown ids and datasets without an elastic input set are request errors, not 500s."""
        self.resolve()  # raises ValueError with the library's own message
        return self


def _material_kind(value) -> str:
    """Route a request to one material form so validation errors name only that form's fields."""
    if isinstance(value, (MaterialInput, LibraryMaterialInput)):
        return "library" if isinstance(value, LibraryMaterialInput) else "explicit"
    return "library" if isinstance(value, dict) and "library_id" in value else "explicit"


MaterialChoice = Annotated[
    Annotated[MaterialInput, Tag("explicit")] | Annotated[LibraryMaterialInput, Tag("library")],
    Discriminator(_material_kind),
]


class CitedValueOutput(Contract):
    role: str
    key: str
    value: float
    unit: str
    source_value: float
    source_unit: str
    basis: str
    page: int
    printed_page: int | None
    reference_url: str


class MaterialProvenance(Contract):
    """Which library dataset the engine used and the citation of every value it took from it."""

    material_id: str
    name: str
    dataset_id: str
    dataset: str
    record_revision: str | None
    rights: str
    citation: str
    E1_pa: float
    E2_pa: float
    G12_pa: float
    nu12: float
    ply_thickness_m: float | None
    not_provided: list[str]
    values: list[CitedValueOutput]

    @classmethod
    def of(cls, material: LibraryMaterial) -> "MaterialProvenance":
        return cls(material_id=material.material_id, name=material.name, dataset_id=material.dataset_id,
                   dataset=material.dataset, record_revision=material.record_revision, rights=material.rights,
                   citation=material.citation, E1_pa=material.lamina.E1, E2_pa=material.lamina.E2,
                   G12_pa=material.lamina.G12, nu12=material.lamina.nu12, ply_thickness_m=material.ply_thickness_m,
                   not_provided=list(material.not_provided),
                   values=[CitedValueOutput(**vars(v)) for v in material.values])


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
    material: MaterialChoice
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
    material_provenance: MaterialProvenance | None = Field(default=None, description="Set when the material came from the library")


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
    material: MaterialChoice
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
    material_provenance: MaterialProvenance | None = Field(default=None, description="Set when the material came from the library")
    A_N_per_m: Matrix3
    B_N: Matrix3
    D_N_m: Matrix3
    midplane_strain: Vector3
    moments_N_m_per_m: Vector3 = Field(description="Required [Mx, My, Mxy] applied to the laminate, N*m/m")
    verification: VerificationResponse
