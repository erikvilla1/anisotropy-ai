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
from anisotropy_engine.summary import FailureSummary, LaminateSummary
from anisotropy_engine.units import UNIT_SYSTEMS
from anisotropy_engine.repair import RepairChange, RepairSweep
from anisotropy_engine.wing.changes import PlyChange


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
    values: list[CitedValueOutput]  # what the analysis used, then the density and fiber volume fraction the record states (ADR-0059)
    density_kg_per_m3: float | None = Field(default=None, description="The composite density the record states; null when it states none")
    fiber_volume_fraction: float | None = Field(default=None, description="A fraction; null when the record states none")

    @classmethod
    def of(cls, material: LibraryMaterial) -> "MaterialProvenance":
        return cls(material_id=material.material_id, name=material.name, dataset_id=material.dataset_id,
                   dataset=material.dataset, record_revision=material.record_revision, rights=material.rights,
                   citation=material.citation, E1_pa=material.lamina.E1, E2_pa=material.lamina.E2,
                   G12_pa=material.lamina.G12, nu12=material.lamina.nu12, ply_thickness_m=material.ply_thickness_m,
                   not_provided=list(material.not_provided),
                   values=[CitedValueOutput(**vars(v)) for v in material.values + material.extra_values],
                   density_kg_per_m3=material.density_kg_per_m3, fiber_volume_fraction=material.fiber_volume_fraction)


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


class CouplingOutput(Contract):
    """Which couplings the stack shows, each judged to the summary's relative tolerance."""

    extension_shear: bool = Field(description="A16 or A26 nonzero: an axial load shears the laminate")
    extension_bending: bool = Field(description="any B nonzero: an in-plane load bends it")
    bending_twisting: bool = Field(description="D16 or D26 nonzero: a bending moment twists it")


class LaminateSummaryOutput(Contract):
    """The stack described before any load (ADR-0059): counts, symmetry, kind, coupling and mass per area, in SI."""

    ply_count: int
    total_thickness_m: float
    symmetric: bool
    antisymmetric: bool
    balanced: bool
    kind: Literal["unidirectional", "cross-ply", "angle-ply", "quasi-isotropic", "general"]
    coupling: CouplingOutput
    relative_tolerance: float = Field(description="An entry counts as zero within this fraction of its matrix's largest entry")
    areal_mass_kg_per_m2: float | None = Field(description="Sum of density times thickness; null when a ply's material records no density")
    areal_mass_missing: str | None = Field(description="Why the areal mass is null, naming the plies without a density")

    @classmethod
    def of(cls, summary: LaminateSummary) -> "LaminateSummaryOutput":
        coupling = summary.coupling
        return cls(ply_count=int(summary.ply_count), total_thickness_m=float(summary.total_thickness_m),
                   symmetric=bool(summary.symmetric), antisymmetric=bool(summary.antisymmetric), balanced=bool(summary.balanced),
                   kind=summary.kind,
                   coupling=CouplingOutput(extension_shear=bool(coupling.extension_shear), extension_bending=bool(coupling.extension_bending),
                                           bending_twisting=bool(coupling.bending_twisting)),
                   relative_tolerance=float(summary.tolerance),
                   areal_mass_kg_per_m2=None if summary.areal_mass_kg_per_m2 is None else float(summary.areal_mass_kg_per_m2),
                   areal_mass_missing=summary.areal_mass_missing)


class CriterionOutput(Contract):
    """First-ply failure by one criterion under the request's loads, every load scaling together."""

    criterion: Literal["max_stress", "max_strain", "tsai_hill", "tsai_wu"]
    strength_ratio: float | None = Field(description="R, the factor on every load at which the first ply fails; null when no face reaches the criterion")
    ply: int = Field(description="The failing ply, 1 at the bottom face")
    angle_deg: float
    face: Literal["bottom", "top"]
    z_m: float = Field(description="z of the failing face, positive upward from the mid-plane")
    mode: str = Field(description="The governing maximum-stress or maximum-strain mode, or 'interactive' for Tsai-Hill and Tsai-Wu")
    failure_loads: LoadInput = Field(description="R times the request's loads, N/m and N*m/m")


class NotComputedOutput(Contract):
    criterion: Literal["max_stress", "max_strain", "tsai_hill", "tsai_wu"]
    reason: str


class FirstPlyFailureOutput(Contract):
    """First-ply failure under the request's loads by every criterion the inputs support (ADR-0059, ADR-0021).

    evaluated is false, with the reason, when every load is zero or a ply's material has no strengths. A criterion
    the inputs cannot support (maximum strain without strain limits, Tsai-Wu without f12_star) is listed under
    not_computed with the engine's message; nothing is assumed.
    """

    evaluated: bool
    reason: str | None
    criteria: list[CriterionOutput]
    not_computed: list[NotComputedOutput]

    @classmethod
    def of(cls, summary: FailureSummary) -> "FirstPlyFailureOutput":
        return cls(evaluated=bool(summary.evaluated), reason=summary.reason,
                   criteria=[CriterionOutput(criterion=r.criterion, strength_ratio=None if r.strength_ratio is None else float(r.strength_ratio),
                                             ply=int(r.ply_number), angle_deg=float(r.angle_deg), face=r.face, z_m=float(r.z_m), mode=r.mode,
                                             failure_loads=LoadInput(**{k: float(v) for k, v in r.failure_loads.model_dump().items()}))
                             for r in summary.results],
                   not_computed=[NotComputedOutput(criterion=n.criterion, reason=n.reason) for n in summary.not_computed])


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
    summary: LaminateSummaryOutput | None = Field(default=None, description="The stack described before any load (ADR-0059)")
    first_ply_failure: FirstPlyFailureOutput | None = Field(default=None, description="First-ply failure under the request's loads (ADR-0059)")


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
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


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
    # The workspace project the job is run for (ADR-0062 part 6): its row lists the job; unknown or not the requester's, it is ignored.
    project_id: Annotated[str, Field(pattern=UUID_PATTERN)] | None = None

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
        return {**source, "run_by": self.run_by, "replace": self.replace, "pdf": self.pdf, "theory": self.theory,
                **({"project_id": self.project_id} if self.project_id is not None else {})}

    def options(self) -> list[str]:
        """The tool's options for this request."""
        return ["--run-by", self.run_by, *(["--replace"] if self.replace else []), *([] if self.pdf else ["--no-pdf"]),
                *([] if self.theory else ["--no-theory"])]


class JobAnswer(Contract):
    """A done run's answer in a few values (ADR-0109), as the fea package wrote it: on the gauge section or the whole model, by the
    criterion that governs, whether a ply fails at the applied loading, the factor on that loading at first-ply failure, and the ply."""

    basis: Literal["gauge", "whole"]
    criterion: str
    fails: bool
    factor: float
    ply: int
    angle: float
    face: str | None = None


class CouponJobOutput(Contract):
    """A coupon job as it stands (ADR-0050). `outputs` are paths from the repository root, by key: the files made so far while it
    runs (ADR-0051), every file once it is done; `stage` is the step the tool is at and `stages_done` the steps behind it;
    `run_id` names the job's receipt once it has ended (null while it runs, or when recording is switched off). With the job queue
    (ADR-0056 amendment 3) a job is `queued` until a solver takes it up, its message saying what it waits for. `result` is the
    result's one line as soon as the solve and the CalculiX record are done, while the job still draws and builds the package
    (ADR-0064); `documents` is then "building", and once the job is done "written" or what is missing and why."""

    job_id: str
    state: Literal["queued", "running", "done", "stopped", "refused"]
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
    project_id: str | None = None  # the workspace project it was started for (ADR-0062 part 6)
    result: str | None = None
    documents: str | None = None
    claimed_at: str | None = None  # when a solver took the queued job up (ADR-0056 amendment 6)
    timings: dict[str, float] = {}  # the seconds of each stage of the tool and of the solver's phases around it, as far as the job got
    answer: JobAnswer | None = None  # a done run's answer in a few values, for the list of past analyses (ADR-0109); null when it kept none
    # the report asked for after the run (ADR-0064 amendment 3): "writing" while its PDF is typeset, "failed" when the last try did not
    # write it, null otherwise; once written it is the output `document`
    report: Literal["writing", "failed"] | None = None

    @classmethod
    def of(cls, job) -> "CouponJobOutput":
        outcome = job.outcome or {}
        progress = job.progress() or {}
        outputs = outcome.get("outputs") if outcome else progress.get("outputs", {})
        if outcome:
            result = (outcome.get("result") or outcome.get("message")) if outcome.get("status") == "done" else None
            documents = outcome.get("documents")
        else:
            result = progress.get("result")
            documents = None if result is None else "building"
        return cls(job_id=str(job.id), state=job.state, actor=job.actor, started_at=job.started_at.isoformat(), user_email=job.user_email,
                   finished_at=None if job.finished_at is None else job.finished_at.isoformat(), coupon=outcome.get("coupon") or progress.get("coupon"),
                   attempt=outcome.get("attempt") or progress.get("attempt"), message=outcome.get("message") if outcome else (result or progress.get("message")),
                   result=result, documents=documents,
                   stage=progress.get("stage"),
                   stages_done=list(progress.get("done", [])), stages=list(progress.get("stages", [])), outputs=outputs or {},
                   run_id=None if job.run_id is None else str(job.run_id), log_tail=job.log_tail(),
                   project_id=None if getattr(job, "project_id", None) is None else str(job.project_id),
                   claimed_at=None if getattr(job, "claimed_at", None) is None else job.claimed_at.isoformat(),
                   timings=job.all_timings() if hasattr(job, "all_timings") else {},
                   answer=job.answer() if hasattr(job, "answer") else None, report=getattr(job, "report", None))


class CouponCheckReceipt(Contract):
    """What the run record keeps of a check: the values' digest and version, never the rows (the team's own constants stay with the coupon)."""

    values: dict[str, str | int]
    project_id: str | None = None


class CouponCheckRequest(Contract):
    """The studio's setup check (ADR-0051): the form's rows as one JSON object, judged without a run; `project_id` names the workspace
    project to write the derived designation back to (ADR-0062 part 6)."""

    values: dict[str, Any]
    project_id: Annotated[str, Field(pattern=UUID_PATTERN)] | None = None

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
                                          "form_version": str(self.values.get("form_version", "")), "rows": len(self.values)},
                                  **({"project_id": self.project_id} if self.project_id is not None else {}))


ModelProgram = Literal["abaqus", "ansys"]  # the programs a model is written for on request (ADR-0129)


class CouponModelReceipt(Contract):
    """What the run record keeps of a model written as a file (ADR-0129): the values' digest and version, and the program asked for."""

    values: dict[str, str | int]
    program: str
    project_id: str | None = None


class CouponCheckResponse(Contract):
    """What the check found: the checklist as fea/src/anisotropy_fea/checks.py writes it, and the model to draw when the inputs build
    one. Recorded as a run, since it reaches the engine (ADR-0026)."""

    run_id: str | None
    state: Literal["ready", "blocked"]
    designation: str | None
    checklist: dict[str, Any]
    preview: dict[str, Any] | None


class LiveSolveResponse(Contract):
    """The live solve (ADR-0086): the setup check and, when nothing blocks, our kernel's fields with the answer (ADR-0085) and their
    explanation, as the fea package wrote them; a preview, with no mesh study and no CalculiX. `fields`, `explanation` and `preview` are
    null when nothing was solved or drawn. `seconds` is the API's, from the request to the files read; `timings` the tool's stages."""

    run_id: str | None
    state: str
    designation: str | None
    solver: str
    warm: bool
    seconds: float
    timings: dict[str, float]
    checklist: dict[str, Any]
    preview: dict[str, Any] | None
    fields: dict[str, Any] | None
    explanation: dict[str, Any] | None


ModelUnits = Literal["mm-MPa", "m-Pa", "in-psi", "in-ksi"]  # the systems a model may be stated in (fea/src/anisotropy_fea/units.py)


class ImportedModelReceipt(Contract):
    """What the run record keeps of a model brought in as a deck (ADR-0105): its name, its size and digest and the units stated,
    never the deck."""

    name: str
    units: ModelUnits
    bytes: int
    sha256: str


class ImportedModelResponse(Contract):
    """A model brought in as an Abaqus deck (ADR-0105), as the fea package answered it. `state` is `refused` (outside what the reader
    takes, or the units; `problem` says why and on which line), `read` (taken, but our kernel could not solve it as it stands;
    `problem` says why) or `solved`. `reading` is what the reader took and skipped; `preview` the model to draw; `fields` and
    `explanation` the kernel's answer (ADR-0085), a preview with no mesh study and no CalculiX. Nothing of the deck is kept."""

    run_id: str | None
    state: Literal["refused", "read", "solved"]
    name: str
    units: str
    solver: str
    warm: bool
    seconds: float
    timings: dict[str, float]
    problem: dict[str, Any] | None
    reading: dict[str, Any] | None
    preview: dict[str, Any] | None
    fields: dict[str, Any] | None
    explanation: dict[str, Any] | None


class TowTestRequest(CouponCheckRequest):
    """A fibre tow record under ASTM D4018 (ADR-0074): the tow test's rows and its specimens as one JSON object, the way the studio states
    them; `test` is "fibre tow tension". The record keeps the values' digest, as a check does, never the rows."""


class TowTestResponse(Contract):
    """What the tow record gives: its checklist as fea/src/anisotropy_fea/tow_test.py writes it and, when nothing blocks, the result: the
    fibre's area, each specimen's strength and chord modulus, their statistics, the planning loads and, under the standard, each clause
    judged. Every number is the engine's (anisotropy_engine.tow). Recorded as a run (ADR-0026)."""

    run_id: str | None
    state: Literal["ready", "blocked"]
    checklist: dict[str, Any]
    result: dict[str, Any] | None


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


class Quantity(Contract):
    """A value with the unit it was typed in (ADR-0060). The engine converts it with its unit table; the browser never does."""

    value: FiniteFloat
    unit: Annotated[str, Field(min_length=1, pattern=r"\S")]


class OwnMaterial(Contract):
    """Elastic constants typed by the engineer, each with its unit, and the five strengths together or none (ADR-0003)."""

    name: Annotated[str, Field(min_length=1, pattern=r"\S")]
    E1: Quantity
    E2: Quantity
    G12: Quantity
    nu12: FiniteFloat
    F1t: Quantity | None = None
    F1c: Quantity | None = None
    F2t: Quantity | None = None
    F2c: Quantity | None = None
    F6: Quantity | None = None
    source: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = Field(default=None, description="Where the numbers come from, when stated")
    strain_limits: Literal["from-strengths"] | None = Field(
        default=None, description="Ask for maximum strain with limits derived from the strengths (strength divided by modulus, linear to failure, ADR-0021)")
    alpha1: Quantity | None = Field(default=None, description="Thermal expansion along the fibres, with its unit (1/degC, 1/K, 1/degF or their 1e-6 forms)")
    alpha2: Quantity | None = Field(default=None, description="Thermal expansion across the fibres; alpha1 and alpha2 come together or not at all")

    @model_validator(mode="after")
    def _alphas_together(self) -> Self:
        if (self.alpha1 is None) != (self.alpha2 is None):
            raise ValueError("give alpha1 and alpha2 together, or neither")
        return self

    @model_validator(mode="after")
    def all_five_strengths_or_none(self) -> Self:
        given = [name for name in ("F1t", "F1c", "F2t", "F2c", "F6") if getattr(self, name) is not None]
        if given and len(given) != 5:
            raise ValueError(f"give all five strengths (F1t, F1c, F2t, F2c, F6) or none; got {', '.join(given)}")
        if self.strain_limits is not None and not given:
            raise ValueError('strain_limits = "from-strengths" needs all five strengths (F1t, F1c, F2t, F2c, F6)')
        return self


class LibraryChoice(Contract):
    """A material of the cited library by its id, and a dataset when not the primary one (ADR-0020)."""

    library: Annotated[str, Field(min_length=1, pattern=r"\S")]
    dataset: Annotated[str, Field(min_length=1, pattern=r"\S")] | None = None
    strain_limits: Literal["from-strengths"] | None = Field(
        default=None, description="Ask for maximum strain with limits derived from the dataset's strengths (ADR-0021)")


def _problem_material_kind(value) -> str:
    if isinstance(value, (OwnMaterial, LibraryChoice)):
        return "library" if isinstance(value, LibraryChoice) else "own"
    return "library" if isinstance(value, dict) and "library" in value else "own"


ProblemMaterial = Annotated[
    Annotated[OwnMaterial, Tag("own")] | Annotated[LibraryChoice, Tag("library")],
    Discriminator(_problem_material_kind),
]


class ProblemLoads(Contract):
    """The six resultants per unit width, each with its unit; every one is required, zeros stated (ADR-0003)."""

    Nx: Quantity
    Ny: Quantity
    Nxy: Quantity
    Mx: Quantity
    My: Quantity
    Mxy: Quantity


ReportUnits = Literal["SI", "mm-MPa", "US", "psi"]
assert set(ReportUnits.__args__) == set(UNIT_SYSTEMS), "the reporting systems are the engine's"  # noqa: S101


class LaminateProblem(Contract):
    """A laminate problem as the chat states it (ADR-0060): the material, the stack as angles from the bottom face up (ADR-0004),
    one ply thickness unless the library dataset records it, the six loads, Tsai-Wu's f12* when wanted, and the units to report in.
    Every value carries its own unit; the API converts it with the engine's table and solves the case the engine's runner solves."""

    title: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    material: ProblemMaterial
    layup: Annotated[list[FiniteFloat], Field(min_length=1, max_length=64)] = Field(description="Ply angles in degrees, bottom face first")
    layup_notation: Annotated[str, Field(min_length=1, max_length=120)] | None = Field(default=None, description="The notation typed, for the record")
    ply_thickness: Quantity | None = None
    loads: ProblemLoads
    f12_star: FiniteFloat | None = None
    delta_T: Quantity | None = Field(default=None, description="A uniform temperature change, with its unit (degC, K or degF); the material "
                                     "needs alpha1 and alpha2. With loads, it is held and the loads scale to failure; alone, it scales itself")
    report_units: ReportUnits


class LaminateAnswer(Contract):
    """Everything the case determines, in the reporting system's units, with the stack described, the material cited when it came
    from the library, and the explanation (ADR-0052: the template's sentences, or a model's rewording with every number checked).

    `case` is the case the engine solved, every input in the reporting units, for inspection. `results` is keyed as
    engine/validation/README.md lists the case runner's results. run_id is the record of this run (ADR-0026); null only when
    recording is switched off."""

    run_id: str | None
    engine_version: str
    report_units: ReportUnits
    units: dict[str, str] = Field(description="The unit of each reported kind: modulus, stress, length, N, M, kappa, A, B, D, areal_mass")
    case: dict[str, Any]
    results: dict[str, Any]
    criteria: list[str]
    summary: LaminateSummaryOutput
    material: MaterialProvenance | None
    writer: str
    model: str | None
    prose: list[str]
    withheld: bool
    reason: str | None
    facts: dict[str, Any]


Key = Annotated[str, Field(min_length=1, max_length=48, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")]
ShortText = Annotated[str, Field(min_length=1, max_length=200)]
Dimension = Literal["pressure", "length", "force_per_length", "moment_per_length", "temperature_change", "expansion"]
CouponUnit = Literal["m", "cm", "mm", "in", "N", "kN", "lbf", "kip", "Pa", "kPa", "MPa", "GPa", "psi", "ksi", "Msi"]


class OfferedChoice(Contract):
    value: ShortText
    label: ShortText


class OfferedRow(Contract):
    """A row the page offers a message to fill (ADR-0088): a number, a choice, a notation or a ply's angle. A coupon's number names the unit
    it is stated in, and a value written in another unit of the same system is converted to it; a laminate's number names the dimension of
    its units, and the value keeps the unit written (the engine converts, ADR-0060). A pure number names neither. An angle is in degrees,
    from -90 to 90 (ADR-0121 amendment 5)."""

    key: Key
    label: ShortText
    kind: Literal["number", "choice", "notation", "angle"]
    unit: CouponUnit | None = None
    dimension: Dimension | None = None
    choices: Annotated[list[OfferedChoice], Field(min_length=1, max_length=120)] | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.kind == "choice" and not self.choices:
            raise ValueError(f"{self.key}: a choice row lists its choices")
        if self.kind != "choice" and self.choices is not None:
            raise ValueError(f"{self.key}: only a choice row lists choices")
        if self.kind != "number" and (self.unit or self.dimension):
            raise ValueError(f"{self.key}: only a number carries a unit")
        if self.unit and self.dimension:
            raise ValueError(f"{self.key}: a row names its unit (a coupon) or its dimension (a laminate), not both")
        return self


class OfferedCondition(Contract):
    id: Key
    title: ShortText
    detail: Annotated[str, Field(max_length=400)] = ""


PlateRegion = Literal["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Hole", "Face", "Tab-Bottom", "Tab-Top"]
PLATE_REGION_KINDS: dict[str, str] = {"Edge-Bottom": "edge", "Edge-Top": "edge", "Edge-Left": "edge", "Edge-Right": "edge", "Hole": "edge",
                                      "Face": "area", "Tab-Bottom": "area", "Tab-Top": "area"}


class OfferedRegion(Contract):
    name: PlateRegion
    kind: Literal["edge", "area"]


class PlateOffer(Contract):
    """A plate's regions offered to a message (ADR-0101): the plate's own named regions (never a box the engineer drew and named), those
    the clicked element belongs to, the units a force and a pressure are stated in, and which regions are already held and loaded."""

    regions: Annotated[list[OfferedRegion], Field(min_length=1, max_length=8)]
    here: Annotated[list[PlateRegion], Field(max_length=8)] = []
    force_unit: Literal["N", "lbf"]
    stress_unit: Literal["MPa", "psi"]
    held: Annotated[list[PlateRegion], Field(max_length=8)] = []
    loaded: Annotated[list[PlateRegion], Field(max_length=8)] = []

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        names = [region.name for region in self.regions]
        if len(set(names)) != len(names):
            raise ValueError("each region is offered once")
        for region in self.regions:
            if PLATE_REGION_KINDS[region.name] != region.kind:
                raise ValueError(f"{region.name} is an {PLATE_REGION_KINDS[region.name]}, not an {region.kind}")
        for name in self.here:
            if name not in names:
                raise ValueError(f"{name} is clicked and not offered: a clicked region is one of those on offer")
        if (self.force_unit == "N") != (self.stress_unit == "MPa"):
            raise ValueError("a plate's force and pressure are stated in one system: N with MPa, or lbf with psi")
        return self


class ProposalRequest(Contract):
    """A message to read into rows (ADR-0088): the product, the message, the rows and conditions on offer, and the rows already filled.
    The model sees these, with every name, note and source taken out (R-11); never a file, a deck or a result. A plate adds its regions
    and the place clicked (ADR-0101)."""

    product: Literal["coupon", "laminate"]
    message: Annotated[str, Field(min_length=1, max_length=2000)]
    rows: Annotated[list[OfferedRow], Field(min_length=1, max_length=200)]
    conditions: Annotated[list[OfferedCondition], Field(max_length=20)] = []
    form: Annotated[dict[str, Annotated[str, Field(max_length=400)]], Field(max_length=400)] = {}
    plate: PlateOffer | None = None

    @model_validator(mode="after")
    def _distinct(self) -> Self:
        keys = [row.key for row in self.rows]
        if self.plate is not None and self.product != "coupon":
            raise ValueError("only a coupon's message offers a plate's regions")
        if len(set(keys)) != len(keys):
            raise ValueError("each row is offered once")
        return self


class Proposal(Contract):
    """A value the engineer wrote, for a row the page offered: as the row takes it (`value`, `unit`), as written, and the words it came from."""

    key: str
    label: str
    value: str
    unit: str | None
    written_value: str
    written_unit: str | None
    quote: str


class ConditionProposal(Contract):
    id: str
    title: str
    quote: str


class DroppedProposal(Contract):
    key: str
    reason: str


class SupportProposal(Contract):
    """A support the engineer's words or click hold (ADR-0101): the region and the plate's directions it holds, 1 to 6."""

    region: PlateRegion
    dofs: list[int]
    quote: str


class LoadProposal(Contract):
    """A load the engineer's words or click hold (ADR-0101): a force along a direction (1 to 3), the total over the region, or a pressure
    on an area; the value as the plate takes it, signed, and as written. `sense` says a force was stated as tension or compression, so
    its direction and sign came from the edge."""

    region: PlateRegion
    kind: Literal["force", "pressure"]
    dof: int | None
    value: str
    unit: str
    written_value: str
    written_unit: str | None
    sense: Literal["tension", "compression", "as_signed"] | None
    quote: str


class UnreadPart(Contract):
    """Words of the message the model proposed nothing for, and why, by name (ADR-0088 amendment 1). The words are the engineer's own."""

    quote: str
    reason: Literal["not_offered", "no_value", "refers_back"]


class ProposalResponse(Contract):
    """What the model read and the source guard kept (ADR-0088), for the engineer to tick; nothing here has entered the problem. `writer` is
    `template` when no model read the message, with the reason when one was asked; the page then reads it with its own patterns."""

    run_id: str | None
    writer: str
    model: str | None
    proposals: list[Proposal]
    conditions: list[ConditionProposal]
    question: str | None
    dropped: list[DroppedProposal]
    reason: str | None
    unread: list[UnreadPart] = []
    supports: list[SupportProposal] = []
    loads: list[LoadProposal] = []


ResultQuantity = Literal["S11", "S22", "S12", "Mises", "Tresca", "Max. Principal", "Mid. Principal", "Min. Principal", "Pressure", "E11", "E22", "E12"]


class OfferedPly(Contract):
    ply: Annotated[int, Field(ge=1, le=200)]
    angle: Annotated[float, Field(ge=-360, le=360)]


class ResultQuestionRequest(Contract):
    """A message to read as a question about a result (ADR-0100): the message and what it may name, the quantities of the page's probe
    table, the plies from the bottom face with their angles, whether the model has a gauge section, and whether an element is clicked.
    The model sees these and never a result, a file, a name or a note (R-11)."""

    message: Annotated[str, Field(min_length=1, max_length=2000)]
    quantities: Annotated[list[ResultQuantity], Field(min_length=1, max_length=12)]
    plies: Annotated[list[OfferedPly], Field(min_length=1, max_length=200)]
    gauge: bool
    picked: bool

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        if len(set(self.quantities)) != len(self.quantities):
            raise ValueError("each quantity is offered once")
        if [p.ply for p in self.plies] != list(range(1, len(self.plies) + 1)):
            raise ValueError("the plies are numbered from 1, bottom face first")
        return self


class ResultRequest(Contract):
    """What a message asks of the results, as the guard kept it: names from the offer and whole numbers, no value of a result. `values`
    reads the quantities at an element (its number, or the clicked one when `here`); `extreme` finds where they are largest, smallest or
    largest in magnitude over a region. Empty `plies` is every ply. `failure` (ADR-0100 amendment 1) asks which ply fails first or whether
    the coupon fails: it names nothing, and the page answers with the first-ply failure the package wrote."""

    kind: Literal["values", "extreme", "failure"]
    quantities: list[ResultQuantity]
    plies: list[int]
    element: int | None
    here: bool
    sense: Literal["largest", "smallest", "magnitude"] | None
    region: Literal["default", "gauge", "whole"]


class ResultQuestionResponse(Contract):
    """The model's reading of a question about a result, as the guard kept it (ADR-0100); the page looks the values up. `request` is null
    when the message asks nothing of the results or the reading did not stand (`dropped` says why); `writer` is `template` when no model
    read the message, with the reason when one was asked."""

    run_id: str | None
    writer: str
    model: str | None
    request: ResultRequest | None
    question: str | None
    dropped: list[str]
    reason: str | None


FactValue = bool | int | float | str | None | list[bool | int | float | str | None]
MAX_FACTS_CHARS = 40_000


class ResultAnswerRequest(Contract):
    """A question to answer in words about a result (ADR-0102): the question, and the fact sheet of the result the page shows, the
    numbers our engine computed for it (a job's `explanation.json`, or a live solve's). The model sees the sheet without a name, a note,
    a date or a record name (R-11), beside the theory sections the question finds."""

    question: Annotated[str, Field(min_length=1, max_length=2000)]
    facts: Annotated[dict[str, FactValue], Field(min_length=1, max_length=400)]

    @model_validator(mode="after")
    def _a_sheet_not_a_file(self) -> Self:
        if len(json.dumps(self.facts, ensure_ascii=False)) > MAX_FACTS_CHARS:
            raise ValueError(f"the fact sheet is longer than {MAX_FACTS_CHARS} characters")
        return self


class ResultAnswerReceipt(Contract):
    """What the run record keeps of an answer: the question, the digest of the facts the writer saw, and the sections found."""

    question: str
    facts_sha256: str
    sections: list[str]


class TheorySource(Contract):
    """A section of our theory pages, as an answer names it."""

    id: str
    document: str
    title: str


class GeneralQuestionRequest(Contract):
    """A question asked in the FEA section before anything is set up (ADR-0124): the question, and the kinds of work the page offers to
    set up, which the model may name. No result, no rows and no name go with it."""

    question: Annotated[str, Field(min_length=1, max_length=2000)]
    kinds: Annotated[list[Literal["coupon", "wing"]], Field(max_length=4)] = []


class GeneralAnswerResponse(Contract):
    """An answer in words to a question asked before a setup (ADR-0124). `prose` is the model's, kept only when every number in it is the
    question's; `sources` are the theory sections it rests on, or with no prose the sections found. `start` is a kind of work the
    question asks to set up, from those offered, which the page offers as a button; null when it names none."""

    run_id: str | None
    writer: str
    model: str | None
    prose: list[str]
    sources: list[TheorySource]
    covered: bool
    withheld: bool
    reason: str | None
    start: str | None


class ResultAnswerResponse(Contract):
    """An answer in words to a question about a result (ADR-0102). `prose` is the model's, kept only when every number in it is the fact
    sheet's or the question's; `sources` are the theory sections it rests on. With no model, or an answer the guard set aside
    (`withheld`), `prose` is empty and `sources` are the sections the question found, so the page can say where to read. `covered` is
    false when the sections do not hold the reason asked for."""

    run_id: str | None
    writer: str
    model: str | None
    prose: list[str]
    sources: list[TheorySource]
    covered: bool
    withheld: bool
    reason: str | None


class TheorySectionsRequest(Contract):
    """A question whose words find sections of our theory pages (ADR-0107): the question alone, no result with it."""

    question: Annotated[str, Field(min_length=1, max_length=2000)]
    limit: Annotated[int, Field(ge=1, le=5)] = 3
    # what the question is about: a coupon's result searches the theory pages as before; a wing searches the wing's theory and the three
    # reference pages of design rules, test methods and allowables (ADR-0127, ADR-0128); a repair searches the repair's theory and the page
    # "Bonded repairs" (ADR-0136)
    about: Literal["coupon", "wing", "repair"] = "coupon"


class TheorySection(Contract):
    """A section of our theory pages with its own text, as a reader is handed it: without the lines that pair equations with functions."""

    id: str
    document: str
    title: str
    text: str


class TheorySectionsResponse(Contract):
    """The sections a question's words find, best first (ADR-0107); none when no word of the question is in any section."""

    run_id: str | None
    sections: list[TheorySection]


class CouponTests(Contract):
    """Whether every coupon test is offered here (ADR-0089): the page asks once, and with no answer offers the unnotched tension
    coupon only, the list its form definition carries. `imports`: whether a model may be brought in as a file (ADR-0105), which a
    founder's sign-in is offered where the tests are not (ADR-0089 amendment 6). `plates`: whether a plate may be set up on the model tree,
    held and loaded on any edge or face (ADR-0089 amendment 7), offered where the import is."""

    all: bool
    imports: bool = False
    plates: bool = False
    ansys_model: bool = False  # whether the model may be downloaded as an Ansys file (ADR-0129): everyone's since amendment 3


class AssistantInfo(Contract):
    """Whether a model reads messages here (ADR-0088): the page asks once, and with none it reads with its own patterns. `checked`: whether
    the model is one the real-model Assistant check has been run with (ADR-0121 amendment 8); null with no model."""

    proposes: bool
    provider: str | None
    model: str | None
    checked: bool | None = None


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


PROJECT_KINDS = ("fea", "laminate")


class ProjectInput(Contract):
    """A workspace project as the page states it (ADR-0062 part 6): its kind, its name, its content as one JSON object (a coupon's rows
    and a plate's lists, a laminate problem's draft, or a wing's description under `wing`, ADR-0122), and the form version and unit
    system the content was stated in. The API keeps it; the fea package judges a coupon's rows at check time (ADR-0051). PUT
    /v1/projects/{id} creates or replaces it."""

    kind: Literal["fea", "laminate", "wing"]
    name: Annotated[str, Field(max_length=200)] = ""
    content: dict[str, Any]
    form_version: Annotated[str, Field(max_length=20)] | None = None
    units: Annotated[str, Field(max_length=20)] | None = None

    @model_validator(mode="after")
    def not_empty(self) -> Self:
        if not self.content:
            raise ValueError("content must hold the project as the page states it; the object is empty")
        if self.kind == "wing" and not isinstance(self.content.get("wing"), dict):
            raise ValueError("a wing project's content holds the wing's description as an object under `wing` (ADR-0122)")
        size = len(json.dumps(self.content, ensure_ascii=False).encode("utf-8"))
        if size > VALUES_LIMIT_BYTES:
            raise ValueError(f"the content is {size} bytes; a project's rows are far below {VALUES_LIMIT_BYTES}")
        return self


class ProjectRename(Contract):
    name: Annotated[str, Field(max_length=200)]


class ProjectJobOutput(Contract):
    """A job of a project, as its row stands: enough to list it and open it by its id. `queued` until a solver takes it, on the hosted
    tier (ADR-0056 amendment 3); a project read while one of its jobs waited failed before ADR-0122 found it."""

    job_id: str
    state: Literal["queued", "running", "done", "stopped", "refused"]
    coupon: str | None
    attempt: str | None
    message: str | None
    started_at: str
    finished_at: str | None
    run_id: str | None

    @classmethod
    def of(cls, row) -> "ProjectJobOutput":
        return cls(job_id=str(row.id), state=row.state, coupon=row.coupon, attempt=row.attempt, message=row.message, started_at=row.started_at.isoformat(),
                   finished_at=None if row.finished_at is None else row.finished_at.isoformat(), run_id=None if row.run_id is None else str(row.run_id))


class ProjectOutput(Contract):
    """A project as the API keeps it (ADR-0062 part 6), with its jobs when read by its id."""

    id: str
    kind: Literal["fea", "laminate", "wing"]
    name: str
    actor: str
    user_email: str | None
    content: dict[str, Any]
    form_version: str | None
    units: str | None
    designation: str | None
    last_check_run_id: str | None
    created_at: str
    updated_at: str
    jobs: list[ProjectJobOutput] = []

    @classmethod
    def of(cls, row, jobs=()) -> "ProjectOutput":
        return cls(id=str(row.id), kind=row.kind, name=row.name, actor=row.actor, user_email=row.user_email, content=dict(row.content),
                   form_version=row.form_version, units=row.units, designation=row.designation,
                   last_check_run_id=None if row.last_check_run_id is None else str(row.last_check_run_id),
                   created_at=row.created_at.isoformat(), updated_at=row.updated_at.isoformat(), jobs=[ProjectJobOutput.of(job) for job in jobs])


class CouponValuesOutput(Contract):
    """A coupon's rows as the values object the studio edits (ADR-0051): the inverse of the form's reading."""

    name: str
    values: dict[str, Any]


class UploadTokenInput(Contract):
    """A token for the connector (ADR-0094 part 6): the name its owner tells it from the others by, such as the machine it is for."""

    name: Annotated[str, Field(max_length=100)] = ""


class UploadTokenOutput(Contract):
    """A token as the API keeps it: never the token itself, only its last characters."""

    id: str
    name: str
    hint: str
    created_at: str
    last_used_at: str | None
    revoked_at: str | None

    @classmethod
    def of(cls, row) -> "UploadTokenOutput":
        return cls(id=str(row.id), name=row.name, hint=row.hint, created_at=row.created_at.isoformat(),
                   last_used_at=None if row.last_used_at is None else row.last_used_at.isoformat(),
                   revoked_at=None if row.revoked_at is None else row.revoked_at.isoformat())


class UploadTokenCreated(UploadTokenOutput):
    """A token just created, with the token itself: shown this once and never again, because only its SHA-256 is kept."""

    token: str

    @classmethod
    def with_token(cls, row, token: str) -> "UploadTokenCreated":
        return cls(**UploadTokenOutput.of(row).model_dump(), token=token)


class PairingCode(Contract):
    """A one-time code that connects a machine to the requester's account (ADR-0094 amendment 1): in this answer and nowhere else,
    good for `minutes` and for one swap."""

    code: str
    expires_at: str
    minutes: int


class PairInput(Contract):
    """What a machine sends to be connected: the code its user's page handed it, and the name the token will carry. With `look`,
    nothing is swapped: the answer says whose account the code is for, so the machine can ask its user first."""

    code: Annotated[str, Field(min_length=20, max_length=200)]
    name: Annotated[str, Field(max_length=100)] = ""
    look: bool = False


class Paired(Contract):
    """The answer to a machine: whose account it is (`owner`: the signed-in email, or the local actor) and, once swapped, the upload
    token, shown this once."""

    owner: str
    token: str | None = None
    token_id: str | None = None
    name: str | None = None


class AbaqusExchange(Contract):
    """What the page's card needs to know before it offers anything (ADR-0094 step 6): whether this API keeps uploads at all, whether
    the connector's own route can be reached with an upload token (always without a sign-in in front; behind Cloudflare Access only
    when the setting opens it), and the limits a person meets."""

    uploads: bool
    connector_route: bool
    max_bundle_bytes: int
    max_uploads: int
    max_tokens: int
    connector_version: str | None = None  # the connector this API hands out, and the SHA-256 recorded for that version's zip (amendment 3)
    connector_sha256: str | None = None


class UploadDocument(Contract):
    """The document of an upload's comparison, written and kept (ADR-0094 step 7). The page asks for this first, so that it can say
    that the document is being written, and then follows the link to the file under `filename`."""

    upload_id: str
    compared_at: str
    filename: str


class UploadOutput(Contract):
    """An upload from Abaqus as the API keeps it (ADR-0094 part 6): whose it is, the bundle's identity, what the check found in it, and,
    once it stood beside a run of ours, that job with the verdict and the comparison as `fea/tools/abaqus_upload.py compare` wrote it.
    `not_compared` says why no comparison was made. A list leaves `facts` and `comparison` out; read the upload by its id for them."""

    id: str
    actor: str
    user_email: str | None
    token_id: str | None
    created_at: str
    bundle_sha256: str
    bundle_bytes: int
    units: str
    job: str | None
    coupon: str | None
    in_scope: bool
    may_train: bool
    job_id: str | None
    verdict: Literal["agrees", "differs", "incomplete", "refused"] | None
    compared_at: str | None
    not_compared: str | None
    facts: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None

    @classmethod
    def of(cls, row, full: bool = True) -> "UploadOutput":
        return cls(id=str(row.id), actor=row.actor, user_email=row.user_email, token_id=None if row.token_id is None else str(row.token_id),
                   created_at=row.created_at.isoformat(), bundle_sha256=row.bundle_sha256, bundle_bytes=row.bundle_bytes, units=row.units, job=row.job,
                   coupon=row.coupon, in_scope=row.in_scope, may_train=row.may_train, job_id=None if row.job_id is None else str(row.job_id),
                   verdict=row.verdict, compared_at=None if row.compared_at is None else row.compared_at.isoformat(), not_compared=row.not_compared,
                   facts=dict(row.facts) if full else None, comparison=dict(row.comparison) if full and row.comparison is not None else None)


class WingRequest(Contract):
    """A wing to work by hand (ADR-0115, ADR-0118): its description as the JSON object of a wing file, or the file's TOML text, in
    the file's own units. The engine reads it with the same rules as a file on disk and refuses anything unknown or missing."""

    wing: dict[str, Any] | None = None
    toml: Annotated[str, Field(min_length=1, max_length=200_000)] | None = None

    @model_validator(mode="after")
    def exactly_one_form(self) -> Self:
        if (self.wing is None) == (self.toml is None):
            raise ValueError("Give exactly one of wing (a JSON object) or toml (the wing file's text)")
        return self


class WingCheckRequest(WingRequest):
    """A wing's finite element check (ADR-0119): the wing as for its hand calculation, and the wing project it is run for (ADR-0122),
    whose row then lists the check; a project unknown or not the requester's is ignored, so a wing the browser alone knows still runs."""

    project_id: Annotated[str, Field(pattern=UUID_PATTERN)] | None = None


class WingChangeRequest(WingRequest):
    """A change of plies to preview on a wing (ADR-0128): the wing as for its hand calculation, and the change, plies of one angle added to
    or taken from one part over a stretch of the half span. The wing sent is never kept or changed."""

    change: PlyChange


class WingChangePreview(Contract):
    """A change worked before it is applied (ADR-0128): the change in one sentence, the wing file it gives, the summary of the wing as it is
    and as changed (the passes, the lowest margin and where, each check's lowest margin, mass, tip deflection and first bending frequency,
    in the file's units), and the design rules of the part changed. Applying it is the engineer's tap on the page."""

    run_id: str | None = None
    engine_version: str
    change: dict[str, Any]
    words: str
    wing: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]
    units: dict[str, Any]
    rules: list[dict[str, Any]]


class WingAnswer(Contract):
    """The hand calculation of a wing (ADR-0118): the description as the engine read it, the results in the file's units as
    `wing_report` gives them, and what a page draws (`wing_views`)."""

    run_id: str | None = None
    engine_version: str
    wing: dict[str, Any]
    report: dict[str, Any]
    views: dict[str, Any]


class WingCheckOutput(Contract):
    """A wing's finite element check as it stands (ADR-0119): `queued` until a solver takes it, `running` with its stage (build, solve,
    modes), then `done` with the check's report in the wing file's units, `refused` with the reason the description cannot be checked,
    or `stopped` with what to do. `message` is shown as it is; the causes of a stop stay in the log."""

    job_id: str
    state: Literal["queued", "running", "done", "stopped", "refused"]
    wing: str | None = None
    started_at: str
    finished_at: str | None = None
    stage: str | None = None
    stages_done: list[str] = []
    stages: list[str] = []
    message: str | None = None
    run_id: str | None = None
    report: dict[str, Any] | None = None


class WingShapeAnswer(Contract):
    """A wing's shape for a CAD program (ADR-0116, ADR-0118): its STEP file's text, in millimetres with every part named, and the
    part table in the wing file's units: each part's layup, the thickness to thicken it to, its area and mass."""

    run_id: str | None = None
    step: str
    parts: dict[str, Any]



class RepairRequest(Contract):
    """A stepped patch repair to work (ADR-0131, ADR-0135): its description as the JSON object of a repair file, or the file's TOML
    text, in the file's own units. The engine reads it with the same rules as a file on disk and refuses anything unknown or missing."""

    repair: dict[str, Any] | None = None
    toml: Annotated[str, Field(min_length=1, max_length=200_000)] | None = None

    @model_validator(mode="after")
    def exactly_one_form(self) -> Self:
        if (self.repair is None) == (self.toml is None):
            raise ValueError("Give exactly one of repair (a JSON object) or toml (the repair file's text)")
        return self


class RepairSolveRequest(RepairRequest):
    """A repair whose slice is to be solved (ADR-0132, ADR-0135): the repair as for its hand calculation, and whether the adhesive on the
    cut faces of a flush repair carries load (`bonded`) or nothing (`open`, ADR-0132's choice unless said)."""

    cut_faces: Literal["open", "bonded"] = "open"


class RepairAnswer(Contract):
    """The hand calculation of a repair (ADR-0135): the description as the engine read it, what it works out to in the file's units as
    `repair_report` gives it (sizes, the slice's rectangles, areas, volumes, the lap and its answer), what a page draws beside the
    rectangles (`repair_views`), what a solve of the slice still needs (`solve_needs`, empty when it can be solved) and what following
    the bond until it lets go still needs (`bond_needs`, ADR-0140)."""

    run_id: str | None = None
    engine_version: str
    repair: dict[str, Any]
    report: dict[str, Any]
    views: dict[str, Any]
    needs: list[dict[str, str]]
    bond_needs: list[dict[str, str]] = []


class RepairSolveAnswer(Contract):
    """A repair's slice solved (ADR-0132, ADR-0135): `slice_report` in the file's units (the model and its checks, the bondline's
    stresses, the forces along the slice and at the lap's boundaries beside the hand calculation, the plies, what reaches its limit
    first) and the solve in one line."""

    run_id: str | None = None
    headline: str
    report: dict[str, Any]


class RepairBondAnswer(Contract):
    """A repair's bond followed until it lets go (ADR-0140): `bond_report` in the file's units (the model and its checks, the bond's
    law, the load at which the bond first softens and where, the load at which it lets go with the bond's state there, and the curve
    of the load against the movement of the panel's end) and the run in one line."""

    run_id: str | None = None
    headline: str
    report: dict[str, Any]


class RepairChangeRequest(RepairRequest):
    """A change to preview on a repair (ADR-0136): the repair as for its hand calculation, and one change: a quantity set to a value,
    in the unit as written, or steps added, removed or regrouped. The repair sent is never kept or changed."""

    change: RepairChange


class RepairChangePreview(Contract):
    """A change worked before it is applied (ADR-0136): the change in one sentence, the repair file it gives, and the summary of the
    repair as it is and as changed (its steps, its width, the largest bondline shear and where, the load at the adhesive's elastic
    limit), in the file's units. Applying it is the engineer's tap on the page."""

    run_id: str | None = None
    engine_version: str
    change: dict[str, Any]
    words: str
    repair: dict[str, Any]
    before: dict[str, Any]
    after: dict[str, Any]
    units: dict[str, Any]


class RepairSweepRequest(RepairRequest):
    """One quantity of a repair to sweep (ADR-0136): the repair as for its hand calculation, the sweep (the quantity, optionally its
    range and a load the adhesive is to stay elastic at), whether a pick is then solved as a slice (`confirm`), and how that slice's
    cut faces are taken (as `/v1/repairs/solve`)."""

    sweep: RepairSweep
    confirm: bool = True
    cut_faces: Literal["open", "bonded"] = "open"


class RepairSweepAnswer(Contract):
    """A sweep's answer (ADR-0136), as `sweep_repair` gives it in the file's units: a row for every value (the repair's width, the
    largest shear and where, the load at the adhesive's elastic limit, or the refusal of that value), the pick's row index and its
    repair file when a load was named, from which value the limit load no longer changes, the sweep in sentences (`words`) and the one or two of them that are its answer
    (`answer`: the pick, or that there is none, or with no load named where the curve goes flat). `check` is
    what a solved slice of the pick says (`pick_check`), or why it was not solved; null with no pick or with `confirm` false."""

    run_id: str | None = None
    engine_version: str
    sweep: dict[str, Any]
    quantity: dict[str, Any]
    units: dict[str, Any]
    load: float
    target: float | None
    rows: list[dict[str, Any]]
    pick: int | None
    picked: dict[str, Any] | None
    flat_from: dict[str, Any] | None
    most: dict[str, Any] | None
    words: list[str]
    answer: list[str]
    cautions: list[str]
    check: dict[str, Any] | None = None


class RepairShapeAnswer(Contract):
    """A repair's solids for a CAD program (ADR-0131, ADR-0135): its STEP file's text, in millimetres with every solid named, and the
    table of the solids: each one's name, kind, ply angle and volume."""

    run_id: str | None = None
    step: str
    parts: dict[str, Any]
