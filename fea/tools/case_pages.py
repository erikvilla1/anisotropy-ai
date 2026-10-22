"""Write the generated blocks of the case pages and the indexes from the records (ADR-0039).

    uv run python tools/case_pages.py           # rewrite every generated block
    uv run python tools/case_pages.py --check   # name the files that are out of date and exit 1; change nothing
    uv run python tools/case_pages.py --local   # also write .local/INDEX.md: every case, homework and projects included

Run it after a record, a team summary, a case line or an attempt log changes. What it writes is described in
`anisotropy_fea.case_pages`.
"""

from __future__ import annotations

import argparse
import sys

from anisotropy_fea.case_pages import LOCAL_INDEX, CasePageError, local_index, pages, rel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="change nothing; exit 1 when a file is out of date")
    parser.add_argument("--local", action="store_true", help="also write .local/INDEX.md (git-ignored)")
    args = parser.parse_args()
    try:
        wanted = pages()
    except CasePageError as exc:
        sys.exit(str(exc))
    stale = [path for path, text in wanted.items() if path.read_text(encoding="utf-8").replace("\r\n", "\n") != text]
    for path in wanted:
        print(("OUT OF DATE " if path in stale else "current     ") + rel(path))
    if args.check:
        sys.exit(1 if stale else 0)
    for path in stale:
        path.write_text(wanted[path], encoding="utf-8", newline="\n")
    print(f"{len(stale)} file(s) rewritten")
    if args.local:
        LOCAL_INDEX.write_text(local_index(), encoding="utf-8", newline="\n")
        print(f"written {rel(LOCAL_INDEX)}")


if __name__ == "__main__":
    main()
