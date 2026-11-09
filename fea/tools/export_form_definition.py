"""Write the coupon input form's definition as JSON for the website, so the studio's form and the Excel form are one definition (ADR-0051).

    uv run python tools/export_form_definition.py            # writes lib/coupon-form-definition.json at the repository root
    uv run python tools/export_form_definition.py --check    # exits 1 when the file differs from what the package defines today

Every row of the form (key, label, kind, what it means, whether it is required, its default, its words, its bounds, and for a row
with a unit its label and default in each unit system), the sections they sit in, the unit systems a coupon may be stated in with
their labels, the instructions, the Definitions sheet, the tests offered, the criterion words, and the library materials the form
lists with their constants in MPa and mm and, under `library_constants`, in every system (ADR-0061), and under `standards` the test
standards the Standard row offers, each with the tests it covers, the rows it needs, its specimens or classes with their sizes in every
system, and its requirements by clause (ADR-0072). The page converts nothing:
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
from anisotropy_fea.spec import AREA_REGIONS, EDGE_REGIONS, TOW_TEST, test_name
from anisotropy_fea.standards import NONE, PROFILES
from anisotropy_fea.standards.astm_d4018 import FAILURE_AREAS, FAILURE_LOCATIONS, FAILURE_TYPES, KIND as TOW_KIND
from anisotropy_fea.tow_test import ITEM_OF_ROW as TOW_ITEM_OF_ROW, REPORT_UNITS as TOW_UNITS, SHARED as TOW_SHARED, SPECIMEN_FIELDS, TOW_BLOCKS
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


def clean(value: float) -> float:
    """A converted value without the float noise of the conversion: 0.5 in, not 0.49999999999999994."""
    return float(f"{value:.10g}")


def preset_entry(preset) -> dict:
    """A specimen or class of a standard: its rows in every system (the standard's own inch values for a coupon stated in inches when it
    gives them), the rows that are least values, and the laminate thickness it suggests."""
    return {"key": preset.key, "label": preset.label, "clause": preset.clause, "minimum": list(preset.minimum), "note": preset.note,
            "values": {units: {row: clean(v) for row, v in preset.values_in(units).items()} for units in UNIT_SYSTEMS},
            "thickness": {units: None if preset.thickness_si(units) is None else clean(from_si(preset.thickness_si(units), "length", units))
                          for units in UNIT_SYSTEMS}}


def standards() -> dict:
    """The standards the Standard row offers, as the page reads them: by test, with the rows each needs and its sizes; every judgement stays
    in the package (standards.conformance), the page shows the checklist's answer."""
    profiles = []
    for p in PROFILES.values():
        needs = (["specimen"] if p.variant_words else []) + (["strain_device", "strain_length"] if p.requires_strain else [])
        profiles.append({"id": p.id, "designation": p.designation, "title": p.title, "organisation": p.organisation, "catalog_url": p.catalog_url,
                         "edition_note": p.edition_note, "systems": p.systems, "rights": p.rights, "tests": [test_name(k) for k in p.kinds],
                         "aliases": list(p.aliases), "needs": needs, "variant_words": list(p.variant_words),
                         "variants": [preset_entry(v) for v in p.variants], "classes": [preset_entry(c) for c in p.classes],
                         "requirements": [{"id": r.id, "clause": r.clause, "level": r.level, "text": r.text, "rows": list(r.rows)} for r in p.requirements]})
    return {"none": NONE, "profiles": profiles}


def tow() -> dict:
    """The fibre tow test (ADR-0073): its rows in sections, the coupon form's rows it reads too, the rows of one specimen, the words of the
    Fig. 1 failure code, and the units it reports in. Its rows carry the standard's units in their labels; no Units row changes them."""
    return {"test": TOW_TEST, "kind": TOW_KIND, "shared": list(TOW_SHARED),
            "sections": [{"title": title, "fields": [field_entry(f) for f in fields]} for title, fields in TOW_BLOCKS],
            "specimen_fields": [field_entry(f) for f in SPECIMEN_FIELDS], "item_of_row": dict(TOW_ITEM_OF_ROW),
            "failure_code": {"type": dict(FAILURE_TYPES), "area": dict(FAILURE_AREAS), "location": dict(FAILURE_LOCATIONS)},
            "units": dict(TOW_UNITS)}


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
        "standards": standards(),
        "tow": tow(),
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
