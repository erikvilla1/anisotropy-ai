"""Prove the solver image works (ADR-0056): inside a running container, with the network off, start one public coupon job through
the API and wait for its package with the PDF. Standard library only, so any Python in the image runs it.

    docker run -d --name api --network none -e ANISOTROPY_RUN_RECORDS=off \
        -v "$PWD/tests/fixtures/studio/values.json:/check/values.json:ro" -v "$PWD/docker/check-image.py:/check/check-image.py:ro" anisotropy-solver
    docker exec api /app/api/.venv/bin/python /check/check-image.py --values /check/values.json --summary /tmp/summary.json

The values are the public IM7/8552 coupon's form rows, as the studio sends them (tests/fixtures/studio/values.json, the file the
browser tests and `fea/tools/studio_tool.py fixtures` read; never a team coupon, ADR-0042). Exit 0 when the job ends `done` with its document; otherwise the
job's console tail is printed and the exit code is 1. The summary names the job's time, the document and fields sizes and the
container's peak memory (cgroup v2), for the record in ADR-0056.
"""

from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ACTOR = "test"  # one of records.ACTORS: this is a check, not a person's run
PEAK = (Path("/sys/fs/cgroup/memory.peak"), Path("/sys/fs/cgroup/memory/memory.max_usage_in_bytes"))


def call(base: str, path: str, body: dict | None = None, timeout: float = 30.0) -> tuple[int, bytes, dict[str, str]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, method="GET" if body is None else "POST",
                                     headers={"Content-Type": "application/json", "X-Anisotropy-Actor": ACTOR})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), dict(exc.headers)


def wait_for_api(base: str, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while True:
        try:
            status, body, _ = call(base, "/healthz", timeout=5.0)
            if status == 200 and json.loads(body) == {"status": "ok"}:
                return
        except (urllib.error.URLError, OSError, ValueError):
            pass
        if time.monotonic() > deadline:
            raise SystemExit(f"the API did not answer /healthz within {seconds:.0f} s")
        time.sleep(1.0)


def peak_memory_bytes() -> int | None:
    for path in PEAK:
        try:
            return int(path.read_text().strip())
        except (OSError, ValueError):
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--values", type=Path, required=True, help="the coupon's form rows as JSON (tests/fixtures/studio/values.json)")
    parser.add_argument("--base", default="http://127.0.0.1:8080", help="the API inside the container")
    parser.add_argument("--summary", type=Path, default=None, help="write the measurements to this JSON file")
    parser.add_argument("--timeout", type=float, default=1200.0, help="seconds to wait for the job")
    args = parser.parse_args()

    wait_for_api(args.base, 90.0)
    values = json.loads(args.values.read_text(encoding="utf-8"))
    t0 = time.monotonic()
    status, body, _ = call(args.base, "/v1/coupon-jobs", {"values": values, "run_by": "image check", "pdf": True})
    if status != 202:
        print(f"POST /v1/coupon-jobs answered {status}: {body.decode('utf-8', 'replace')}")
        return 1
    job = json.loads(body)
    job_id = job["job_id"]
    print(f"job {job_id} started; coupon from the values: {values.get('designation') or values.get('coupon') or '?'}")

    seen: list[str] = []
    deadline = time.monotonic() + args.timeout
    while job["state"] == "running":
        if time.monotonic() > deadline:
            print(f"the job is still running after {args.timeout:.0f} s; its console tail:")
            print("\n".join(job["log_tail"]))
            return 1
        time.sleep(2.0)
        status, body, _ = call(args.base, f"/v1/coupon-jobs/{job_id}")
        if status != 200:
            print(f"GET the job answered {status}: {body.decode('utf-8', 'replace')}")
            return 1
        job = json.loads(body)
        for stage in job["stages_done"]:
            if stage not in seen:
                seen.append(stage)
                print(f"  {time.monotonic() - t0:6.1f} s  done: {stage}")
    elapsed = time.monotonic() - t0
    if job["state"] != "done":
        print(f"the job ended {job['state']}: {job['message']}")
        print("\n".join(job["log_tail"]))
        return 1
    started, finished = (dt.datetime.fromisoformat(job[key]) for key in ("started_at", "finished_at"))

    outputs = job["outputs"]
    document = outputs.get("document", "")
    if not document.endswith(".pdf"):
        print(f"the job is done but reports no PDF: outputs {sorted(outputs)}")
        return 1
    document_path, fields_path = (Path("/app") / outputs[key] for key in ("document", "fields"))
    for path in (document_path, fields_path):
        if not path.is_file() or path.stat().st_size == 0:
            print(f"the job reports {path} but it is missing or empty")
            return 1

    status, body, _ = call(args.base, f"/v1/coupon-jobs/{job_id}/package", timeout=120.0)
    if status != 200:
        print(f"GET the package answered {status}")
        return 1
    names = zipfile.ZipFile(io.BytesIO(body)).namelist()
    pdfs = [name for name in names if name.endswith(".pdf")]
    if not pdfs:
        print(f"the package zip holds no PDF: {names[:20]}")
        return 1

    summary = {
        "job_id": job_id, "state": job["state"], "coupon": job["coupon"], "attempt": job["attempt"], "message": job["message"],
        "job_seconds": round((finished - started).total_seconds(), 1), "wall_seconds": round(elapsed, 1),
        "document": outputs["document"], "document_bytes": document_path.stat().st_size,
        "fields_bytes": fields_path.stat().st_size, "package_zip_bytes": len(body), "package_pdf": pdfs,
        "peak_memory_bytes": peak_memory_bytes(),
    }
    print(json.dumps(summary, indent=2))
    if args.summary is not None:
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
