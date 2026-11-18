"""A run's coupon as data for the connector (ADR-0094 amendment 4). A finished run of an unnotched tension coupon stores the script
that builds it in Abaqus/CAE (`anisotropy_fea.write_cae_script`, the output `abaqus_build`). That script states the whole model at
its head as named literals, numbers, names and tuples of them, before any of its code. This module reads those literals and answers
them as one JSON object, the format `anisotropy-coupon/1`, which the connector on a user's PC checks and builds with code of its own
(`fea/tools/anisotropy_build.py`). So a click on Send to Abaqus moves numbers and names to the PC and no code.

The script is read, never run: it is parsed, the assignments of the names below are taken where their value is a literal, and
everything else in it is ignored. A script that does not state every name is refused, so an answer is whole or there is none.

The standard library only, and no import from this package, so the fea project's tests load this file by its path and set its answer
beside what the build script itself asks of Abaqus (`fea/tests/test_anisotropy_build.py`).
"""

from __future__ import annotations

import ast

FORMAT = "anisotropy-coupon/1"
MARK = "# Built by anisotropy_fea "  # in the first lines of every build script
HEAD_LINES = 4
MAX_SCRIPT_BYTES = 2 * 1024 * 1024
# the script's name for each field of the data; ELEMENT_NAME is the element type as text, which the script also states as Abaqus's own constant
FIELDS = {"UNITS": "units", "MODEL": "model", "JOB": "job", "PART": "part", "INSTANCE": "instance", "DESCRIPTION": "description",
          "WIDTH": "width", "LENGTH": "length", "LINES": "lines", "BANDS": "bands", "ROWS": "rows", "COLUMNS": "columns",
          "ELEMENT_NAME": "element", "MATERIAL": "material", "ELASTIC": "elastic", "FAIL_STRESS": "fail_stress", "LAYUP": "layup",
          "SYMMETRIC": "symmetric", "PLIES": "plies", "INTEGRATION_POINTS": "integration_points", "SECTION_POINTS": "section_points",
          "SETS": "sets", "POINTS": "points", "COUPLINGS": "couplings", "BOUNDARIES": "boundaries", "LOADS": "loads"}


class NotABuildScript(ValueError):
    """The text is not a build script of ours that states the whole coupon."""


def _plain(value):
    """A literal as JSON holds it: a tuple as a list, and nothing but numbers, text, true, false and null inside."""
    if isinstance(value, (tuple, list)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise NotABuildScript(f"a value of the kind {type(value).__name__} is not one a build script states")


def coupon_data(script: str, coupon: str) -> dict:
    """The coupon a build script states, as the data the connector builds from; `coupon` is the run's name for it on the site.
    Raises `NotABuildScript` when the text is not a script our writer wrote, or does not state every field."""
    if len(script) > MAX_SCRIPT_BYTES or not any(line.startswith(MARK) for line in script.splitlines()[:HEAD_LINES]):
        raise NotABuildScript("the text is not a build script Anisotropy wrote")
    try:
        tree = ast.parse(script)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        raise NotABuildScript(f"the build script cannot be read ({type(exc).__name__})") from None
    found: dict = {}
    for node in tree.body:  # the statements of the script itself, not of its functions
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name = node.targets[0].id
        if name not in FIELDS or FIELDS[name] in found:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, SyntaxError, RecursionError, MemoryError):
            raise NotABuildScript(f"the build script's {name} is not a literal") from None
        found[FIELDS[name]] = _plain(value)
    missing = [name for name, field in FIELDS.items() if field not in found]
    if missing:
        raise NotABuildScript(f"the build script does not state {', '.join(missing)}")
    return {"format": FORMAT, "coupon": coupon, **found}
