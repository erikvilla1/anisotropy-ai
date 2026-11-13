"""A stand-in for `docs/models/upload.py` in the API's tests: the same command line and the same answer file, and no LaTeX.

    python document_stub.py <comparison>.json --out <folder> --upload <id> [--run <words>] [--compared <when>] --json <answer>

What it does is chosen by DOCUMENT_STUB: `pdf` (the default) writes <folder>/comparison.pdf, a file that begins as a PDF does and then
holds, as JSON, the options it was given and the comparison's verdict, so a test reads back what the API passed; `refused` answers
that no document can be written; `latex` answers as the real command does where Tectonic is not installed; `silent` writes no
answer. Each call adds a line to the file DOCUMENT_STUB_LOG names. Run by the API under test and imported by nothing.
"""

import json
import os
import sys
from pathlib import Path


def option(argv: list[str], name: str) -> str | None:
    return argv[argv.index(name) + 1] if name in argv else None


def main(argv: list[str]) -> int:
    comparison, out, answer = Path(argv[0]), Path(option(argv, "--out")), Path(option(argv, "--json"))
    mode = os.environ.get("DOCUMENT_STUB", "pdf")
    if os.environ.get("DOCUMENT_STUB_LOG"):
        with open(os.environ["DOCUMENT_STUB_LOG"], "a", encoding="utf-8") as log:
            log.write(f"{option(argv, '--upload')} {mode}\n")
    if mode == "silent":
        print("the stand-in stopped before it answered", file=sys.stderr)
        return 3
    if mode == "refused":
        answer.write_text(json.dumps({"written": None, "reason": "the comparison was refused, so there is nothing to print: a stand-in's reason"}), encoding="utf-8")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    if mode == "latex":
        (out / "comparison.tex").write_text("a stand-in", encoding="utf-8")
        answer.write_text(json.dumps({"written": str(out / "comparison.tex"), "pdf": False, "reason": "Tectonic is not installed, so no PDF was written"}),
                          encoding="utf-8")
        return 0
    said = {"upload": option(argv, "--upload"), "run": option(argv, "--run"), "compared": option(argv, "--compared"),
            "verdict": json.loads(comparison.read_text(encoding="utf-8"))["verdict"]}
    (out / "comparison.pdf").write_bytes(b"%PDF-1.4\n" + json.dumps(said).encode("utf-8"))
    answer.write_text(json.dumps({"written": str(out / "comparison.pdf"), "pdf": True}), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
