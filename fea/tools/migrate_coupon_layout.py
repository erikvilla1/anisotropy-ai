"""Move each coupon folder under .local/fea/ to the team / ours / documents layout (ADR-0040 amendment 3), once.

    uv run python tools/migrate_coupon_layout.py            # list what would move and what would be rewritten; change nothing
    uv run python tools/migrate_coupon_layout.py --apply    # do it

    before                                              after
    <coupon>.toml, <coupon>-nodal.toml                  ours/
    decks/                                              ours/decks/
    records/*, comparison/* (manifest, records,         ours/verification/
      readings, notes/, figures/)
    our-runs/                                           ours/runs/
    documents/<coupon>.tex, documents/figures/          ours/latex/
    from-team/                                          team/
    README.md, the rest of documents/                   stay where they are

A path in a moved TOML file that starts with ../ (a record's spec and decks, the manifest's team deck, reports, spec and
CalculiX record) is rewritten so that it reaches the same file from the new place. Nothing is deleted: what stays in
documents/ from before ADR-0043 (a loose PDF, a zip) is listed for the founder to delete by hand. A folder already in the new
layout is skipped. Every move is checked before the first one is made: a move onto an existing path, or an entry this tool
does not know, stops it with the reason.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from anisotropy_fea import paths

RELATIVE = re.compile(r'"(\.\./[^"\n]*)"')  # a quoted path that starts with ../


@dataclass
class Plan:
    folder: Path
    moves: list[tuple[Path, Path]] = field(default_factory=list)  # (from, to), absolute
    rewrites: list[tuple[Path, str, str]] = field(default_factory=list)  # (the file at its new place, old path, new path)
    left: list[Path] = field(default_factory=list)  # stays in documents/, from before ADR-0043
    nowhere: list[tuple[Path, str]] = field(default_factory=list)  # a path that already reached no file; left as it is
    skipped: str | None = None  # why nothing moves


class LayoutError(ValueError):
    pass


def plan(folder: Path) -> Plan:
    """What moving one coupon folder takes; nothing is changed."""
    name = folder.name
    out = Plan(folder)
    if (folder / paths.OURS).exists():
        out.skipped = "already in the new layout"
        return out
    if not (folder / f"{name}.toml").is_file():
        out.skipped = f"no {name}.toml at its top: not a coupon folder"
        return out
    ours, verification, latex = folder / paths.OURS, folder / paths.OURS / paths.VERIFICATION, folder / paths.OURS / paths.LATEX
    unknown = []
    for entry in sorted(folder.iterdir()):
        if entry.is_file() and entry.suffix == ".toml":
            out.moves.append((entry, ours / entry.name))
        elif entry.name == "from-team":
            out.moves.append((entry, folder / paths.TEAM_FILES))
        elif entry.name == "decks":
            out.moves.append((entry, ours / "decks"))
        elif entry.name == "our-runs":
            out.moves.append((entry, ours / paths.RUNS))
        elif entry.name in ("records", "comparison"):
            out.moves += [(item, verification / item.name) for item in sorted(entry.iterdir())]
        elif entry.name == paths.DOCUMENTS:
            for item in sorted(entry.iterdir()):
                if item.name in (f"{name}.tex", "figures"):
                    out.moves.append((item, latex / item.name))
                elif not (item.is_dir() and item.name.endswith(f"_{name}")):  # a package (ADR-0043) is where it belongs
                    out.left.append(item)
        elif entry.name != "README.md":
            unknown.append(entry.name)
    problems = [f"{entry}: not part of either layout; move it by hand first" for entry in unknown]
    targets = [to for _, to in out.moves]
    problems += [f"{to.relative_to(folder).as_posix()} exists already" for to in targets if to.exists()]
    problems += [f"two entries would move to {to.relative_to(folder).as_posix()}" for to in set(targets) if targets.count(to) > 1]
    if problems:
        raise LayoutError(f"{folder}: " + "; ".join(problems))

    def moved(target: Path) -> Path:
        for source, to in out.moves:
            if target == source or source in target.parents:
                return to / target.relative_to(source)
        return target

    for source, to in out.moves:
        if source.is_file() and source.suffix == ".toml":
            text = source.read_text(encoding="utf-8")
            for old in dict.fromkeys(RELATIVE.findall(text)):
                target = Path(os.path.normpath(source.parent / old))
                if not target.exists():
                    out.nowhere.append((to, old))
                    continue
                new = Path(os.path.relpath(moved(target), to.parent)).as_posix()
                if new != old:
                    out.rewrites.append((to, old, new))
    return out


def apply(p: Plan) -> None:
    """Make the moves, rewrite the paths, and remove records/ and comparison/ once they are empty."""
    for source, to in p.moves:
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(to))
    for path, old, new in p.rewrites:
        data = path.read_bytes()  # bytes, so the file keeps its line ends
        path.write_bytes(data.replace(f'"{old}"'.encode("utf-8"), f'"{new}"'.encode("utf-8")))
    for empty in ("records", "comparison"):
        if (p.folder / empty).is_dir() and not any((p.folder / empty).iterdir()):
            (p.folder / empty).rmdir()


def report(p: Plan) -> list[str]:
    rel = lambda path: path.relative_to(p.folder).as_posix() + ("/" if path.is_dir() else "")  # noqa: E731
    if p.skipped:
        return [f"{p.folder.name}: skipped, {p.skipped}"]
    lines = [f"{p.folder.name}:"]
    lines += [f"  move     {rel(source):56} -> {to.relative_to(p.folder).as_posix()}" for source, to in p.moves]
    lines += [f"  rewrite  {path.relative_to(p.folder).as_posix()}: \"{old}\" -> \"{new}\"" for path, old, new in p.rewrites]
    lines += [f"  stays    {rel(item)} (from before ADR-0043; delete it by hand if you agree)" for item in p.left]
    lines += [f"  note     {path.relative_to(p.folder).as_posix()}: \"{old}\" reached no file before the move either; left as it is"
              for path, old in p.nowhere]
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="make the moves; without it, only list them")
    parser.add_argument("--root", type=Path, default=paths.LOCAL, help="the folder holding one folder per coupon (default .local/fea)")
    args = parser.parse_args()
    folders = [d for d in sorted(args.root.iterdir()) if d.is_dir() and d.name not in paths.NOT_TESTS] if args.root.is_dir() else []
    try:
        plans = [plan(d) for d in folders]  # every folder is checked before anything moves
    except LayoutError as exc:
        sys.exit(str(exc))
    for p in plans:
        print("\n".join(report(p)))
    if not args.apply:
        print("\nNothing was changed. Run with --apply to make these moves.")
        return
    for p in plans:
        if not p.skipped:
            apply(p)
    print("\nMoved. Then run tools/case_pages.py, and update the case pages' 'Where to look' by hand.")


if __name__ == "__main__":
    main()
