"""Configuration read from the environment when the API starts. Nothing here has a silent default (ADR-0003).

Run records are on unless ANISOTROPY_RUN_RECORDS=off is set on purpose. With records on, DATABASE_URL
must be set and the API refuses to start otherwise (ADR-0026). Variables may come from a `.env` file
found by walking up from the current directory (python-dotenv); values already in the process
environment win over the file.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from dotenv import find_dotenv, load_dotenv
from sqlalchemy.engine import make_url

RECORDING_VARIABLE = "ANISOTROPY_RUN_RECORDS"
DATABASE_VARIABLE = "DATABASE_URL"
# A hosted PostgreSQL (Neon, ADR-0056) hands out two addresses: the pooled one for the application and an unpooled one for
# migrations and other session-level work. `neon env pull` writes both; a local Docker server has only the first.
UNPOOLED_DATABASE_VARIABLE = "DATABASE_URL_UNPOOLED"
# The one driver the API installs (ADR-0025). A plain `postgresql://` address, which hosted services hand out, is routed to it;
# an address that names another driver is refused rather than guessed.
DRIVER = "postgresql+psycopg"
ASSISTANT_PROVIDER_VARIABLE = "ANISOTROPY_ASSISTANT_PROVIDER"
ASSISTANT_MODEL_VARIABLE = "ANISOTROPY_ASSISTANT_MODEL"
CREDENTIAL_VARIABLES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")  # what the Anthropic SDK reads; one of them must be present
PROVIDERS = ("anthropic",)
# Cloudflare Access in front of the API (ADR-0056): the team's domain, <team>.cloudflareaccess.com, which issues the tokens and
# publishes the keys, and the application's audience tag. Both or neither.
ACCESS_TEAM_DOMAIN_VARIABLE = "ANISOTROPY_ACCESS_TEAM_DOMAIN"
ACCESS_AUDIENCE_VARIABLE = "ANISOTROPY_ACCESS_AUD"
TEAM_DOMAIN = re.compile(r"^[a-z0-9-]+\.cloudflareaccess\.com$")
# The website origins that may read the API's answers from a browser, comma-separated; unset, the local development origins apply.
ALLOWED_ORIGINS_VARIABLE = "ANISOTROPY_ALLOWED_ORIGINS"
# Durable outputs in an object store through the S3 API, R2 in the hosted tier (ADR-0056, ADR-0050 amendment 2): the bucket, the
# endpoint (https://<account>.r2.cloudflarestorage.com, or a local MinIO) and the key pair. All four or none.
STORAGE_VARIABLES = ("ANISOTROPY_R2_BUCKET", "ANISOTROPY_R2_ENDPOINT", "ANISOTROPY_R2_ACCESS_KEY_ID", "ANISOTROPY_R2_SECRET_ACCESS_KEY")
# The per-user limits of the hosted tier (ADR-0056, stage 5): with a number set, a signed-in person (or, without an email, an actor)
# may have one coupon job running at a time and start at most that many a day (UTC), counted in the jobs table; off unless set.
JOBS_PER_DAY_VARIABLE = "ANISOTROPY_JOBS_PER_USER_PER_DAY"
# The job queue (ADR-0056 stage 3, amendment 3): unset, this process runs each coupon job itself, one at a time (ADR-0050). `queue`:
# it files the job in the object store and the jobs table and leaves it to the queue, which the Worker feeds; `solver`: it runs the
# queued job a request names, in a container of that job's own. Either needs the jobs table and the store.
JOB_ROLE_VARIABLE = "ANISOTROPY_JOB_ROLE"
JOB_ROLES = ("queue", "solver")
# The live solve (ADR-0086): how many warm `studio_tool.py serve` workers answer edits with our kernel, each holding the fea package
# imported (about 2 s of imports a cold call would pay). 0 starts a fresh `studio_tool.py live` per call instead. Default 1.
LIVE_WORKERS_VARIABLE = "ANISOTROPY_LIVE_WORKERS"
LIVE_WORKERS_DEFAULT = 1
# One workflow first (ADR-0089): the studio offers the unnotched tension coupon only until its comparison with Abaqus is validated.
# `on` offers every test again, for development; unset or `off` keeps the list. The fea package reads the same variable from the
# environment its processes inherit (`anisotropy_fea.enabled`), so a change needs a restart. The hosted tier never sets it.
ALL_TESTS_VARIABLE = "ANISOTROPY_ALL_TESTS"
# The uploads from Abaqus (ADR-0094 part 6, step 5). An upload is its owner's alone; the founders also see every upload, and who they
# are is named here by signed-in email, comma-separated. An email exists only behind Cloudflare Access, so the variable needs it.
FOUNDER_EMAILS_VARIABLE = "ANISOTROPY_FOUNDER_EMAILS"
# The connector on a user's machine cannot sign in to Cloudflare Access. `on`: the one route it sends to, POST /v1/connector/uploads,
# is let through without Access's token and checked by the upload token alone; the Access application needs a bypass policy for that
# path, or the request never arrives. Unset or `off`: that route needs Access's token like every other, so only a signed-in browser
# uploads. Without Access (the local API) the route takes an upload token as it is, and the variable is refused.
CONNECTOR_UPLOADS_VARIABLE = "ANISOTROPY_CONNECTOR_UPLOADS"
EMAIL = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")
LOCAL_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001")


@dataclass(frozen=True)
class AssistantSettings:
    """The assistant's model, as ADR-0027 requires it: off unless a deployment names a provider and a model (ADR-0052). With it off,
    only the template writes, and a solve makes no outbound request."""

    provider: str | None
    model: str | None

    @property
    def on(self) -> bool:
        return self.provider is not None


@dataclass(frozen=True)
class AccessSettings:
    """Cloudflare Access in front of the API (ADR-0056): off unless the team domain and the audience tag are both named. On, every
    request but /healthz must carry the token Access adds, and the signed-in email goes to the run records."""

    team_domain: str | None
    audience: str | None

    @property
    def on(self) -> bool:
        return self.team_domain is not None

    @property
    def issuer(self) -> str:
        return f"https://{self.team_domain}"

    @property
    def certs_url(self) -> str:
        return f"{self.issuer}/cdn-cgi/access/certs"


@dataclass(frozen=True)
class StorageSettings:
    """The object store the hosted tier keeps a job's files in (ADR-0056): off unless the bucket, the endpoint and the key pair are all
    named. Off, the files stay on the local disk, as before."""

    bucket: str | None
    endpoint: str | None
    access_key_id: str | None
    secret_access_key: str | None

    @property
    def on(self) -> bool:
        return self.bucket is not None


@dataclass(frozen=True)
class Settings:
    """What the process was told. `run_records` False means recording was switched off explicitly."""

    database_url: str | None
    run_records: bool
    assistant: AssistantSettings = AssistantSettings(None, None)
    access: AccessSettings = AccessSettings(None, None)
    allowed_origins: tuple[str, ...] = LOCAL_ORIGINS
    storage: StorageSettings = StorageSettings(None, None, None, None)
    jobs_per_user_per_day: int | None = None  # None: no per-user limit, as locally
    job_role: str | None = None  # None: jobs run in this process; "queue" or "solver" with the job queue (ADR-0056 amendment 3)
    live_workers: int = LIVE_WORKERS_DEFAULT  # warm live-solve workers (ADR-0086); 0: a fresh process per live solve
    all_tests: bool = False  # every test offered (ADR-0089); False: the unnotched tension coupon only
    founder_emails: frozenset[str] = frozenset()  # who also sees every upload from Abaqus (ADR-0094 part 6); lower case
    connector_uploads: bool = False  # behind Access, the connector's route is checked by the upload token alone (ADR-0094 step 5)


def environment() -> Mapping[str, str]:
    """The process environment after the nearest `.env` file is loaded; values already in the environment win."""
    load_dotenv(find_dotenv(usecwd=True), override=False)
    return os.environ


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Read the switch and the database address; raise with the fix when the combination is invalid.

    With no `environ`, the process environment is used after loading the nearest `.env` file.
    """
    if environ is None:
        environ = environment()
    switch = environ.get(RECORDING_VARIABLE, "on").strip().lower()
    if switch not in {"on", "off"}:
        raise RuntimeError(f"{RECORDING_VARIABLE} must be 'on' or 'off', not {switch!r}")
    url = environ.get(DATABASE_VARIABLE, "").strip() or None
    if switch == "on" and url is None:
        raise RuntimeError(
            f"{DATABASE_VARIABLE} is not set. Run records are on by default and need the database "
            f"(see .env.example and ADR-0025). To run without recording, set {RECORDING_VARIABLE}=off."
        )
    if url is not None:
        url = sqlalchemy_url(url, DATABASE_VARIABLE)
    return Settings(database_url=url, run_records=switch == "on", assistant=assistant_settings(environ), access=access_settings(environ),
                    allowed_origins=allowed_origins(environ), storage=storage_settings(environ),
                    jobs_per_user_per_day=jobs_per_user_per_day(environ, records_on=switch == "on"),
                    job_role=job_role(environ, records_on=switch == "on", storage_on=storage_settings(environ).on),
                    live_workers=live_workers(environ), all_tests=all_tests(environ),
                    founder_emails=founder_emails(environ, access_on=access_settings(environ).on),
                    connector_uploads=connector_uploads(environ, access_on=access_settings(environ).on))


def founder_emails(environ: Mapping[str, str], *, access_on: bool) -> frozenset[str]:
    """The founders' signed-in emails, lower case, or none when unset. Each must be an email; and since only Cloudflare Access gives a
    request an email, the list without Access is refused rather than ignored (ADR-0003)."""
    raw = environ.get(FOUNDER_EMAILS_VARIABLE, "").strip()
    if not raw:
        return frozenset()
    emails = [part.strip().lower() for part in raw.split(",")]
    wrong = [email for email in emails if not EMAIL.match(email)]
    if wrong:
        raise RuntimeError(f"{FOUNDER_EMAILS_VARIABLE} must list emails separated by commas; not one: {', '.join(repr(email) for email in wrong)}")
    if not access_on:
        raise RuntimeError(f"{FOUNDER_EMAILS_VARIABLE} names who sees every upload by signed-in email, which only Cloudflare Access gives; set "
                           f"{ACCESS_TEAM_DOMAIN_VARIABLE} and {ACCESS_AUDIENCE_VARIABLE}, or unset it")
    return frozenset(emails)


def connector_uploads(environ: Mapping[str, str], *, access_on: bool) -> bool:
    """Whether, behind Access, the connector's route is checked by the upload token alone: `on`; unset, blank or `off` keeps Access's
    token on it. Any other word is refused, and so is `on` without Access, where the route takes an upload token already (ADR-0003)."""
    raw = environ.get(CONNECTOR_UPLOADS_VARIABLE, "").strip().lower()
    if not raw:
        return False
    if raw not in {"on", "off"}:
        raise RuntimeError(f"{CONNECTOR_UPLOADS_VARIABLE} must be 'on' or 'off', not {raw!r}; unset it to keep Cloudflare Access's token on the connector's route")
    if raw == "on" and not access_on:
        raise RuntimeError(f"{CONNECTOR_UPLOADS_VARIABLE}=on lets the connector's route past Cloudflare Access, which is off here: without Access "
                           f"the route takes an upload token already; unset it, or set {ACCESS_TEAM_DOMAIN_VARIABLE} and {ACCESS_AUDIENCE_VARIABLE}")
    return raw == "on"


def job_role(environ: Mapping[str, str], *, records_on: bool, storage_on: bool) -> str | None:
    """`queue`, `solver`, or None when unset. Both roles hand a job from one container to another through the jobs table and the
    object store, so each needs run records on and the store's four settings; without them it is refused (ADR-0003)."""
    raw = environ.get(JOB_ROLE_VARIABLE, "").strip()
    if not raw:
        return None
    if raw not in JOB_ROLES:
        raise RuntimeError(f"{JOB_ROLE_VARIABLE} must be one of {', '.join(JOB_ROLES)}, not {raw!r}; unset it to run jobs in this process")
    missing = [what for what, on in ((f"run records ({RECORDING_VARIABLE}=on with {DATABASE_VARIABLE})", records_on),
                                     (f"the object store ({', '.join(STORAGE_VARIABLES)})", storage_on)) if not on]
    if missing:
        raise RuntimeError(f"{JOB_ROLE_VARIABLE}={raw} passes jobs between containers through the jobs table and the object store; "
                           f"it needs {' and '.join(missing)}")
    return raw


def all_tests(environ: Mapping[str, str]) -> bool:
    """Whether every test is offered (ADR-0089): `on`; unset, blank or `off` offers the unnotched tension coupon only. Any other word is
    refused at startup, not read as off (ADR-0003); the fea package applies the same rule to the same variable."""
    raw = environ.get(ALL_TESTS_VARIABLE, "").strip().lower()
    if not raw:
        return False
    if raw not in {"on", "off"}:
        raise RuntimeError(f"{ALL_TESTS_VARIABLE} must be 'on' or 'off', not {raw!r}; unset it to offer the unnotched tension coupon only")
    return raw == "on"


def live_workers(environ: Mapping[str, str]) -> int:
    """The warm live-solve workers, a whole number from 0 (a fresh process per solve) to 8, or the default when unset; anything else is
    refused, not read as the default (ADR-0003)."""
    raw = environ.get(LIVE_WORKERS_VARIABLE, "").strip()
    if not raw:
        return LIVE_WORKERS_DEFAULT
    if not raw.isdigit() or int(raw) > 8:
        raise RuntimeError(f"{LIVE_WORKERS_VARIABLE} must be a whole number of warm workers from 0 to 8, not {raw!r}; unset it for {LIVE_WORKERS_DEFAULT}")
    return int(raw)


def jobs_per_user_per_day(environ: Mapping[str, str], *, records_on: bool) -> int | None:
    """The daily cap per person, a whole number of at least 1, or None when unset. It counts jobs in the jobs table, so it needs run
    records on; set with them off, it is refused rather than ignored (ADR-0003)."""
    raw = environ.get(JOBS_PER_DAY_VARIABLE, "").strip()
    if not raw:
        return None
    if not raw.isdigit() or int(raw) < 1:
        raise RuntimeError(f"{JOBS_PER_DAY_VARIABLE} must be a whole number of jobs per person per day, at least 1, not {raw!r}; unset it for no limit")
    if not records_on:
        raise RuntimeError(f"{JOBS_PER_DAY_VARIABLE} counts a person's jobs in the jobs table, which needs run records on; "
                           f"unset it, or set {RECORDING_VARIABLE}=on with {DATABASE_VARIABLE}")
    return int(raw)


def storage_settings(environ: Mapping[str, str]) -> StorageSettings:
    """Off unless all four variables are set; some but not all is refused naming the missing ones, and an endpoint that is not an
    address is refused too."""
    values = {name: environ.get(name, "").strip() or None for name in STORAGE_VARIABLES}
    if all(value is None for value in values.values()):
        return StorageSettings(None, None, None, None)
    missing = [name for name, value in values.items() if value is None]
    if missing:
        raise RuntimeError(f"{', '.join(missing)} not set: the object store needs all four of {', '.join(STORAGE_VARIABLES)}, "
                           "or none of them to keep a job's files on the local disk")
    endpoint = values["ANISOTROPY_R2_ENDPOINT"]
    parts = urlsplit(endpoint)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path.strip("/") or parts.query or parts.fragment:
        raise RuntimeError(f"ANISOTROPY_R2_ENDPOINT must be the store's address, scheme://host[:port], such as "
                           f"https://<account>.r2.cloudflarestorage.com, not {endpoint!r}")
    return StorageSettings(values["ANISOTROPY_R2_BUCKET"], endpoint.rstrip("/"), values["ANISOTROPY_R2_ACCESS_KEY_ID"],
                           values["ANISOTROPY_R2_SECRET_ACCESS_KEY"])


def docs_urls(environ: Mapping[str, str]) -> dict[str, str | None]:
    """Where the API publishes its own documentation: /docs, /redoc and the OpenAPI schema locally, nowhere behind Cloudflare Access, the
    hosted tier (ADR-0091 amendment 2). Access is named by its team domain here; the lifespan refuses a half-set pair (access_settings)."""
    if (environ.get(ACCESS_TEAM_DOMAIN_VARIABLE) or "").strip():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}


def access_settings(environ: Mapping[str, str]) -> AccessSettings:
    """Off unless both variables are set; one without the other, or a domain that is not a team's, is refused with the fix."""
    domain = environ.get(ACCESS_TEAM_DOMAIN_VARIABLE, "").strip().lower() or None
    audience = environ.get(ACCESS_AUDIENCE_VARIABLE, "").strip() or None
    if domain is None and audience is None:
        return AccessSettings(None, None)
    if domain is None:
        raise RuntimeError(f"{ACCESS_AUDIENCE_VARIABLE} is set but {ACCESS_TEAM_DOMAIN_VARIABLE} is not: name the team domain, "
                           f"<team>.cloudflareaccess.com, or unset both to run without Access")
    if audience is None:
        raise RuntimeError(f"{ACCESS_TEAM_DOMAIN_VARIABLE} is set but {ACCESS_AUDIENCE_VARIABLE} is not: name the Access application's "
                           f"audience tag, or unset both to run without Access")
    if not TEAM_DOMAIN.match(domain):
        raise RuntimeError(f"{ACCESS_TEAM_DOMAIN_VARIABLE} must be the team's domain alone, such as myteam.cloudflareaccess.com, not {domain!r}")
    return AccessSettings(domain, audience)


def allowed_origins(environ: Mapping[str, str]) -> tuple[str, ...]:
    """The origins that may read the API from a browser: the variable's comma-separated list when it is set, each an origin and
    nothing more, else the local development origins."""
    raw = environ.get(ALLOWED_ORIGINS_VARIABLE, "").strip()
    if not raw:
        return LOCAL_ORIGINS
    origins = tuple(part.strip() for part in raw.split(","))
    for origin in origins:
        parts = urlsplit(origin)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.path or parts.query or parts.fragment or origin.endswith("/"):
            raise RuntimeError(f"{ALLOWED_ORIGINS_VARIABLE} must list origins, scheme://host[:port] separated by commas, such as "
                               f"https://studio.example.com; {origin!r} is not one")
    return origins


def sqlalchemy_url(url: str, variable: str) -> str:
    """The address as SQLAlchemy needs it: `postgresql://` and `postgres://` become `postgresql+psycopg://`, the installed
    driver; `postgresql+psycopg://` passes unchanged; any other scheme is refused, naming the variable and the fix. Query
    parameters such as Neon's `sslmode=require` and `channel_binding=require` are kept; psycopg reads them."""
    try:
        parsed = make_url(url)
    except Exception as exc:  # SQLAlchemy raises ArgumentError; the message names the variable, not the secret
        raise RuntimeError(f"{variable} is not a database address SQLAlchemy can read: {exc}") from exc
    if parsed.drivername in ("postgresql", "postgres"):
        parsed = parsed.set(drivername=DRIVER)
    elif parsed.drivername != DRIVER:
        raise RuntimeError(f"{variable} must start with postgresql:// or {DRIVER}://, not {parsed.drivername}://; "
                           "the API installs psycopg only (ADR-0025)")
    return parsed.render_as_string(hide_password=False)


def assistant_settings(environ: Mapping[str, str]) -> AssistantSettings:
    """The assistant is off unless the provider is named; named, it needs its model and a credential, each refusal naming the variable."""
    provider = environ.get(ASSISTANT_PROVIDER_VARIABLE, "").strip().lower() or None
    if provider is None:
        return AssistantSettings(None, None)
    if provider not in PROVIDERS:
        raise RuntimeError(f"{ASSISTANT_PROVIDER_VARIABLE} must be one of {', '.join(PROVIDERS)} or unset, not {provider!r}")
    model = environ.get(ASSISTANT_MODEL_VARIABLE, "").strip() or None
    if model is None:
        raise RuntimeError(f"{ASSISTANT_MODEL_VARIABLE} is not set: name the model the assistant uses (see .env.example and ADR-0052), or unset "
                           f"{ASSISTANT_PROVIDER_VARIABLE} to run with the template writer only")
    if not any(environ.get(name, "").strip() for name in CREDENTIAL_VARIABLES):
        raise RuntimeError(f"{ASSISTANT_PROVIDER_VARIABLE}={provider} needs a credential: set {' or '.join(CREDENTIAL_VARIABLES)}, or unset "
                           f"{ASSISTANT_PROVIDER_VARIABLE} to run with the template writer only")
    return AssistantSettings(provider, model)


def database_url_for_migrations(environ: Mapping[str, str] | None = None) -> str:
    """Migrations need the database even when recording is off, and need a session of their own: with a hosted server the
    unpooled address (DATABASE_URL_UNPOOLED) is used when it is set, because a pooled connection does not keep session state
    across statements; a server with one address (local Docker) uses DATABASE_URL."""
    if environ is None:
        load_dotenv(find_dotenv(usecwd=True), override=False)
        environ = os.environ
    unpooled = environ.get(UNPOOLED_DATABASE_VARIABLE, "").strip() or None
    if unpooled is not None:
        return sqlalchemy_url(unpooled, UNPOOLED_DATABASE_VARIABLE)
    settings = load_settings(environ)
    if settings.database_url is None:
        raise RuntimeError(f"{DATABASE_VARIABLE} is not set; migrations need the database even with {RECORDING_VARIABLE}=off")
    return settings.database_url
