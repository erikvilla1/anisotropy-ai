"""Rewrite a coupon spec whose `coupon.standard` is free text so that the form, whose Standard row is now a list, can reopen it (ADR-0072).

    uv run python tools/migrate_standard.py <spec.toml> [<spec.toml> ...]            # rewrite each spec in place
    uv run python tools/migrate_standard.py --dry-run <spec.toml> [<spec.toml> ...]  # print what would change; write nothing

Before form 0.8 the Standard row took any text ("ASTM D3039", "ASTM D7264 proportions"). Since ADR-0072 it takes "none" or the designation
of a standard we check, and a spec that names one carries `[test_method]`. A spec with other text still loads and runs; only reopening it in
the studio refuses the row. This tool states such a spec's standard as "none" and keeps the old words where a reader finds them: at the end
of `size_from` ("...; stated before as: ASTM D7264 proportions"), with a dated comment at the end of the file. A spec whose standard is
already "none" or a listed designation is left alone. Nothing else in the file changes, line endings included. The tool does not decide that
a coupon follows a standard: a person picks it on the form, and the checklist then judges it.

Run on .local/fea by the founder, and on the hosted coupons before a deploy that carries form 0.8.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from anisotropy_fea.standards import STANDARD_WORDS as LISTED  # the Standard row's words

STRING_LINE = r'^(?P<indent>[ \t]*){key}[ \t]*=[ \t]*"(?P<value>(?:[^"\\\r\n]|\\.)*)"(?P<rest>[^\r\n]*)(?P<eol>\r?\n)'


class MigrationError(ValueError):
    """The file is not a spec this tool rewrites: no [coupon] table, or its standard or size_from line cannot be read."""


def coupon_table(text: str) -> tuple[int, int]:
    """Where the [coupon] table's lines start and end in the text."""
    head = re.search(r"^\[coupon\][^\r\n]*\r?\n", text, re.MULTILINE)
    if head is None:
        raise MigrationError("the spec has no [coupon] table")
    following = re.search(r"^\[", text[head.end():], re.MULTILINE)
    return head.end(), head.end() + following.start() if following else len(text)


def line_of(text: str, key: str, start: int, end: int) -> re.Match:
    match = re.compile(STRING_LINE.format(key=key), re.MULTILINE).search(text, start, end)
    if match is None:
        raise MigrationError(f"the [coupon] table has no `{key} = \"...\"` line on one line")
    return match


def migrate_text(text: str, today: date | None = None) -> tuple[str, str] | None:
    """The spec text rewritten and the standard it stated; None when its standard is already one the list holds."""
    start, end = coupon_table(text)
    standard = line_of(text, "standard", start, end)
    old = standard.group("value")
    if old in LISTED:
        return None
    size = line_of(text, "size_from", start, end)
    eol = standard.group("eol")
    new_size = f'{size.group("indent")}size_from = "{size.group("value")}; stated before as: {old}"{size.group("rest")}{size.group("eol")}'
    new_standard = f'{standard.group("indent")}standard = "none"{standard.group("rest")}{eol}'
    pieces = sorted(((standard.start(), standard.end(), new_standard), (size.start(), size.end(), new_size)), reverse=True)
    rewritten = text
    for a, b, replacement in pieces:
        rewritten = rewritten[:a] + replacement + rewritten[b:]
    if not rewritten.endswith(("\n", "\r\n")):
        rewritten += eol
    day = (today or date.today()).isoformat()
    rewritten += (f'# Migrated on {day} by fea/tools/migrate_standard.py (ADR-0072): coupon.standard was "{old}", which the form\'s Standard list '
                  f"does not hold; it is now \"none\" and the old words close size_from.{eol}")
    return rewritten, old


def migrate_file(path: Path, dry_run: bool, today: date | None = None) -> str:
    raw = path.read_bytes().decode("utf-8")
    done = migrate_text(raw, today)
    if done is None:
        return f"{path}: standard already on the list, left as it is"
    rewritten, old = done
    line = f'{path}: standard "{old}" -> "none", the old words kept in size_from'
    if dry_run:
        return line + " (dry run, nothing written)"
    path.write_bytes(rewritten.encode("utf-8"))
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("specs", nargs="+", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="print what would change; write nothing")
    args = parser.parse_args(argv)
    failed = 0
    for path in args.specs:
        try:
            print(migrate_file(path, args.dry_run))
        except (MigrationError, OSError, UnicodeDecodeError) as exc:
            print(f"{path}: not migrated: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
