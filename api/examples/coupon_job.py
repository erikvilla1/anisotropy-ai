"""Send a filled-in coupon input form to the local API, follow the job, and save its package (ADR-0050).

    uv run python examples/coupon_job.py <filled form>.xlsx --run-by "Erik Villa" --actor founder-terminal
    uv run python examples/coupon_job.py --coupon AS4-UNT-L3 --run-by "Erik Villa" --actor founder-terminal

The API must be running (README: Run it) on a machine with uv, the fea environment and CalculiX. Prints the job's state every few
seconds, then the files it made and where the package zip was saved. Standard library only, so any Python runs it.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("form", type=Path, nargs="?", help="a filled-in coupon input form (.xlsx)")
    parser.add_argument("--coupon", help="instead of a form: a coupon under .local/fea/ that has its specs")
    parser.add_argument("--run-by", required=True, help="who runs it, as the record and the attempt log name them")
    parser.add_argument("--actor", required=True, help="which client this is (X-Anisotropy-Actor), e.g. founder-terminal")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="the API's address")
    parser.add_argument("--out", type=Path, default=Path("."), help="the folder the package zip is saved in")
    args = parser.parse_args()
    if (args.form is None) == (args.coupon is None):
        parser.error("give a form or --coupon, not both and not neither")
    headers = {"Content-Type": "application/json", "X-Anisotropy-Actor": args.actor}

    def call(method: str, path: str, body: dict | None = None) -> tuple[dict, bytes]:
        request = urllib.request.Request(args.api + path, method=method, headers=headers,
                                         data=None if body is None else json.dumps(body).encode("utf-8"))
        try:
            with urllib.request.urlopen(request) as answer:
                return dict(answer.headers), answer.read()
        except urllib.error.HTTPError as exc:
            sys.exit(f"{method} {path}: {exc.code} {exc.read().decode('utf-8', errors='replace')}")
        except urllib.error.URLError as exc:
            sys.exit(f"the API at {args.api} did not answer ({exc.reason}); is it running?")

    source = {"coupon": args.coupon} if args.coupon else {"form_name": args.form.name,
                                                           "form_base64": base64.b64encode(args.form.read_bytes()).decode("ascii")}
    answer, body = call("POST", "/v1/coupon-jobs", {**source, "run_by": args.run_by})
    job, where = json.loads(body), answer["location"]
    print(f"job {job['job_id']} started")
    started, steps = time.monotonic(), set()
    while job["state"] == "running":
        time.sleep(3)
        job = json.loads(call("GET", where)[1])
        for line in job["log_tail"]:  # the console's last lines; each step opens with its own "== " line
            if line.startswith("== ") and line not in steps:
                steps.add(line)
                print(f"  {time.monotonic() - started:4.0f} s  {line[3:]}")
    print(f"{job['state']} after {time.monotonic() - started:.0f} s: {job['message']}")
    if job["run_id"]:
        print(f"run record: GET /v1/runs/{job['run_id']}")
    if job["state"] != "done":
        sys.exit(1)
    for key, path in job["outputs"].items():
        print(f"  {key:17} {path}")
    answer, data = call("GET", where + "/package")
    name = answer.get("content-disposition", "").split("filename=")[-1].strip('"') or f"{job['coupon']}-package.zip"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / name).write_bytes(data)
    print(f"package saved: {args.out / name} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
