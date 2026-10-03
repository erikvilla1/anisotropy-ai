"""Read a course Excel laminate input file into a case.

The layout is the course template on the first sheet: a "Units:" row, a material table
headed "Matl ID" (E1, E2, G12, nu12, Ply Thk, alpha1, alpha2, X, X', Y, Y', S), a load row
headed "Nx" (Nx ... Mxy, DT) or a stress row headed "sigx", and a ply table headed
"Ply No." where ply 1 is the bottom-most ply. The template enters compressive strengths
as negative numbers; cases store them as positive magnitudes. Placeholder text such as
"TBD" is reported as an error, never replaced by a value.
"""

import math
from pathlib import Path

from openpyxl import load_workbook

# The course template's unit cell, and the case unit system that matches it exactly:
# psi, inches, lb/in, in-lb/in, 1/degF and degF.
COURSE_UNITS = {"lbf, in, psi, F": "psi"}
STRENGTH_COLUMNS = {"X": "F1t", "X'": "F1c", "Y": "F2t", "Y'": "F2c", "S": "F6"}
LOAD_COLUMNS = ("Nx", "Ny", "Nxy", "Mx", "My", "Mxy")


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _find_row(rows: list[tuple], label: str) -> int | None:
    """Index of the first row whose column A reads `label`."""
    return next((r for r, row in enumerate(rows) if row and _text(row[0]) == label), None)


def _columns(header: tuple) -> dict[str, int]:
    return {_text(cell): c for c, cell in enumerate(header) if _text(cell)}


def _cell(row: tuple, column: int | None):
    return row[column] if column is not None and column < len(row) else None


def _materials(rows: list[tuple]) -> tuple[dict[str, dict], dict[str, float]]:
    start = _find_row(rows, "Matl ID")
    if start is None:
        raise ValueError("No material table: expected a row whose column A reads 'Matl ID'")
    columns = _columns(rows[start])
    materials, thicknesses = {}, {}
    for row in rows[start + 1:]:
        if not row or not _number(row[0]):
            break
        name = str(int(row[0]))
        elastic = {key: _cell(row, columns.get(key)) for key in ("E1", "E2", "G12", "nu12")}
        if not any(_number(v) for v in elastic.values()):
            continue  # a template placeholder row such as "Can add more materials here"; used only if a ply needs it
        if not all(_number(v) for v in elastic.values()):
            raise ValueError(f"Material {name}: E1, E2, G12 and nu12 must all be numbers, got {elastic}")
        table = dict(elastic)
        alphas = {key: _cell(row, columns.get(key)) for key in ("alpha1", "alpha2")}
        if any(_number(v) for v in alphas.values()):
            if not all(_number(v) for v in alphas.values()):
                raise ValueError(f"Material {name}: give both alpha1 and alpha2 or neither, got {alphas}")
            table.update(alphas)
        strengths = {key: _cell(row, columns.get(key)) for key in STRENGTH_COLUMNS}
        if any(_number(v) for v in strengths.values()):
            if not all(_number(v) for v in strengths.values()):
                raise ValueError(f"Material {name}: give all five strengths X, X', Y, Y', S or none, got {strengths}")
            for key in ("X'", "Y'"):
                if strengths[key] >= 0:
                    raise ValueError(f"Material {name}: {key} must be entered as a negative number "
                                     f"(compression), as the course template states; got {strengths[key]}")
            for key in ("X", "Y", "S"):
                if strengths[key] <= 0:
                    raise ValueError(f"Material {name}: {key} must be positive, got {strengths[key]}")
            table.update({STRENGTH_COLUMNS[key]: abs(value) for key, value in strengths.items()})
        materials[name] = table
        thickness = _cell(row, columns.get("Ply Thk"))
        if _number(thickness):
            thicknesses[name] = thickness
    return materials, thicknesses


def _applied(rows: list[tuple]) -> dict:
    loads_row = _find_row(rows, "Nx")
    stress_row = _find_row(rows, "sigx")
    if loads_row is None and stress_row is None:
        raise ValueError("No loading: expected a row whose column A reads 'Nx' (or 'sigx' for an applied stress)")
    if loads_row is not None:
        columns = _columns(rows[loads_row])
        values = rows[loads_row + 1] if loads_row + 1 < len(rows) else ()
        loads = []
        for name in LOAD_COLUMNS:
            value = _cell(values, columns.get(name))
            if not _number(value):
                raise ValueError(f"Load {name} is {value!r}; enter a number (0 when there is no load)")
            loads.append(value)
        applied = {"loads": loads}
        delta_T = _cell(values, columns.get("DT"))
        if _number(delta_T):
            applied["delta_T"] = delta_T
        elif delta_T is not None:
            raise ValueError(f"DT is {delta_T!r}; enter a number, or leave it empty for no temperature change")
        return applied
    columns = _columns(rows[stress_row])
    values = rows[stress_row + 1] if stress_row + 1 < len(rows) else ()
    stress = [_cell(values, columns.get(name)) for name in ("sigx", "sigy", "sigxy")]
    if not all(_number(v) for v in stress):
        raise ValueError(f"Applied stress sigx, sigy, sigxy is {stress}; enter three numbers")
    return {"stress": stress}


def _plies(rows: list[tuple], materials: dict, thicknesses: dict) -> list[dict]:
    start = _find_row(rows, "Ply No.")
    if start is None:
        raise ValueError("No ply table: expected a row whose column A reads 'Ply No.'")
    columns = _columns(rows[start])
    found = []
    for row in rows[start + 1:]:
        if not row or not _number(row[0]):
            break
        number, angle, material = row[0], _cell(row, columns.get("Angle")), _cell(row, columns.get("Matl ID"))
        if not _number(angle) or not _number(material):
            raise ValueError(f"Ply {number}: Angle and Matl ID must be numbers, got {angle!r} and {material!r}")
        name = str(int(material))
        if name not in materials:
            raise ValueError(f"Ply {number} uses material {name}, which has no numeric properties in the material table")
        ply_thickness = _cell(row, columns.get("Ply Thk"))
        listed = thicknesses.get(name)
        if _number(ply_thickness) and listed is not None and not math.isclose(ply_thickness, listed):
            raise ValueError(f"Ply {number}: Ply Thk {ply_thickness} differs from material {name}'s {listed}")
        thickness = ply_thickness if _number(ply_thickness) else listed
        if thickness is None:
            raise ValueError(f"Ply {number}: no ply thickness in the ply table or the material table")
        found.append((int(number), {"angle": angle, "material": name, "thickness": thickness}))
    numbers = [number for number, _ in found]
    if sorted(numbers) != list(range(1, len(numbers) + 1)):
        repeated = sorted({n for n in numbers if numbers.count(n) > 1})
        raise ValueError(f"Ply numbers must run from 1 (bottom) to {len(numbers)} without repeats; "
                         f"found {sorted(numbers)}" + (f", repeated {repeated}" if repeated else ""))
    return [ply for _, ply in sorted(found, key=lambda item: item[0])]


def read_course_workbook(path: Path) -> dict:
    """The case described by a course Excel input file, with plies bottom first."""
    path = Path(path)
    sheet = load_workbook(path, data_only=True).worksheets[0]
    rows = [tuple(row) for row in sheet.iter_rows(values_only=True)]
    units_row = _find_row(rows, "Units:")
    units_text = _text(rows[units_row][1]) if units_row is not None and len(rows[units_row]) > 1 else ""
    if units_text not in COURSE_UNITS:
        raise ValueError(f"Units cell reads {units_text!r}; this reader knows {list(COURSE_UNITS)}")
    materials, thicknesses = _materials(rows)
    if not materials:
        raise ValueError("The material table has no numeric E1, E2, G12 and nu12. The engine needs a material "
                         "even when a result does not depend on it; add one to the Excel file.")
    title = _text(rows[0][0]) if rows and rows[0] else ""
    return {
        "title": title or path.stem,
        "source": f"Course Excel input file {path.name}",
        "units": COURSE_UNITS[units_text],
        "materials": materials,
        "laminate": {"plies": _plies(rows, materials, thicknesses)},
        "applied": _applied(rows),
    }
