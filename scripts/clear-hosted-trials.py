"""Clear the hosted tier's trial records once, on the founder's word (ADR-0026 amendment 2). Nothing here computes a result.

    uv run --project api python scripts/clear-hosted-trials.py count
    uv run --project api python scripts/clear-hosted-trials.py delete --expect runs=373,jobs=27,projects=40 --confirm "delete the trial records"

What goes: every row of `runs`, `jobs` and `projects` (with the jobs' QA checks, ADR-0137, reported by count), and every object under `coupons/`, `owners/` and `jobs/` in the store. What
stays: the Abaqus uploads (the rows and `uploads/` in the store; each loses the link to its run of ours, which goes), the connector's
upload keys and pairing codes, and anything else in the store. `count` changes nothing. `delete` refuses unless the confirmation is
typed, the counts are the ones `--expect` names (so it deletes what was counted, from the database that was counted) and no job is
queued or running; the rows go in one transaction, the objects after it.

The database is DATABASE_URL_UNPOOLED, else DATABASE_URL; the store is ANISOTROPY_R2_BUCKET, ANISOTROPY_R2_ENDPOINT,
ANISOTROPY_R2_ACCESS_KEY_ID and ANISOTROPY_R2_SECRET_ACCESS_KEY: the API's own names (docs/walkthroughs/hosted-deploy.md). The output
holds counts only, never an email or a coupon's name. The founder's PC holds no R2 keys, so the run is made by the workflow
`.github/workflows/clear-hosted-trials.yml`, from the repository's secrets.
"""

from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url

CLEARED_TABLES = ("runs", "jobs", "projects")
KEPT_TABLES = ("abaqus_uploads", "upload_tokens", "pairing_codes")
CLEARED_PREFIXES = ("coupons/", "owners/", "jobs/")
CONFIRMATION = "delete the trial records"
TRANSFERS = 8


class Store(Protocol):
    def objects(self, prefix: str) -> dict[str, int]: ...  # every key under the prefix with its size in bytes

    def delete(self, key: str) -> None: ...


class R2(Store):
    """The bucket through the S3 API, configured as the API's own store is (api/src/anisotropy_api/storage.py, R2Store)."""

    def __init__(self, bucket: str, endpoint: str, access_key_id: str, secret_access_key: str):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key,
                                   region_name="auto", config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                                                                     request_checksum_calculation="when_required",
                                                                     response_checksum_validation="when_required",
                                                                     retries={"max_attempts": 3, "mode": "standard"}))

    def objects(self, prefix: str) -> dict[str, int]:
        pages = self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix)
        return {item["Key"]: item["Size"] for page in pages for item in page.get("Contents", [])}

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def engine_from_environment(environ=os.environ) -> Engine:
    for name in ("DATABASE_URL_UNPOOLED", "DATABASE_URL"):
        url = environ.get(name, "").strip()
        if url:
            parsed = make_url(url)
            if parsed.drivername in ("postgresql", "postgres"):
                parsed = parsed.set(drivername="postgresql+psycopg")
            return create_engine(parsed, connect_args={"connect_timeout": 10})
    raise SystemExit("Neither DATABASE_URL_UNPOOLED nor DATABASE_URL is set: name the hosted database first.")


def store_from_environment(environ=os.environ) -> R2:
    names = ("ANISOTROPY_R2_BUCKET", "ANISOTROPY_R2_ENDPOINT", "ANISOTROPY_R2_ACCESS_KEY_ID", "ANISOTROPY_R2_SECRET_ACCESS_KEY")
    values = [environ.get(name, "").strip() for name in names]
    missing = [name for name, value in zip(names, values) if not value]
    if missing:
        raise SystemExit(f"Not set: {', '.join(missing)}. Name the hosted store first.")
    return R2(*values)


def _table_counts(connection: Connection) -> dict[str, int]:
    return {table: connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() for table in (*CLEARED_TABLES, *KEPT_TABLES)}


def count(engine: Engine, store: Store) -> dict:
    """What is there, in counts: the rows of each table, the people behind them, the jobs not ended, and the objects under each prefix."""
    with engine.connect() as connection:
        rows = _table_counts(connection)
        people = {table: connection.execute(text(f"SELECT count(DISTINCT user_email) FROM {table}")).scalar_one() for table in CLEARED_TABLES}
        no_email = {table: connection.execute(text(f"SELECT count(*) FROM {table} WHERE user_email IS NULL")).scalar_one() for table in CLEARED_TABLES}
        busy = connection.execute(text("SELECT count(*) FROM jobs WHERE state IN ('queued', 'running')")).scalar_one()
        linked = connection.execute(text("SELECT count(*) FROM abaqus_uploads WHERE job_id IS NOT NULL")).scalar_one()
    objects = {}
    for prefix in (*CLEARED_PREFIXES, "uploads/", ""):
        found = store.objects(prefix)
        objects[prefix or "(whole bucket)"] = {"files": len(found), "bytes": sum(found.values())}
    return {"rows": rows, "people": people, "no_email": no_email, "busy_jobs": busy, "uploads_linked_to_a_job": linked, "objects": objects}


def parse_expect(value: str) -> dict[str, int]:
    expected = {}
    for part in value.split(","):
        table, _, number = part.strip().partition("=")
        if table not in CLEARED_TABLES or not number.isdigit():
            raise argparse.ArgumentTypeError(f"--expect is table=count for each of {', '.join(CLEARED_TABLES)}, e.g. runs=373,jobs=27,projects=40")
        expected[table] = int(number)
    if set(expected) != set(CLEARED_TABLES):
        raise argparse.ArgumentTypeError(f"--expect names each of {', '.join(CLEARED_TABLES)} once")
    return expected


class Refused(Exception):
    pass


def delete(engine: Engine, store: Store, expected: dict[str, int], confirmation: str) -> dict:
    """The rows of the cleared tables, in one transaction that holds the tables against writers, then the objects under the cleared
    prefixes. Refuses, changing nothing, when the confirmation is not typed, a count is not the one expected, or a job has not ended."""
    if confirmation != CONFIRMATION:
        raise Refused(f'Type the confirmation exactly: --confirm "{CONFIRMATION}"')
    with engine.begin() as connection:
        has_qa = inspect(connection).has_table("qa_checks")  # the jobs' QA record (ADR-0137, migration 0016): goes with its jobs
        connection.execute(text(f"LOCK TABLE {', '.join((*CLEARED_TABLES, 'abaqus_uploads', *(('qa_checks',) if has_qa else ())))} IN ACCESS EXCLUSIVE MODE"))
        found = {table: count for table, count in _table_counts(connection).items() if table in CLEARED_TABLES}
        if found != expected:
            raise Refused(f"The counts are {found}, not the {expected} expected: count again and check before deleting.")
        busy = connection.execute(text("SELECT count(*) FROM jobs WHERE state IN ('queued', 'running')")).scalar_one()
        if busy:
            raise Refused(f"{busy} job(s) are queued or running: wait until they end.")
        unlinked = connection.execute(text("UPDATE abaqus_uploads SET job_id = NULL WHERE job_id IS NOT NULL")).rowcount
        checks = 0
        if has_qa:  # before jobs: a check names its job; never deleted one by one either, so its trigger is off for this statement only
            connection.execute(text("ALTER TABLE qa_checks DISABLE TRIGGER qa_checks_immutable"))
            checks = connection.execute(text("DELETE FROM qa_checks")).rowcount
            connection.execute(text("ALTER TABLE qa_checks ENABLE TRIGGER qa_checks_immutable"))
        connection.execute(text("DELETE FROM jobs"))  # before projects and runs: a job names both
        connection.execute(text("DELETE FROM projects"))  # before runs: a project names its last check's run
        # Run records are never deleted one by one (ADR-0026); this one clearing is amendment 2, as migration 0003 switched the
        # trigger off and on around its one change.
        connection.execute(text("ALTER TABLE runs DISABLE TRIGGER runs_immutable"))
        connection.execute(text("DELETE FROM runs"))
        connection.execute(text("ALTER TABLE runs ENABLE TRIGGER runs_immutable"))
        left = _table_counts(connection)
    keys = [key for prefix in CLEARED_PREFIXES for key in store.objects(prefix)]
    with ThreadPoolExecutor(TRANSFERS) as pool:
        list(pool.map(store.delete, keys))
    remaining = {prefix: len(store.objects(prefix)) for prefix in CLEARED_PREFIXES}
    return {"deleted_rows": expected, "qa_checks_deleted": checks, "uploads_unlinked": unlinked, "rows_now": left, "deleted_files": len(keys),
            "files_left": remaining}


def show(title: str, report: dict) -> None:
    print(title)
    for name, value in report.items():
        print(f"  {name}: {value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("count", help="what is there, in counts; changes nothing")
    deleting = commands.add_parser("delete", help="delete the trial records")
    deleting.add_argument("--expect", required=True, type=parse_expect, help="the counts `count` gave, e.g. runs=373,jobs=27,projects=40")
    deleting.add_argument("--confirm", required=True, help=f'exactly "{CONFIRMATION}"')
    args = parser.parse_args(argv)
    engine, store = engine_from_environment(), store_from_environment()
    if args.command == "count":
        show("What the hosted tier holds now (nothing changed):", count(engine, store))
        return 0
    try:
        show("Deleted:", delete(engine, store, args.expect, args.confirm))
    except Refused as exc:
        print(f"Nothing deleted. {exc}", file=sys.stderr)
        return 1
    show("What the hosted tier holds now:", count(engine, store))
    return 0


if __name__ == "__main__":
    sys.exit(main())
