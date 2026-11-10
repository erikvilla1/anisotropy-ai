"""Rewrite a coupon spec written before ADR-0065 so that it states the same physical laminate with its angles counted from the length axis.

    uv run python tools/migrate_angles.py <spec.toml> [<spec.toml> ...]            # rewrite each spec in place
    uv run python tools/migrate_angles.py --dry-run <spec.toml> [<spec.toml> ...]  # print what would change; write nothing

Before ADR-0065 a spec's `[layup] angles` were counted from global x, across the coupon's width; since it they are counted from the
coupon's length axis, global y, so a stated 0-degree ply runs along the pull. The same fibre direction is therefore stated 90 degrees
lower: this tool subtracts 90 from every angle, brings the result into (-90, 90] (a fibre has no arrow, so -90 is 90), adds
`angles_from = "length"` under the angles, and appends a dated comment line to the file. `[45, 0, -45, 90]` becomes `[-45, 90, 45, 0]`,
the laminate the old spec meant; old records and the team's deck equivalence hold. A spec that already states `angles_from` is refused:
the tool is run once per file, never twice. Nothing else in the file changes, line endings included.

It is not run on the public checks under fea/checks, which keep their stated layups and change their physical laminate on purpose
(ADR-0065), and it is run on .local/fea only by the founder.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ANGLES_LINE = re.compile(r"^(?P<indent>[ \t]*)angles[ \t]*=[ \t]*\[(?P<body>[^\]]*)\](?P<rest>[^\r\n]*)(?P<eol>\r?\n)", re.MULTILINE)
LENGTH_AXIS_ROTATION_DEG = 90.0  # the same number spec.LENGTH_AXIS_ROTATION_DEG states; repeated here so the tool reads no package


class MigrationError(ValueError):
    """The file is not a spec this tool rewrites: it already states angles_from, or its layup line cannot be read."""


def normalised_angle(angle_deg: float) -> float:
    """The same fibre direction in (-90, 90], as spec.normalised_angle computes it."""
    angle = angle_deg % 180.0
    if angle > 90.0:
        angle -= 180.0
    return 0.0 if angle == 0.0 else angle


def migrated_angle(angle_deg: float) -> float:
    """An angle counted from x, restated from the length axis: the same fibres, 90 degrees lower."""
    return normalised_angle(angle_deg - LENGTH_AXIS_ROTATION_DEG)


def angle_text(angle: float) -> str:
    return str(int(angle)) if float(angle).is_integer() else f"{angle:g}"


def migrate_text(text: str, today: date | None = None) -> tuple[str, list[float], list[float]]:
    """The spec text rewritten; also the angles before and after, for the report."""
    if re.search(r"^[ \t]*angles_from[ \t]*=", text, re.MULTILINE):
        raise MigrationError("the spec already states layup.angles_from: it was written or migrated under ADR-0065 and is not rewritten again")
    layup = re.search(r"^\[layup\][^\r\n]*\r?\n", text, re.MULTILINE)
    if layup is None:
        raise MigrationError("the spec has no [layup] table")
    match = ANGLES_LINE.search(text, layup.end())
    if match is None or re.search(r"^\[", text[layup.end():match.start()], re.MULTILINE):
        raise MigrationError("the [layup] table has no `angles = [...]` line on one line")
    body = match.group("body").strip()
    try:
        before = [float(token) for token in body.split(",")] if body else []
    except ValueError:
        raise MigrationError(f"the angles line holds something other than numbers: [{body}]") from None
    after = [migrated_angle(angle) for angle in before]
    eol = match.group("eol")
    indent = match.group("indent")
    day = (today or date.today()).isoformat()
    new_line = (f"{indent}angles = [{', '.join(angle_text(a) for a in after)}]{match.group('rest')}{eol}"
                f"{indent}angles_from = \"length\"  # counted from the coupon's length axis, the direction it is pulled: 0 = fibres along the pull (ADR-0065){eol}")
    rewritten = text[:match.start()] + new_line + text[match.end():]
    if not rewritten.endswith(("\n", "\r\n")):
        rewritten += eol
    rewritten += (f"# Migrated on {day} by fea/tools/migrate_angles.py (ADR-0065): the angles were [{', '.join(angle_text(a) for a in before)}] counted "
                  f"from x, across the width; they are now stated from the coupon's length axis, the same fibres.{eol}")
    return rewritten, before, after


def migrate_file(path: Path, dry_run: bool, today: date | None = None) -> str:
    """Rewrite one spec, or describe the change; the file's bytes and line endings are kept apart from the two lines that change."""
    raw = path.read_bytes().decode("utf-8")
    rewritten, before, after = migrate_text(raw, today)
    line = f"{path}: angles [{', '.join(angle_text(a) for a in before)}] -> [{', '.join(angle_text(a) for a in after)}], angles_from = \"length\" added"
    if dry_run:
        return line + " (dry run, nothing written)"
    path.write_bytes(rewritten.encode("utf-8"))
    return line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("specs", nargs="+", type=Path, help="the spec files to rewrite")
    parser.add_argument("--dry-run", action="store_true", help="print the change and write nothing")
    args = parser.parse_args(argv)
    failed = 0
    for spec in args.specs:
        try:
            print(migrate_file(spec, args.dry_run))
        except (MigrationError, OSError, UnicodeDecodeError) as exc:
            failed += 1
            print(f"{spec}: refused: {exc}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
