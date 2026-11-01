"""Explicit JSON contracts for forward and prescribed-curvature laminate analysis, and for coupon jobs."""

import base64
import binascii
import hashlib
import json
from typing import Annotated, Any, Literal, Self

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


class CaseRequest(Contract):
    """A whole problem in the engine's case format, as a JSON object or as TOML text (ADR-0024).

    The format is the one the calculator and the validation cases use (engine/validation/README.md):
    units, one material or several, the laminate, exactly one applied form, and optional
    f12_star, [failure], [plate] with [buckling], and [expected]. The engine validates every
    field and rejects anything unknown or half filled, with the same messages as the calculator.
    """

    case: dict[str, Any] | None = None
    toml: Annotated[str, Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def exactly_one_form(self) -> Self:
        if (self.case is None) == (self.toml is None):
            raise ValueError("Give exactly one of case (a JSON object) or toml (the case file text)")
        return self


class ComparisonOutput(Contract):
    """One expected value of the case next to the engine's, in the case's units."""

    key: str
    expected: float
    engine: float
    allowed: float
    agrees: bool


class CaseResponse(Contract):
    """Every result the case determines, in the case's units, keyed as engine/validation/README.md lists them.

    Values are numbers or nested lists. A ratio that is unbounded (an unstressed ply) is null,
    since JSON has no infinity. materials holds the library provenance of each material that
    came from the library, by the case's material name; typed materials are absent. run_id is
    the record of this run (ADR-0026); it is null only when recording is switched off.
    """

    run_id: str | None
    engine_version: str
    units: str
    title: str | None
    results: dict[str, Any]
    criteria: list[str]
    materials: dict[str, MaterialProvenance]
    comparison: list[ComparisonOutput] | None
    problems: list[str]


class RunSummary(Contract):
    """One line of a run listing (ADR-0026): enough to pick a run; GET /v1/runs/{run_id} has the rest."""

    run_id: str
    created_at: str
    actor: str
    endpoint: str
    status: str
    engine_version: str
    api_version: str
    git_commit: str | None
    inputs_sha256: str
    error: str | None
    user_email: str | None  # the signed-in email Cloudflare Access verified (ADR-0056); null with Access off

    @classmethod
    def of(cls, run) -> "RunSummary":
        return cls(run_id=str(run.id), created_at=run.created_at.isoformat(), actor=run.actor, endpoint=run.endpoint,
                   status=run.status, engine_version=run.engine_version, api_version=run.api_version,
                   git_commit=run.git_commit, inputs_sha256=run.inputs_sha256, error=run.error, user_email=run.user_email)


class RunOutput(Contract):
    """One run record as stored (ADR-0026).

    inputs is the request as received. response is the CaseResponse body as returned, without
    run_id, and is null for a rejected run; error is the rejection message and null otherwise.
    """

    run_id: str
    created_at: str
    actor: str
    endpoint: str
    status: str
    inputs: dict[str, Any]
    inputs_sha256: str
    engine_version: str
    api_version: str
    git_commit: str | None
    response: dict[str, Any] | None
    error: str | None
    supersedes_run_id: str | None
    llm_provider: str | None
    llm_model_version: str | None
    user_email: str | None

    @classmethod
    def of(cls, run) -> "RunOutput":
        return cls(run_id=str(run.id), created_at=run.created_at.isoformat(), actor=run.actor, endpoint=run.endpoint, status=run.status,
                   inputs=run.inputs, inputs_sha256=run.inputs_sha256, engine_version=run.engine_version,
                   api_version=run.api_version, git_commit=run.git_commit, response=run.response, error=run.error,
                   supersedes_run_id=None if run.supersedes_run_id is None else str(run.supersedes_run_id),
                   llm_provider=run.llm_provider, llm_model_version=run.llm_model_version, user_email=run.user_email)


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
    """Engine results in base units, with the accepted inputs echoed for inspection.

    run_id is the record of this run (ADR-0026); it is null only when recording is switched off.
    """

    run_id: str | None = None
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

    run_id: str | None = Field(default=None, description="The record of this run (ADR-0026); null only when recording is switched off")
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


FORM_LIMIT_BYTES = 5_000_000  # a filled-in form is tens of kilobytes


VALUES_LIMIT_BYTES = 200_000  # a values object is a few kilobytes


class CouponJobRequest(Contract):
    """Start a coupon job (ADR-0050): a filled-in input form, the coupon's values as the studio sends them (ADR-0051), or the name of
    a coupon that has its specs, and who runs it.

    The form travels as base64 with its file name; the values travel as one JSON object of the form's rows by field key. The run
    record keeps the input's name and SHA-256; the tool files the input itself in the coupon's team/<date>/ folder. The options are
    those of fea/tools/run_coupon.py.
    """

    form_name: Annotated[str, Field(pattern=r"^[^/\\:*?\"<>|\s-][^/\\:*?\"<>|]*\.xlsx$", max_length=120)] | None = None
    form_base64: str | None = None
    values: dict[str, Any] | None = None
    coupon: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$", max_length=80)] | None = None
    run_by: Annotated[str, Field(pattern=r"^[^\s-][^\r\n]*$", max_length=120)]
    replace: bool = False
    pdf: bool = True
    theory: bool = True

    @model_validator(mode="after")
    def one_source(self) -> Self:
        given = self.form_name is not None or self.form_base64 is not None
        sources = sum((given, self.values is not None, self.coupon is not None))
        if sources != 1:
            raise ValueError("give a form (form_name and form_base64), the values, or a coupon: one of the three, not none and not several")
        if given and (self.form_name is None or self.form_base64 is None):
            raise ValueError("a form needs both form_name and form_base64")
        if self.coupon is not None and self.replace:
            raise ValueError("replace rewrites a coupon's specs from its input, so it needs a form or the values")
        if given:
            self.form_bytes()
        if self.values is not None:
            self.values_bytes()
        return self

    def values_bytes(self) -> bytes:
        """The values object as the file the tool reads: JSON with sorted keys, so the digest does not depend on the order sent."""
        if not self.values:
            raise ValueError("values must hold the form's rows by field key; the object is empty")
        content = json.dumps(self.values, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")
        if len(content) > VALUES_LIMIT_BYTES:
            raise ValueError(f"the values are {len(content)} bytes; the form's rows are far below {VALUES_LIMIT_BYTES}")
        return content

    def form_bytes(self) -> bytes:
        try:
            content = base64.b64decode(self.form_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"form_base64 is not base64: {exc}") from None
        if len(content) > FORM_LIMIT_BYTES:
            raise ValueError(f"the form is {len(content)} bytes; a filled-in form is far below {FORM_LIMIT_BYTES}")
        if not content.startswith(b"PK"):
            raise ValueError("form_base64 is not an .xlsx file (an .xlsx file starts with PK)")
        return content

    def recorded_inputs(self) -> dict[str, Any]:
        """What the run record keeps of the request: the input's digest, never the team's constants."""
        if self.coupon is not None:
            source: dict[str, Any] = {"coupon": self.coupon}
        elif self.values is not None:
            source = {"values": {"sha256": hashlib.sha256(self.values_bytes()).hexdigest(), "form_version": str(self.values.get("form_version", ""))}}
        else:
            source = {"form": {"name": self.form_name, "sha256": hashlib.sha256(self.form_bytes()).hexdigest()}}
        return {**source, "run_by": self.run_by, "replace": self.replace, "pdf": self.pdf, "theory": self.theory}

    def options(self) -> list[str]:
        """The tool's options for this request."""
        return ["--run-by", self.run_by, *(["--replace"] if self.replace else []), *([] if self.pdf else ["--no-pdf"]),
                *([] if self.theory else ["--no-theory"])]


class CouponJobOutput(Contract):
    """A coupon job as it stands (ADR-0050). `outputs` are paths from the repository root, by key: the files made so far while it
    runs (ADR-0051), every file once it is done; `stage` is the step the tool is at and `stages_done` the steps behind it;
    `run_id` names the job's receipt once it has ended (null while it runs, or when recording is switched off)."""

    job_id: str
    state: Literal["running", "done", "stopped", "refused"]
    actor: str
    started_at: str
    finished_at: str | None
    coupon: str | None
    attempt: str | None
    message: str | None
    stage: str | None
    stages_done: list[str]
    stages: list[str]
    outputs: dict[str, str]
    run_id: str | None
    log_tail: list[str]
    user_email: str | None = None  # the signed-in email of the request that started it (ADR-0056); null with Access off

    @classmethod
    def of(cls, job) -> "CouponJobOutput":
        outcome = job.outcome or {}
        progress = job.progress() or {}
        outputs = outcome.get("outputs") if outcome else progress.get("outputs", {})
        return cls(job_id=str(job.id), state=job.state, actor=job.actor, started_at=job.started_at.isoformat(), user_email=job.user_email,
                   finished_at=None if job.finished_at is None else job.finished_at.isoformat(), coupon=outcome.get("coupon") or progress.get("coupon"),
                   attempt=outcome.get("attempt") or progress.get("attempt"), message=outcome.get("message"), stage=progress.get("stage"),
                   stages_done=list(progress.get("done", [])), stages=list(progress.get("stages", [])), outputs=outputs or {},
                   run_id=None if job.run_id is None else str(job.run_id), log_tail=job.log_tail())


class CouponCheckReceipt(Contract):
    """What the run record keeps of a check: the values' digest and version, never the rows (the team's own constants stay with the coupon)."""

    values: dict[str, str | int]


class CouponCheckRequest(Contract):
    """The studio's setup check (ADR-0051): the form's rows as one JSON object, judged without a run."""

    values: dict[str, Any]

    @model_validator(mode="after")
    def not_empty(self) -> Self:
        if not self.values:
            raise ValueError("values must hold the form's rows by field key; the object is empty")
        return self

    def values_bytes(self) -> bytes:
        content = json.dumps(self.values, sort_keys=True, ensure_ascii=False, indent=1).encode("utf-8")
        if len(content) > VALUES_LIMIT_BYTES:
            raise ValueError(f"the values are {len(content)} bytes; the form's rows are far below {VALUES_LIMIT_BYTES}")
        return content

    def receipt(self) -> CouponCheckReceipt:
        return CouponCheckReceipt(values={"sha256": hashlib.sha256(self.values_bytes()).hexdigest(),
                                          "form_version": str(self.values.get("form_version", "")), "rows": len(self.values)})


class CouponCheckResponse(Contract):
    """What the check found: the checklist as fea/src/anisotropy_fea/checks.py writes it, and the model to draw when the inputs build
    one. Recorded as a run, since it reaches the engine (ADR-0026)."""

    run_id: str | None
    state: Literal["ready", "blocked"]
    designation: str | None
    checklist: dict[str, Any]
    preview: dict[str, Any] | None


class ExplainRequest(Contract):
    """What to explain of a job (ADR-0052): the setup, from the attempt's checklist, or the result, from the solve's fact sheet."""

    kind: Literal["setup", "result"]


class ExplainReceipt(Contract):
    """What the run record keeps of an explanation: the job, the kind and the digest of the facts the writer saw."""

    job_id: str
    kind: str
    facts_sha256: str


class ExplainResponse(Contract):
    """An explanation (ADR-0052): the prose, who wrote it (`template`, or the provider's name with its model), and when the model's draft
    was withheld by the number guard or the model did not answer, why; the template's prose stands in both cases."""

    run_id: str | None
    job_id: str
    kind: str
    writer: str
    model: str | None
    prose: list[str]
    withheld: bool
    reason: str | None
    facts: dict[str, Any]


class CouponSummary(Contract):
    """One coupon on this machine, from its spec and its case page (ADR-0051)."""

    name: str
    designation: str | None
    kind: str
    test: str
    title: str
    layup: str
    status: str | None
    accepted: str | None
    attempts: int
    category: str | None
    problem: str | None = None


class CouponValuesOutput(Contract):
    """A coupon's rows as the values object the studio edits (ADR-0051): the inverse of the form's reading."""

    name: str
    values: dict[str, Any]
