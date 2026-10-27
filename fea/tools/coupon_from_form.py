"""Read a filled-in coupon input form and start its coupon (ADR-0046).

    uv run python tools/coupon_from_form.py <filled form>.xlsx [--date YYYY-MM-DD] [--root PATH] [--replace] [--dry-run]

The form is refused, with every problem named by its row, when it is not ours, incomplete or inconsistent; the spec's own rules
judge the exact text that will be written. A form that passes gives the coupon its name (<material code>-<test code>-<layup
code>) and writes, under .local/fea/<coupon>/ (or --root): ours/<coupon>.toml and ours/<coupon>-nodal.toml, the form as received
in team/<date>/ with a README, and a case page when there is none. Then it prints what to run next. --replace rewrites the two
specs of a coupon that already has them and nothing else; --dry-run prints and writes nothing.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.intake import IntakeError, convert


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("form", type=Path, help="the filled-in coupon input form (.xlsx)")
    parser.add_argument("--date", default=date.today().isoformat(), help="the day the form arrived (default today): the team/<date>/ folder")
    parser.add_argument("--root", type=Path, default=paths.LOCAL, help="the folder holding one folder per coupon (default .local/fea)")
    parser.add_argument("--replace", action="store_true", help="rewrite the two specs of a coupon that already has them")
    parser.add_argument("--dry-run", action="store_true", help="print the coupon's name and its specs; write nothing")
    args = parser.parse_args()
    try:
        date.fromisoformat(args.date)
        intake = convert(args.form, root=args.root, day=args.date, replace=args.replace, dry_run=args.dry_run)
    except (IntakeError, ValueError) as exc:
        sys.exit(str(exc))
    print(f"{intake.designation.name}: {intake.folder}")
    if args.dry_run:
        print(intake.main)
        print("# ---- the CalculiX twin")
        print(intake.twin)
    for path in intake.written:
        print(f"written  {path.relative_to(intake.folder).as_posix()}")
    print("Next, from fea/:")
    for command in intake.commands:
        print(f"  {command}")
    print(f'Or all of it in one go: uv run python tools/run_coupon.py {intake.designation.name} --run-by "<your name>"')


if __name__ == "__main__":
    main()
