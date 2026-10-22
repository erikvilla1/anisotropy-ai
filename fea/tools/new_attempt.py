"""Start the next attempt at a test: a new numbered folder for its runs (ADR-0039).

    uv run python tools/new_attempt.py tension-coupon

Creates .local/fea/<test>/attempts/attempt-NN_<today>/run/, where NN is the next row of the case page's attempt log (a folder
is never reused), and prints the --out paths for the run tools. Before that it deletes the CalculiX results (.frd) of every
earlier run that a later attempt has a run of the same kind for, and names each file. Add the attempt's row to the case
page's attempt log when it is done. The layout is described in `anisotropy_fea.attempts`.
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
    args = parser.parse_args()
    try:
        folder, deleted = start_attempt(args.test)
    except AttemptError as exc:
        sys.exit(str(exc))
    for path in deleted:
        print(f"deleted {path.relative_to(paths.ROOT).as_posix()} (a later attempt has a run of the same kind)")
    where = Path("..") / folder.relative_to(paths.ROOT)
    print(f"attempt folder: {folder.relative_to(paths.ROOT).as_posix()}")
    print(f"  build_model.py         --out {(where / 'run' / 'kernel').as_posix()}")
    print(f"  run_calculix.py        --out {(where / 'run' / 'calculix').as_posix()}")
    print(f"  convert_to_calculix.py --out {(where / 'run' / 'team-in-calculix').as_posix()}")
    print(f"When done, add row {folder.name[8:10]} to the attempt log of fea/models/{args.test}/README.md and run tools/case_pages.py.")


if __name__ == "__main__":
    main()
