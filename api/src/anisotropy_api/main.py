"""A synchronous local API. It adapts HTTP to the engine and to our coupon tool; it contains no laminate math."""

import datetime as dt
import math
import tomllib
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import Annotated, TypeVar

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from anisotropy_engine.cases import compare, engine_results, solve_case, validate_case_inputs
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.library import library_material, list_datasets
from anisotropy_engine.response import midplane_response, prescribed_curvature_response

from .coupon_jobs import CouponJobs, Job, JobBusy, JobRefused, RecordingFailed, runner_command
from .records import ACTORS, STATUSES, check_ready, connect, fetch_run, git_commit, list_runs, record_run
from .settings import load_settings
from .schemas import (
    AnalysisRequest, AnalysisResponse, CaseRequest, CaseResponse, ComparisonOutput, CouponJobOutput, CouponJobRequest,
    LibraryMaterialInput, MaterialProvenance, PrescribedCurvatureRequest, PrescribedCurvatureResponse, RunOutput, RunSummary,
    VerificationResponse,
)

RUN_ID_HEADER = "X-Anisotropy-Run-Id"
COUPON_JOBS = "/v1/coupon-jobs"


def job_recorder(app: FastAPI):
    """The receipt of an ended coupon job, written as every run is (ADR-0026): solved with the tool's outcome, or rejected with
    its message."""
    def record(job: Job, state: str, outcome: dict) -> uuid.UUID | None:
        engine = getattr(app.state, "records", None)
        if engine is None:
            return None
        try:
            return record_run(engine, actor=job.actor, endpoint=COUPON_JOBS, inputs=job.inputs, engine_version=version("anisotropy-engine"),
                              api_version=version("anisotropy-api"), git_commit=getattr(app.state, "git_commit", None),
                              response={**outcome, "job_id": str(job.id)} if state == "done" else None,
                              error=None if state == "done" else outcome["message"])
        except SQLAlchemyError as exc:
            raise RecordingFailed(str(exc).splitlines()[0]) from exc
    return record


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Read the configuration once and refuse to serve without the run records database (ADR-0026)."""
    settings = load_settings()
    app.state.settings = settings
    app.state.git_commit = git_commit()
    app.state.records = connect(settings.database_url) if settings.run_records else None
    if app.state.records is not None:
        check_ready(app.state.records)
    app.state.coupon_jobs = CouponJobs(runner_command(), job_recorder(app))
    yield
    if app.state.records is not None:
        app.state.records.dispose()
        app.state.records = None


app = FastAPI(
    title="Anisotropy engine API",
    version=version("anisotropy-api"),
    description="Local development: one-material laminate stiffness and deformation in SI base units.",
    lifespan=lifespan,
)

# Only the local website origins used by this development project may read API responses.
# This browser policy is not authentication; deployment remains a separate future task.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://127.0.0.1:3000",
        "http://localhost:3001", "http://127.0.0.1:3001",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Anisotropy-Actor"],
    expose_headers=[RUN_ID_HEADER, "Location"],
    allow_credentials=False,
)


@app.exception_handler(RequestValidationError)
async def invalid_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return field locations and reasons without echoing malformed/non-finite input."""
    return JSONResponse(status_code=422, content={
        "detail": [
            {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ],
    })


def resolve_material(choice) -> tuple[object, MaterialProvenance | None]:
    """Explicit constants are used as given; a library choice is resolved and cited (ADR-0020)."""
    if isinstance(choice, LibraryMaterialInput):
        resolved = choice.resolve()
        return resolved.lamina, MaterialProvenance.of(resolved)
    return choice.to_engine(), None


def _json_value(value):
    """Engine results as JSON: numpy scalars and arrays to numbers and lists, non-finite to null."""
    if isinstance(value, np.ndarray):
        return [_json_value(v) for v in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    number = float(value)
    return number if math.isfinite(number) else None


def actor_from_header(x_anisotropy_actor: Annotated[str | None, Header()] = None) -> str:
    """Who sent the request (ADR-0026): a required header naming one of the known clients."""
    if x_anisotropy_actor not in ACTORS:
        raise HTTPException(status_code=422, detail=(
            f"Header X-Anisotropy-Actor is required and must be one of {', '.join(ACTORS)}; got {x_anisotropy_actor!r}"
        ))
    return x_anisotropy_actor


Actor = Annotated[str, Depends(actor_from_header)]


def _record(request: Request, actor: str, problem: BaseModel, *, response: dict | None = None,
            error: str | None = None) -> uuid.UUID | None:
    """Write the run and return its id; None when recording is switched off.

    `inputs` is the request as received: only the fields the client sent. When the row cannot be
    written the result is withheld (503) rather than returned without a receipt, the same policy
    as refusing to start (ADR-0026).
    """
    engine = getattr(request.app.state, "records", None)
    if engine is None:
        return None
    try:
        return record_run(engine, actor=actor, endpoint=request.url.path,
                          inputs=problem.model_dump(mode="json", exclude_unset=True),
                          engine_version=version("anisotropy-engine"), api_version=version("anisotropy-api"),
                          git_commit=getattr(request.app.state, "git_commit", None), response=response, error=error)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=(
            f"The result was not returned because it could not be recorded: {str(exc).splitlines()[0]}"
        )) from exc


def _run_header(run_id: uuid.UUID | None) -> dict[str, str] | None:
    return None if run_id is None else {RUN_ID_HEADER: str(run_id)}


Body = TypeVar("Body", bound=BaseModel)


def _deliver(request: Request, response: Response, actor: str, problem: BaseModel, compute: Callable[[], Body]) -> Body:
    """Compute, record the outcome, and attach the run id (ADR-0026).

    A 422 raised while computing is recorded as a rejection and re-raised with the run id in its
    header; a successful body is recorded as returned, without run_id, and returned with it.
    """
    try:
        body = compute()
    except HTTPException as exc:
        if exc.status_code != 422:
            raise
        run_id = _record(request, actor, problem, error=str(exc.detail))
        raise HTTPException(status_code=422, detail=exc.detail, headers=_run_header(run_id)) from exc
    run_id = _record(request, actor, problem, response=body.model_dump(mode="json", exclude={"run_id"}))
    if run_id is None:
        return body
    response.headers[RUN_ID_HEADER] = str(run_id)
    return body.model_copy(update={"run_id": str(run_id)})


@app.post("/v1/cases/solve", response_model=CaseResponse)
def solve_case_endpoint(problem: CaseRequest, actor: Actor, request: Request, response: Response) -> CaseResponse:
    """Solve a problem written in the engine's case format and return every result it determines.

    One endpoint for everything the calculator does: stiffness, any of the seven applied forms
    including mixed conditions and a temperature change, library materials, several materials,
    first-ply failure by every criterion the inputs allow, plate buckling, and the answer-key
    comparison when the case carries [expected]. Validation and calculation happen in the engine.
    Every request that reaches the engine is recorded with its actor, solved or rejected, and the
    record's id comes back as run_id and in the X-Anisotropy-Run-Id header (ADR-0026).
    """
    def compute() -> CaseResponse:
        try:
            case = tomllib.loads(problem.toml) if problem.toml is not None else problem.case
            validate_case_inputs(case)
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                solution = solve_case(case)
                results = engine_results(case)
                comparisons, problems = compare(case) if "expected" in case else ([], [])
        except (ValueError, TypeError, KeyError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
            message = f"toml: {exc}" if isinstance(exc, tomllib.TOMLDecodeError) else (str(exc) or exc.__class__.__name__)
            raise HTTPException(status_code=422, detail=message) from exc
        return CaseResponse(
            run_id=None, engine_version=version("anisotropy-engine"), units=case["units"], title=case.get("title"),
            results={key: _json_value(value) for key, (value, _scale) in results.items()},
            criteria=[key.removeprefix("fpf_ratio_") for key in results if key.startswith("fpf_ratio_")],
            materials={name: MaterialProvenance.of(item) for name, item in solution.library.items()},
            comparison=[ComparisonOutput(key=c.key, expected=float(c.expected), engine=float(c.engine), allowed=float(c.allowed), agrees=c.agrees)
                        for c in comparisons] if "expected" in case else None,
            problems=problems,
        )

    return _deliver(request, response, actor, problem, compute)


def _records_engine(request: Request):
    """The connection pool, or 503 when recording is switched off: there is nothing to read."""
    engine = getattr(request.app.state, "records", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="Run records are switched off (ANISOTROPY_RUN_RECORDS=off); there is nothing to read")
    return engine


def _aware(name: str, moment: dt.datetime | None) -> dt.datetime | None:
    """A time filter must carry its offset; a naive time would be guessed (ADR-0003)."""
    if moment is not None and moment.tzinfo is None:
        raise HTTPException(status_code=422, detail=f"{name} must include a timezone offset, e.g. 2026-10-14T00:00:00Z")
    return moment


@app.get("/v1/runs", response_model=list[RunSummary])
def list_runs_endpoint(
    request: Request,
    actor: str | None = None, endpoint: str | None = None, status: str | None = None,
    since: dt.datetime | None = None, until: dt.datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[RunSummary]:
    """The newest runs first, narrowed by actor, endpoint, status and time (ADR-0026).

    `since` is inclusive and `until` exclusive, both with a timezone offset. An unknown actor or
    status is refused rather than answered with an empty list.
    """
    engine = _records_engine(request)
    if actor is not None and actor not in ACTORS:
        raise HTTPException(status_code=422, detail=f"actor must be one of {', '.join(ACTORS)}; got {actor!r}")
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {', '.join(STATUSES)}; got {status!r}")
    try:
        runs = list_runs(engine, actor=actor, endpoint=endpoint, status=status,
                         since=_aware("since", since), until=_aware("until", until), limit=limit)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"The run records database did not answer: {str(exc).splitlines()[0]}") from exc
    return [RunSummary.of(run) for run in runs]


@app.get("/v1/runs/{run_id}", response_model=RunOutput)
def run_detail(run_id: uuid.UUID, request: Request) -> RunOutput:
    """One run record as stored (ADR-0026)."""
    engine = _records_engine(request)
    try:
        run = fetch_run(engine, run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"The run records database did not answer: {str(exc).splitlines()[0]}") from exc
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run {run_id}")
    return RunOutput.of(run)


def _coupon_jobs(request: Request) -> CouponJobs:
    jobs = getattr(request.app.state, "coupon_jobs", None)
    if jobs is None:
        raise HTTPException(status_code=503, detail="Coupon jobs are not set up: the API was started without its startup step")
    return jobs


def _known_job(jobs: CouponJobs, job_id: uuid.UUID) -> Job:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=(
            f"No coupon job {job_id} in this API process; jobs are kept in memory until it stops, and every job that ended has "
            f"its receipt in GET /v1/runs?endpoint={COUPON_JOBS}"))
    return job


@app.post(COUPON_JOBS, status_code=202, response_model=CouponJobOutput)
def start_coupon_job(job_request: CouponJobRequest, actor: Actor, request: Request, response: Response) -> CouponJobOutput:
    """Start a coupon job (ADR-0050): fea/tools/run_coupon.py takes a filled-in input form, or a coupon that has its specs, to the
    coupon's package, in the background. One job runs at a time; another is refused with 409 while it runs. Poll the job at the
    Location header until its state is no longer running; its receipt is a run record written when it ends (ADR-0026).
    """
    jobs = _coupon_jobs(request)
    form = None if job_request.coupon is not None else (job_request.form_name, job_request.form_bytes())
    try:
        job = jobs.start(actor, job_request.recorded_inputs(), job_request.options(), form=form, coupon=job_request.coupon)
    except JobBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response.headers["Location"] = f"{COUPON_JOBS}/{job.id}"
    with jobs.lock:
        return CouponJobOutput.of(job)


@app.get(COUPON_JOBS + "/{job_id}", response_model=CouponJobOutput)
def coupon_job(job_id: uuid.UUID, request: Request) -> CouponJobOutput:
    """A coupon job as it stands: its state, the end of its console, and once it is done the files it made (ADR-0050)."""
    jobs = _coupon_jobs(request)
    job = _known_job(jobs, job_id)
    with jobs.lock:
        return CouponJobOutput.of(job)


@app.get(COUPON_JOBS + "/{job_id}/package")
def coupon_job_package(job_id: uuid.UUID, request: Request) -> FileResponse:
    """The package of a job that is done, as a zip: the document, the decks, the material, the results and the audit form."""
    jobs = _coupon_jobs(request)
    job = _known_job(jobs, job_id)
    with jobs.lock:
        state, outcome = job.state, job.outcome
    if state != "done":
        raise HTTPException(status_code=409, detail=f"coupon job {job_id} is {state}" + ("" if outcome is None else f": {outcome['message']}"))
    try:
        archive = jobs.package_archive(job)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(archive, media_type="application/zip", filename=archive.name)


@app.get("/v1/materials")
def list_materials() -> list[dict]:
    """Every library dataset, and whether it has the elastic inputs an analysis needs."""
    return list_datasets()


@app.get("/v1/materials/{material_id}", response_model=MaterialProvenance)
def material_detail(material_id: str, dataset: str | None = None) -> MaterialProvenance:
    """The SI values the engine would use for a dataset, each with its page."""
    try:
        return MaterialProvenance.of(library_material(material_id, dataset))
    except ValueError as error:
        message = str(error)
        raise HTTPException(status_code=404 if message.startswith("unknown library material") or "has no dataset" in message else 422,
                            detail=message) from None


@app.post("/v1/laminates/response", response_model=AnalysisResponse)
def analyze_laminate(problem: AnalysisRequest, actor: Actor, request: Request, response: Response) -> AnalysisResponse:
    """Validate a problem, call existing stiffness/response functions, and serialize their output.

    Recorded with its actor like every analysis (ADR-0026); the website calculator sends `calculator`.
    """
    def compute() -> AnalysisResponse:
        material, provenance = resolve_material(problem.material)
        plies = [Ply(material=material, **ply.model_dump()) for ply in problem.plies]
        try:
            # Floating-point overflow/invalid operations must become errors, never JSON null/NaN.
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                A, B, D = abd_matrices(plies)
                eps0, kappa = midplane_response(plies, problem.loads.to_engine())
            if not all(np.isfinite(value).all() for value in (A, B, D, eps0, kappa)):
                raise FloatingPointError("Non-finite solver output")
        except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="These inputs do not produce a finite, solvable laminate response. Check values and units.",
            ) from exc
        return AnalysisResponse(material_provenance=provenance,
            engine_version=version("anisotropy-engine"),
            inputs=problem,
            A_N_per_m=A.tolist(), B_N=B.tolist(), D_N_m=D.tolist(),
            midplane_strain=eps0.tolist(), curvature_per_m=kappa.tolist(),
        )

    return _deliver(request, response, actor, problem, compute)


@app.post("/v1/laminates/prescribed-curvature", response_model=PrescribedCurvatureResponse)
def analyze_prescribed_curvature(problem: PrescribedCurvatureRequest, actor: Actor, request: Request,
                                 response: Response) -> PrescribedCurvatureResponse:
    """Find required moments from explicit force resultants and a curvature constraint.

    Set all curvatures to zero for a flat laminate. This is a local constitutive
    calculation, not a displacement boundary-value problem or fixture design.
    Unknown moments must be omitted, not sent as zero or null. All calculation
    and numerical verification happen in the engine. Recorded with its actor (ADR-0026).
    """
    def compute() -> PrescribedCurvatureResponse:
        material = resolve_material(problem.material)[0]
        plies = [Ply(material=material, **ply.model_dump()) for ply in problem.plies]
        try:
            result = prescribed_curvature_response(
                plies, [problem.forces.Nx, problem.forces.Ny, problem.forces.Nxy],
                problem.prescribed_curvature_per_m,
            )
        except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as exc:
            raise HTTPException(
                status_code=422,
                detail="These inputs do not produce a finite, numerically verified prescribed-curvature response. Check values, units and conditioning.",
            ) from exc
        check = result.verification
        return PrescribedCurvatureResponse(material_provenance=resolve_material(problem.material)[1],
            analysis_type="prescribed_curvature", engine_version=version("anisotropy-engine"), inputs=problem,
            A_N_per_m=result.A.tolist(), B_N=result.B.tolist(), D_N_m=result.D.tolist(),
            midplane_strain=result.midplane_strain.tolist(), moments_N_m_per_m=result.moments.tolist(),
            verification=VerificationResponse(
                passed=check.passed, recovered_midplane_strain=check.recovered_strain.tolist(),
                recovered_curvature_per_m=check.recovered_curvature.tolist(),
                strain_residual=check.strain_residual.tolist(), curvature_residual_per_m=check.curvature_residual.tolist(),
                strain_allowed_error=check.strain_allowed_error.tolist(),
                curvature_allowed_error_per_m=check.curvature_allowed_error.tolist(),
            ),
        )

    return _deliver(request, response, actor, problem, compute)
