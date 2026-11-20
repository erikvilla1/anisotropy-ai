"""What the language model cost this month, by person and by feature, from the `model_calls` table (ADR-0119).

    uv run --project api python -m anisotropy_api.cost_report             # this month (UTC)
    uv run --project api python -m anisotropy_api.cost_report --month 2026-11 --weeks 8

It reads the database the migrations use (DATABASE_URL_UNPOOLED, else DATABASE_URL, from the environment or the nearest .env) through
the views the migration made, and prints three tables: each person's calls and cost in the month, each feature's last weeks with the
flag the view sets when the cost per call or the hidden thinking share is more than 30% above the four weeks before, and the month's
total by model to set beside the provider's usage page for the key. It changes nothing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine, create_engine, text

MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _cell(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, Decimal):
        return format(value, "f")  # as the database rounded it: costs to a millionth of a dollar, shares to a tenth of a percent
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Rows under their headers, each column as wide as its widest cell; numbers to the right."""
    cells = [[_cell(v) for v in row] for row in rows]
    numeric = [all(isinstance(row[i], (int, float, Decimal)) or row[i] is None for row in rows) and bool(rows) for i in range(len(headers))]
    widths = [max([len(h)] + [len(row[i]) for row in cells]) for i, h in enumerate(headers)]

    def line(values: Sequence[str]) -> str:
        return "  ".join(v.rjust(w) if numeric[i] else v.ljust(w) for i, (v, w) in enumerate(zip(values, widths))).rstrip()

    return "\n".join([line(headers), line(["-" * w for w in widths]), *(line(row) for row in cells)])


def report(engine: Engine, month: str, weeks: int) -> str:
    """The month's report as text."""
    with engine.connect() as connection:
        people = connection.execute(text("SELECT person, calls, cost_usd, unpriced_calls, features FROM model_costs_by_person "
                                         "WHERE month = :month ORDER BY cost_usd DESC NULLS LAST, person"), {"month": month}).all()
        recent = connection.execute(text(
            "SELECT week_of, feature, calls, cost_per_call_usd, usual_cost_per_call_usd, thinking_share_pct, usual_thinking_share_pct, flag "
            "FROM model_costs_by_feature WHERE week_of >= (SELECT max(week_of) FROM model_costs_by_feature) - make_interval(weeks => :back) "
            "ORDER BY week_of DESC, feature"), {"back": max(weeks - 1, 0)}).all()
        models = connection.execute(text(
            "SELECT model, sum(calls), sum(input_tokens), sum(output_tokens), sum(thinking_tokens), sum(cache_read_tokens), "
            "sum(cache_write_tokens), sum(cost_usd), sum(unpriced_calls) FROM model_costs_by_day "
            "WHERE to_char(day, 'YYYY-MM') = :month GROUP BY model ORDER BY model"), {"month": month}).all()
    calls = sum(int(row[1]) for row in models)
    cost = sum((row[7] or Decimal(0) for row in models), Decimal(0))
    unpriced = sum(int(row[8]) for row in models)
    looks = [row for row in recent if str(row[7]).startswith("look")]
    out = [f"Language model costs, {month} (UTC), from the model_calls table", ""]
    if not calls:
        out.append("No calls to the model were recorded this month.")
    else:
        out += ["By person", table(["person", "calls", "cost USD", "not priced", "used for"], people), ""]
    out += [f"By feature, the last {weeks} week(s) (usual = the average of the four weeks with calls before)",
            table(["week of", "feature", "calls", "USD per call", "usual", "thinking %", "usual", "flag"], recent) if recent else "No weeks yet.", ""]
    if calls:
        out += ["By model, to set beside the provider's usage page for this key (same month, UTC)",
                table(["model", "calls", "input", "output", "of it thinking", "cache read", "cache write", "cost USD", "not priced"], models), ""]
        out.append(f"Total: {calls} call(s), {cost:.6f} USD" + (f", and {unpriced} call(s) of a model not on the price list" if unpriced else "") + ".")
    if looks:
        out.append(f"{len(looks)} week(s) flagged: see whether the model, the effort or a prompt changed that week (git log), else ask why.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m anisotropy_api.cost_report", description=__doc__.splitlines()[0])
    parser.add_argument("--month", default=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m"), help="YYYY-MM, in UTC; default this month")
    parser.add_argument("--weeks", type=int, default=5, help="how many recent weeks of the features to show; default 5")
    args = parser.parse_args(argv)
    if not MONTH.match(args.month):
        print(f"refused:\n  --month is YYYY-MM, such as 2026-11, not {args.month!r}", file=sys.stderr)
        return 2
    if args.weeks < 1:
        print("refused:\n  --weeks is 1 or more", file=sys.stderr)
        return 2
    from .settings import database_url_for_migrations

    try:
        engine = create_engine(database_url_for_migrations())
    except RuntimeError as exc:
        print(f"refused:\n  {exc}", file=sys.stderr)
        return 2
    try:
        print(report(engine, args.month, args.weeks))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
