"""Write the coupon input form's definition as JSON for the website, so the studio's form and the Excel form are one definition (ADR-0051).

    uv run python tools/export_form_definition.py            # writes lib/coupon-form-definition.json at the repository root
    uv run python tools/export_form_definition.py --check    # exits 1 when the file differs from what the package defines today

Every row of the form (key, label, kind, what it means, whether it is required, its default, its words, its bounds, and for a row
with a unit its label and default in each unit system), the sections they sit in, the unit systems a coupon may be stated in with
their labels, the instructions, the Definitions sheet, the tests offered, the criterion words, and the library materials the form
lists with their constants in MPa and mm and, under `library_constants`, in every system (ADR-0061). The page converts nothing:
every number it shows in a system is written here by the engine. The website imports the file at build time;
`fea/tests/test_studio_tool.py` fails when it drifts from the package, as `tests/material-library-export.test.ts` does for the
material library.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from anisotropy_fea import __version__, paths
from anisotropy_fea.intake import (BLOCKS, CRITERION_WORDS, FORM_VERSION, GLOSSARY, HOW_TO, LIBRARY_COLUMNS, TESTS, UNITS, in_stated, library_records,
                                   library_row)
from anisotropy_fea.spec import AREA_REGIONS, EDGE_REGIONS
from anisotropy_fea.units import DECK_UNITS, UNIT_LABEL, UNIT_SYSTEMS, from_si, units_words

TARGET = paths.ROOT / "lib" / "coupon-form-definition.json"


def field_entry(f) -> dict:
    entry = {"key": f.key, "label": f.label, "kind": f.kind, "help": f.help, "required": f.required, "default": f.default, "words": list(f.words),
             "at_least": f.at_least, "above": f.above, "unit": f.unit}
    if f.unit is not None:
        entry["labels"] = {units: f.label_in(units) for units in UNIT_SYSTEMS}  # the row's label in each system the coupon may be stated in
        if f.unit == "length" and isinstance(f.default, (int, float)) and not isinstance(f.default, bool):
            entry["defaults"] = {units: in_stated(float(f.default), units) for units in UNIT_SYSTEMS}  # our mm default, in each system
    return entry


def library_constants() -> dict:
    """Each library material's E1, E2, G12 and ply thickness in every system, from the library's SI values: what the chat's tape
    estimate and thickness note read, so the page converts nothing."""
    out = {}
    for lib in library_records():
        t = lib.ply_thickness_m
        out[lib.material_id] = {units: {"E1": from_si(lib.lamina.E1, "stress", units), "E2": from_si(lib.lamina.E2, "stress", units),
                                        "G12": from_si(lib.lamina.G12, "stress", units),
                                        "ply_thickness": None if t is None else from_si(t, "length", units)} for units in UNIT_SYSTEMS}
    return out


def definition() -> dict:
    sections = [{"title": title, "fields": [field_entry(f) for f in fields]} for title, fields in BLOCKS]
    library = [dict(zip(LIBRARY_COLUMNS, library_row(lib))) for lib in library_records()]
    return {
        "form_version": FORM_VERSION, "fea_version": __version__, "units": UNITS, "row_units": {"length": "mm", "stress": "MPa", "force": "N"},
        "unit_systems": {units: {"words": units_words(units), "labels": dict(UNIT_LABEL[units])} for units in UNIT_SYSTEMS},
        "deck_units": DECK_UNITS,
        "sections": sections,
        "how_to": list(HOW_TO),
        "glossary": [{"group": group, "terms": [{"term": term, "meaning": meaning, "example": example} for term, meaning, example in terms]}
                     for group, terms in GLOSSARY],
        "tests": dict(TESTS),
        "criteria": list(CRITERION_WORDS),
        "library": library,
        "library_constants": library_constants(),
        "plate": {"test": "plate", "edges": list(EDGE_REGIONS), "areas": list(AREA_REGIONS), "with_tabs": ["Tab-Bottom", "Tab-Top"], "with_hole": ["Hole"],
                  "dofs": {"1": "x", "2": "y", "3": "z", "4": "tilt about x", "5": "tilt about y", "6": "rotation about z"}},
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
