"""A synchronous local API. It adapts HTTP to the engine and to our coupon tool; it contains no laminate math."""

import datetime as dt
import hashlib
import json
import math
import subprocess
import tempfile
import tomllib
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any, TypeVar
from urllib.parse import unquote

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
from anisotropy_engine.repair import bond_needs, pick_check, preview_change as preview_repair_change, repair_from_dict, repair_report, repair_views, solve_needs, sweep_repair
from anisotropy_engine.response import midplane_response, prescribed_curvature_response
from anisotropy_engine.summary import first_ply_failure_summary, laminate_summary
from anisotropy_engine.wing.analysis import analyze_wing
from anisotropy_engine.wing.changes import preview_change
from anisotropy_engine.wing.wing_file import wing_from_dict, wing_report, wing_views

from .abaqus_coupon import NotABuildScript, coupon_data
from .access import CONNECTOR_PAIR, CONNECTOR_RUNS, CONNECTOR_UPLOADS, AccessMiddleware
from .access import verifier as access_verifier
from .assistant import CHECKED_MODELS, PROPOSAL_SCHEMA, Assistant, LimitedAssistant, TemplateAssistant, assistant_for, model_view_of_facts
from .laminate_problems import case_of, facts_of, sentences_of, unit_labels
from .plate_proposals import PLATE_SYSTEM, KeptPlate, plate_guard, plate_schema, plate_view
from .proposals import model_view_of_form, source_guard
from .general_answers import general_guard, general_schema, general_view
from .result_answers import SECTIONS_SHOWN, answer_guard, answer_schema, answer_view
from .result_questions import model_view, question_guard, question_schema
from .theory import find as find_theory, repair_sections, wing_sections
from .live import LiveBusy, LiveRefused, LiveSolver, LiveTimedOut
from .model_costs import ModelCall
from .coupon_jobs import (EVERY_TEST, FEA, FILE_ALIASES, LOCAL_FEA, NEUTRAL_DECKS, OWNERS_FEA, CheckTimedOut, CouponJobs, Job, JobBusy, JobLimited, JobNotDone, JobRefused, NoDocument, NotOffered, RecordingFailed,
                          SolverBusy, UnknownCoupon, WING, is_wing, neutral_deck, repair_bond_command, repair_model_command, repair_shape_command, runner_command, studio_command, wing_check_command,
                          wing_shape_command)
from .records import (ACTORS, EVERYONE, STATUSES, KindChanged, ProjectTaken, check_ready, claim_pairing_code, connect, count_uploads, delete_upload, fetch_pairing_code,
                      model_calls_since,
                      fetch_project, fetch_run, fetch_upload, git_commit, insert_pairing_code, insert_upload, insert_upload_token, latest_done_job, list_projects, list_runs, list_upload_tokens, list_uploads,
                      live_upload_tokens, name_pairing_token, owns_project, project_jobs, record_model_calls, record_run, revoke_upload_token, stop_orphans, update_project, update_upload,
                      upsert_project, use_upload_token)
from .settings import all_tests, allowed_origins, docs_urls, environment, load_settings
from .storage import (UPLOAD_DOCUMENT, FolderStore, R2Store, content_type, download_name, restore, restore_owners, sync, upload_document_key, upload_key,
                      upload_prefix)
from .uploads import (CONNECTOR_NOTE, LOCAL_UPLOADS, MAX_BUNDLE_BYTES, MAX_TOKENS, MAX_UPLOADS, NotCompared, ToolFailed, UploadRefused, Uploads, bearer, connector_release,
                      new_pairing_code, new_token, ours_of,
                      token_digest)
from .uploads import tool_command as upload_command
from .schemas import (
    AbaqusExchange, AnalysisRequest, AnalysisResponse, AssistantInfo, CaseRequest, CouponTests, CaseResponse, ComparisonOutput, CouponCheckRequest, CouponCheckResponse, CouponJobOutput,
    CouponModelReceipt, ImportedModelReceipt, ImportedModelResponse, LiveSolveResponse, ModelProgram, ModelUnits, TowTestRequest, TowTestResponse, WingAnswer, WingChangePreview, WingChangeRequest, WingCheckOutput, WingCheckRequest,
    WingRequest, WingShapeAnswer, RepairAnswer, RepairBondAnswer, RepairChangePreview, RepairChangeRequest, RepairRequest, RepairShapeAnswer, RepairSolveAnswer, RepairSolveRequest,
    RepairSweepAnswer, RepairSweepRequest,
    CouponJobRequest, CouponSummary, CouponValuesOutput, ExplainReceipt, ExplainRequest, ExplainResponse, FirstPlyFailureOutput, LaminateAnswer,
    LaminateProblem,
    LaminateSummaryOutput, LibraryMaterialInput, MaterialProvenance, Paired, PairingCode, PairInput, PrescribedCurvatureRequest, PrescribedCurvatureResponse, ProjectInput, ProjectOutput,
    GeneralAnswerResponse, GeneralQuestionRequest, ProjectRename, ProposalRequest, ProposalResponse, ResultAnswerReceipt, ResultAnswerRequest, ResultAnswerResponse, ResultQuestionRequest, ResultQuestionResponse, TheorySection, TheorySectionsRequest, TheorySectionsResponse, TheorySource, RunOutput, RunSummary, UploadDocument, UploadOutput, UploadTokenCreated, UploadTokenInput, UploadTokenOutput,
    VerificationResponse,
)

RUN_ID_HEADER = "X-Anisotropy-Run-Id"
# What a request's calls to the model cost, on the answer to a request with no signed-in email only: the site check's service token (ADR-0138)
MODEL_COST_HEADER = "X-Anisotropy-Model-Cost"
# "off" on the 503 of an API that keeps no records, so the page tells "this server keeps no projects" from an outage (ADR-0091 amendment 2)
RECORDS_HEADER = "X-Anisotropy-Records"
# With the job queue (ADR-0056 amendment 3), a queued job's answer carries its id here; the Worker sends the id to the queue and
# drops the header, so a browser never sees it.
ENQUEUE_HEADER = "X-Anisotropy-Enqueue"
COUPON_JOBS = "/v1/coupon-jobs"
MODEL_PROGRAM_NAMES = {"abaqus": "Abaqus", "ansys": "Ansys"}  # as a refusal names them (ADR-0129)
MODEL_NAME_HEADER = "X-Anisotropy-Model-File"  # the written file's name, which a page on another origin reads without parsing Content-Disposition
WAKE = "/v1/wake"  # the page says an analysis may be started soon (ADR-0056 amendment 11)
WAKE_HEADER = "X-Anisotropy-Wake"  # what the Worker reads on the answer to start a solver (worker/routing.ts)
SOLVER_STATE = "/v1/solver/state"  # whether a solver container runs a job: the wake-up's question (ADR-0056 amendment 11)
SOLVER_JOBS = "/v1/solver/jobs"  # a solver container's own routes, which only its Durable Object reaches (worker/index.ts)
PROJECTS = "/v1/projects"
IMPORTED_MODELS = "/v1/imported-models"  # a model brought in as an Abaqus deck, answered and not kept (ADR-0105)
MODEL_NAME_HEADER = "X-Anisotropy-Model-Name"  # the file's name, percent-encoded: a header, so it stays out of the address
MAX_MODEL_BYTES = 20_000_000  # the deck as sent; the fea package's own limit (`imported.MAX_BYTES`)
UPLOADS = "/v1/abaqus-uploads"  # the uploads from Abaqus, each its owner's alone (ADR-0094 part 6)
UPLOAD_TOKENS = "/v1/upload-tokens"  # what the connector sends with
PAIRING_CODES = "/v1/pairing-codes"  # a one-time code that a signed-in page hands to the user's machine (ADR-0094 amendment 1)
PAIRING_MINUTES = 10
ABAQUS_EXCHANGE = "/v1/abaqus-exchange"  # what the page's card may offer here (step 6)
ABAQUS_CONNECTOR = "/v1/abaqus-connector"  # the connector's files as one zip
WING_CHECKS = "/v1/wings/checks"  # a wing's finite element check, a job like a coupon run (ADR-0119)


def job_recorder(app: FastAPI):
    """The receipt of an ended coupon job, written as every run is (ADR-0026): solved with the tool's outcome, or rejected with
    its message. A wing's check is recorded at its own address (ADR-0119), its description among the inputs."""
    def record(job: Job, state: str, outcome: dict) -> uuid.UUID | None:
        engine = getattr(app.state, "records", None)
        if engine is None:
            return None
        try:
            return record_run(engine, actor=job.actor, endpoint=WING_CHECKS if is_wing(job) else COUPON_JOBS, inputs=job.inputs, engine_version=version("anisotropy-engine"),
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
    # Each signed-in person's own coupons (ADR-0106) come back at startup where this container runs the jobs itself; with the queue
    # they are brought level when that person asks (`CouponJobs.refresh`), so a start does not grow with the number of people.
    store = R2Store(settings.storage) if settings.storage.on else None
    role = settings.job_role
    if store is not None and role != "solver":
        files, coupons = (sync if role == "queue" else restore)(store, LOCAL_FEA)
        print(f"restored {files} file(s) of {coupons} coupon(s) from the bucket {settings.storage.bucket}", flush=True)
        if role is None:
            files, people = restore_owners(store, OWNERS_FEA)
            print(f"restored {files} file(s) of the coupons of {people} signed-in owner(s)", flush=True)
    if app.state.records is not None and role is None:
        orphans = stop_orphans(app.state.records, "the API stopped while this job ran, so it did not finish; start it again")
        if orphans:
            print(f"marked {orphans} job(s) of a stopped process as stopped", flush=True)
    app.state.coupon_jobs = CouponJobs(runner_command(), job_recorder(app), studio=studio_command(), store=store, table=app.state.records,
                                       per_day=settings.jobs_per_user_per_day if role != "solver" else None, role=role, wing=wing_check_command())
    app.state.assistant = assistant_for(settings.assistant.provider, settings.assistant.model)  # the template unless a provider is named (ADR-0052)
    if settings.assistant.model is not None and settings.assistant.model not in CHECKED_MODELS:  # said, not refused (ADR-0121 amendment 8)
        print(f"the assistant's model {settings.assistant.model} is not one the Assistant check has been run with (CHECKED_MODELS)", flush=True)
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
    allow_headers=["Content-Type", "X-Anisotropy-Actor", MODEL_NAME_HEADER],
    expose_headers=[RUN_ID_HEADER, RECORDS_HEADER, MODEL_NAME_HEADER, "Location"],
    allow_credentials=False,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Alive, without touching the database or any tool: what a platform polls to know the container answers (ADR-0056).
    Not a run, so no actor header and no run record."""
    return {"status": "ok"}


@app.get("/version")
async def running_version(request: Request) -> dict[str, str | None]:
    """The commit this container runs and its packages' versions: what the check after a deploy reads to know the deployed code
    answers, not a container left from before it (ADR-0114, ADR-0056 amendment 10). Not a run; behind Access like every route but
    /healthz."""
    return {"git_commit": getattr(request.app.state, "git_commit", None), "api_version": version("anisotropy-api"),
            "engine_version": version("anisotropy-engine")}


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


Billed = TypeVar("Billed")


def _billed(calls: list[ModelCall], outcome: Billed) -> Billed:
    """A writer's draft or reading, its call to the model, when it made one, added to the request's calls (ADR-0120)."""
    call = getattr(outcome, "call", None)
    if call is not None:
        calls.append(call)
    return outcome


def _record_calls(request: Request, actor: str, calls: list[ModelCall], run_id: uuid.UUID | None) -> None:
    """Each call to the model the request made, with who asked and the request's run (ADR-0120). A row that cannot be written is
    named in the log and the answer still goes back: the run is the request's receipt, and the provider's usage page holds the call."""
    engine = getattr(request.app.state, "records", None)
    if engine is None or not calls:
        return
    try:
        record_model_calls(engine, calls, actor=actor, user_email=_email(request), run_id=run_id)
    except SQLAlchemyError as exc:
        print(f"{len(calls)} model call(s) of {request.url.path} could not be recorded: {str(exc).splitlines()[0]}", flush=True)


def _cost_header(request: Request, response: Response, calls: list[ModelCall]) -> None:
    """What the request's calls to the model cost at the price list (ADR-0120), as `<dollars>; calls=<n>; unpriced=<n>`, on the answer
    to a request with no signed-in email. On the hosted site only a service token asks without one: the site check's, which stops
    before its cap with it (ADR-0138). A signed-in person's answer never carries it, and nothing else about the calls goes with it."""
    if not calls or _email(request) is not None:
        return
    priced = [call.cost_usd for call in calls if call.cost_usd is not None]
    response.headers[MODEL_COST_HEADER] = f"{sum(priced, Decimal(0)):.6f}; calls={len(calls)}; unpriced={len(calls) - len(priced)}"


Body = TypeVar("Body", bound=BaseModel)


def _deliver(request: Request, response: Response, actor: str, problem: BaseModel, compute: Callable[[], Body],
             llm_of: Callable[[Body], tuple[str | None, str | None]] | None = None, calls: list[ModelCall] | None = None) -> Body:
    """Compute, record the outcome, and attach the run id (ADR-0026).

    A 422 raised while computing is recorded as a rejection and re-raised with the run id in its
    header; a successful body is recorded as returned, without run_id, and returned with it. `llm_of`
    names the language model whose draft the body holds, for the record (ADR-0052). `calls` is filled by
    `compute` with each call to the model it made; they are written after the run, naming it, however
    the request ends (ADR-0120): a call that was made was billed.
    """
    run_id: uuid.UUID | None = None
    try:
        try:
            body = compute()
        except HTTPException as exc:
            if exc.status_code != 422:
                raise
            run_id = _record(request, actor, problem, error=str(exc.detail))
            raise HTTPException(status_code=422, detail=exc.detail, headers=_run_header(run_id)) from exc
        run_id = _record(request, actor, problem, response=body.model_dump(mode="json", exclude={"run_id"}),
                         llm=llm_of(body) if llm_of is not None else (None, None))
    finally:
        if calls:
            _record_calls(request, actor, calls, run_id)
    _cost_header(request, response, calls or [])
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


def _email(request: Request) -> str | None:
    return getattr(request.state, "user_email", None)


def _assistant(request: Request, actor: str) -> Assistant:
    """Who writes or reads for this request (ADR-0052): the settings' model, or the template with none. A signed-in person whose
    requests have called the model the day's cap of times since midnight UTC (ADR-0139) gets the template with the reason the page reads,
    until midnight. With no cap set, no records, no model or no email, nothing is counted: behind Access a request with no email is a
    service token of ours (the deploy check, the site check, ADR-0138), which keeps a budget of its own. A count that cannot be read
    leaves the model on: the run's own record then fails and withholds the answer (ADR-0026)."""
    assistant = getattr(request.app.state, "assistant", None) or TemplateAssistant()
    settings = getattr(request.app.state, "settings", None)
    cap = getattr(settings, "model_calls_per_user_per_day", None)
    engine = getattr(request.app.state, "records", None)
    email = _email(request)
    if cap is None or engine is None or email is None or isinstance(assistant, TemplateAssistant):
        return assistant
    midnight = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        used = model_calls_since(engine, email, midnight)
    except SQLAlchemyError as exc:
        print(f"the day's calls to the model could not be counted: {str(exc).splitlines()[0]}", flush=True)
        return assistant
    if used >= cap:
        print(f"model call capped for the actor {actor}: {used} today, the cap is {cap}", flush=True)
        return LimitedAssistant(cap)
    return assistant


def _owner(request: Request) -> str | None:
    """Whose runs, jobs, files and coupons a request may see (ADR-0104). Behind Cloudflare Access: the signed-in email, or None for a
    service token, which has no email and sees what was made with none. With no sign-in in front of the API (the local one,
    ADR-0011) there is one user and nothing is narrowed: EVERYONE."""
    if getattr(request.app.state, "access_verifier", None) is None:
        return EVERYONE
    return _email(request)


def _theirs(owner: str | None, user_email: str | None) -> bool:
    """Whether a record made under `user_email` is that owner's to see."""
    return owner == EVERYONE or owner == user_email


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
    """The requester's runs, newest first, narrowed by actor, endpoint, status and time (ADR-0026, ADR-0104).

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
                         since=_aware("since", since), until=_aware("until", until), limit=limit, user_email=_owner(request))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"The run records database did not answer: {str(exc).splitlines()[0]}") from exc
    return [RunSummary.of(run) for run in runs]


@app.get("/v1/runs/{run_id}", response_model=RunOutput)
def run_detail(run_id: uuid.UUID, request: Request) -> RunOutput:
    """One run record as stored (ADR-0026). 404 for a run that is not the requester's, in the same words as for none (ADR-0104)."""
    engine = _records_engine(request)
    try:
        run = fetch_run(engine, run_id)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"The run records database did not answer: {str(exc).splitlines()[0]}") from exc
    if run is None or not _theirs(_owner(request), run.user_email):
        raise HTTPException(status_code=404, detail=f"No run {run_id}")
    return RunOutput.of(run)


def _coupon_jobs(request: Request) -> CouponJobs:
    jobs = getattr(request.app.state, "coupon_jobs", None)
    if jobs is None:
        raise HTTPException(status_code=503, detail="Coupon jobs are not set up: the API was started without its startup step")
    return jobs


def _coupons_unread(exc: SQLAlchemyError) -> HTTPException:
    print(f"the jobs table did not answer: {str(exc).splitlines()[0]}", flush=True)  # the cause stays in the log, not in the answer
    return HTTPException(status_code=503, detail="Your coupons could not be read right now. Try again in a minute.")


def _their_coupon(request: Request, jobs: CouponJobs, name: str) -> None:
    """Passes when the coupon of that name is the requester's: in a signed-in person's own folder of coupons (ADR-0106); in the
    shared folder, for a request with no email behind the sign-in (a service token), one that jobs with no email alone have run
    (ADR-0104). 404 otherwise, in the same words as for a name there is no coupon of."""
    owner = _owner(request)
    try:
        if owner == EVERYONE:
            known = True
        elif owner is not None:
            known = jobs.has_coupon(name, owner)
        else:
            known = name in jobs.coupons_of(owner)
    except SQLAlchemyError as exc:
        raise _coupons_unread(exc) from exc
    if not known:
        raise HTTPException(status_code=404, detail=f"no coupon of that name: {name}")


def _known_job(request: Request, jobs: CouponJobs, job_id: uuid.UUID) -> Job:
    """The job by its id when it is the requester's (ADR-0104). 404 otherwise, in the same words as for none, so no job is confirmed
    to a stranger."""
    job = jobs.get(job_id)
    if job is None or not _theirs(_owner(request), job.user_email):
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
    if job_request.coupon is not None:
        _their_coupon(request, jobs, job_request.coupon)
    try:
        # a founder's job carries the option to its tool, here or through the queue to a solver, which is not told who the founders are
        options = [*job_request.options(), *EVERY_TEST[_every_for(request, values)]]
        job = jobs.start(actor, job_request.recorded_inputs(), options, form=form, coupon=job_request.coupon, values=values,
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


@app.post(WAKE, status_code=202)
def wake_a_solver(request: Request, response: Response) -> dict[str, bool]:
    """The page says an analysis may be started soon: it opened, or a setup check passed (ADR-0056 amendment 11). With the job queue
    the answer carries a header and the Worker starts the pool's first free solver container, so the job that follows does not wait
    for one to start; the request passed the sign-in like any other, which is why the page asks here and not the Worker alone. Without
    the queue this process runs the jobs itself and there is nothing to wake: `waking` is false. Nothing is computed or recorded."""
    waking = _coupon_jobs(request).role == "queue"
    if waking:
        response.headers[WAKE_HEADER] = "1"
    return {"waking": waking}


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


@app.get(SOLVER_STATE)
def solver_state(request: Request) -> dict[str, bool]:
    """Whether this solver container runs a job now. The Worker asks the pool's solvers in turn when the page opens, which starts the
    first free one before a job is filed (ADR-0056 amendment 11): the ask itself is what wakes a sleeping container."""
    return {"busy": _solver_jobs(request).busy()}


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
    every = _every_for(request, problem.values_bytes)

    def compute() -> CouponCheckResponse:
        try:
            found = jobs.check(problem.values_bytes(), every=every, user_email=_email(request))
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
        email = _email(request)  # the preview names the coupon among the coupons of whoever asked (ADR-0106)
        found = live.solve(problem.values_bytes(), every=_every_for(request, problem.values_bytes), root=None if email is None else _coupon_jobs(request).root_of(email))
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


@app.post(COUPON_JOBS + "/model", response_model=None, responses={200: {"content": {"text/plain": {}}, "description": "The model file"}})
def coupon_model(problem: CouponCheckRequest, actor: Actor, request: Request, program: ModelProgram) -> Response:
    """The model the rows build, as a file another program reads (ADR-0129): `program=abaqus` gives the Abaqus input deck a run writes,
    `program=ansys` a Mechanical APDL input file of the same model. The fea package judges the rows as a live solve does and writes the
    file; nothing is solved and nothing is kept. The answer is the file, named in `Content-Disposition`. The Abaqus file is everyone's;
    the Ansys file is too since ADR-0129 amendment 3 (403 if it is closed again, `_ansys_model`). 422 when the setup check stops the model, with its first reason, or the program's writer cannot state it; 429, 504 and
    503 as the live solve. Recorded with its actor (ADR-0026): the values' digest, the program and the file's name, size and SHA-256."""
    if program == "ansys" and not _ansys_model(request):
        raise HTTPException(status_code=403, detail="The Ansys model is not offered yet.")
    receipt = CouponModelReceipt(**problem.receipt().model_dump(exclude_none=True), program=program)
    live: LiveSolver = request.app.state.live
    try:
        email = _email(request)
        found = live.model_file(problem.values_bytes(), program, every=_every_for(request, problem.values_bytes),
                                root=None if email is None else _coupon_jobs(request).root_of(email))
    except LiveBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LiveTimedOut as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except LiveRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if found.state != "written" or found.content is None:
        if found.state == "refused":
            detail = f"This model cannot be written for {MODEL_PROGRAM_NAMES[program]} yet: {found.head.get('problem', 'no reason given')}"
        else:
            reasons = [f"{item.get('label', item.get('id'))}: {item.get('message')}" for item in found.checklist.get("items", [])
                       if item.get("state") in ("fail", "missing") and item.get("message")]
            detail = "The setup is not complete, so there is no model to write yet." + (f" {reasons[0]}" if reasons else "")
        run_id = _record(request, actor, receipt, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id))
    name = Path(str(found.head["name"])).name
    run_id = _record(request, actor, receipt, response={
        "state": found.state, "designation": found.checklist.get("designation"), "program": program, "name": name, "units": found.head.get("units"),
        "bytes": len(found.content), "sha256": hashlib.sha256(found.content).hexdigest(), "nodes": found.head.get("nodes"),
        "elements": found.head.get("elements"), "warm": found.warm, "seconds": round(found.seconds, 3)})
    headers = {"Content-Disposition": f'attachment; filename="{name}"', MODEL_NAME_HEADER: name, **(_run_header(run_id) or {})}
    return Response(content=found.content, media_type="text/plain; charset=utf-8", headers=headers)


async def _read_model(request: Request) -> bytes:
    """The request's body, an Abaqus input deck as it is, refused past the size a model may have before more of it is read."""
    too_large = HTTPException(status_code=413, detail=f"A model is at most {MAX_MODEL_BYTES} bytes as sent")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_MODEL_BYTES:
        raise too_large
    received = bytearray()
    async for chunk in request.stream():
        received += chunk
        if len(received) > MAX_MODEL_BYTES:
            raise too_large
    if not received:
        raise HTTPException(status_code=422, detail="The request has no body: send the Abaqus input deck (.inp) as the body")
    return bytes(received)


@app.post(IMPORTED_MODELS, response_model=None, responses={200: {"model": ImportedModelResponse}})
def import_model(actor: Actor, request: Request, data: Annotated[bytes, Depends(_read_model)], units: ModelUnits,
                 x_anisotropy_model_name: Annotated[str | None, Header(max_length=800)] = None) -> Response:
    """A model brought in as an Abaqus input deck (ADR-0105): the request's body is the .inp file, `units` the system it is written
    in (a deck carries none, and nothing is inferred from its numbers) and the header `X-Anisotropy-Model-Name` the file's name,
    percent-encoded, which so stays out of the address and its logs. The fea package reads it, or
    refuses it with the line, draws it and solves it with our kernel as it stands: nothing is repaired or filled in. The answer is
    the requester's alone and nothing of the deck is kept: the run record holds its name, size and digest, the state, the counts of
    what was read and the answer's summary. Offered where every test is offered, and to a founder's sign-in (ADR-0089 amendment 6): 403 otherwise. 413 past the size a
    model may have, 429 when every solver stays busy, 422 when one does not answer in time, 503 when none can run."""
    if not _imports(request):
        raise HTTPException(status_code=403, detail="Importing a model is not offered yet.")
    name = unquote(x_anisotropy_model_name or "").replace("\\", "/").rsplit("/", 1)[-1].strip()[:200] or "model.inp"
    live: LiveSolver = request.app.state.live
    try:
        found = live.read_model(data, name, units)
    except LiveBusy as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except LiveTimedOut as exc:
        print(f"an imported model was not answered: {exc}", flush=True)  # the cause stays in the log
        raise HTTPException(status_code=422, detail="This model took too long to solve here. Try a coarser mesh.") from exc  # the engineer's to act on
    except LiveRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    fields = found.raw.get("fields")
    head = found.head
    receipt = ImportedModelReceipt(name=name, units=units, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    refused = found.state == "refused"  # recorded as a rejection, with the reader's reason
    run_id = _record(request, actor, receipt, error=str((head.get("problem") or {}).get("message", "refused")) if refused else None, response=None if refused else {
        "state": found.state, "solver": "kernel", "warm": found.warm, "seconds": round(found.seconds, 3), "timings": found.timings,
        "problem": head.get("problem"), "reading": head.get("reading"), "summary": found.summary,
        "fields_sha256": hashlib.sha256(fields).hexdigest() if fields is not None else None})
    first = {"run_id": None if run_id is None else str(run_id), "state": found.state, "name": name, "units": units, "solver": "kernel",
             "warm": found.warm, "seconds": round(found.seconds, 3), "timings": found.timings, "problem": head.get("problem"),
             "reading": head.get("reading")}
    parts = [json.dumps(first)[1:-1].encode("utf-8")]
    for part in ("preview", "fields", "explanation"):
        parts.append(f'"{part}":'.encode("utf-8") + (found.raw[part].strip() if part in found.raw else b"null"))
    return Response(content=b"{" + b",".join(parts) + b"}", media_type="application/json", headers=_run_header(run_id))


@app.post("/v1/tow-tests", response_model=TowTestResponse)
def calculate_tow_test(problem: TowTestRequest, actor: Actor, request: Request, response: Response) -> TowTestResponse:
    """A fibre tow record under ASTM D4018 (ADR-0074): its rows and specimens read and refused by row, judged clause by clause against the
    standard when it names one, and reduced by the engine to each specimen's strength and chord modulus and their statistics, by
    fea/tools/studio_tool.py tow. It is answered at once: a tow has no model and no solver. Recorded with its actor (ADR-0026); the
    record keeps the values' digest. The studio tool answers within two minutes or the request is refused with 504.
    """
    jobs = _coupon_jobs(request)

    every = _every_test(request)

    def compute() -> TowTestResponse:
        try:
            found = jobs.tow(problem.values_bytes(), every=every)
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
    try:
        release = connector_release()
    except ToolFailed:
        release = {"version": None, "sha256": None}  # the card then shows the download without them
    return AbaqusExchange(uploads=getattr(state, "records", None) is not None and getattr(state, "uploads", None) is not None,
                          connector_route=not behind_access or bool(getattr(state, "connector_uploads", False)),
                          max_bundle_bytes=MAX_BUNDLE_BYTES, max_uploads=MAX_UPLOADS, max_tokens=MAX_TOKENS,
                          connector_version=release["version"], connector_sha256=release["sha256"])


@app.get(ABAQUS_CONNECTOR)
def abaqus_connector(request: Request) -> Response:
    """The connector as one zip (ADR-0094 step 6): the four files a user keeps in one folder and the note of its commands, written
    by `fea/tools/abaqus_upload.py connector`. The same for every requester; nothing of theirs is in it."""
    try:
        path = _uploads(request).connector()
    except ToolFailed as exc:
        raise HTTPException(status_code=503, detail=f"The connector could not be handed out: {exc}") from exc
    return FileResponse(path, media_type="application/zip", filename=path.name)


@app.get(ABAQUS_CONNECTOR + "/security-note")
def abaqus_connector_note() -> Response:
    """What the connector installs, reads and sends, as plain text (ADR-0094 amendment 3): the same words as SECURITY.txt in its zip,
    for whoever decides whether it may be installed, before anything is downloaded. The same for every requester."""
    try:
        text = CONNECTOR_NOTE.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=503, detail="The connector's security note could not be read.") from exc
    return Response(text, media_type="text/plain; charset=utf-8", headers={"Content-Disposition": 'inline; filename="anisotropy-connector-SECURITY.txt"'})


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


def _owner_words(actor: str, user_email: str | None) -> str:
    """Whose account a token or a code is for, as a machine shows it to its user before it connects."""
    return user_email if user_email is not None else f"the local user {actor}"


@app.post(PAIRING_CODES, status_code=201, response_model=PairingCode)
def create_pairing_code(actor: Actor, request: Request) -> PairingCode:
    """A one-time code that connects the requester's machine to their account (ADR-0094 amendment 1). The page puts it in a link
    that the machine's helper opens; the helper swaps it at `POST /v1/connector/pair` for an upload token of its own, so no token is
    copied by hand. The code is in this answer and nowhere else, lasts a few minutes and is good for one swap; asking again ends
    the earlier one."""
    engine = _records_engine(request)
    code, digest = new_pairing_code()
    now = dt.datetime.now(dt.timezone.utc)
    try:
        row = insert_pairing_code(engine, code_id=uuid.uuid4(), actor=actor, user_email=_email(request), code_sha256=digest, now=now,
                                  expires_at=now + dt.timedelta(minutes=PAIRING_MINUTES))
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return PairingCode(code=code, expires_at=row.expires_at.isoformat(), minutes=PAIRING_MINUTES)


@app.post(CONNECTOR_PAIR, response_model=Paired)
def pair_machine(wanted: PairInput, request: Request) -> Paired:
    """A machine swaps its one-time code for an upload token (ADR-0094 amendment 1). No sign-in and no token: the code is the proof,
    made minutes ago by a signed-in page. With `look` nothing is swapped and the answer only says whose account the code is for, so
    the machine asks its user before it connects. 401 for a code that is unknown, used or ended, in the same words. Behind
    Cloudflare Access this route is reachable only when ANISOTROPY_CONNECTOR_UPLOADS=on and the Access application lets the path
    through."""
    engine = _records_engine(request)
    now = dt.datetime.now(dt.timezone.utc)
    refused = HTTPException(status_code=401, detail=f"This code is not one of ours, was used already, or is older than {PAIRING_MINUTES} minutes. "
                                                    "Click Connect this PC on the site again")
    digest = token_digest(wanted.code)
    try:
        if wanted.look:
            with_code = fetch_pairing_code(engine, digest, now)
            if with_code is None:
                raise refused
            return Paired(owner=_owner_words(with_code.actor, with_code.user_email))
        code = claim_pairing_code(engine, digest, now)
        if code is None:
            raise refused
        if live_upload_tokens(engine, actor=code.actor, user_email=code.user_email) >= MAX_TOKENS:
            raise HTTPException(status_code=429, detail=f"This account has {MAX_TOKENS} upload keys that are not cancelled. Cancel one on the site, then "
                                                        "click Connect this PC again")
        token, token_sha, hint = new_token()
        name = wanted.name.strip() or "a connected PC"
        row = insert_upload_token(engine, token_id=uuid.uuid4(), actor=code.actor, user_email=code.user_email, name=name, token_sha256=token_sha, hint=hint, now=now)
        name_pairing_token(engine, code.id, row.id)
    except SQLAlchemyError as exc:
        raise _database_error(exc) from exc
    return Paired(owner=_owner_words(code.actor, code.user_email), token=token, token_id=str(row.id), name=row.name)


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


def _connector_run_script(job_id: uuid.UUID, request: Request, owner) -> tuple[str, str]:
    """(the build script of a finished run of the token's owner, the coupon's name as a plain name). 404 for any other run, in the
    same words as for none, so no run is confirmed to a stranger. Nothing is changed."""
    jobs = _coupon_jobs(request)
    job = jobs.get(job_id)
    mine = job is not None and (job.user_email == owner.user_email if owner.user_email is not None else job.user_email is None and job.actor == owner.actor)
    if not mine:
        raise HTTPException(status_code=404, detail=f"No run {job_id} of yours")
    if job.state != "done":
        raise HTTPException(status_code=409, detail=f"Run {job_id} is {job.state}; its coupon for Abaqus is there once it is done")
    try:
        path = jobs.output_file(job, "abaqus_build")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Run {job_id} has no build script for Abaqus: only an unnotched tension run has one") from exc
    except (FileNotFoundError, PermissionError) as exc:
        print(f"coupon job {job_id}: no build script: {exc}", flush=True)
        raise HTTPException(status_code=404, detail="This run's files are no longer available. Run the analysis again from your project.") from exc
    coupon = "".join(c for c in str((job.outcome or {}).get("coupon") or "coupon") if c.isalnum() or c in "-_.") or "coupon"
    return path.read_text(encoding="utf-8"), coupon


@app.get(CONNECTOR_RUNS + "/{job_id}/coupon")
def connector_coupon(job_id: uuid.UUID, request: Request, owner=Depends(_token_owner)) -> JSONResponse:
    """A run's coupon as data for the machine of the run's owner (ADR-0094 amendment 4): the numbers and names its build script
    states, read from the script and never run (`abaqus_coupon.coupon_data`), as one JSON object of the format `anisotropy-coupon/1`.
    The connector checks it and builds the model with code of its own, so a click on Send to Abaqus moves no code to the PC. Asked
    with an upload token and answered only for a finished run of the token's owner, as the build script is. Behind Cloudflare Access
    this route is reachable only when ANISOTROPY_CONNECTOR_UPLOADS=on and the Access application lets the path through."""
    script, coupon = _connector_run_script(job_id, request, owner)
    plain = "".join(c for c in coupon if c.isascii())[:80]  # the name of a folder on the PC, which the connector checks again
    try:
        data = coupon_data(script, plain if plain[:1].isalnum() else "coupon")
    except NotABuildScript as exc:
        print(f"coupon job {job_id}: its build script is not read as data: {exc}", flush=True)
        raise HTTPException(status_code=409, detail="This run's files do not state its coupon for Abaqus. Run the analysis again from your project.") from exc
    return JSONResponse(data, headers={"Cache-Control": "no-store"})


@app.get(CONNECTOR_RUNS + "/{job_id}/build-script")
def connector_build_script(job_id: uuid.UUID, request: Request, owner=Depends(_token_owner)) -> Response:
    """The script that builds a run's coupon in Abaqus/CAE, for the machine of the run's owner (ADR-0094 amendment 1): asked with an
    upload token, answered only for a finished run of the token's owner. 404 for any other run, in the same words as for none, so no
    run is confirmed to a stranger. Nothing is changed. Connectors before 0.7.0 ask for it and run it; since amendment 4 the
    connector asks for the coupon as data instead (`connector_coupon`), and this route stays for the PCs that are not yet set up
    again. Behind Cloudflare Access this route is reachable only when ANISOTROPY_CONNECTOR_UPLOADS=on and the Access application
    lets the path through."""
    script, coupon = _connector_run_script(job_id, request, owner)
    return Response(script, media_type="text/x-python; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{coupon}-build.py"', "X-Anisotropy-Coupon": coupon})


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
    # a run named by its id must be the upload's owner's own (ADR-0104); locally, with no sign-in and no email, any run is
    owner = row.user_email if row.user_email is not None or getattr(request.app.state, "access_verifier", None) is not None else EVERYONE
    if job is None or not _theirs(owner, job.user_email):
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
    """The requester's coupon jobs, newest first (ADR-0051, ADR-0104): this process's and, from the jobs table, those of earlier ones."""
    jobs = _coupon_jobs(request)
    listed = jobs.listed(_owner(request))
    with jobs.lock:
        return [CouponJobOutput.of(job) for job in listed]


@app.get(COUPON_JOBS + "/{job_id}", response_model=CouponJobOutput)
def coupon_job(job_id: uuid.UUID, request: Request) -> CouponJobOutput:
    """A coupon job as it stands: its state, the end of its console, and once it is done the files it made (ADR-0050)."""
    jobs = _coupon_jobs(request)
    job = _known_job(request, jobs, job_id)
    with jobs.lock:
        return CouponJobOutput.of(job)


# What the page shows for a report that cannot be written (ADR-0091 amendment 2): what happened and what to do; the cause goes to the log.
NO_REPORT = "This analysis kept no report to write. Run the analysis again to get one."
REPORT_NOT_NOW = "The report cannot be written right now. Try again in a minute; if it keeps failing, contact us."


@app.post(COUPON_JOBS + "/{job_id}/document", response_model=CouponJobOutput)
def write_coupon_job_document(job_id: uuid.UUID, request: Request, response: Response) -> CouponJobOutput:
    """The report of a done job as a PDF, written when someone asks for it (ADR-0064 amendment 3): a run started with `pdf: false`
    ends without typesetting it and keeps its LaTeX and figures (`document_source`); this typesets them, half a minute on the hosted
    tier, and files the PDF as the job's `document`. 202 with the job as it stands, `report: "writing"`, while it is typeset: poll the
    job until its outputs hold `document`, or `report` says "failed" (ask again to retry). 200 when the job has its report already. 409
    while the job has not ended done, or when it kept no source. Nothing is computed: the report is the run's own, typeset later."""
    jobs = _coupon_jobs(request)
    job = _known_job(request, jobs, job_id)
    try:
        state = jobs.write_document(job)
    except JobNotDone as exc:
        raise HTTPException(status_code=409, detail="The report is written once the analysis has finished.") from exc
    except NoDocument as exc:
        print(str(exc), flush=True)
        raise HTTPException(status_code=409, detail=NO_REPORT) from exc
    except JobRefused as exc:
        print(f"coupon job {job_id}: its report was not started: {exc}", flush=True)
        raise HTTPException(status_code=503, detail=REPORT_NOT_NOW) from exc
    response.status_code = 200 if state == "written" else 202
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
    job = _known_job(request, jobs, job_id)
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
    job = _known_job(request, jobs, job_id)
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
    except JobNotDone as exc:  # the package's zip while the job still writes it (ADR-0064 amendment 2)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    job = _known_job(request, jobs, job_id)
    explanation = _job_json(jobs, job, "explanation", "no explanation")
    facts, sentences = explanation.get("facts", {}), list(explanation.get("sentences", []))
    checklist = _job_json(jobs, job, "checklist", "no setup check") if problem.kind == "setup" else None
    template = list(explanation.get("setup_sentences", [])) if problem.kind == "setup" else sentences
    seen = checklist if problem.kind == "setup" else facts
    receipt = ExplainReceipt(job_id=str(job_id), kind=problem.kind,
                             facts_sha256=hashlib.sha256(json.dumps(seen, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest())
    assistant = _assistant(request, actor)
    calls: list[ModelCall] = []

    def compute() -> ExplainResponse:
        draft = _billed(calls, assistant.explain_setup(checklist, template) if problem.kind == "setup" else assistant.explain_result(facts, template))
        return ExplainResponse(run_id=None, job_id=str(job_id), kind=problem.kind, writer=draft.writer, model=draft.model, prose=list(draft.prose),
                               withheld=draft.withheld, reason=draft.reason, facts=facts if problem.kind == "result" else {"checklist": checklist})

    return _deliver(request, response, actor, receipt, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None),
                    calls=calls)


@app.get("/v1/coupons", response_model=list[CouponSummary])
def list_coupons(request: Request) -> list[CouponSummary]:
    """The requester's coupons, from their specs and case pages (ADR-0051): what the studio offers to reopen. A signed-in person's
    are those in their own folder (ADR-0106). With no sign-in in front of the API, every coupon on this machine; for a request with
    no email behind the sign-in (a service token), the shared folder's coupons that jobs with no email alone have run (ADR-0104)."""
    jobs = _coupon_jobs(request)
    owner = _owner(request)
    try:
        if owner != EVERYONE and owner is not None:
            return [CouponSummary(**entry) for entry in jobs.list_coupons(user_email=owner)]
        mine = None if owner == EVERYONE else jobs.coupons_of(owner)
        return [CouponSummary(**entry) for entry in jobs.list_coupons() if mine is None or entry.get("name") in mine]
    except SQLAlchemyError as exc:
        raise _coupons_unread(exc) from exc
    except CheckTimedOut as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except JobRefused as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/v1/coupons/{name}/values", response_model=CouponValuesOutput)
def coupon_values(name: str, request: Request) -> CouponValuesOutput:
    """A coupon's rows as the values object the studio edits (ADR-0051): the inverse of the form's reading. 404 for a coupon that
    is not the requester's (ADR-0104, ADR-0106)."""
    jobs = _coupon_jobs(request)
    _their_coupon(request, jobs, name)
    try:
        return CouponValuesOutput(name=name, values=jobs.coupon_values(name, every=_every_test(request), user_email=_email(request)))
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
    assistant = _assistant(request, actor)
    calls: list[ModelCall] = []

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
        draft = _billed(calls, assistant.explain_laminate(facts, template))
        return LaminateAnswer(
            run_id=None, engine_version=version("anisotropy-engine"), report_units=problem.report_units, units=unit_labels(problem.report_units),
            case=case, results={key: _json_value(value) for key, (value, _scale) in results.items()}, criteria=list(failures),
            summary=LaminateSummaryOutput.of(summary), material=None if cited is None else MaterialProvenance.of(cited),
            writer=draft.writer, model=draft.model, prose=list(draft.prose), withheld=draft.withheld, reason=draft.reason, facts=facts,
        )

    return _deliver(request, response, actor, problem, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None),
                    calls=calls)


WINGS = "/v1/wings/analyze"
WING_CHANGES = "/v1/wings/changes"
WING_SHAPE = "/v1/wings/shape"
WING_SHAPE_TIMEOUT_S = 90.0  # Gmsh builds the example in under a second; a cold start of the fea environment takes a few
SHAPE_REFUSED = 2  # anisotropy_fea.wing_shape.REFUSED: the description was refused, the reason on stderr


def _finite(value) -> bool:
    """Whether a JSON-like value holds only finite numbers (None stands for an unloaded check and is fine)."""
    if isinstance(value, dict):
        return all(_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite(v) for v in value)
    return not isinstance(value, float) or math.isfinite(value)


@app.post(WINGS, response_model=WingAnswer)
def analyze_wing_endpoint(problem: WingRequest, actor: Actor, request: Request, response: Response) -> WingAnswer:
    """A wing worked by hand (ADR-0115) for the wing workspace (ADR-0118): the description read by the engine's own rules, every
    flight case that its values allow, the results in the file's units and what the page draws. Recorded with its actor (ADR-0026):
    the record keeps the description, the verdict, the governing check and the design summary, not the drawings, which follow from
    them. Answers in well under a second, so the page asks again on every change."""
    try:
        data = tomllib.loads(problem.toml) if problem.toml is not None else problem.wing
        wing, envelope = wing_from_dict(data)
        result = analyze_wing(wing, envelope)
        report = wing_report(result, data["units"], data["envelope"]["speed_unit"])
        views = wing_views(result, data["units"])
        if not (_finite(report) and _finite(views)):
            raise FloatingPointError("Non-finite result")
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError, FloatingPointError, OverflowError, ZeroDivisionError) as exc:
        detail = (str(exc) or exc.__class__.__name__) if not isinstance(exc, (FloatingPointError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError)) \
            else "These values do not give a finite, solvable wing. Check the values and their units."
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    summary = {key: report[key] for key in ("wing", "passes", "seconds", "design", "governing", "aeroelastic")}
    run_id = _record(request, actor, problem, response=summary | {"cases_run": len(report["cases"]), "cases_not_run": len(report["not_run"])})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return WingAnswer(run_id=None if run_id is None else str(run_id), engine_version=version("anisotropy-engine"), wing=data,
                      report=report, views=views)


@app.post(WING_CHANGES, response_model=WingChangePreview)
def preview_wing_change(problem: WingChangeRequest, actor: Actor, request: Request, response: Response) -> WingChangePreview:
    """A change of plies previewed on a wing (ADR-0128): the engine makes it on a copy of the wing file (zones split and joined, ADR-0125)
    and works the wing as it is and as changed by hand, in well under a second. Nothing is kept: the engineer applies the change on the
    page, or not, and the chat and the MCP server only preview. A change the wing cannot take (no spar caps, too few plies of the angle)
    is refused in the engine's words. Recorded with its actor (ADR-0026): the change, its sentence and both summaries, not the wing."""
    try:
        data = tomllib.loads(problem.toml) if problem.toml is not None else problem.wing
        preview = preview_change(data, problem.change)
        if not _finite(preview):
            raise FloatingPointError("Non-finite result")
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError, FloatingPointError, OverflowError, ZeroDivisionError) as exc:
        detail = (str(exc) or exc.__class__.__name__) if not isinstance(exc, (FloatingPointError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError)) \
            else "These values do not give a finite, solvable wing. Check the values and their units."
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    run_id = _record(request, actor, problem, response={key: preview[key] for key in ("change", "words", "before", "after")})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return WingChangePreview(run_id=None if run_id is None else str(run_id), engine_version=version("anisotropy-engine"), **preview)


@app.post(WING_SHAPE, response_model=WingShapeAnswer)
def wing_shape_endpoint(problem: WingRequest, actor: Actor, request: Request, response: Response) -> WingShapeAnswer:
    """A wing's shape for a CAD program (ADR-0116), from the wing workspace's Download STEP (ADR-0118): the engine reads the
    description first, so a wing the page could not work is refused in the same words, then the fea package's `wing_shape` builds
    the parts in Gmsh's OpenCASCADE in a process of its own (the API depends on the engine alone, ADR-0051) and writes the STEP file
    and the part table. Recorded with its actor: the description and a summary, never the file."""
    try:
        data = tomllib.loads(problem.toml) if problem.toml is not None else problem.wing
        wing_from_dict(data)
    except (ValueError, TypeError, KeyError) as exc:
        detail = str(exc) or exc.__class__.__name__
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    command = wing_shape_command()
    if command is None:
        raise HTTPException(status_code=503, detail="The shape builder is not installed here")
    with tempfile.TemporaryDirectory(prefix="wing-shape-") as folder:
        wing_json, step_path, parts_path = Path(folder) / "wing.json", Path(folder) / "wing.step", Path(folder) / "parts.json"
        wing_json.write_text(json.dumps(data), encoding="utf-8")
        try:
            done = subprocess.run([*command, str(wing_json), str(step_path), "--parts", str(parts_path)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", cwd=FEA, timeout=WING_SHAPE_TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired as exc:
            run_id = _record(request, actor, problem, error="the shape took longer than the time allowed")
            raise HTTPException(status_code=504, detail="The shape took too long to build", headers=_run_header(run_id)) from exc
        reason = next((line.strip() for line in reversed(done.stderr.splitlines()) if line.strip()), "")
        if done.returncode == SHAPE_REFUSED and reason:
            run_id = _record(request, actor, problem, error=reason)
            raise HTTPException(status_code=422, detail=reason, headers=_run_header(run_id))
        if done.returncode != 0 or not step_path.exists() or not parts_path.exists():
            print(f"the wing shape stopped with status {done.returncode}: {reason}", flush=True)  # the tool's own words stay in the log
            run_id = _record(request, actor, problem, error=f"the shape builder stopped with status {done.returncode}")
            raise HTTPException(status_code=503, detail="The shape could not be built", headers=_run_header(run_id))
        step = step_path.read_text(encoding="ascii", errors="replace")
        parts = json.loads(parts_path.read_text(encoding="utf-8"))
    run_id = _record(request, actor, problem, response={"wing": parts.get("wing"), "parts": len(parts.get("parts", [])), "mass": parts.get("mass"),
                                                        "step_bytes": len(step)})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return WingShapeAnswer(run_id=None if run_id is None else str(run_id), step=step, parts=parts)


# What the page shows of a wing's check that did not end done, in its own words (ADR-0091 amendment 2): the cause goes to the log.
CHECK_STOPPED = "The check could not be finished. Start it again; if it keeps failing, contact us."
CHECK_UNREAD = "The check's result could not be read right now. Try again in a minute."
WING_REPORT = "wing_check"  # the key the check's tool lists its report under (anisotropy_fea.wing_check.OUTPUT_KEY)


def _wing_check(request: Request, jobs: CouponJobs, job_id: uuid.UUID) -> Job:
    """A wing's check by its id when it is the requester's; 404 in the same words as for none, a coupon job included."""
    job = _known_job(request, jobs, job_id)
    if not is_wing(job):
        raise HTTPException(status_code=404, detail="These results are no longer available. Run the analysis again from your project.")
    return job


def _wing_check_output(jobs: CouponJobs, job: Job) -> WingCheckOutput:
    """The check as it stands, and once done its report, read here from the job's file (the disk or the store)."""
    with jobs.lock:
        state, outcome, progress = job.state, dict(job.outcome or {}), dict(job.progress() or {})
    message, report = None, None
    if state == "queued":
        message = progress.get("message")
    elif state == "refused":
        message = outcome.get("message")  # the reason the description cannot be checked, in the engine's or the model's words
    elif state == "stopped":
        print(f"wing check {job.id} stopped: {outcome.get('message')}", flush=True)
        message = CHECK_STOPPED
    elif state == "done":
        try:
            report = json.loads(jobs.output_file(job, WING_REPORT).read_text(encoding="utf-8"))
        except (KeyError, OSError, ValueError, PermissionError) as exc:
            print(f"wing check {job.id}: its report could not be read: {exc}", flush=True)
            message = CHECK_UNREAD
    return WingCheckOutput(job_id=str(job.id), state=state, wing=(job.inputs or {}).get("wing"), started_at=job.started_at.isoformat(),
                           finished_at=None if job.finished_at is None else job.finished_at.isoformat(), stage=progress.get("stage"),
                           stages_done=list(progress.get("done") or []), stages=list(progress.get("stages") or []), message=message,
                           run_id=None if job.run_id is None else str(job.run_id), report=report)


@app.post(WING_CHECKS, status_code=202, response_model=WingCheckOutput)
def start_wing_check(problem: WingCheckRequest, actor: Actor, request: Request, response: Response) -> WingCheckOutput:
    """A wing's finite element check (ADR-0117, ADR-0119), started from the wing workspace like a coupon run: the engine reads the
    description first, so a wing the page could not work is refused in the same words and at once; then the check runs in the
    background, through the job queue on the hosted tier, half a minute for the example. Poll the Location until the state is
    neither queued nor running; once done the answer holds the check's report in the wing file's units. The same limits as a
    coupon run apply: one at a time here, and the hosted tier's per-user limits (409, 429). Its receipt is a run record at this
    address, written when it ends. `project_id` names the wing project it is run for, when it is the requester's (ADR-0122)."""
    try:
        data = tomllib.loads(problem.toml) if problem.toml is not None else problem.wing
        wing, _ = wing_from_dict(data)
    except (ValueError, TypeError, KeyError) as exc:
        detail = str(exc) or exc.__class__.__name__
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    jobs = _coupon_jobs(request)
    try:
        job = jobs.start_wing(actor, {"kind": WING, "wing": wing.name, "description": data}, user_email=getattr(request.state, "user_email", None),
                              project_id=_own_project_id(request, actor, problem.project_id))
    except JobBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except JobLimited as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except JobRefused as exc:
        print(f"wing check not started: {exc}", flush=True)
        raise HTTPException(status_code=503, detail="The check could not be started right now. Try again in a minute.") from exc
    response.headers["Location"] = f"{WING_CHECKS}/{job.id}"
    if job.state == "queued":
        response.headers[ENQUEUE_HEADER] = str(job.id)
    return _wing_check_output(jobs, job)


@app.get(WING_CHECKS + "/{job_id}", response_model=WingCheckOutput)
def wing_check(job_id: uuid.UUID, request: Request) -> WingCheckOutput:
    """A wing's check as it stands: its state and stage, and once done its report (ADR-0119)."""
    jobs = _coupon_jobs(request)
    return _wing_check_output(jobs, _wing_check(request, jobs, job_id))


REPAIRS = "/v1/repairs/analyze"
REPAIR_SOLVE = "/v1/repairs/solve"
REPAIR_SHAPE = "/v1/repairs/shape"
REPAIR_SOLVE_TIMEOUT_S = 120.0  # CalculiX solves the example's slice in about 3 s; a cold start of the fea environment takes a few more
REPAIR_REFUSED, REPAIR_STOPPED = 2, 3  # anisotropy_fea.repair_shape.REFUSED and repair_model.STOPPED: the repair was refused; the solver failed
REPAIR_REPORT = "repair-solve.json"  # anisotropy_fea.repair_model.REPORT, in the folder the solve is given
# What the page shows when the solve or the shape fails for a reason that is not the repair's (ADR-0091 amendment 2): the cause goes to the log.
SLICE_NOT_NOW = "The slice could not be solved right now. Try again in a minute; if it keeps failing, contact us."
UNSOLVABLE_REPAIR = "These values do not give a finite, solvable repair. Check the values and their units."


def _repair_read(request: Request, actor: str, problem: RepairRequest):
    """The repair a request states, by the engine's own reading: the table, the repair and its load; 422 in the engine's words."""
    try:
        data = tomllib.loads(problem.toml) if problem.toml is not None else problem.repair
        repair, load = repair_from_dict(data)
    except (ValueError, TypeError, KeyError) as exc:
        detail = str(exc) or exc.__class__.__name__
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    return data, repair, load


def _repair_tool(request: Request, actor: str, problem: RepairRequest, command: list[str], folder: Path, what: str, timeout_s: float) -> subprocess.CompletedProcess:
    """One of the fea package's repair tools run to its end in a process of its own (ADR-0051, ADR-0135); 504 when it outlasts its time."""
    try:
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=FEA, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as exc:
        run_id = _record(request, actor, problem, error=f"{what} took longer than the time allowed")
        raise HTTPException(status_code=504, detail=f"{what[0].upper()}{what[1:]} took too long", headers=_run_header(run_id)) from exc


@app.post(REPAIRS, response_model=RepairAnswer)
def analyze_repair_endpoint(problem: RepairRequest, actor: Actor, request: Request, response: Response) -> RepairAnswer:
    """A stepped patch repair worked by hand (ADR-0130, ADR-0131) for the repair's page (ADR-0135): the description read by the engine's
    own rules, what it works out to in the file's units (sizes, the slice's rectangles, the lap and, with a load, its answer), the
    hand calculation's curve along the bond for the page to draw, and what a solve of the slice still needs. Recorded with its actor
    (ADR-0026): the description and the answer's headline numbers, not the drawings. Answers in milliseconds, so the page asks again
    on every change."""
    data, repair, load = _repair_read(request, actor, problem)
    try:
        report = repair_report(repair, data["units"], load)
        views = repair_views(repair, data["units"], load)
        if not (_finite(report) and _finite(views)):
            raise FloatingPointError("Non-finite result")
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError, FloatingPointError, OverflowError, ZeroDivisionError) as exc:
        detail = (str(exc) or exc.__class__.__name__) if not isinstance(exc, (FloatingPointError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError)) \
            else UNSOLVABLE_REPAIR
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    needs = solve_needs(repair, load)
    answer = report["lap"].get("answer") or {}
    run_id = _record(request, actor, problem, response={"kind": report["kind"], "units": report["units"], "sizes": report["sizes"], "load": report["lap"].get("load"),
                                                        "peak_shear": answer.get("peak_shear"), "elastic_limit_load": answer.get("elastic_limit_load"),
                                                        "solve_needs": [need["path"] for need in needs]})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return RepairAnswer(run_id=None if run_id is None else str(run_id), engine_version=version("anisotropy-engine"), repair=data, report=report,
                        views=views, needs=needs, bond_needs=bond_needs(repair))


def _repair_tool_report(command: list[str] | None, data: dict, options: list[str], report_name: str, what: str, timeout_s: float) -> tuple[str, Any]:
    """One of the fea package's repair tools run on a repair's table in a process of its own (ADR-0051), and the report it leaves in
    the folder it is given: how it ended and what came of it. `("solved", report)` with the tool's report, its headline in it;
    `("refused", words)` in the tool's words; `("absent", None)` where the tool is not installed; `("slow", None)` when it outlasts
    its time; `("failed", status)`, the cause written to the log and to no reader (ADR-0091 amendment 2)."""
    if command is None:
        return "absent", None
    with tempfile.TemporaryDirectory(prefix="repair-solve-") as folder:
        stated, out = Path(folder) / "repair.json", Path(folder) / "model"
        stated.write_text(json.dumps(data), encoding="utf-8")
        try:
            done = subprocess.run([*command, str(stated), "--out", str(out), *options], capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", cwd=FEA, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            return "slow", None
        refusal = next((line.strip()[len("refused:"):].strip() for line in reversed(done.stdout.splitlines()) if line.strip().startswith("refused:")), "")
        if done.returncode == REPAIR_REFUSED and refusal:
            return "refused", refusal
        try:
            report = json.loads((out / report_name).read_text(encoding="utf-8")) if done.returncode == 0 else None
        except (OSError, ValueError):
            report = None
        if not isinstance(report, dict) or not isinstance(report.get("headline"), str) or not _finite(report):
            cause = next((line.strip() for line in reversed(done.stderr.splitlines()) if line.strip()), "")
            print(f"{what} stopped with status {done.returncode}: {cause}", flush=True)  # the tool's own words stay in the log
            return "failed", done.returncode
    return "solved", report


def _slice_solved(data: dict, cut_faces: str, timeout_s: float) -> tuple[str, Any]:
    """A repair's slice built, solved and read back by the fea package's `repair_model` (ADR-0132), as `_repair_tool_report` ends."""
    return _repair_tool_report(repair_model_command(), data, ["--cut-faces", cut_faces], REPAIR_REPORT, "the repair's solve", timeout_s)


@app.post(REPAIR_SOLVE, response_model=RepairSolveAnswer)
def solve_repair_endpoint(problem: RepairSolveRequest, actor: Actor, request: Request, response: Response) -> RepairSolveAnswer:
    """A repair's slice solved in CalculiX (ADR-0132) from the repair's page (ADR-0135): the engine reads the description first, so a
    repair the page could not work is refused in the same words, and one that lacks what a solve needs is refused with the list; then
    the fea package's `repair_model` builds the slice, solves it and reads it back in a process of its own, with ADR-0132's mesh and
    its checks. A solve the tool refuses (the forces do not add up, the panel is too short for the far field) is refused in its
    words; a solver that fails is said so without them. Recorded with its actor: the description and the solve's headline numbers."""
    data, repair, load = _repair_read(request, actor, problem)
    needs = solve_needs(repair, load)
    if needs:
        detail = "The solve of the slice needs: " + "; ".join(need["words"] for need in needs) + "."
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id))
    ended, report = _slice_solved(data, problem.cut_faces, REPAIR_SOLVE_TIMEOUT_S)
    if ended == "absent":
        raise HTTPException(status_code=503, detail="The solver is not installed here")
    if ended == "slow":
        run_id = _record(request, actor, problem, error="the solve of the slice took longer than the time allowed")
        raise HTTPException(status_code=504, detail="The solve of the slice took too long", headers=_run_header(run_id))
    if ended == "refused":
        run_id = _record(request, actor, problem, error=report)
        raise HTTPException(status_code=422, detail=report, headers=_run_header(run_id))
    if ended == "failed":
        run_id = _record(request, actor, problem, error=f"the solve stopped with status {report}")
        raise HTTPException(status_code=503, detail=SLICE_NOT_NOW, headers=_run_header(run_id))
    headline = report.pop("headline")
    run_id = _record(request, actor, problem, response={"headline": headline, "model": report.get("model"), "checks": report.get("checks"),
                                                        "peak_shear": report.get("bond", {}).get("peak_shear"), "peak_peel": report.get("bond", {}).get("peak_peel"),
                                                        "first": report.get("first")})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return RepairSolveAnswer(run_id=None if run_id is None else str(run_id), headline=headline, report=report)


REPAIR_BOND = "/v1/repairs/bond"
REPAIR_BOND_TIMEOUT_S = 120.0  # the example's bond is followed in about 10 s; a cold start of the fea environment takes a few more
REPAIR_BOND_REPORT = "repair-bond.json"  # anisotropy_fea.repair_bond.REPORT, in the folder the run is given
BOND_NOT_NOW = "The bond could not be followed right now. Try again in a minute; if it keeps failing, contact us."


@app.post(REPAIR_BOND, response_model=RepairBondAnswer)
def follow_repair_bond_endpoint(problem: RepairRequest, actor: Actor, request: Request, response: Response) -> RepairBondAnswer:
    """A repair's bond followed until it lets go (ADR-0140) from the repair's page: the engine reads the description first, so a repair
    the page could not work is refused in the same words, and one that lacks what the run needs (the adhesive's two strengths and two
    fracture energies, and what a solve needs) is refused with the list; then the fea package's `repair_bond` builds the slice with the
    bond as pairs, follows its path and reads it back in a process of its own. It needs no load: the load is what it finds. A run the
    tool refuses is refused in its words; one that fails is said so without them. Recorded with its actor: the description and the
    run's headline numbers, not its curves."""
    data, repair, _ = _repair_read(request, actor, problem)
    needs = bond_needs(repair)
    if needs:
        detail = "To follow the bond until it lets go the repair needs: " + "; ".join(need["words"] for need in needs) + "."
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id))
    ended, report = _repair_tool_report(repair_bond_command(), data, [], REPAIR_BOND_REPORT, "the repair's bond run", REPAIR_BOND_TIMEOUT_S)
    if ended == "absent":
        raise HTTPException(status_code=503, detail="The solver is not installed here")
    if ended == "slow":
        run_id = _record(request, actor, problem, error="following the bond took longer than the time allowed")
        raise HTTPException(status_code=504, detail="Following the bond took too long", headers=_run_header(run_id))
    if ended == "refused":
        run_id = _record(request, actor, problem, error=report)
        raise HTTPException(status_code=422, detail=report, headers=_run_header(run_id))
    if ended == "failed":
        run_id = _record(request, actor, problem, error=f"the bond's run stopped with status {report}")
        raise HTTPException(status_code=503, detail=BOND_NOT_NOW, headers=_run_header(run_id))
    headline = report.pop("headline")
    onset, fell = report.get("onset") or {}, report.get("let_go")
    run_id = _record(request, actor, problem, response={
        "headline": headline, "model": report.get("model"), "checks": report.get("checks"), "ended": report.get("ended"),
        "onset": {key: onset.get(key) for key in ("load", "r", "part")},
        "let_go": None if fell is None else {key: fell.get(key) for key in ("load", "softening_length", "parted_length")},
        "largest_load": (report.get("largest") or {}).get("load")})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return RepairBondAnswer(run_id=None if run_id is None else str(run_id), headline=headline, report=report)


REPAIR_CHANGES = "/v1/repairs/changes"
REPAIR_SWEEPS = "/v1/repairs/sweeps"
PICK_NOT_CHECKED = "The pick's slice could not be solved right now, so the pick is not checked by a solved slice."


def _repair_worked(request: Request, actor: str, problem: RepairRequest, work):
    """What the engine makes of a repair request's table (`work(data)`), every number finite; 422 in the engine's words otherwise."""
    try:
        data = tomllib.loads(problem.toml) if problem.toml is not None else problem.repair
        found = work(data)
        if not _finite(found):
            raise FloatingPointError("Non-finite result")
    except (ValueError, TypeError, KeyError, np.linalg.LinAlgError, FloatingPointError, OverflowError, ZeroDivisionError) as exc:
        detail = (str(exc) or exc.__class__.__name__) if not isinstance(exc, (FloatingPointError, OverflowError, ZeroDivisionError, np.linalg.LinAlgError)) \
            else UNSOLVABLE_REPAIR
        run_id = _record(request, actor, problem, error=detail)
        raise HTTPException(status_code=422, detail=detail, headers=_run_header(run_id)) from exc
    return found


@app.post(REPAIR_CHANGES, response_model=RepairChangePreview)
def preview_repair_change_endpoint(problem: RepairChangeRequest, actor: Actor, request: Request, response: Response) -> RepairChangePreview:
    """A change previewed on a repair (ADR-0136): the engine makes it on a copy of the repair file (a quantity set, in the unit as
    written; steps added, removed or regrouped) and works the repair as it is and as changed by hand, in milliseconds. Nothing is
    kept: the engineer applies the change on the page, or not, and the chat and the MCP server only preview. A change the repair
    cannot take is refused in the engine's words. Recorded with its actor (ADR-0026): the change, its sentence and both summaries."""
    preview = _repair_worked(request, actor, problem, lambda data: preview_repair_change(data, problem.change))
    run_id = _record(request, actor, problem, response={key: preview[key] for key in ("change", "words", "before", "after")})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return RepairChangePreview(run_id=None if run_id is None else str(run_id), engine_version=version("anisotropy-engine"), **preview)


@app.post(REPAIR_SWEEPS, response_model=RepairSweepAnswer)
def sweep_repair_endpoint(problem: RepairSweepRequest, actor: Actor, request: Request, response: Response) -> RepairSweepAnswer:
    """One quantity of a repair swept (ADR-0136): the engine works the repair by hand at every value, in milliseconds, and with a load
    named picks the smallest repair whose adhesive is still elastic at it. That pick is then solved as a slice here (ADR-0132, as
    `/v1/repairs/solve` does, a few seconds) unless `confirm` is false, and `check` says what the slice makes of it: the largest
    shear and peel, what reaches its limit first and at what load, and whether that load is at or above the load named. A repair
    that lacks what a solve needs, or a solve that cannot run, leaves the sweep's answer whole and says the pick is not checked.
    Nothing is kept or changed. Recorded with its actor: the sweep, its sentences, the pick's row and the check, not every row."""
    found = _repair_worked(request, actor, problem, lambda data: sweep_repair(data, problem.sweep))
    check = None
    if found["pick"] is not None and problem.confirm:
        repair, load = repair_from_dict(found["picked"])
        needs = solve_needs(repair, load)
        if needs:
            check = {"state": "needs", "holds": None, "needs": needs,
                     "words": ["The pick is not checked by a solved slice, which needs: " + "; ".join(need["words"] for need in needs) + "."]}
        else:
            ended, report = _slice_solved(found["picked"], problem.cut_faces, REPAIR_SOLVE_TIMEOUT_S)
            if ended == "solved":
                try:
                    check = pick_check(found["target"], report) | {"headline": report["headline"]}
                except (KeyError, TypeError, ValueError):  # a report without what the check reads: the pick stays unchecked
                    check = {"state": "failed", "holds": None, "words": [PICK_NOT_CHECKED]}
            elif ended == "refused":
                check = {"state": "refused", "holds": None, "words": [f"The pick's slice was not solved: {report}", "The pick is not checked by a solved slice."]}
            else:
                check = {"state": "failed", "holds": None, "words": [PICK_NOT_CHECKED]}
    pick = None if found["pick"] is None else found["rows"][found["pick"]]
    run_id = _record(request, actor, problem, response={"sweep": found["sweep"], "words": found["words"], "rows": len(found["rows"]), "pick": pick,
                                                        "target": found["target"], "flat_from": found["flat_from"],
                                                        "check": None if check is None else {key: check.get(key) for key in ("state", "holds", "close", "first", "words")}})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return RepairSweepAnswer(run_id=None if run_id is None else str(run_id), engine_version=version("anisotropy-engine"), check=check, **found)


@app.post(REPAIR_SHAPE, response_model=RepairShapeAnswer)
def repair_shape_endpoint(problem: RepairRequest, actor: Actor, request: Request, response: Response) -> RepairShapeAnswer:
    """A repair's solids for a CAD program (ADR-0131), from the repair page's Download STEP (ADR-0135): the engine reads the description
    first, then the fea package's `repair_shape` builds every ply and the adhesive as a named solid in Gmsh's OpenCASCADE, in a process
    of its own, and writes the STEP file and the table of the solids. Recorded with its actor: the description and a summary, never
    the file."""
    data, _, _ = _repair_read(request, actor, problem)
    command = repair_shape_command()
    if command is None:
        raise HTTPException(status_code=503, detail="The shape builder is not installed here")
    with tempfile.TemporaryDirectory(prefix="repair-shape-") as folder:
        stated, step_path, parts_path = Path(folder) / "repair.json", Path(folder) / "repair.step", Path(folder) / "parts.json"
        stated.write_text(json.dumps(data), encoding="utf-8")
        done = _repair_tool(request, actor, problem, [*command, str(stated), "--step", str(step_path), "--parts", str(parts_path)], Path(folder),
                            "the shape", WING_SHAPE_TIMEOUT_S)
        reason = next((line.strip() for line in reversed(done.stderr.splitlines()) if line.strip()), "")
        if done.returncode == REPAIR_REFUSED and reason:
            run_id = _record(request, actor, problem, error=reason)
            raise HTTPException(status_code=422, detail=reason, headers=_run_header(run_id))
        if done.returncode != 0 or not step_path.exists() or not parts_path.exists():
            print(f"the repair's shape stopped with status {done.returncode}: {reason}", flush=True)  # the tool's own words stay in the log
            run_id = _record(request, actor, problem, error=f"the shape builder stopped with status {done.returncode}")
            raise HTTPException(status_code=503, detail="The shape could not be built", headers=_run_header(run_id))
        step = step_path.read_text(encoding="ascii", errors="replace")
        parts = json.loads(parts_path.read_text(encoding="utf-8"))
    run_id = _record(request, actor, problem, response={"title": parts.get("title"), "parts": len(parts.get("parts", [])), "volumes": parts.get("volumes"),
                                                        "step_bytes": len(step)})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return RepairShapeAnswer(run_id=None if run_id is None else str(run_id), step=step, parts=parts)


@app.get("/v1/workspace/assistant", response_model=AssistantInfo)
def workspace_assistant(request: Request) -> AssistantInfo:
    """Whether a model reads the chat's messages here (ADR-0088); the page asks once. Not a run: nothing is computed or recorded. With a
    model, whether the Assistant check has been run with it (ADR-0121 amendment 8); the check after a deploy reads it."""
    assistant = getattr(request.app.state, "assistant", None) or TemplateAssistant()
    proposes = assistant.name != "template"
    model = getattr(assistant, "model", None) if proposes else None
    return AssistantInfo(proposes=proposes, provider=assistant.name if proposes else None, model=model,
                         checked=None if model is None else model in CHECKED_MODELS)


@app.get("/v1/coupon-tests", response_model=CouponTests)
def coupon_tests(request: Request) -> CouponTests:
    """What is offered to the requester (ADR-0089); the page asks once. `all`: every coupon test, by the machine's switch alone; the
    page offers the unnotched tension coupon only unless this says so. `imports`: bringing a model in as a file (ADR-0105), by the
    switch or a founder's sign-in (amendment 6). Not a run: nothing is computed or recorded."""
    return CouponTests(all=_every_test(request), imports=_imports(request), plates=_plates(request), ansys_model=_ansys_model(request))


def _every_test(request: Request) -> bool:
    """Whether every test is offered to this request (ADR-0089): the machine's switch is on. A founder's sign-in was offered every
    test from amendment 5 to amendment 6, and is no longer. Nothing the request itself says can turn it on. Without the startup's
    settings (a test client), the environment is read."""
    settings = getattr(request.app.state, "settings", None)
    return all_tests(environment()) if settings is None else settings.all_tests


PLATE_WORD = "plate"  # the Test row's word of a plate, held and loaded on regions the engineer names (ADR-0054)


def _plates(request: Request) -> bool:
    """Whether a plate may be set up on the model tree by this request (ADR-0089 amendment 7): where the import is, the machine's switch
    or a founder's sign-in. Nothing the request itself says can turn it on."""
    return _imports(request)


def _every_for(request: Request, values: bytes | Callable[[], bytes] | None) -> bool:
    """Whether every test is offered to this call: the machine's switch is on, or a founder sets up a plate (ADR-0089 amendment 7), that
    is, the values the call sends name the plate's test. The package's list holds the tension coupon alone, so the plate needs the option;
    a founder's values of any other test are judged by the list, as everyone's are."""
    if _every_test(request):
        return True
    if values is None or not _plates(request):
        return False
    try:  # a values object the request's own check refuses is refused there, by row, as before
        test = json.loads(values() if callable(values) else values).get("test")
    except (ValueError, AttributeError):
        return False
    return isinstance(test, str) and test.strip().lower() == PLATE_WORD


def _ansys_model(request: Request) -> bool:
    """Whether the model may be downloaded as an Ansys file by this request (ADR-0129): everyone's since amendment 3, on the founder's
    word. It was offered where the import is until then; a False here closes it again, and the route answers 403."""
    return True


def _imports(request: Request) -> bool:
    """Whether a model may be brought in as a file by this request (ADR-0105; ADR-0089 amendment 6): the machine's switch is on, or the
    signed-in email Cloudflare Access verified is one of the founders'. Nothing the request itself says can turn it on."""
    if _every_test(request):
        return True
    settings = getattr(request.app.state, "settings", None)
    email = getattr(request.state, "user_email", None)
    return settings is not None and email is not None and email.strip().lower() in settings.founder_emails


@app.post("/v1/workspace/proposals", response_model=ProposalResponse)
def propose_rows(proposal: ProposalRequest, actor: Actor, request: Request, response: Response) -> ProposalResponse:
    """The model reads a message into the rows the page offers, and the source guard keeps what the engineer's own words hold (ADR-0088):
    each value as written, in the quote it came from, converted only between the decimal units of the row's own system. The engineer ticks
    what enters the problem; nothing here computes a result. With no model, or one that does not answer, nothing is proposed and the page
    reads the message with its own patterns. Recorded with the model's name when one read it (ADR-0026)."""
    assistant = _assistant(request, actor)
    calls: list[ModelCall] = []

    def compute() -> ProposalResponse:
        rows = [row.model_dump(mode="json", exclude_none=True) for row in proposal.rows]
        conditions = [c.model_dump(mode="json") for c in proposal.conditions]
        view = {"product": proposal.product, "message": proposal.message, "rows": rows, "conditions": conditions,
                "form": model_view_of_form(proposal.form)}
        plate = proposal.plate.model_dump(mode="json") if proposal.plate is not None else None
        if plate is None:
            reading = _billed(calls, assistant.propose(view))
        else:  # a plate's regions and the place clicked: the same reading, with supports and loads in its schema (ADR-0101)
            view["plate"] = plate_view(plate)
            reading = _billed(calls, assistant.propose(view, plate_schema(PROPOSAL_SCHEMA, [r["name"] for r in plate["regions"]]), PLATE_SYSTEM))
        if reading.raw is None:
            return ProposalResponse(run_id=None, writer=reading.writer, model=None, proposals=[], conditions=[], question=None, dropped=[],
                                    reason=reading.reason)
        kept = source_guard(reading.raw, proposal.message, rows, conditions)
        on_plate = plate_guard(reading.raw, proposal.message, plate) if plate is not None else KeptPlate()
        return ProposalResponse(run_id=None, writer=reading.writer, model=reading.model, proposals=kept.proposals, conditions=kept.conditions,
                                question=kept.question, dropped=[*kept.dropped, *on_plate.dropped], reason=None,
                                unread=on_plate.not_taken(kept.unread), supports=on_plate.supports, loads=on_plate.loads)

    return _deliver(request, response, actor, proposal, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None),
                    calls=calls)


@app.post("/v1/workspace/result-questions", response_model=ResultQuestionResponse)
def read_result_question(asked: ResultQuestionRequest, actor: Actor, request: Request, response: Response) -> ResultQuestionResponse:
    """The model reads a loose question about a result into a fixed request, and the guard keeps it only inside what the page offered
    (ADR-0100): quantities and a region by name, plies the laminate holds, an element the message writes. No result is sent here, shown to
    the model or returned: the page runs the request on the results it shows. With no model, or one that does not answer, nothing is read
    and the page's own patterns stand (ADR-0099). Recorded with the model's name when one read it (ADR-0026)."""
    assistant = _assistant(request, actor)
    calls: list[ModelCall] = []

    def compute() -> ResultQuestionResponse:
        view = model_view(asked.message, list(asked.quantities), [p.model_dump(mode="json") for p in asked.plies], asked.gauge, asked.picked)
        reading = _billed(calls, assistant.read_question(view, question_schema([q["key"] for q in view["quantities"]], [r["key"] for r in view["regions"]])))
        if reading.raw is None:
            return ResultQuestionResponse(run_id=None, writer=reading.writer, model=None, request=None, question=None, dropped=[], reason=reading.reason)
        kept = question_guard(reading.raw, asked.message, view)
        return ResultQuestionResponse(run_id=None, writer=reading.writer, model=reading.model, request=kept.request, question=kept.question,
                                      dropped=kept.dropped, reason=None)

    return _deliver(request, response, actor, asked, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None),
                    calls=calls)


@app.post("/v1/workspace/result-answers", response_model=ResultAnswerResponse)
def answer_result_question(asked: ResultAnswerRequest, actor: Actor, request: Request, response: Response) -> ResultAnswerResponse:
    """A question about a result answered in words (ADR-0102): from the fact sheet of the result the page shows and the sections of our
    theory pages the question's words find. The model's answer is kept only when every number in it is the sheet's or the question's
    (the explanation's guard, ADR-0052), and the sections it rests on come back by name. With no model, or an answer set aside, no prose
    comes back and the sections found do, so the page says where to read. Recorded with the question, the digest of the facts, the
    sections found and the model's name when one wrote (ADR-0026)."""
    assistant = _assistant(request, actor)
    facts = model_view_of_facts(asked.facts)
    found = [section for section, _ in find_theory(asked.question, limit=SECTIONS_SHOWN)]
    receipt = ResultAnswerReceipt(question=asked.question, sections=[s.id for s in found],
                                  facts_sha256=hashlib.sha256(json.dumps(facts, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest())

    calls: list[ModelCall] = []

    def named(sections) -> list[TheorySource]:
        return [TheorySource(id=s.id, document=s.document, title=s.title) for s in sections]

    def compute() -> ResultAnswerResponse:
        reading = _billed(calls, assistant.answer_question(answer_view(asked.question, facts, found), answer_schema([s.id for s in found])))
        if reading.raw is None:
            return ResultAnswerResponse(run_id=None, writer=reading.writer, model=None, prose=[], sources=named(found), covered=False, withheld=False,
                                        reason=reading.reason)
        kept = answer_guard(reading.raw, asked.question, facts, found)
        if not kept.prose:  # set aside by the guard: no prose of the model's is shown, and the page says where to read
            return ResultAnswerResponse(run_id=None, writer="template", model=None, prose=[], sources=named(found), covered=False,
                                        withheld=kept.withheld, reason=kept.reason)
        return ResultAnswerResponse(run_id=None, writer=reading.writer, model=reading.model, prose=list(kept.prose), sources=named(kept.sources),
                                    covered=kept.covered, withheld=False, reason=None)

    return _deliver(request, response, actor, receipt, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None),
                    calls=calls)


@app.post("/v1/workspace/questions", response_model=GeneralAnswerResponse)
def answer_general_question(asked: GeneralQuestionRequest, actor: Actor, request: Request, response: Response) -> GeneralAnswerResponse:
    """A question asked in the FEA section before anything is set up, answered in words (ADR-0124): from the sections of our theory pages
    the question's words find, with the kind of work it asks to set up when it names one of those offered. The model's answer is kept
    only when every number in it is the question's (the why answers' guard, ADR-0102), and the sections it rests on come back by name.
    With no model, or an answer set aside, no prose comes back and the sections found do, so the page says where to read. Recorded with
    the question and the model's name when one wrote (ADR-0026)."""
    assistant = _assistant(request, actor)
    kinds = list(dict.fromkeys(asked.kinds))
    found = [section for section, _ in find_theory(asked.question, limit=SECTIONS_SHOWN)]
    calls: list[ModelCall] = []

    def named(sections) -> list[TheorySource]:
        return [TheorySource(id=s.id, document=s.document, title=s.title) for s in sections]

    def compute() -> GeneralAnswerResponse:
        reading = _billed(calls, assistant.answer_general(general_view(asked.question, found, kinds), general_schema([s.id for s in found], kinds)))
        if reading.raw is None:
            return GeneralAnswerResponse(run_id=None, writer=reading.writer, model=None, prose=[], sources=named(found), covered=False, withheld=False,
                                         reason=reading.reason, start=None)
        kept = general_guard(reading.raw, asked.question, found, kinds)
        if not kept.prose:  # set aside by the guard: no prose of the model's is shown, and the page says where to read
            return GeneralAnswerResponse(run_id=None, writer="template", model=None, prose=[], sources=named(found), covered=False,
                                         withheld=kept.withheld, reason=kept.reason, start=kept.start)
        return GeneralAnswerResponse(run_id=None, writer=reading.writer, model=reading.model, prose=list(kept.prose), sources=named(kept.sources),
                                     covered=kept.covered, withheld=False, reason=None, start=kept.start)

    return _deliver(request, response, actor, asked, compute, llm_of=lambda body: (body.writer, body.model) if body.model else (None, None),
                    calls=calls)


@app.post("/v1/workspace/theory-sections", response_model=TheorySectionsResponse)
def find_theory_sections(asked: TheorySectionsRequest, actor: Actor, request: Request, response: Response) -> TheorySectionsResponse:
    """The sections of our theory pages a question's words find, with their text (ADR-0107): what `result-answers` hands the API's own
    model, handed to a reader whose own model writes, such as an MCP client; a wing's question (`about="wing"`) searches the wing's theory
    and the reference pages instead (ADR-0128), and a repair's (`about="repair"`) the repair's theory and the page "Bonded repairs"
    (ADR-0136). No result is sent here, no model is called and nothing is computed: the sections are the
    documents' text, cut and ranked (`theory.py`). Recorded with its actor (ADR-0026) as the question and
    the ids of the sections found, never their text, so the questions that find nothing can be read back."""
    # a wing's question: its theory and the reference pages (ADR-0127); a repair's: its theory and the page "Bonded repairs" (ADR-0136)
    among = wing_sections() if asked.about == "wing" else repair_sections() if asked.about == "repair" else None
    found = [section for section, _ in find_theory(asked.question, among=among, limit=asked.limit)]
    run_id = _record(request, actor, asked, response={"sections": [section.id for section in found]})
    if run_id is not None:
        response.headers[RUN_ID_HEADER] = str(run_id)
    return TheorySectionsResponse(run_id=None if run_id is None else str(run_id),
                                  sections=[TheorySection(id=s.id, document=s.document, title=s.title, text=s.shown) for s in found])


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
