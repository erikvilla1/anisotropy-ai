"""Write the coupon input form's definition as JSON for the website, so the studio's form and the Excel form are one definition (ADR-0051).

    uv run python tools/export_form_definition.py            # writes lib/coupon-form-definition.json at the repository root
    uv run python tools/export_form_definition.py --check    # exits 1 when the file differs from what the package defines today

Every row of the form (key, label, kind, what it means, whether it is required, its default, its words, its bounds), the sections
they sit in, the instructions, the Definitions sheet, the tests offered, the criterion words, and the library materials the form
lists with their constants in MPa and mm. The website imports the file at build time; `fea/tests/test_form_definition.py` fails when
it drifts from the package, as `tests/material-library-export.test.ts` does for the material library.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from anisotropy_fea import __version__, paths
from anisotropy_fea.intake import (BLOCKS, CRITERION_WORDS, FORM_VERSION, GLOSSARY, HOW_TO, LIBRARY_COLUMNS, TESTS, UNITS, library_records,
                                   library_row)

TARGET = paths.ROOT / "lib" / "coupon-form-definition.json"


def definition() -> dict:
    sections = []
    for title, fields in BLOCKS:
        sections.append({"title": title, "fields": [
            {"key": f.key, "label": f.label, "kind": f.kind, "help": f.help, "required": f.required, "default": f.default, "words": list(f.words),
             "at_least": f.at_least, "above": f.above} for f in fields]})
    library = [dict(zip(LIBRARY_COLUMNS, library_row(lib))) for lib in library_records()]
    return {
        "form_version": FORM_VERSION, "fea_version": __version__, "units": UNITS, "row_units": {"length": "mm", "stress": "MPa", "force": "N"},
        "sections": sections,
        "how_to": list(HOW_TO),
        "glossary": [{"group": group, "terms": [{"term": term, "meaning": meaning, "example": example} for term, meaning, example in terms]}
                     for group, terms in GLOSSARY],
        "tests": dict(TESTS),
        "criteria": list(CRITERION_WORDS),
        "library": library,
    }


def render(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=TARGET)
    parser.add_argument("--check", action="store_true", help="compare with the file instead of writing it")
    args = parser.parse_args()
    text = render(definition())
    if args.check:
        current = args.out.read_text(encoding="utf-8").replace("\r\n", "\n") if args.out.is_file() else None
        if current != text:
            sys.exit(f"{args.out} differs from the package's definition; run tools/export_form_definition.py")
        print(f"{args.out}: current")
        return
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"written {args.out}")


if __name__ == "__main__":
    main()
