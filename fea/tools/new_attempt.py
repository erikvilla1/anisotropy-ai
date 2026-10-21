"""Start the next attempt at a test: a new numbered folder for the request, the engine commit and every run (ADR-0039).

    uv run python tools/new_attempt.py tension-coupon --prompt "the founder's request, word for word"
    uv run python tools/new_attempt.py tension-coupon --prompt-file request.txt

Creates .local/fea/<test>/attempts/attempt-NN_<today>/ (NN one more than the last; a folder is never reused) with prompt.md,
notes.md and run/, and prints the --out paths for the run tools. Before that it deletes the CalculiX results (.frd) of every
earlier run that a later attempt has a run of the same kind for, and names each file. The layout is described in
`anisotropy_fea.attempts`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.attempts import AttemptError, start_attempt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("test", help="the model folder under fea/models/, e.g. tension-coupon")
    request = parser.add_mutually_exclusive_group(required=True)
    request.add_argument("--prompt", help="the request for this attempt, word for word")
    request.add_argument("--prompt-file", type=Path, help="a file holding the request, word for word")
    args = parser.parse_args()
    prompt = args.prompt if args.prompt is not None else args.prompt_file.read_text(encoding="utf-8")
    try:
        folder, deleted = start_attempt(args.test, prompt)
    except AttemptError as exc:
        sys.exit(str(exc))
    for path in deleted:
        print(f"deleted {path.relative_to(paths.ROOT).as_posix()} (a later attempt has a run of the same kind)")
    where = Path("..") / folder.relative_to(paths.ROOT)
    print(f"attempt folder: {folder.relative_to(paths.ROOT).as_posix()}")
    print(f"  build_model.py         --out {(where / 'run' / 'kernel').as_posix()}")
    print(f"  run_calculix.py        --out {(where / 'run' / 'calculix').as_posix()}")
    print(f"  convert_to_calculix.py --out {(where / 'run' / 'team-in-calculix').as_posix()}")
    print("Fill in notes.md as you go, then add the attempt's row to the case page's attempt log and run tools/case_pages.py.")


if __name__ == "__main__":
    main()
