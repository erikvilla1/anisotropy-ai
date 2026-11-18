"""Check a hosted Anisotropy after a deploy (ADR-0114): the site answers, the API answers with the commit just deployed, and one
public coupon job goes through the queue to a solver and comes back with its result. Standard library only, so the runner's Python
runs it.

    python3 scripts/check-hosted.py --site https://anisotropy.dev --commit <sha> --values tests/fixtures/studio/values.json

Behind Cloudflare Access the check needs a service token the Access application admits (a policy with the action Service Auth): its
two halves come from CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET and go with every request. Without them, or with a token Access
does not admit, Access answers with its sign-in and the check says so.

The values are the public IM7/8552 coupon's form rows, as the studio sends them (tests/fixtures/studio/values.json; never a team
coupon, ADR-0042). The job is started with the actor `test` and no PDF; it keeps its coupon under the service token's owner (none) and
replaces it each time. Exit 0 when every step passed; 1 with the step that failed and what the site answered.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ACTOR = "test"  # one of the API's records.ACTORS: a check, not a person's run
AGENT = "anisotropy-deploy-check/1"  # Cloudflare refuses Python-urllib's own user agent with 403 before Access sees the request
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # Access's sign-in is a redirect: report it, never follow it
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def headers() -> dict[str, str]:
    client_id, secret = os.environ.get("CF_ACCESS_CLIENT_ID", "").strip(), os.environ.get("CF_ACCESS_CLIENT_SECRET", "").strip()
    return {"CF-Access-Client-Id": client_id, "CF-Access-Client-Secret": secret} if client_id and secret else {}


def call(url: str, body: dict | None = None, timeout: float = 60.0) -> tuple[int, bytes, dict[str, str]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="GET" if body is None else "POST",
                                     headers={"Content-Type": "application/json", "User-Agent": AGENT, "X-Anisotropy-Actor": ACTOR, **headers()})
    try:
        with OPENER.open(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def step(text: str) -> None:
    print(text, flush=True)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as out:
            out.write(f"- {text}\n")


def fail(text: str) -> int:
    print(f"::error::{text}", flush=True)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as out:
            out.write(f"- **Failed:** {text}\n")
    return 1


def signed_out(status: int, answer: dict[str, str]) -> bool:
    return status in (301, 302, 303, 307, 308) and "cloudflareaccess.com" in answer.get("Location", answer.get("location", ""))


def wait_for(what: str, seconds: float, probe) -> tuple[bool, str]:
    """Probe every 10 s until it answers True or the time is up; the last answer says what was seen."""
    deadline, seen = time.monotonic() + seconds, "no answer"
    while True:
        try:
            ok, seen = probe()
        except (urllib.error.URLError, OSError, ValueError) as exc:
            ok, seen = False, f"{type(exc).__name__}: {exc}"
        if ok or time.monotonic() > deadline:
            return ok, seen
        print(f"  waiting for {what}: {seen}", flush=True)
        time.sleep(10.0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--site", required=True, help="the site's address, such as https://anisotropy.dev")
    parser.add_argument("--commit", default=None, help="the commit that was deployed; the API must answer with it")
    parser.add_argument("--values", type=Path, required=True, help="the coupon's form rows as JSON (tests/fixtures/studio/values.json)")
    parser.add_argument("--wait", type=float, default=600.0, help="seconds to wait for the API to answer with the commit")
    parser.add_argument("--timeout", type=float, default=900.0, help="seconds to wait for the coupon job")
    args = parser.parse_args()
    site, api = args.site.rstrip("/"), args.site.rstrip("/") + "/api"
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as out:
            out.write(f"### The check of {site}\n\n")

    # 1. the site: its home page, from the deployed assets
    status, body, answer = call(site + "/")
    if signed_out(status, answer):
        return fail(f"{site} answered with Cloudflare Access's sign-in: CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET are missing or "
                    "name a service token the Access application does not admit (docs/walkthroughs/hosted-deploy.md)")
    if status != 200 or b"<html" not in body[:2000].lower():
        return fail(f"GET {site}/ answered {status}, not the home page")
    step(f"The home page answers ({len(body)} bytes).")

    # 2. the API's container, started on the deployed code: a deploy restarts it at the first request (ADR-0056 amendment 10)
    def version():
        status, body, answer = call(api + "/version", timeout=30.0)
        if signed_out(status, answer):
            return False, "Access's sign-in"
        if status != 200:
            return False, f"{status} {body[:200].decode('utf-8', 'replace')}"
        commit = json.loads(body).get("git_commit")
        return (args.commit is None or commit == args.commit), f"the API runs {commit}"

    t0 = time.monotonic()
    ok, seen = wait_for("the API on the deployed commit", args.wait, version)
    if not ok:
        return fail(f"after {args.wait:.0f} s the API still does not answer with {args.commit}: {seen}")
    step(f"The API answers after {time.monotonic() - t0:.0f} s; {seen}.")

    # 3. one public coupon job, through the queue to a solver, to its result
    values = json.loads(args.values.read_text(encoding="utf-8"))
    t0 = time.monotonic()
    status, body, _ = call(api + "/v1/coupon-jobs", {"values": values, "run_by": "deploy check", "pdf": False, "replace": True})
    if status == 429:  # the per-person daily cap (ADR-0056): the API, its database and its limits answered; no job is proved today
        print(f"::warning::the coupon job was refused by the daily cap, so no job ran: {body.decode('utf-8', 'replace')}", flush=True)
        step("The coupon job was not run: the day's cap for the check's jobs is reached.")
        return 0
    if status != 202:
        return fail(f"POST /api/v1/coupon-jobs answered {status}: {body[:400].decode('utf-8', 'replace')}")
    job = json.loads(body)
    print(f"job {job['job_id']} {job['state']}", flush=True)
    deadline, result_at = time.monotonic() + args.timeout, None
    while job["state"] in ("queued", "running"):
        if time.monotonic() > deadline:
            print("\n".join(job.get("log_tail") or []))
            return fail(f"the coupon job is still {job['state']} after {args.timeout:.0f} s (stage {job.get('stage')})")
        time.sleep(3.0)
        status, body, _ = call(f"{api}/v1/coupon-jobs/{job['job_id']}", timeout=30.0)
        if status != 200:
            return fail(f"GET the job answered {status}: {body[:400].decode('utf-8', 'replace')}")
        job = json.loads(body)
        if result_at is None and job.get("result"):
            result_at = time.monotonic() - t0
            print(f"  {result_at:6.1f} s  result: {job['result']}", flush=True)
    if job["state"] != "done" or not job.get("result"):
        print("\n".join(job.get("log_tail") or []))
        return fail(f"the coupon job ended {job['state']} with no result: {job.get('message')}")
    done_at = time.monotonic() - t0
    step(f"One public coupon job ran through the queue: its result after {result_at if result_at is not None else done_at:.0f} s, done after {done_at:.0f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
