"""Read an audit form that came back from the team, and put it on the coupon's case page (ADR-0043).

    uv run python tools/read_audit.py X840PW-UNT-L1 <path to the returned .xlsx> [--date YYYY-MM-DD]

The form is refused, with every reason named, when it is incomplete or inconsistent (a row without a result, a failed
row without a cause, a verdict the rule does not give, a result of our tools that was changed) or not this coupon's (another
coupon, an attempt the case page does not log, a team deck other than the one the comparison reads now). A form that passes
is kept in .local/fea/<coupon>/team/<date>/ (today, or --date: the day it came back), unless it is already in a
team folder, and the case page's audit block lists it. The case line is written by hand: the tool says what it suggests.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from anisotropy_fea import paths
from anisotropy_fea.case_pages import file_audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("coupon", help="the coupon, e.g. X840PW-UNT-L1")
    parser.add_argument("form", type=Path, help="the returned audit form (.xlsx)")
    parser.add_argument("--date", default=date.today().isoformat(), help="the day the form came back (default today)")
    args = parser.parse_args()
    try:
        date.fromisoformat(args.date)
        form, kept, case = file_audit(args.coupon, args.form, args.date)
    except ValueError as exc:  # audit.AuditError, case_pages.CasePageError, a date that is not one
        sys.exit(str(exc))
    print(f"{args.coupon}: {form.verdict} by {form.auditor} on {form.date}, attempt {form.cover['Attempt']}; failed rows and observations: {form.counts()}")
    print(f"kept at {kept.relative_to(paths.ROOT).as_posix() if paths.ROOT in kept.resolve().parents else kept}; the case page's audit block lists it")
    if form.verdict == "Fail":
        print("The package fails. Each failed row names its cause; start the next attempt with tools/new_attempt.py.")
    elif case.status == "in progress":
        print(f"Suggested case line, to write by hand if you agree: Status: verified | Accepted attempt: {form.cover['Attempt']}")


if __name__ == "__main__":
    main()
