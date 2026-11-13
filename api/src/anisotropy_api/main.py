"""A synchronous local API. It adapts HTTP to the engine and to our coupon tool; it contains no laminate math."""

import datetime as dt
import hashlib
import json
import math
import tempfile
import tomllib
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, TypeVar

import numpy as np
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

from anisotropy_engine.cases import compare, engine_results, first_ply_failures, solve_case, validate_case_inputs
from anisotropy_engine.laminate import Ply, abd_matrices
from anisotropy_engine.library import library_material, list_datasets
from anisotropy_engine.response import midplane_response, prescribed_curvature_response
from anisotropy_engine.summary import first_ply_failure_summary, laminate_summary

from .access import CONNECTOR_UPLOADS, AccessMiddleware
from .access import verifier as access_verifier
from .assistant import TemplateAssistant, assistant_for
from .laminate_problems import case_of, facts_of, sentences_of, unit_labels
from .proposals import model_view_of_form, source_guard
from .live import LiveBusy, LiveRefused, LiveSolver, LiveTimedOut
from .coupon_jobs import (FILE_ALIASES, LOCAL_FEA, NEUTRAL_DECKS, CheckTimedOut, CouponJobs, Job, JobBusy, JobLimited, JobRefused, NotOffered, RecordingFailed,
                          SolverBusy, UnknownCoupon, neutral_deck, runner_command, studio_command)
from .records import (ACTORS, STATUSES, KindChanged, ProjectTaken, check_ready, connect, count_uploads, delete_upload, fetch_project, fetch_run, fetch_upload,
                      git_commit, insert_upload, insert_upload_token, latest_done_job, list_projects, list_runs, list_upload_tokens, list_uploads,
                      live_upload_tokens, owns_project, project_jobs, record_run, revoke_upload_token, stop_orphans, update_project, update_upload,
                      upsert_project, use_upload_token)
from .settings import all_tests, allowed_origins, docs_urls, environment, load_settings
from .storage import (UPLOAD_DOCUMENT, FolderStore, R2Store, content_type, download_name, restore, sync, upload_document_key, upload_key,
                      upload_prefix)
from .uploads import (LOCAL_UPLOADS, MAX_BUNDLE_BYTES, MAX_TOKENS, MAX_UPLOADS, NotCompared, ToolFailed, UploadRefused, Uploads, bearer, new_token, ours_of,
                      token_digest)
from .uploads import tool_command as upload_command
from .schemas import (
    AbaqusExchange, AnalysisRequest, AnalysisResponse, AssistantInfo, CaseRequest, CouponTests, CaseResponse, ComparisonOutput, CouponCheckRequest, CouponCheckResponse, CouponJobOutput,
    LiveSolveResponse, TowTestRequest, TowTestResponse,
    CouponJobRequest, CouponSummary, CouponValuesOutput, ExplainReceipt, ExplainRequest, ExplainResponse, FirstPlyFailureOutput, LaminateAnswer,
    LaminateProblem,
    LaminateSummaryOutput, LibraryMaterialInput, MaterialProvenance, PrescribedCurvatureRequest, PrescribedCurvatureResponse, ProjectInput, ProjectOutput,
    ProjectRename, ProposalRequest, ProposalResponse, RunOutput, RunSummary, UploadDocument, UploadOutput, UploadTokenCreated, UploadTokenInput, UploadTokenOutput,
    VerificationResponse,
)

RUN_ID_HEADER = "X-Anisotropy-Run-Id"
# "off" on the 503 of an API that keeps no records, so the page tells "this server keeps no projects" from an outage (ADR-0091 amendment 2)
RECORDS_HEADER = "X-Anisotropy-Records"
# With the job queue (ADR-0056 amendment 3), a queued job's answer carries its id here; the Worker sends the id to the queue and
# drops the header, so a browser never sees it.
ENQUEUE_HEADER = "X-Anisotropy-Enqueue"
COUPON_JOBS = "/v1/coupon-jobs"
SOLVER_JOBS = "/v1/solver/jobs"  # a solver container's own routes, which only its Durable Object reaches (worker/index.ts)
PROJECTS = "/v1/projects"
UPLOADS = "/v1/abaqus-uploads"  # the uploads from Abaqus, each its owner's alone (ADR-0094 part 6)
UPLOAD_TOKENS = "/v1/upload-tokens"  # what the connector sends with
ABAQUS_EXCHANGE = "/v1/abaqus-exchange"  # what the page's card may offer here (step 6)
ABAQUS_CONNECTOR = "/v1/abaqus-connector"  # the connector's files as one zip


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
                              error=None if state == "done" else outcome["message"], user_email=job.user_email)
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
    # Durable outputs (ADR-0050 amendment 2): with an object store named, the coupons come back from it before any job runs, and
    # every done job's files go to it; with the database, the jobs table keeps each job's status, and the jobs a stopped process
    # never saw end are marked so.
    # With the job queue (ADR-0056 amendment 3) the jobs run in solver containers: the API's container keeps its coupons level
    # with the store (`sync`) and leaves the running rows to their solvers' heartbeats; a solver fetches the coupons per job.
    store = R2Store(settings.storage) if settings.storage.on else None
    role = settings.job_role
    if store is not None and role != "solver":
        files, coupons = (sync if role == "queue" else restore)(store, LOCAL_FEA)
        print(f"restored {files} file(s) of {coupons} coupon(s) from the bucket {settings.storage.bucket}", flush=True)
    if app.state.records is not None and role is None:
        orphans = stop_orphans(app.state.records, "the API stopped while this job ran, so it did not finish; start it again")
        if orphans:
            print(f"marked {orphans} job(s) of a stopped process as stopped", flush=True)
    app.state.coupon_jobs = CouponJobs(runner_command(), job_recorder(app), studio=studio_command(), store=store, table=app.state.records,
                                       per_day=settings.jobs_per_user_per_day if role != "solver" else None, role=role)
    app.state.assistant = assistant_for(settings.assistant.provider, settings.assistant.model)  # the template unless a provider is named (ADR-0052)
    # our kernel's answer to every edit (ADR-0086): warm workers, started on the first live request
    app.state.live = LiveSolver(studio_command(), Path(tempfile.gettempdir()) / "anisotropy-live", settings.live_workers)
    # The uploads from Abaqus (ADR-0094 part 6): in the bucket under their own prefix, or in a folder of the local disk without one.
    app.state.uploads = Uploads(store if store is not None else FolderStore(LOCAL_UPLOADS), upload_command(), founders=settings.founder_emails)
    # Behind Cloudflare Access, every request but /healthz must carry a valid token (ADR-0056); None means no sign-in, the local API.
    # The connector's one route passes on its upload token alone only when the settings say so (ADR-0094 step 5).
    app.state.connector_uploads = settings.connector_uploads
    app.state.access_verifier = access_verifier(settings.access) if settings.access.on else None
    yield
    app.state.live.close()
    app.state.access_verifier = None
    app.state.connector_uploads = False
    if app.state.records is not None:
        app.state.records.dispose()
        app.state.records = None


app = FastAPI(
    title="Anisotropy engine API",
    version=version("anisotropy-api"),
    description="Composite laminate and coupon analysis: every number computed by the engine and the fea package.",
    lifespan=lifespan,
    **docs_urls(environment()),  # no /docs, /redoc or OpenAPI schema behind Access, the hosted tier (ADR-0091 amendment 2)
)

# The Access check sits inside the CORS layer (the last middleware added is the outermost), so a preflight is answered without a
# token and a refusal still carries the CORS headers the browser needs to show it (ADR-0056).
# A live solve's fields run to megabytes of JSON (ADR-0086): compressed for the browser that asks, innermost so Access and CORS see it whole.
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(AccessMiddleware)

# Only the website origins named in ANISOTROPY_ALLOWED_ORIGINS, or without it the local development origins, may read API
# responses from a browser. This browser policy is not authentication; sign-in is Cloudflare Access in front of the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(allowed_origins(environment())),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Anisotropy-Actor"],
    expose_headers=[RUN_ID_HEADER, RECORDS_HEADER, "Location"],
    allow_credentials=False,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Alive, without touching the database or any tool: what a platform polls to know the container answers (ADR-0056).
    Not a run, so no actor header and no run record."""
    return {"status": "ok"}


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


def actor_of_a_link(x_anisotropy_actor: Annotated[str | None, Header()] = None, actor: Annotated[str | None, Query()] = None) -> str:
    """The same for a route a page links to: a link carries no header, so there the actor may be named as `?actor=` instead."""
    return actor_from_header(x_anisotropy_actor if x_anisotropy_actor is not None else actor)


LinkActor = Annotated[str, Depends(actor_of_a_link)]


def _record(request: Request, actor: str, problem: BaseModel, *, response: dict | None = None,
            error: str | None = None, llm: tuple[str | None, str | None] = (None, None)) -> uuid.UUID | None:
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
                          git_commit=getattr(request.app.state, "git_commit", None), response=response, error=error,
                          llm_provider=llm[0], llm_model_version=llm[1], user_email=getattr(request.state, "user_email", None))
    except SQLAlchemyError as exc:
        print(f"a run of {request.url.path} could not be recorded: {str(exc).splitlines()[0]}", flush=True)  # the cause stays in the log
        raise HTTPException(status_code=503, detail="The result was not returned because it could not be recorded. Try again in a minute.") from exc


def _run_header(run_id: uuid.UUID | None) -> dict[str, str] | None:
    return None if run_id is None else {RUN_ID_HEADER: str(run_id)}


Body = TypeVar("Body", bound=BaseModel)


def _deliver(request: Request, response: Response, actor: str, problem: BaseModel, compute: Callable[[], Body],
             llm_of: Callable[[Body], tuple[str | None, str | None]] | None = None) -> Body:
    """Compute, record the outcome, and attach the run id (ADR-0026).

    A 422 raised while computing is recorded as a rejection and re-raised with the run id in its
    header; a successful body is recorded as returned, without run_id, and returned with it. `llm_of`
    names the language model whose draft the body holds, for the record (ADR-0052).
    """
    try:
        body = compute()
    except HTTPException as exc:
        if exc.status_code != 422:
            raise
        run_id = _record(request, actor, problem, error=str(exc.detail))
        raise HTTPException(status_code=422, detail=exc.detail, headers=_run_header(run_id)) from exc
    run_id = _record(request, actor, problem, response=body.model_dump(mode="json", exclude={"run_id"}),
                     llm=llm_of(body) if llm_of is not None else (None, None))
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
        raise HTTPException(status_code=503, detail="Records are switched off on this server, so there is nothing to read",
                            headers={RECORDS_HEADER: "off"})
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
        # not in this process, nor in the jobs table (none without records); a job that ended has its receipt among the runs
        raise HTTPException(status_code=404, detail="These results are no longer available. Run the analysis again from your project.")
    return job


@app.post(COUPON_JOBS, status_code=202, response_model=CouponJobOutput)
def start_coupon_job(job_request: CouponJobRequest, actor: Actor, request: Request, response: Response) -> CouponJobOutput:
    """Start a coupon job (ADR-0050): fea/tools/run_coupon.py takes a filled-in input form, the coupon's values as the studio sends
    them (ADR-0051), or a coupon that has its specs, to the coupon's package, in the background. One job runs at a time; another is
    refused with 409 while it runs. With the hosted tier's per-user limit set, a person's second running job or a job past the day's
    cap is refused with 429 and the reason (ADR-0056). Poll the job at the Location header until its state is neither queued nor
    running: its stage and the files made so far appear as it goes; its receipt is a run record written when it ends (ADR-0026).
    With the job queue (ADR-0056 amendment 3) the job is answered `queued`, many run at once, each in a solver container of its own,
    and the answer's X-Anisotropy-Enqueue header tells the Worker to queue it.
    """
    jobs = _coupon_jobs(request)
    form = (job_request.form_name, job_request.form_bytes()) if job_request.form_name is not None else None
    values = job_request.values_bytes() if job_request.values is not None else None
    project_id = _own_project_id(request, actor, job_request.project_id)
    try:
        job = jobs.start(actor, job_request.recorded_inputs(), job_request.options(), form=form, coupon=job_request.coupon, values=values,
                         user_email=getattr(request.state, "user_email", None), project_id=project_id)
    except JobBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobLimited as exc:  # the hosted tier's per-user limit (ADR-0056): the reason is what the studio shows
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except JobRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response.headers["Location"] = f"{COUPON_JOBS}/{job.id}"
    if job.state == "queued":
        response.headers[ENQUEUE_HEADER] = str(job.id)
    with jobs.lock:
        return CouponJobOutput.of(job)


def _solver_jobs(request: Request) -> CouponJobs:
    """The jobs of a solver container; 404 anywhere else, as if the route did not exist, since only the solver's Durable Object reaches it."""
    jobs = _coupon_jobs(request)
    if jobs.role != "solver":
        raise HTTPException(status_code=404, detail="Not Found")
    return jobs


@app.post(SOLVER_JOBS + "/{job_id}", response_model=CouponJobOutput)
def solve_queued_job(job_id: uuid.UUID, request: Request, response: Response) -> CouponJobOutput:
    """A solver container's start (ADR-0056 amendment 3): the queued job claimed and run here, 202. The job as it stands, 200, when
    this container has it already, running or ended; 409 when its row is not queued (another solver took it, it ended, or there is
    none), so the consumer lets the message go."""
    jobs = _solver_jobs(request)
    with jobs.lock:
        already = jobs.jobs.get(job_id)
        running_here = already is not None and already.state != "queued"
    try:
        job = jobs.take(job_id)
    except SolverBusy as exc:  # 423: the consumer tries the pool's next solver (ADR-0056 amendment 6)
        raise HTTPException(status_code=423, detail=str(exc)) from exc
    except JobRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    if job is None:
        raise HTTPException(status_code=409, detail=f"coupon job {job_id} is not queued: another solver took it, it ended, or there is none")
    response.status_code = 200 if running_here else 202
    with jobs.lock:
        return CouponJobOutput.of(job)


@app.get(SOLVER_JOBS + "/{job_id}", response_model=CouponJobOutput)
def solver_job(job_id: uuid.UUID, request: Request) -> CouponJobOutput:
    """The job as this solver container runs it: `running`, an ended state, or `queued` when it went back to the queue (another job
    holds its coupon). 404 when this container does not have it (a new container after the old one stopped)."""
    jobs = _solver_jobs(request)
    with jobs.lock:
        job = jobs.jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"this solver has no coupon job {job_id}")
        return CouponJobOutput.of(job)


@app.post(SOLVER_JOBS + "/{job_id}/stop", response_model=CouponJobOutput)
def stop_solver_job(job_id: uuid.UUID, request: Request, reason: Annotated[str, Query(min_length=1, max_length=300)]) -> CouponJobOutput:
    """The per-job timeout: the tool is killed and the job ends `stopped` with the reason the solver's timer gives (ADR-0056 amendment 4)."""
    jobs = _solver_jobs(request)
    job = jobs.stop(job_id, reason)
    if job is None:
        raise HTTPException(status_code=404, detail=f"this solver has no coupon job {job_id}")
    with jobs.lock:
        return CouponJobOutput.of(job)


@app.post(COUPON_JOBS + "/check", response_model=CouponCheckResponse)
def check_coupon_setup(problem: CouponCheckRequest, actor: Actor, request: Request, response: Response) -> CouponCheckResponse:
    """The studio's setup check (ADR-0051): the values judged as fea/tools/run_coupon.py would judge them, item by item, and the
    model to draw when they build one. Nothing is written to the coupons' folders. It reaches the engine, so it is recorded with
    its actor (ADR-0026); the studio tool answers within two minutes or the check is refused with 504.
    """
    jobs = _coupon_jobs(request)

    def compute() -> CouponCheckResponse:
        try:
            found = jobs.check(problem.values_bytes())
        except CheckTimedOut as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except JobRefused as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        checklist = found["checklist"]
        return CouponCheckResponse(run_id=None, state=checklist["state"], designation=checklist.get("designation"), checklist=checklist,
                                   preview=found["preview"])

    body = _deliver(request, response, actor, problem.receipt(), compute)
    if problem.project_id is not None:
        _note_check(request, actor, problem.project_id, body)
    return body


@app.post(COUPON_JOBS + "/live", response_model=None, responses={200: {"model": LiveSolveResponse}})
def live_solve(problem: CouponCheckRequest, actor: Actor, request: Request) -> Response:
    """Our kernel's answer to the rows as they stand (ADR-0086): the setup check and, when nothing blocks, the kernel's fields with
    the answer (ADR-0085) and the explanation, a preview with no mesh study, no CalculiX, no attempt and no document; the full run
    stays `POST /v1/coupon-jobs`. A warm worker answers a strip in under a second. Recorded with its actor (ADR-0026): the record
    keeps the check's state, the summary and the fields' SHA-256, never the arrays. The fields are passed on as the package wrote
    them. 429 when every live solver stays busy, 504 when one does not answer in time, 503 when none can run."""
    live: LiveSolver = request.app.state.live
    try:
        found = live.solve(problem.values_bytes())
    except LiveBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LiveTimedOut as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LiveRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    fields = found.raw.get("fields")
    designation = found.checklist.get("designation")
    run_id = _record(request, actor, problem.receipt(), response={
        "state": found.state, "designation": designation, "solver": "kernel", "warm": found.warm, "seconds": round(found.seconds, 3),
        "timings": found.timings, "summary": found.summary,
        "fields_sha256": hashlib.sha256(fields).hexdigest() if fields is not None else None})
    head = {"run_id": None if run_id is None else str(run_id), "state": found.state, "designation": designation, "solver": "kernel",
            "warm": found.warm, "seconds": round(found.seconds, 3), "timings": found.timings}
    parts = [json.dumps(head)[1:-1].encode("utf-8")]
    for name in ("checklist", "preview", "fields", "explanation"):
        parts.append(f'"{name}":'.encode("utf-8") + (found.raw[name].strip() if name in found.raw else b"null"))
    return Response(content=b"{" + b",".join(parts) + b"}", media_type="application/json", headers=_run_header(run_id))


@app.post("/v1/tow-tests", response_model=TowTestResponse)
def calculate_tow_test(problem: TowTestRequest, actor: Actor, request: Request, response: Response) -> TowTestResponse:
    """A fibre tow record under ASTM D4018 (ADR-0074): its rows and specimens read and refused by row, judged clause by clause against the
    standard when it names one, and reduced by the engine to each specimen's strength and chord modulus and their statistics, by
    fea/tools/studio_tool.py tow. It is answered at once: a tow has no model and no solver. Recorded with its actor (ADR-0026); the
    record keeps the values' digest. The studio tool answers within two minutes or the request is refused with 504.
    """
    jobs = _coupon_jobs(request)

    def compute() -> TowTestResponse:
        try:
            found = jobs.tow(problem.values_bytes())
        except CheckTimedOut as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except JobRefused as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        checklist = found["checklist"]
        return TowTestResponse(run_id=None, state=checklist["state"], checklist=checklist, result=found.get("result"))

    return _deliver(request, response, actor, problem.receipt(), compute)


# ----------------------------------------------------------------------------------------------- the projects (ADR-0062 part 6)

def _database_error(exc: SQLAlchemyError) -> HTTPException:
    print(f"the records did not answer: {str(exc).splitlines()[0]}", flush=True)  # the cause stays in the log, not in the answer
    return HTTPException(status_code=503, detail="Saved projects could not be read right now. Try again in a minute.")


def _own_project_id(request: Request, actor: str, project_id: str | None) -> uuid.UUID | None:
    """The project a check or a job names, when it is the requester's own; None otherwise (unknown, another's, or no records), so a
    project the browser alone knows never blocks a check or a run."""
    engine = getattr(request.app.state, "records", None)
    if engine is None or project_id is None:
        return None
    try:
        row = fetch_project(engine, uuid.UUID(project_id))
    except SQLAlchemyError:
        return None
    return row.id if row is not None and owns_project(row, actor, getattr(request.state, "user_email", None)) else None


def _note_check(request: Request, actor: str, project_id: str, body: CouponCheckResponse) -> None:
    """After a check: the designation the fea package derived and the check's run, written to the project (ADR-0062 part 6). A write
    that fails is printed, not raised: the check's answer is the engine's and stands."""
    found = _own_project_id(request, actor, project_id)
    if found is None:
        return
    try:
        update_project(request.app.state.records, found, designation=body.designation,
                       last_check_run_id=None if body.run_id is None else uuid.UUID(body.run_id), updated_at=dt.datetime.now(dt.timezone.utc))
    except (SQLAlchemyError, LookupError) as exc:
        print(f"the check of project {project_id} was not noted on it: {str(exc).splitlines()[0]}", flush=True)


def _requesters_project(request: Request, actor: str, project_id: uuid.UUID):
    """The project by its id, when it is the requester's; 404 otherwise, so no project is confirmed to a stranger."""
    engine = _records_engine(request)
    try:
        row = fetch_project(engine, project_id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    if row is None or not owns_project(row, actor, getattr(request.state, "user_email", None)):
        raise HTTPException(status_code=404, detail=f"No project {project_id} of yours")
    return engine, row


@app.get(PROJECTS, response_model=list[ProjectOutput])
def list_projects_endpoint(actor: Actor, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 50) -> list[ProjectOutput]:
    """The requester's workspace projects, the last changed first (ADR-0062 part 6): by signed-in email behind Cloudflare Access, by
    actor locally. 503 when run records are off: there is no table."""
    engine = _records_engine(request)
    try:
        rows = list_projects(engine, actor=actor, user_email=getattr(request.state, "user_email", None), limit=limit)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return [ProjectOutput.of(row) for row in rows]


@app.put(PROJECTS + "/{project_id}", response_model=ProjectOutput)
def put_project(project_id: uuid.UUID, project: ProjectInput, actor: Actor, request: Request, response: Response) -> ProjectOutput:
    """The project as the page states it now (ADR-0062 part 6): created with 201 when the id is new, replaced with 200 when it is the
    requester's own; 404 when it is someone else's, 409 when its kind would change."""
    engine = _records_engine(request)
    try:
        row, created = upsert_project(engine, project_id=project_id, kind=project.kind, name=project.name, actor=actor,
                                      user_email=getattr(request.state, "user_email", None), content=project.content, form_version=project.form_version,
                                      units=project.units, now=dt.datetime.now(dt.timezone.utc))
    except ProjectTaken:
        raise HTTPException(status_code=404, detail=f"No project {project_id} of yours") from None
    except KindChanged as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    response.status_code = 201 if created else 200
    return ProjectOutput.of(row)


@app.get(PROJECTS + "/{project_id}", response_model=ProjectOutput)
def project_detail(project_id: uuid.UUID, actor: Actor, request: Request) -> ProjectOutput:
    """One project with the jobs started for it, newest first (ADR-0062 part 6)."""
    engine, row = _requesters_project(request, actor, project_id)
    try:
        jobs = project_jobs(engine, row.id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return ProjectOutput.of(row, jobs)


@app.patch(PROJECTS + "/{project_id}", response_model=ProjectOutput)
def rename_project(project_id: uuid.UUID, change: ProjectRename, actor: Actor, request: Request) -> ProjectOutput:
    """A project's name (ADR-0062 part 6)."""
    engine, row = _requesters_project(request, actor, project_id)
    try:
        row = update_project(engine, row.id, name=change.name, updated_at=dt.datetime.now(dt.timezone.utc))
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return ProjectOutput.of(row)


# ----------------------------------------------------------------------------- the uploads from Abaqus (ADR-0094 part 6, step 5)

def _email(request: Request) -> str | None:
    return getattr(request.state, "user_email", None)


def _uploads(request: Request) -> Uploads:
    uploads = getattr(request.app.state, "uploads", None)
    if uploads is None:
        raise HTTPException(status_code=503, detail="Uploads are not set up: the API was started without its startup step")
    return uploads


@app.get(ABAQUS_EXCHANGE, response_model=AbaqusExchange)
def abaqus_exchange(request: Request) -> AbaqusExchange:
    """What the page's card may offer here (ADR-0094 step 6); the page asks once. `uploads` is false when run records are off, since
    an upload's row is where its owner is kept. `connector_route` says whether a bundle sent with an upload token alone arrives:
    with no sign-in in front of the API it does; behind Cloudflare Access only when ANISOTROPY_CONNECTOR_UPLOADS=on (the Access
    application must let the path through as well, which this API cannot see). Not a run: nothing is computed or recorded."""
    state = request.app.state
    behind_access = getattr(state, "access_verifier", None) is not None
    return AbaqusExchange(uploads=getattr(state, "records", None) is not None and getattr(state, "uploads", None) is not None,
                          connector_route=not behind_access or bool(getattr(state, "connector_uploads", False)),
                          max_bundle_bytes=MAX_BUNDLE_BYTES, max_uploads=MAX_UPLOADS, max_tokens=MAX_TOKENS)


@app.get(ABAQUS_CONNECTOR)
def abaqus_connector(request: Request) -> Response:
    """The connector as one zip (ADR-0094 step 6): the four files a user keeps in one folder and the note of its commands, written
    by `fea/tools/abaqus_upload.py connector`. The same for every requester; nothing of theirs is in it."""
    try:
        path = _uploads(request).connector()
    except ToolFailed as exc:
        raise HTTPException(status_code=503, detail=f"The connector could not be handed out: {exc}") from exc
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.post(UPLOAD_TOKENS, status_code=201, response_model=UploadTokenCreated)
def create_upload_token(wanted: UploadTokenInput, actor: Actor, request: Request) -> UploadTokenCreated:
    """A token for the connector (ADR-0094 part 6): what `anisotropy_connector.py --send` sends a bundle with, in the name of who
    created it. The token is in this answer and nowhere else: the API keeps its SHA-256 only. At most a few live tokens per person;
    cancel one to make another."""
    engine = _records_engine(request)
    token, digest, hint = new_token()
    try:
        if live_upload_tokens(engine, actor=actor, user_email=_email(request)) >= MAX_TOKENS:
            raise HTTPException(status_code=429, detail=f"You have {MAX_TOKENS} tokens that are not cancelled; cancel one to create another")
        row = insert_upload_token(engine, token_id=uuid.uuid4(), actor=actor, user_email=_email(request), name=wanted.name, token_sha256=digest,
                                  hint=hint, now=dt.datetime.now(dt.timezone.utc))
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return UploadTokenCreated.with_token(row, token)


@app.get(UPLOAD_TOKENS, response_model=list[UploadTokenOutput])
def list_upload_tokens_endpoint(actor: Actor, request: Request) -> list[UploadTokenOutput]:
    """The requester's tokens, newest first, the cancelled ones among them; never a token itself."""
    engine = _records_engine(request)
    try:
        rows = list_upload_tokens(engine, actor=actor, user_email=_email(request))
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return [UploadTokenOutput.of(row) for row in rows]


@app.delete(UPLOAD_TOKENS + "/{token_id}", response_model=UploadTokenOutput)
def cancel_upload_token(token_id: uuid.UUID, actor: Actor, request: Request) -> UploadTokenOutput:
    """Cancel a token: from now on a bundle sent with it is refused. Its row stays, so the uploads it sent still name it. 404 for a
    token that is not the requester's."""
    engine = _records_engine(request)
    try:
        row = revoke_upload_token(engine, token_id, actor=actor, user_email=_email(request), now=dt.datetime.now(dt.timezone.utc))
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail=f"No token {token_id} of yours")
    return UploadTokenOutput.of(row)


async def _read_bundle(request: Request) -> bytes:
    """The request's body, a bundle's zip as it is, refused past the size a bundle may have before more of it is read."""
    too_large = HTTPException(status_code=413, detail=f"A bundle is at most {MAX_BUNDLE_BYTES} bytes as sent")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_BUNDLE_BYTES:
        raise too_large
    received = bytearray()
    async for chunk in request.stream():
        received += chunk
        if len(received) > MAX_BUNDLE_BYTES:
            raise too_large
    if not received:
        raise HTTPException(status_code=422, detail="The request has no body: send the bundle's zip, <job>-anisotropy.zip, as the body")
    return bytes(received)


def _token_owner(request: Request, authorization: Annotated[str | None, Header()] = None):
    """Who the connector's request speaks for: the owner of the upload token it carries. 401 for no token, an unknown one or a
    cancelled one, in the same words, before any of the body is read."""
    engine = _records_engine(request)
    token = bearer(authorization)
    try:
        row = None if token is None else use_upload_token(engine, token_digest(token), dt.datetime.now(dt.timezone.utc))
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    if row is None:
        raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"}, detail=(
            "This route takes a bundle sent with an upload token, and the request carries none that stands: create one on the site and "
            "send it as  Authorization: Bearer <token>  (a cancelled token is refused)"))
    return row


async def _connector_bundle(request: Request, owner=Depends(_token_owner)):
    return owner, await _read_bundle(request)


def _requesters_upload(request: Request, actor: str, upload_id: uuid.UUID, *, reading: bool):
    """The upload by its id when it is the requester's; when only reading, also when the requester is a founder (ADR-0094 part 6). 404
    otherwise, so no upload is confirmed to a stranger."""
    engine = _records_engine(request)
    try:
        row = fetch_upload(engine, upload_id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    mine = row is not None and owns_project(row, actor, _email(request))
    if row is None or not (mine or (reading and _uploads(request).sees_all(_email(request)))):
        raise HTTPException(status_code=404, detail=f"No upload {upload_id} of yours")
    return engine, row


def _our_run(request: Request, row, job_id: uuid.UUID | None) -> Job:
    """The finished run of ours an upload stands beside: the job named, or, with none named, the owner's newest finished job of the
    coupon the bundle names. Raises `NotCompared` with the reason when there is none."""
    jobs = _coupon_jobs(request)
    if job_id is None:
        if not row.coupon:
            raise NotCompared("the bundle names no coupon of ours (the connector's --coupon) and no run was named: name one with job_id")
        found = latest_done_job(request.app.state.records, coupon=row.coupon, actor=row.actor, user_email=row.user_email)
        if found is None:
            raise NotCompared(f"you have no finished run of {row.coupon} here to stand beside it: run the coupon, or name a run with job_id")
        job_id = found.id
    job = jobs.get(job_id)
    if job is None:
        raise NotCompared(f"there is no coupon job {job_id}")
    if job.state != "done":
        raise NotCompared(f"coupon job {job_id} is {job.state}; an upload stands beside a run that is done")
    return job


def _compare_upload(request: Request, row, job_id: uuid.UUID | None, *, asked: bool):
    """Put the stored bundle beside a run of ours and write the job, the verdict and the comparison to its row. When no comparison
    can be made: at an upload (`asked` False) the row keeps the reason and the upload stands; when the owner asked for this comparison,
    the reason is the answer, 409 or 503, and the row keeps what it had."""
    uploads, engine = _uploads(request), request.app.state.records
    try:
        if not row.in_scope:
            raise NotCompared("the bundle is out of the comparison's scope; the upload's facts say what our reader did not take")
        job = _our_run(request, row, job_id)
        with uploads.folder() as folder:
            bundle = Path(folder) / "bundle.zip"
            try:
                uploads.store.get(row.object_key, bundle)
                ours, deck = ours_of(_coupon_jobs(request), job, Path(folder) / "ours")
            except NotCompared:
                raise
            except Exception as exc:  # the store's own errors or the disk's
                raise ToolFailed(f"the files could not be fetched: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}") from exc
            found = uploads.compare(bundle, ours, deck)
        found["compared_by"] = {"api": version("anisotropy-api"), "git_commit": getattr(request.app.state, "git_commit", None)}
        return update_upload(engine, row.id, job_id=job.id, verdict=found["verdict"], comparison=found,
                             compared_at=dt.datetime.now(dt.timezone.utc), not_compared=None)
    except (NotCompared, ToolFailed) as exc:
        failed = isinstance(exc, ToolFailed)
        if asked:
            raise HTTPException(status_code=503 if failed else 409, detail=f"Not compared: {exc}") from exc
        try:
            return update_upload(engine, row.id, not_compared=f"the comparison did not run: {exc}" if failed else str(exc))
        except SQLAlchemyError as inner:
            raise _database_error(inner) from inner
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc


def _receive_upload(request: Request, data: bytes, *, actor: str, user_email: str | None, token_id: uuid.UUID | None, may_train: bool,
                    job_id: uuid.UUID | None) -> UploadOutput:
    """Check the bundle, store it under its own prefix with its owner's row, and put it beside a run of ours when there is one."""
    engine, uploads = _records_engine(request), _uploads(request)
    try:
        if count_uploads(engine, actor=actor, user_email=user_email) >= MAX_UPLOADS:
            raise HTTPException(status_code=429, detail=f"You have {MAX_UPLOADS} uploads stored; delete one to send another")
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    upload_id = uuid.uuid4()
    key = upload_key(str(upload_id))
    with uploads.folder() as folder:
        bundle = Path(folder) / "bundle.zip"
        bundle.write_bytes(data)
        try:
            facts = uploads.check(bundle)
        except UploadRefused as exc:
            raise HTTPException(status_code=422, detail="Not a bundle this version takes, so nothing was stored: " + "; ".join(exc.problems)) from exc
        except ToolFailed as exc:
            raise HTTPException(status_code=503, detail=f"The bundle was not checked, so nothing was stored: {exc}") from exc
        stated = facts["bundle"]
        try:
            uploads.store.put(key, bundle, "application/zip", f'attachment; filename="{upload_id}.zip"')
        except Exception as exc:  # boto3 raises its own families, the disk OSError: either way the bundle is not kept
            raise HTTPException(status_code=503, detail=f"The bundle could not be stored: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}") from exc
    try:
        row = insert_upload(engine, id=upload_id, actor=actor, user_email=user_email, token_id=token_id, created_at=dt.datetime.now(dt.timezone.utc),
                            bundle_sha256=hashlib.sha256(data).hexdigest(), bundle_bytes=len(data), object_key=key, units=stated["units"],
                            job=stated.get("job"), coupon=stated.get("coupon"), in_scope=bool(facts["in_scope"]), facts=facts, may_train=may_train)
    except SQLAlchemyError as exc:
        try:
            uploads.store.delete(key)  # no row names it, so nobody could ever read or delete it
        except Exception:  # noqa: BLE001
            print(f"the bundle {key} was stored and its row was not written; it could not be removed either", flush=True)
        raise _database_error(exc) from exc
    return UploadOutput.of(_compare_upload(request, row, job_id, asked=False))


OurRun = Annotated[uuid.UUID | None, Query(description="the finished coupon job of ours to compare beside; default the owner's newest of the bundle's coupon")]


@app.post(UPLOADS, status_code=201, response_model=UploadOutput)
def send_upload(actor: Actor, request: Request, data: Annotated[bytes, Depends(_read_bundle)], job_id: OurRun = None, may_train: bool = False) -> UploadOutput:
    """Send a bundle from the signed-in browser (ADR-0094 step 5): the request's body is the zip the connector wrote. It is checked
    by `fea/tools/abaqus_upload.py check`; one that breaks the format is refused with every reason, 422, and nothing is stored. A bundle
    is stored under its own prefix and belongs to the requester: the signed-in email behind Cloudflare Access, the actor locally. It
    is then put beside a finished run of ours, the job `job_id` names or the requester's newest of the coupon the bundle names, and
    the answer carries the verdict and the comparison, or `not_compared` with the reason. `may_train` is the box of part 6, off unless
    sent. 413 past the size a bundle may have, 429 past the number a person may store."""
    return _receive_upload(request, data, actor=actor, user_email=_email(request), token_id=None, may_train=may_train, job_id=job_id)


@app.post(CONNECTOR_UPLOADS, status_code=201, response_model=UploadOutput)
def send_upload_from_connector(request: Request, sent: Annotated[tuple, Depends(_connector_bundle)], job_id: OurRun = None) -> UploadOutput:
    """Send a bundle from the connector (ADR-0094 step 5): `anisotropy_connector.py --send` under the user's own Abaqus, with an upload
    token as `Authorization: Bearer <token>`. The upload belongs to who created the token; everything else is `POST /v1/abaqus-uploads`.
    401 without a token that stands, a cancelled one included. Behind Cloudflare Access this route is reached without Access's token
    only when ANISOTROPY_CONNECTOR_UPLOADS=on and the Access application lets the path through."""
    owner, data = sent
    return _receive_upload(request, data, actor=owner.actor, user_email=owner.user_email, token_id=owner.id, may_train=False, job_id=job_id)


@app.get(UPLOADS, response_model=list[UploadOutput])
def list_uploads_endpoint(actor: Actor, request: Request, limit: Annotated[int, Query(ge=1, le=200)] = 50, job_id: uuid.UUID | None = None,
                         mine: bool = False) -> list[UploadOutput]:
    """The requester's uploads, newest first, without their facts and comparisons; a founder named in the settings sees every
    owner's (ADR-0094 part 6) unless `mine` asks for the requester's own alone, as the page's card does. With `job_id`, only those
    that stand beside that run of ours."""
    engine = _records_engine(request)
    try:
        rows = list_uploads(engine, actor=actor, user_email=_email(request), everyone=not mine and _uploads(request).sees_all(_email(request)),
                            limit=limit, job_id=job_id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return [UploadOutput.of(row, full=False) for row in rows]


@app.get(UPLOADS + "/{upload_id}", response_model=UploadOutput)
def upload_detail(upload_id: uuid.UUID, actor: Actor, request: Request) -> UploadOutput:
    """One upload with what the check found and, once compared, the comparison. 404 for anyone but its owner and the founders."""
    _engine, row = _requesters_upload(request, actor, upload_id, reading=True)
    return UploadOutput.of(row)


@app.get(UPLOADS + "/{upload_id}/bundle")
def upload_bundle(upload_id: uuid.UUID, actor: LinkActor, request: Request) -> Response:
    """The bundle as it was sent, the same bytes: a redirect to a short-lived link when a bucket holds it, the file itself otherwise.
    The page offers it as a link, so the actor may be named as `?actor=`; who owns the upload is decided as on every other route."""
    _engine, row = _requesters_upload(request, actor, upload_id, reading=True)
    store = _uploads(request).store
    try:  # the job's name is the user's own text: it names the download only when it is a plain file name
        filename = download_name(f"{row.job}-anisotropy.zip", ".zip") if row.job else f"{row.id}.zip"
    except ValueError:
        filename = f"{row.id}.zip"
    if isinstance(store, FolderStore):
        path = store.path(row.object_key)
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"The bundle of upload {upload_id} is no longer on this disk")
        return FileResponse(path, media_type="application/zip", filename=filename)
    return RedirectResponse(store.link(row.object_key, filename=filename), status_code=307)


def _document_name(row) -> str:
    """What the document is saved as: the user's job when it is a plain file name, else the upload's id."""
    try:
        return download_name(f"{row.job}-compared-with-anisotropy.pdf", ".pdf") if row.job else f"{row.id}.pdf"
    except ValueError:
        return f"{row.id}.pdf"


def _upload_document(request: Request, row) -> str:
    """The key of the document of the upload's present comparison (ADR-0094 step 7), written first when the store does not hold it:
    by `docs/models/upload.py`, from the comparison the row keeps and nothing else. It is kept beside the bundle, under the upload's
    own prefix, named by the time of its comparison; the documents of earlier comparisons go. 409 when there is no comparison to
    print, 503 when the document could not be written or kept."""
    uploads = _uploads(request)
    if row.comparison is None or row.compared_at is None:
        raise HTTPException(status_code=409, detail="Not compared: " + (row.not_compared or "this upload has not stood beside a run of ours yet"))
    key = upload_document_key(str(row.id), row.compared_at)
    try:
        kept = uploads.store.keys(upload_prefix(str(row.id)))
        if key in kept:
            return key
        with uploads.folder() as folder:
            written = uploads.document(dict(row.comparison), Path(folder), upload=str(row.id), run=f"our run {row.job_id}" if row.job_id else None,
                                       compared=f"{row.compared_at.astimezone(dt.timezone.utc):%Y-%m-%d %H:%M} UTC")
            uploads.store.put(key, written, "application/pdf", f'attachment; filename="{row.id}.pdf"')
    except NotCompared as exc:
        raise HTTPException(status_code=409, detail=f"Not compared: {exc}") from exc
    except ToolFailed as exc:
        raise HTTPException(status_code=503, detail=f"The document could not be written: {exc}") from exc
    except Exception as exc:  # the store's own errors or the disk's
        raise HTTPException(status_code=503, detail=f"The document could not be kept: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}") from exc
    for old in kept:  # a document of an earlier comparison prints what the row no longer holds
        if old != key and old.rsplit("/", 1)[-1].startswith(UPLOAD_DOCUMENT):
            try:
                uploads.store.delete(old)
            except Exception:  # it is never handed out again, and it goes with the upload
                pass
    return key


@app.post(UPLOADS + "/{upload_id}/document", response_model=UploadDocument)
def write_upload_document(upload_id: uuid.UUID, actor: Actor, request: Request) -> UploadDocument:
    """Write the document of the upload's comparison, "Compared with the uploaded Abaqus model", when it is not kept yet (ADR-0094
    step 7), and say what it is saved as. The page asks this first and then follows `GET` of the same address. 409 for an upload that
    has no comparison, 404 for anyone but its owner and the founders."""
    _engine, row = _requesters_upload(request, actor, upload_id, reading=True)
    _upload_document(request, row)
    return UploadDocument(upload_id=str(row.id), compared_at=row.compared_at.isoformat(), filename=_document_name(row))


@app.get(UPLOADS + "/{upload_id}/document")
def upload_document(upload_id: uuid.UUID, actor: LinkActor, request: Request) -> Response:
    """The comparison as a PDF, the upload's own document and never a part of the run's (ADR-0094 part 6): a redirect to a short-lived
    link when a bucket holds it, the file itself otherwise; written first when it is not kept yet. The page offers it as a link, so
    the actor may be named as `?actor=`."""
    _engine, row = _requesters_upload(request, actor, upload_id, reading=True)
    key = _upload_document(request, row)
    store = _uploads(request).store
    if isinstance(store, FolderStore):
        return FileResponse(store.path(key), media_type="application/pdf", filename=_document_name(row))
    return RedirectResponse(store.link(key, filename=_document_name(row)), status_code=307)


@app.post(UPLOADS + "/{upload_id}/compare", response_model=UploadOutput)
def compare_upload(upload_id: uuid.UUID, actor: Actor, request: Request, job_id: OurRun = None) -> UploadOutput:
    """Put the upload beside a run of ours again, the one `job_id` names or the owner's newest of the bundle's coupon: after a first
    run of the coupon, or beside another run. The row then holds this comparison in place of the last; when none can be made the
    reason is answered, 409, and the row keeps what it had. Its owner alone."""
    _engine, row = _requesters_upload(request, actor, upload_id, reading=False)
    return UploadOutput.of(_compare_upload(request, row, job_id, asked=True))


@app.delete(UPLOADS + "/{upload_id}", status_code=204)
def delete_upload_endpoint(upload_id: uuid.UUID, actor: Actor, request: Request) -> Response:
    """Delete an upload: its documents and its bundle from the store, then its row with the comparison. Its owner alone; nothing of
    it is kept."""
    engine, row = _requesters_upload(request, actor, upload_id, reading=False)
    store = _uploads(request).store
    try:
        for key in store.keys(upload_prefix(str(row.id))):  # what was written from the bundle first, the bundle last
            if key != row.object_key:
                store.delete(key)
        store.delete(row.object_key)
    except Exception as exc:  # the row stays while the bundle may still be there, so the delete can be asked again
        raise HTTPException(status_code=503, detail=f"The bundle could not be deleted, so the upload stands: {str(exc).splitlines()[0] if str(exc) else type(exc).__name__}") from exc
    try:
        delete_upload(engine, row.id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return Response(status_code=204)


@app.get(COUPON_JOBS, response_model=list[CouponJobOutput])
def list_coupon_jobs(request: Request) -> list[CouponJobOutput]:
    """Every coupon job of this API process, newest first (ADR-0051); jobs of earlier processes are in GET /v1/runs?endpoint=/v1/coupon-jobs."""
    jobs = _coupon_jobs(request)
    listed = jobs.listed()
    with jobs.lock:
        return [CouponJobOutput.of(job) for job in listed]


@app.get(COUPON_JOBS + "/{job_id}", response_model=CouponJobOutput)
def coupon_job(job_id: uuid.UUID, request: Request) -> CouponJobOutput:
    """A coupon job as it stands: its state, the end of its console, and once it is done the files it made (ADR-0050)."""
    jobs = _coupon_jobs(request)
    job = _known_job(jobs, job_id)
    with jobs.lock:
        return CouponJobOutput.of(job)


def _download_name(name: str | None, suffix: str) -> str | None:
    """The page's name for a download (ADR-0091), checked; 422 when it is not one."""
    try:
        return download_name(name, suffix)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


DownloadName = Annotated[str | None, Query(max_length=120, description="File name for the download: letters, digits and _ . , ( ) [ ] + -")]


@app.get(COUPON_JOBS + "/{job_id}/package")
def coupon_job_package(job_id: uuid.UUID, request: Request, name: DownloadName = None) -> FileResponse:
    """The package of a job that is done, as a zip: the document, the decks, the material, the results and the audit form."""
    filename = _download_name(name, ".zip")
    jobs = _coupon_jobs(request)
    job = _known_job(jobs, job_id)
    with jobs.lock:
        state, outcome = job.state, job.outcome
    if state != "done":
        raise HTTPException(status_code=409, detail=f"coupon job {job_id} is {state}" + ("" if outcome is None else f": {outcome['message']}"))
    link = jobs.output_url(job, "package", filename)
    if link is not None:  # the store has it: the browser fetches it there, not through this container (ADR-0050 amendment 2)
        return RedirectResponse(link, status_code=307)
    try:
        archive = jobs.package_archive(job)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(archive, media_type="application/zip", filename=filename or archive.name)


@app.get(COUPON_JOBS + "/{job_id}/files/{key}")
def coupon_job_file(job_id: uuid.UUID, key: str, request: Request, name: DownloadName = None) -> Response:
    """One file of a job by its key (ADR-0051): `fields`, `explanation`, `checklist` and `preview` as soon as the tool reports them,
    while the job runs; every key the status lists once it is done; `package` is the zip. An unknown key names the keys there are.
    Once a job is done and an object store holds its files, the answer is a redirect to a short-lived link there (ADR-0050 amendment 2).
    With `name`, the file is saved under that name, which must end in the file's own suffix (ADR-0091). The page asks for the files a
    customer downloads by their neutral names (`solver_input`, `reference_input`, `reference_results`); the solver inputs are then served
    from here with a neutral header, never as a link to the team's copy (ADR-0091 amendment 2)."""
    jobs = _coupon_jobs(request)
    job = _known_job(jobs, job_id)
    alias, key = key, FILE_ALIASES.get(key, key)
    if alias in NEUTRAL_DECKS:
        try:
            path = jobs.output_file(job, key)
        except (KeyError, FileNotFoundError, PermissionError) as exc:
            # a link the browser opens itself, so the answer is the page's words; the cause goes to the log (ADR-0091 amendment 2)
            print(f"coupon job {job_id}: no file {alias} ({key}): {exc}", flush=True)
            raise HTTPException(status_code=404, detail="This file is no longer available. Run the analysis again from your project.") from exc
        filename = _download_name(name, path.suffix) or f"{alias}{path.suffix}"
        return Response(neutral_deck(path.read_text(encoding="utf-8"), NEUTRAL_DECKS[alias]), media_type=content_type(path),
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    stored = job.stored.get(key)
    if name is not None and stored is not None:
        _download_name(name, Path(stored).suffix or (".zip" if key == "package" else ""))
    link = jobs.output_url(job, key, name)
    if link is not None:
        return RedirectResponse(link, status_code=307)
    try:
        path = jobs.output_file(job, key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"coupon job {job_id} has no file {key!r}; it has: {exc.args[0]}") from exc
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=content_type(path), filename=_download_name(name, path.suffix) or path.name)


def _job_json(jobs: CouponJobs, job: Job, key: str, what: str) -> dict:
    """One JSON file of a job by its key, or 409 while the tool has not written it."""
    try:
        path = jobs.output_file(job, key)
    except KeyError as exc:
        raise HTTPException(status_code=409, detail=f"coupon job {job.id} has {what} yet; it has: {exc.args[0]}") from exc
    except (FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=409, detail=f"the file {key} of coupon job {job.id} is not readable yet: {exc}") from exc


@app.post(COUPON_JOBS + "/{job_id}/explain", response_model=ExplainResponse)
def explain_coupon_job(job_id: uuid.UUID, problem: ExplainRequest, actor: Actor, request: Request, response: Response) -> ExplainResponse:
    """An explanation of a job's result or setup (ADR-0052): the template's sentences the fea package wrote, or, when a provider is
    named in the settings, the model's rephrasing of them from the same fact sheet, kept only when every number in it is a fact.
    Recorded with its actor and, when a model wrote it, the model's name (ADR-0026)."""
    jobs = _coupon_jobs(request)
    job = _known_job(jobs, job_id)
    explanation = _job_json(jobs, job, "explanation", "no explanation")
    facts, sentences = explanation.get("facts", {}), list(explanation.get("sentences", []))
    checklist = _job_json(jobs, job, "checklist", "no setup check") if problem.kind == "setup" else None
    template = list(explanation.get("setup_sentences", [])) if problem.kind == "setup" else sentences
    seen = checklist if problem.kind == "setup" else facts
    receipt = ExplainReceipt(job_id=str(job_id), kind=problem.kind,
                             facts_sha256=hashlib.sha256(json.dumps(seen, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest())
    assistant = getattr(request.app.state, "assistant", None) or TemplateAssistant()

    def compute() -> ExplainResponse:
        draft = assistant.explain_setup(checklist, template) if problem.kind == "setup" else assistant.explain_result(facts, template)
        return ExplainResponse(run_id=None, job_id=str(job_id), kind=problem.kind, writer=draft.writer, model=draft.model, prose=list(draft.prose),
                               withheld=draft.withheld, reason=draft.reason, facts=facts if problem.kind == "result" else {"checklist": checklist})

    return _deliver(request, response, actor, receipt, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None))


@app.get("/v1/coupons", response_model=list[CouponSummary])
def list_coupons(request: Request) -> list[CouponSummary]:
    """Every coupon on this machine, from its spec and its case page (ADR-0051): what the studio offers to reopen."""
    jobs = _coupon_jobs(request)
    try:
        return [CouponSummary(**entry) for entry in jobs.list_coupons()]
    except CheckTimedOut as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except JobRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/coupons/{name}/values", response_model=CouponValuesOutput)
def coupon_values(name: str, request: Request) -> CouponValuesOutput:
    """A coupon's rows as the values object the studio edits (ADR-0051): the inverse of the form's reading."""
    jobs = _coupon_jobs(request)
    try:
        return CouponValuesOutput(name=name, values=jobs.coupon_values(name))
    except UnknownCoupon as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc
    except NotOffered as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CheckTimedOut as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except JobRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
        # The stack's density comes with a library material only; a typed material carries none (ADR-0059).
        densities = [None if provenance is None else provenance.density_kg_per_m3] * len(plies)
        try:
            # Floating-point overflow/invalid operations must become errors, never JSON null/NaN.
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                A, B, D = abd_matrices(plies)
                eps0, kappa = midplane_response(plies, problem.loads.to_engine())
                summary = laminate_summary(plies, densities)
                failure = first_ply_failure_summary(plies, problem.loads.to_engine())
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
            summary=LaminateSummaryOutput.of(summary), first_ply_failure=FirstPlyFailureOutput.of(failure),
        )

    return _deliver(request, response, actor, problem, compute)


@app.post("/v1/laminates/solve", response_model=LaminateAnswer)
def solve_laminate_problem(problem: LaminateProblem, actor: Actor, request: Request, response: Response) -> LaminateAnswer:
    """A laminate problem as the chat states it (ADR-0060): every value with its own unit, converted with the engine's unit table into
    the case the engine's runner solves (ADR-0024), every result in the units asked for, the stack described (ADR-0059), and the
    answer worded from the engine's numbers by the template or, behind the setting, by the model with the number guard (ADR-0052).
    Recorded with its actor and, when a model wrote the words, the model's name (ADR-0026)."""
    assistant = getattr(request.app.state, "assistant", None) or TemplateAssistant()

    def compute() -> LaminateAnswer:
        try:
            case = case_of(problem)
            validate_case_inputs(case)
            with np.errstate(over="raise", invalid="raise", divide="raise"):
                solution = solve_case(case)
                results = engine_results(case)
                failures = first_ply_failures(case, solution)
                cited = solution.library.get("material")
                summary = laminate_summary(solution.plies, [None if cited is None else cited.density_kg_per_m3] * len(solution.plies))
        except (ValueError, TypeError, KeyError, np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
            raise HTTPException(status_code=422, detail=str(exc) or exc.__class__.__name__) from exc
        facts = facts_of(case, results, solution, failures, summary)
        template = sentences_of(facts)
        draft = assistant.explain_laminate(facts, template)
        return LaminateAnswer(
            run_id=None, engine_version=version("anisotropy-engine"), report_units=problem.report_units, units=unit_labels(problem.report_units),
            case=case, results={key: _json_value(value) for key, (value, _scale) in results.items()}, criteria=list(failures),
            summary=LaminateSummaryOutput.of(summary), material=None if cited is None else MaterialProvenance.of(cited),
            writer=draft.writer, model=draft.model, prose=list(draft.prose), withheld=draft.withheld, reason=draft.reason, facts=facts,
        )

    return _deliver(request, response, actor, problem, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None))


@app.get("/v1/workspace/assistant", response_model=AssistantInfo)
def workspace_assistant(request: Request) -> AssistantInfo:
    """Whether a model reads the chat's messages here (ADR-0088); the page asks once. Not a run: nothing is computed or recorded."""
    assistant = getattr(request.app.state, "assistant", None) or TemplateAssistant()
    proposes = assistant.name != "template"
    return AssistantInfo(proposes=proposes, provider=assistant.name if proposes else None, model=getattr(assistant, "model", None) if proposes else None)


@app.get("/v1/coupon-tests", response_model=CouponTests)
def coupon_tests(request: Request) -> CouponTests:
    """Whether every coupon test is offered here (ADR-0089); the page asks once and offers the unnotched tension coupon only unless this
    says all. Not a run: nothing is computed or recorded. Without the startup's settings (a test client), the environment is read."""
    settings = getattr(request.app.state, "settings", None)
    return CouponTests(all=settings.all_tests if settings is not None else all_tests(environment()))


@app.post("/v1/workspace/proposals", response_model=ProposalResponse)
def propose_rows(proposal: ProposalRequest, actor: Actor, request: Request, response: Response) -> ProposalResponse:
    """The model reads a message into the rows the page offers, and the source guard keeps what the engineer's own words hold (ADR-0088):
    each value as written, in the quote it came from, converted only between the decimal units of the row's own system. The engineer ticks
    what enters the problem; nothing here computes a result. With no model, or one that does not answer, nothing is proposed and the page
    reads the message with its own patterns. Recorded with the model's name when one read it (ADR-0026)."""
    assistant = getattr(request.app.state, "assistant", None) or TemplateAssistant()

    def compute() -> ProposalResponse:
        rows = [row.model_dump(mode="json", exclude_none=True) for row in proposal.rows]
        conditions = [c.model_dump(mode="json") for c in proposal.conditions]
        view = {"product": proposal.product, "message": proposal.message, "rows": rows, "conditions": conditions,
                "form": model_view_of_form(proposal.form)}
        reading = assistant.propose(view)
        if reading.raw is None:
            return ProposalResponse(run_id=None, writer=reading.writer, model=None, proposals=[], conditions=[], question=None, dropped=[],
                                    reason=reading.reason)
        kept = source_guard(reading.raw, proposal.message, rows, conditions)
        return ProposalResponse(run_id=None, writer=reading.writer, model=reading.model, proposals=kept.proposals, conditions=kept.conditions,
                                question=kept.question, dropped=kept.dropped, reason=None)

    return _deliver(request, response, actor, proposal, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None))


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
