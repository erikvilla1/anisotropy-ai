"""Solve a plate with its shape followed as the load rises, and write what the page reads of it (ADR-0142, step 2).

    uv run python tools/follow_plate.py ../.local/fea/<coupon>/ours/<coupon>.toml --out <attempt>/run/followed

The spec is a plate that asks for it (`[analysis] large_displacement = true`). CalculiX solves its eight-node twin with a
large-displacement step and prints the whole plate at ten levels of the load; our composite layer reads the plies from its strains
(`anisotropy_fea.followed_plate`). Written into the output folder: followed.inp, the deck CalculiX ran, with its console and status
files; <spec>-fields.json, every field at the whole load and the summary, with the load against the largest displacement and the
failure index level by level under `summary.followed`; and <spec>-explanation.json, the sentences about the result. The printed levels
(followed.dat) are read and then removed: they are the largest file of the run and everything read from them is in the fields.

A run that stops before the whole load writes no fields: it ends with the share of the load it reached and the largest displacement
there, in one line, and exit code 1.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from anisotropy_fea.followed_plate import JOB, SOLVE_TIMEOUT_S, FollowedError, Stopped, follow_plate, write_followed
from anisotropy_fea.mesher import MeshError
from anisotropy_fea.spec import SpecError, load_spec
from anisotropy_fea.write_calculix import CalculixWriterError


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=SOLVE_TIMEOUT_S, help="seconds CalculiX may take")
    parser.add_argument("--keep-levels", action="store_true", help="keep followed.dat, the printed levels")
    args = parser.parse_args()
    try:
        spec = load_spec(args.spec)
        followed = follow_plate(spec, args.out, timeout_s=args.timeout)
    except Stopped as exc:
        raise SystemExit(str(exc)) from None
    except (SpecError, MeshError, CalculixWriterError, FollowedError) as exc:
        raise SystemExit(f"the plate is not followed: {exc}") from None
    finally:
        if not args.keep_levels:
            (args.out / f"{JOB}.dat").unlink(missing_ok=True)
    print(f"{followed.version and 'CalculiX ' + followed.version or 'CalculiX'} followed the plate to its whole load in {len(followed.levels)} levels, "
          f"{followed.elapsed_s:.1f} s")
    for path in write_followed(followed, args.out, args.spec.stem).values():
        print("written", path)


if __name__ == "__main__":
    main()
