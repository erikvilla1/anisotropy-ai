"""A repair's slice as an Abaqus input file and as an Ansys Mechanical APDL input file, and what each program wrote read back
and set beside CalculiX's answer (ADR-0132 amendment 1).

    python -m anisotropy_fea.repair_files ../engine/examples/example-patch-repair.toml --out DIR
    python -m anisotropy_fea.repair_files ../engine/examples/example-patch-repair.toml --abaqus RUN.dat --ansys RUN-ansys.txt

The first form writes `<name>-abaqus.inp` and `<name>-ansys.cdb`. The second solves the slice in CalculiX, reads what Abaqus
printed (its `.dat`) and the table the Ansys file wrote, and prints every number of the answer three ways.

Both files state the model `repair_model` gives CalculiX, node for node and element for element (`SliceModel`): the same
eight-node elements with four integration points, the same materials, supports, width strain and load. They are a second and
a third solver's reading of one model, so they check the solver and the way the model is stated to it, not the model's
assumptions.

- Abaqus: CPE8R, each material `*Elastic, type=ORTHOTROPIC` in an orientation that is the global axes, the width strain as an
  expansion of -1 across the width and a temperature, the load as `*Dload` P2 on the elements of the panel's end. It prints
  the stresses and the strains at every integration point (`*El Print`) and the reaction on the middle. Abaqus prints five
  figures, so its numbers are compared to about four.
- Ansys: PLANE183 in plane strain (KEYOPT(3) = 2), x the load, y the thickness and z the width. Each material is stated by the
  nine engineering constants of its stiffness's orthotropic part (the inverse of the same nine terms the other two files
  hold), the width strain as ALPZ = -1 and a uniform temperature, the load as a pressure on face 2. The file itself writes a
  table of every element's stresses and elastic strains, each the mean of the element's integration points (`ERESX,NO` keeps
  the integration points' values at the corners, and an element table item is the mean of the corners), to fifteen figures.

What is read back goes through the same reading as CalculiX's (`slice_answer`), after the same refusal: a program's stresses
must be the engine's stiffness times its own strains.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import numpy as np

from anisotropy_engine.repair import RepairError, repair_from_dict
from anisotropy_engine.units import UNIT_SYSTEMS

from .abaqus_dat import AbaqusDatError, parse_abaqus_dat
from .repair_model import (
    CUT_FACES, EQUILIBRIUM_TOLERANCE, MATCH_TOLERANCE, MPA, SliceAnswer, SliceModel, SliceModelError, SliceResults, _number, _rows, build_slice_model,
    end_pressures, held_nodes, material_groups, matched_results, run_slice_model, slice_answer,
)
from .repair_shape import MM
from .write_ansys import _block, _comment, _real, ascii_text

PRINTED_TOLERANCE = 1e-3  # for a program that prints five figures: its stresses against the stiffness times its strains, and its forces against the load
ANSYS_COLUMNS = ("SX", "SY", "SZ", "SXY", "EPX", "EPY", "EPZ", "EPXY")  # the Ansys table's columns after the element's number
ANSYS_ITEMS = (("S", "X"), ("S", "Y"), ("S", "Z"), ("S", "XY"), ("EPEL", "X"), ("EPEL", "Y"), ("EPEL", "Z"), ("EPEL", "XY"))


def abaqus_file(model: SliceModel) -> str:
    """The slice as an Abaqus/Standard input file, in mm, N and MPa. Abaqus's 1 is the load's direction, 2 the thickness and 3
    the width, as in CalculiX's deck."""
    mesh, nodes, elements, far = model.mesh, model.nodes_m, model.elements, model.far
    out = ["*Heading", " A stepped patch repair's slice (ADR-0132), written by anisotropy_fea.repair_files. Units: mm, N, MPa.",
           f"** Load {_number(model.load_n_per_m / 1e3)} N/mm of width; the far-field width strain {_number(far.strain_width)} is put on as a temperature.",
           "*Node, nset=NALL"]
    out += [f"{k + 1}, {_number(r / MM)}, {_number(z / MM)}" for k, (r, z) in enumerate(nodes)]
    out += ["** The material axes are the global ones: 1 the load's direction, 2 the thickness, 3 the width.",
            "*Orientation, name=SLICE", "1., 0., 0., 0., 1., 0.", "3, 0."]
    for number, members, inside in material_groups(mesh, model.stiffness):
        c = model.stiffness[members[0]] / MPA  # rows and columns: xx, yy (width), zz (thickness), yz, xz, xy
        out.append(f"** Material {number}: {ascii_text(', '.join(mesh.regions[index].name for index in members))}")
        out.append(f"*Element, type=CPE8R, elset=M{number}")
        out += [", ".join(str(v) for v in [e + 1, *(elements[e] + 1)]) for e in inside]
        out += [f"*Solid Section, elset=M{number}, material=MAT{number}, orientation=SLICE", "1.",
                f"*Material, name=MAT{number}", "*Elastic, type=ORTHOTROPIC",
                # D1111, D1122, D2222, D1133, D2233, D3333, D1212, D1313, then D2323 on the next line
                ", ".join(_number(v) for v in (c[0, 0], c[0, 2], c[2, 2], c[0, 1], c[2, 1], c[1, 1], c[4, 4], c[5, 5])), _number(c[3, 3]),
                "*Expansion, type=ORTHO, zero=0.", "0., 0., -1."]
    middle, bottom = held_nodes(nodes)
    out += ["*Elset, elset=EALL, generate", f"1, {len(elements)}, 1", "*Nset, nset=MIDDLE", *_rows([k + 1 for k in middle]),
            "*Nset, nset=BOTTOM", *_rows([k + 1 for k in bottom]),
            "*Boundary", "MIDDLE, 1, 1, 0.", f"{'NALL' if model.hold == 'everywhere' else 'BOTTOM'}, 2, 2, 0.",
            "*Initial Conditions, type=TEMPERATURE", "NALL, 0.",
            "*Step, name=Load, nlgeom=NO", "*Static", "*Temperature", f"NALL, {_number(far.strain_width)}",
            "** The load: each ply's far-field stress on the panel's end (face 2 of an element is its edge at the larger r).", "*Dload"]
    out += [f"{e + 1}, P2, {_number(pressure / MPA)}" for e, pressure in end_pressures(mesh, far)]
    out += ["** One table holds one variable.", "*El Print, elset=EALL, position=INTEGRATION POINTS, summary=NO", "S",
            "*El Print, elset=EALL, position=INTEGRATION POINTS, summary=NO", "E",
            "*Node Print, nset=MIDDLE, totals=YES, summary=NO", "RF1", "*End Step"]
    return "\n".join(out) + "\n"


def engineering_constants(stiffness_pa: np.ndarray) -> dict[str, float]:
    """The nine engineering constants of a stiffness's orthotropic part, in Ansys's names and the Ansys file's axes (x the
    load, y the thickness, z the width); moduli in Pa. `stiffness_pa` is in the slice's axes, rows and columns xx, yy (the
    width), zz (the thickness), yz, xz, xy. The orthotropic part is the nine terms the CalculiX deck holds; its inverse has
    1/E on the diagonal and -PRij/Ei off it, PRxy being the major ratio (the strain along y for a stress along x)."""
    order = [0, 2, 1]  # the slice's x, thickness, width
    compliance = np.linalg.inv(stiffness_pa[np.ix_(order, order)])
    return {"EX": 1 / compliance[0, 0], "EY": 1 / compliance[1, 1], "EZ": 1 / compliance[2, 2],
            "PRXY": -compliance[1, 0] / compliance[0, 0], "PRYZ": -compliance[2, 1] / compliance[1, 1], "PRXZ": -compliance[2, 0] / compliance[0, 0],
            "GXY": float(stiffness_pa[4, 4]), "GYZ": float(stiffness_pa[3, 3]), "GXZ": float(stiffness_pa[5, 5])}


def ansys_file(model: SliceModel, table: str = "repair-slice-ansys") -> str:
    """The slice as an Ansys Mechanical APDL input file, in mm, N and MPa: read it with /INPUT, or run it in batch. It builds
    the model, solves it and writes `<table>.txt`: one line for each element, its number and then SX, SY, SZ, SXY and the
    elastic strains along x, y, z and xy, each the mean of the element's integration points."""
    if not table or any(sign in table for sign in "',!$%&/\\ "):
        raise SliceModelError(f"The Ansys table's name must be plain, got {table!r}")
    mesh, nodes, elements, far = model.mesh, model.nodes_m, model.elements, model.far
    out: list[str] = []
    out += _comment("A stepped patch repair's slice (ADR-0132), written by anisotropy_fea.repair_files. Ansys Mechanical APDL input: read it with "
                    "/INPUT, or run it in batch. Units: mm, N, MPa. x is the load's direction, y the thickness, z the width.")
    out += _comment(f"Load {_number(model.load_n_per_m / 1e3)} N/mm of width; the far-field width strain {_number(far.strain_width)} is put on as a "
                    "temperature, with an expansion of -1 across the width.")
    out += ["/PREP7", "/TITLE,The slice of a stepped patch repair", "/UNITS,MPA"]
    out += _comment("PLANE183, the eight-node plane element with four integration points, in plane strain (KEYOPT(3) = 2).")
    out += ["ET,1,183", "KEYOPT,1,3,2"]
    out.append(f"NBLOCK,6,SOLID,{len(nodes):10d},{len(nodes):10d}")
    out.append("(3i9,6e21.13e3)")
    out += [f"{index:9d}{0:9d}{0:9d}{_real(r / MM)}{_real(z / MM)}{_real(0.0)}" for index, (r, z) in enumerate(nodes, start=1)]
    out.append("N,R5.3,LOC,       -1,")
    groups = material_groups(mesh, model.stiffness)
    material = np.zeros(len(elements), dtype=int)
    for number, _, inside in groups:
        material[inside] = number
    out += _comment("Elements: material, type, real constant, section, element system, birth, solid model, shape, node count, unused, number, nodes "
                    "(four corners counter-clockwise, then the middle of every edge).")
    out.append(f"EBLOCK,19,SOLID,{len(elements):10d},{len(elements):10d}")
    out.append("(19i10)")
    for index, element in enumerate(elements, start=1):
        out.append("".join(f"{value:10d}" for value in [int(material[index - 1]), 1, 1, 1, 0, 0, 0, 0, 8, 0, index, *(int(n) + 1 for n in element)]))
    out.append("-1")
    middle, bottom = held_nodes(nodes)
    for component, indices in (("N_MIDDLE", middle), ("N_BOTTOM", bottom)):
        out.append(f"CMBLOCK,{component},NODE,{len(indices):10d}")
        out.append("(8i10)")
        out += _block([int(i) + 1 for i in indices])
    for number, members, _ in groups:
        out += _comment(f"Material {number}: {', '.join(mesh.regions[index].name for index in members)}")
        constants = engineering_constants(model.stiffness[members[0]])
        for label, value in constants.items():
            out.append(f"MP,{label},{number},{_number(value if label.startswith('PR') else value / MPA)}")
        out.append(f"MP,ALPZ,{number},-1.")
    out += _comment("The middle is a plane of symmetry; the laminate's bottom face is held flat"
                    + (", and here every node is (the hand calculation's own assumption)." if model.hold == "everywhere" else "."))
    out += ["D,N_MIDDLE,UX,0.", "D,ALL,UY,0." if model.hold == "everywhere" else "D,N_BOTTOM,UY,0."]
    out += _comment("The load: each ply's far-field stress on the panel's end. Face 2 of an element is its edge at the larger r, and a pressure "
                    "pushes into the element.")
    out += [f"SFE,{e + 1},2,PRES,,{_number(pressure / MPA)}" for e, pressure in end_pressures(mesh, far)]
    out.append("FINISH")
    out += _comment("One linear static solution. The temperature is the far-field width strain; ERESX,NO keeps each integration point's results "
                    "at its corner of the element.")
    out += ["/SOLU", "ANTYPE,STATIC", "NLGEOM,OFF", "TREF,0.", f"TUNIF,{_number(far.strain_width)}", "ERESX,NO", "OUTRES,ALL,ALL", "SOLVE", "FINISH"]
    out += _comment("The reaction on the middle, then every element's stresses and elastic strains in the global axes, each the mean of the "
                    f"element's integration points, written to {table}.txt.")
    out += ["/POST1", "SET,LAST", "RSYS,0", "CMSEL,S,N_MIDDLE", "PRRSOL,FX", "ALLSEL,ALL"]
    out += [f"ETABLE,{name},{item},{component}" for name, (item, component) in zip(ANSYS_COLUMNS, ANSYS_ITEMS)]
    out += ["*GET,NE,ELEM,0,COUNT", f"*DIM,RES,ARRAY,NE,{len(ANSYS_COLUMNS)}"]
    out += [f"*VGET,RES(1,{k}),ELEM,1,ETAB,{name}" for k, name in enumerate(ANSYS_COLUMNS, start=1)]
    out += [f"*CFOPEN,'{table}','txt'", "*VWRITE,SEQU," + ",".join(f"RES(1,{k})" for k in range(1, len(ANSYS_COLUMNS) + 1)),
            f"(F10.0,{len(ANSYS_COLUMNS)}E24.15)", "*CFCLOS", "FINISH"]
    return "\n".join(out) + "\n"


def read_abaqus(model: SliceModel, dat_text: str, *, tolerance: float = PRINTED_TOLERANCE) -> SliceResults:
    """The element means of what Abaqus printed for the file `abaqus_file` gives, in SI: the tables of S and of E at the
    integration points of the set EALL. Abaqus prints a shear strain as the engineering one."""
    try:
        dat = parse_abaqus_dat(dat_text)
        stress_table, strain_table = dat.find("element", "EALL", "S11"), dat.find("element", "EALL", "E11")
        printed = []
        for table, columns in ((stress_table, ("S11", "S22", "S33", "S12")), (strain_table, ("E11", "E22", "E33", "E12"))):
            at = [table.column(name) for name in columns]
            labels = np.array([row.label for row in table.rows])
            values = np.array([[row.values[k] for k in at] for row in table.rows])
            printed.append(_element_means(model, labels, values, "Abaqus"))
    except AbaqusDatError as error:
        raise SliceModelError(str(error)) from error
    stress, strain = printed[0] * MPA, printed[1]
    if float(np.max(np.abs(strain[:, 2]))) > 1e-12:
        raise SliceModelError("Abaqus printed a strain across the width: the elements are not in plane strain")
    return matched_results(model, strain[:, [0, 1, 3]], stress[:, [0, 2, 1, 3]], solver=dat.version, tolerance=tolerance, program="Abaqus")


def _element_means(model: SliceModel, labels: np.ndarray, values: np.ndarray, program: str) -> np.ndarray:
    count = len(model.elements)
    order = np.argsort(labels, kind="stable")
    points, extra = divmod(len(labels), count)
    if extra or points < 1 or not np.array_equal(labels[order].reshape(count, points), np.repeat(np.arange(1, count + 1)[:, None], points, axis=1)):
        raise SliceModelError(f"{program} did not print every element of the model the same number of times: the results are not this model's")
    return values[order].reshape(count, points, -1).mean(axis=1)


def read_ansys(model: SliceModel, table_text: str, *, tolerance: float = MATCH_TOLERANCE) -> SliceResults:
    """The table the Ansys file wrote, in SI: one row for each element, its number and the eight columns of ANSYS_COLUMNS.
    Refused when a row is missing, or when the elastic strain across the width is not the far-field width strain."""
    try:
        rows = np.array([[float(word) for word in line.split()] for line in table_text.splitlines() if line.strip()])
    except ValueError as error:
        raise SliceModelError(f"The Ansys table does not read as numbers: {error}") from error
    if rows.ndim != 2 or rows.shape[1] != 1 + len(ANSYS_COLUMNS):
        raise SliceModelError(f"The Ansys table must have {1 + len(ANSYS_COLUMNS)} columns: the element's number, then {', '.join(ANSYS_COLUMNS)}")
    values = _element_means(model, rows[:, 0].astype(int), rows[:, 1:], "Ansys")
    stress, strain = values[:, :4] * MPA, values[:, 4:]
    width = float(np.max(np.abs(strain[:, 2] - model.far.strain_width))) / abs(model.far.strain_width)
    if not width < 1e-9:
        raise SliceModelError(f"Ansys's elastic strain across the width is not the far-field width strain (off by {width:.2e} of it)")
    return matched_results(model, strain[:, [0, 1, 3]], stress[:, [0, 2, 1, 3]], solver="Ansys Mechanical APDL", tolerance=tolerance, program="Ansys")


def compare_answers(ours: SliceAnswer, theirs: SliceAnswer) -> dict:
    """Another program's answer beside CalculiX's, for one model: `rows` holds every reported number as (what, ours, theirs),
    in SI, and `largest` the largest gaps: any element's stress as a fraction of the model's largest stress, any station of a
    bond's curves as a fraction of the largest value on the bondline, and any reported number as a fraction of ours."""
    if theirs.model is not ours.model:
        raise SliceModelError("The two answers are not of one model")
    rows: list[tuple[str, float, float]] = []
    for a, b in zip(ours.boundaries, theirs.boundaries):
        rows.append((f"patch's force at {a.name}, N/m", a.patch, b.patch))
    rows.append(("largest bondline shear stress, Pa", ours.peak_shear.value_pa, theirs.peak_shear.value_pa))
    rows.append(("where, m", ours.peak_shear.r_m, theirs.peak_shear.r_m))
    rows.append(("largest bondline peel stress, Pa", ours.peak_peel.value_pa, theirs.peak_peel.value_pa))
    rows.append(("where, m", ours.peak_peel.r_m, theirs.peak_peel.r_m))
    for a, b in zip(ours.cut_faces, theirs.cut_faces):
        rows.append((f"stress across {a.name}, Pa", a.normal_pa, b.normal_pa))
    if ours.elastic_limit_load is not None:
        rows.append(("load at the adhesive's elastic limit, N/m", ours.elastic_limit_load, theirs.elastic_limit_load))
    checked = [(a, b) for a, b in zip(ours.plies, theirs.plies) if a.ratio is not None]
    for a, b in sorted(checked, key=lambda pair: pair[0].ratio)[:3]:
        rows.append((f"strength ratio of {a.name}", a.ratio, b.ratio))
    scale = float(np.max(np.abs(ours.results.stress)))
    curves = max(float(np.max(np.abs(getattr(a, name) - getattr(b, name)))) for a, b in zip(ours.bond, theirs.bond) for name in ("shear_pa", "peel_pa"))
    on_bond = max(float(np.max(np.abs(getattr(a, name)))) for a in ours.bond for name in ("shear_pa", "peel_pa"))
    same_first = (ours.first_ply is None and theirs.first_ply is None) or (ours.first_ply is not None and theirs.first_ply is not None
                                                                         and ours.first_ply.name == theirs.first_ply.name)
    return {
        "rows": rows,
        "largest": {"element_stress": float(np.max(np.abs(ours.results.stress - theirs.results.stress))) / scale,
                    "bond_curve": curves / on_bond,
                    "reported": max(abs(b - a) / abs(a) for _, a, b in rows if a != 0)},
        "same_places": bool(ours.peak_shear.name == theirs.peak_shear.name and ours.peak_peel.name == theirs.peak_peel.name and same_first),
        "checks": {"equilibrium": theirs.equilibrium_error, "far_field": theirs.far_field_error},
    }


def main(argv: list[str] | None = None) -> int:
    """`python -m anisotropy_fea.repair_files <repair.toml> --out DIR` writes the two files; with `--abaqus FILE.dat` or
    `--ansys FILE.txt` it solves the slice in CalculiX and prints the other program's numbers beside CalculiX's."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m anisotropy_fea.repair_files",
                                     description="A stepped patch repair's slice as an Abaqus and an Ansys input file, and their results read back (ADR-0132).")
    parser.add_argument("repair", type=Path, help="the repair, a TOML file (engine/examples/example-patch-repair.toml)")
    parser.add_argument("--out", type=Path, help="folder for <name>-abaqus.inp and <name>-ansys.cdb")
    parser.add_argument("--name", help="the files' name (the repair file's unless said)")
    parser.add_argument("--abaqus", type=Path, help="the .dat Abaqus wrote for the file, to compare")
    parser.add_argument("--ansys", type=Path, help="the table the Ansys file wrote, to compare")
    parser.add_argument("--size", type=float, help="the longest element along the slice, mm")
    parser.add_argument("--fine", type=float, help="the element length beside every edge, mm")
    parser.add_argument("--cut-faces", default="open", choices=CUT_FACES, help="whether the adhesive on the cut faces carries load (default open)")
    args = parser.parse_args(argv)
    if args.out is None and args.abaqus is None and args.ansys is None:
        parser.error("say --out to write the files, or --abaqus or --ansys to compare a run")
    try:
        case = tomllib.loads(args.repair.read_text(encoding="utf-8"))
        repair, load = repair_from_dict({key: value for key, value in case.items() if key not in ("expected", "solve")})
        if load is None:
            raise SliceModelError("The file states no load ([applied] load), so there is no slice to solve")
        if case.get("units") not in UNIT_SYSTEMS:
            raise SliceModelError(f"units must be one of {', '.join(UNIT_SYSTEMS)}")
        model = build_slice_model(repair, load, cut_faces=args.cut_faces, element_size_m=None if args.size is None else args.size * MM,
                                  fine_m=None if args.fine is None else args.fine * MM)
        name = args.name or args.repair.stem
        if args.out is not None:
            args.out.mkdir(parents=True, exist_ok=True)
            for path, text in ((args.out / f"{name}-abaqus.inp", abaqus_file(model)), (args.out / f"{name}-ansys.cdb", ansys_file(model, f"{name}-ansys"))):
                path.write_text(text, encoding="ascii", newline="\n")
                print(path)
        if args.abaqus is None and args.ansys is None:
            return 0
        runs = [(program, path.read_text(encoding="utf-8", errors="replace"), read, tolerance)
                for program, path, read, tolerance in (("Abaqus", args.abaqus, read_abaqus, PRINTED_TOLERANCE),
                                                       ("Ansys", args.ansys, read_ansys, EQUILIBRIUM_TOLERANCE)) if path is not None]
        ours = slice_answer(model, run_slice_model(model))
        print(f"{case.get('title', args.repair.stem)}: {len(model.elements)} elements, {len(model.nodes_m)} nodes")
        for program, text, read, tolerance in runs:
            theirs = slice_answer(model, read(model, text), equilibrium_tolerance=tolerance)
            found = compare_answers(ours, theirs)
            print(f"\n{program} ({theirs.results.solver}) beside CalculiX ({ours.results.solver}), SI:")
            for what, a, b in found["rows"]:
                print(f"  {what:<58} {a:>14.6g} {b:>14.6g} {(b - a) / a if a else 0.0:>+10.1e}")
            print(f"  largest gap: an element's stress {found['largest']['element_stress']:.1e} of the largest stress; a station of a bond's curves "
                  f"{found['largest']['bond_curve']:.1e} of the largest; a reported number {found['largest']['reported']:.1e}")
            print(f"  the largest stresses and the first ply are {'in the same places' if found['same_places'] else 'NOT in the same places'}; "
                  f"{program}'s forces add up to the load within {found['checks']['equilibrium']:.1e}")
    except (SliceModelError, RepairError, tomllib.TOMLDecodeError, OSError) as error:
        print(f"refused: {(str(error).splitlines() or [type(error).__name__])[0]}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
