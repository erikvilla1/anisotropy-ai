"""One document per coupon: what was solved, the physics our engine uses, how the part is built in our engine and in
Abaqus/CAE, our results, and how they compare with other solvers (ADR-0041).

From the repository root:

    uv run --project fea python docs/models/coupon.py <coupon>             # one coupon
    uv run --project fea python docs/models/coupon.py --all                 # every coupon model under .local/fea/
    uv run --project fea python docs/models/coupon.py --all --check         # before merging an engine change (ADR-0043)
    options: --root <folder> (the folder holding one folder per coupon; default .local/fea), --no-pdf, --no-theory

The LaTeX is written to <root>/<coupon>/ours/latex/: <coupon>.tex beside the figures/ it uses. What goes to the team is the
package, one folder per delivery, <root>/<coupon>/documents/<today>_<coupon>/ (ADR-0043): the PDF, compiled straight into it,
the audit form, the Abaqus deck to import, the CalculiX deck, the specs and the material record. When
<root>/<coupon>/ours/verification/team-comparison.toml exists, the team's Abaqus model is compared item by item and side by
side (docs/models/team.py): those sections join the document, their files join the package, and the comparison's figures
are written to ours/verification/<coupon>-team-summary.toml for the case page. Chapters:

    1 The problem              the coupon card, the material from our library with its pages, supports and loading
    2 The physics              laminate theory, the finite element kernel and the failure criteria, each equation with the
                               code that computes it (engine/docs/theory.md, fea/docs/theory.md), and the hand check
    3 Building it, our engine  the spec, the CalculiX twin, the generated model
    4 Building it, Abaqus/CAE  what the team built (when they did) and the step-by-step guide (docs/models/rebuild.py)
    5 Results, our engine      the solution, the reaction, strains and ply stresses, first-ply failure
    6 Verification             CalculiX against our engine, and the team's Abaqus side by side
    7 What this shows          the readings, and what is not shown yet
    8 The audit                the rubric's rows, scored where our tools judge (docs/models/audit.py)
    Appendices                 the mapping rule, the record, the files in the package

Every number is computed while the document is built, from the coupon's spec, decks and record (local, ADR-0042); nothing is typed in.
"""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


documents = load_module("anisotropy_models_build", HERE / "build.py")
team = load_module("anisotropy_models_team", HERE / "team.py")
audit = load_module("anisotropy_models_audit", HERE / "audit.py")
manual, rebuild = documents.manual, documents.rebuild
escape, code, inline, number, heading = documents.escape, documents.code, documents.inline, documents.number, documents.heading

from anisotropy_engine.library import library_material  # noqa: E402
from anisotropy_fea import __version__ as fea_version  # noqa: E402
from anisotropy_fea import paths  # noqa: E402
from anisotropy_fea.abaqus_reader import parse_deck  # noqa: E402
from anisotropy_fea.audit import CRITERION, form_tables, gauge_text, load_rubric, our_results, read_form, regressions, score, write_form  # noqa: E402
from anisotropy_fea.case_pages import CasePageError, calculix_record, read_case  # noqa: E402
from anisotropy_fea.compare import load_record, sha256_of  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.membrane import solve_membrane  # noqa: E402
from anisotropy_fea.mesh import KernelError  # noqa: E402
from anisotropy_fea.model import to_si  # noqa: E402
from anisotropy_fea.recovery import deck_f12_star, strength_ratios  # noqa: E402
from anisotropy_fea.report import (comparison_rows, element_centroids, fpf_place, gauge_element, gripped_groups, laminate_check,  # noqa: E402
                                   model_facts, solve_record, summarize)
from anisotropy_fea.spec import TEST_CODES, coupon_card, full_angles, load_spec, spec_material, spec_ply_thickness  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402
from anisotropy_fea.write_abaqus import write_abaqus  # noqa: E402

CHAPTER_STYLE = "\n".join([
    r"\titleformat{\chapter}[display]{\sffamily\huge\bfseries\color{ink}}{\color{accent}\large\MakeUppercase{\chaptertitlename}\ \thechapter}{0.6ex}{}",
    r"\titlespacing*{\chapter}{0pt}{0pt}{2.5ex}",
])


@dataclass(frozen=True)
class Sources:
    """The files one coupon document is built from."""

    coupon: str
    spec: Path  # the team's build, <coupon>.toml
    twin: Path  # the CalculiX twin, the spec the record names
    record: Path  # the CalculiX record of the twin
    manifest: Path | None  # the team comparison's manifest, when the team built the coupon
    documents: Path  # where the package folders go, one per delivery
    team_files: Path  # what the team sent: decks, reports, returned audit forms, decks rebuilt from our guide
    latex: Path  # where the LaTeX and its figures go


def sources(coupon: str, root: Path) -> Sources:
    folder = paths.MODELS / coupon / paths.OURS
    spec, record = folder / f"{coupon}.toml", paths.records_dir(folder) / f"{coupon}-calculix.toml"
    for path in (spec, record):
        if not path.is_file():
            raise SystemExit(f"{coupon}: no {path.relative_to(ROOT).as_posix()}")
    twin = (record.parent / load_record(record)["spec"]).resolve()
    manifest = root / coupon / paths.OURS / paths.VERIFICATION / paths.MANIFEST
    return Sources(coupon, spec, twin, record, manifest if manifest.is_file() else None, root / coupon / paths.DOCUMENTS,
                   root / coupon / paths.TEAM_FILES, root / coupon / paths.OURS / paths.LATEX)


# --------------------------------------------------------------------------------------------- chapter 1, the problem

def statement(spec, card: dict[str, str]) -> str:
    units = spec.units
    unit = units.split("-")[0]
    g, loading = spec.geometry, spec.loading
    tab = f"{from_si(g.tab_length, 'length', units):g} {unit}" if g.tab_length else None
    held = f"each end's {tab} tab" if tab and spec.grips and spec.grips.region == "tabs" else "each end's row of nodes"
    team_model = ("as the team's Abaqus model does" if card.get("Team's model", "not built yet") != "not built yet"
                  else "as the team does in its Abaqus model of the tension coupon")
    grips = ((f"{held} is tied to a reference point by a kinematic coupling, {team_model}" if spec.grips.kind == "coupling"
              else f"{held} is held directly") if spec.grips else "it rests on its supports")
    if loading.control == "displacement":
        value = from_si(abs(loading.value), "length", units)
        load = f"the top end is {'pulled' if loading.value > 0 else 'pushed'} {value:g} {unit} along the coupon while the bottom end is held"
    else:
        load = f"a force of {abs(loading.value):g} N is applied along the coupon at the top end while the bottom end is held"
    return escape(f"The {card['Test']} coupon {card['Coupon']}: {card['Size']}; layup {card['Layup']}; material {card['Material'].split(' (')[0]}. "
                  f"In the model, {grips}, and {load}. The questions our engine answers: what force the coupon carries, the strain and the stress in "
                  f"every ply, and at what share of the loading the first ply fails.")


CONVENTIONS = ("Conventions used throughout: x runs across the width and y along the coupon, which is the load axis; plies are listed from "
               "the bottom face up; a ply's angle is measured counterclockwise from x to its material axis 1 (the fibres of a tape; for a woven "
               "fabric, the yarn direction its material record calls 1), so a 0-degree ply has axis 1 across the load and a 90-degree ply along "
               "it; shear strain is the engineering shear strain; lengths are in {length}, stresses in {stress}, forces in N.")


OWN_CONSTANTS = ("Rights class {rights}: these values are the team's. They are used in this package only and never enter our material "
                 "library, which holds published records only.")


def material_heading(spec) -> str:
    """The material section's heading: where the constants come from."""
    if spec.material.library is not None:
        return "The material, from our library"
    return "The material, as given by the team" if spec.material.source is not None else "The material"


def material_file(spec) -> tuple[str, str] | None:
    """The package's material file and what it holds: the library record, the team's own constants, or none (explicit constants of a check)."""
    if spec.material.library is not None:
        return f"3-material/{spec.material.library}.csv", "the material from our library: every value, its unit, basis and source page, and the source"
    if spec.material.source is not None:
        return (f"3-material/{spec_material(spec).name}.csv", "the team's own constants as given on the coupon input form: every value with its unit, "
                "and the source as the team states it")
    return None


def own_material_rows(material, units: str) -> list[tuple[str, float, str]]:
    """The team's own constants, in the stated units, as (property, value, unit) rows: E1, E2, G12, nu12, the strengths when given, G13, G23."""
    stress_unit = documents.UNIT_LABEL[units]["stress"]
    stress = lambda v: from_si(v, "stress", units)  # noqa: E731
    rows = [("E1", stress(material.E1), stress_unit), ("E2", stress(material.E2), stress_unit), ("G12", stress(material.G12), stress_unit),
            ("nu12", material.nu12, "")]
    if material.strengths is not None:
        rows += [(role, stress(getattr(material.strengths, role)), stress_unit) for role in ("F1t", "F1c", "F2t", "F2c", "F6")]
    return rows + [("G13", stress(material.G13), stress_unit), ("G23", stress(material.G23), stress_unit)]


def material_section(spec, units: str, spec_path: Path) -> str:
    """The material from our library with the page of every value, or the team's own constants with their source; the team
    comparison's version adds the team's column."""
    mat = spec.material
    if mat.library is None and mat.source is None:
        return "The material is given by explicit constants in the spec (listed in Section~\\ref{sec:model}); it is not a library record."
    if mat.library is None:
        material = spec_material(spec)
        rows = [[escape(name), f"{number(value, 6)} {escape(unit)}", "as given by the team"] for name, value, unit in own_material_rows(material, units)]
        return "\n\n".join([
            rf"The team gave this material's constants on the coupon input form, under the name {code(material.name)}; it is not a record of "
            r"our material library. The source, as the team states it:",
            rf"\begin{{quote}}{escape(mat.source)}.\end{{quote}}",
            escape(OWN_CONSTANTS.format(rights=material.rights)),
            team.table(["Property", "Value", "Origin"], rows, r">{\raggedright\arraybackslash}p{2.4cm}>{\raggedright\arraybackslash}p{3.6cm}Y"),
            escape(team.SYMBOLS),
            "No strengths were given, so the engine predicts no first-ply failure." if material.strengths is None else
            "With the strengths given, the engine predicts first-ply failure (Chapter~\\ref{ch:results}).",
        ])
    lib = library_material(mat.library, mat.dataset)
    stress_unit = documents.UNIT_LABEL[units]["stress"]
    rows = []
    for v in lib.values:
        if v.role == "tply":
            continue
        shown = from_si(v.value, "stress", units) if v.unit == "Pa" else v.value
        page = f"{v.page}" + (f" (printed {v.printed_page})" if v.printed_page else "")
        rows.append([escape(v.role), f"{number(shown, 6)} {stress_unit if v.unit == 'Pa' else ''}", escape(page)])
    material = spec_material(spec)
    for name, value in (("G13", material.G13), ("G23", material.G23)):
        rows.append([name, f"{number(from_si(value, 'stress', units), 6)} {stress_unit}", escape(team.stated_in_spec(spec_path, name))])
    return "\n\n".join([
        rf"Our model does not type its material in. The spec, the one file our model is generated from (Chapter~\ref{{ch:engine}}), names a "
        rf"record of our material library, {code(lib.material_id)} "
        rf"(dataset {code(lib.dataset_id)}), and the generator writes its values, with their source and page, into the deck header. The source:",
        rf"\begin{{quote}}{escape(team.source_text(lib))}.\end{{quote}}",
        rf"Rights class {code(lib.rights)}: the values are cited by table and page and the source itself is not reproduced.",
        team.table(["Property", "Value", "Source page"], rows, r">{\raggedright\arraybackslash}p{2.4cm}>{\raggedright\arraybackslash}p{3.6cm}Y"),
        escape("G13 and G23 are not in the library record: our spec states them, with the note the table quotes, and this document gives no "
               "page for them, so their source is UNVERIFIED here."),
        escape(team.SYMBOLS),
        rf"What the record does not give: {escape('; '.join(lib.not_provided) or 'nothing listed')}. "
        + escape(f"The ply thickness, {from_si(spec_ply_thickness(spec), 'length', units):g} {documents.UNIT_LABEL[units]['length']}, is "
                 + ("the library record's." if spec.layup.ply_thickness == "library" else team.stated_in_spec(spec_path, "ply_thickness") + ".")),
    ])


def problem_chapter(spec, card: dict[str, str], c, units: str, figures: Path, spec_path: Path) -> str:
    documents.plot_model_module.plot_model(build_model(spec), figures / "model.png", units)
    grips = spec.grips
    labels = documents.UNIT_LABEL[units]
    return "\n\n".join([
        statement(spec, card),
        escape(CONVENTIONS.format(length=labels["length"], stress=labels["stress"])),
        r"\section{The coupon}\label{sec:coupon}",
        documents.kv_table([(escape(label), escape(value)) for label, value in card.items()]),
        rf"\section{{{material_heading(spec)}}}\label{{sec:material}}",
        team.material_section(c) if c is not None else material_section(spec, units, spec_path),
        r"\section{Supports and loading}",
        escape(f"Grips: {grips.kind} on the {'whole tab regions' if grips.region == 'tabs' else 'end node rows'}. "
               f"Loading: {spec.loading.control}, {from_si(spec.loading.value, 'length' if spec.loading.control == 'displacement' else 'force', units):g} "
               f"{labels['length' if spec.loading.control == 'displacement' else 'force']} at the top grip"
               + (f" ({'a pull' if spec.loading.value > 0 else 'a shortening'})" if spec.loading.control == "displacement" else "") + ". "
               "The analysis is linear and static, in the plane of the laminate (a membrane: no bending, no buckling).")
        + r" Figure~\ref{fig:model} shows the model." if grips else "",
        documents.figure("figures/model.png", "The generated model: element sets, the gripped node sets (every node of each tab, named in "
                         "the legend), the reference points, the probes "
                         "(where values are read; Chapter 6 says which of them the CalculiX record compares), and the loading at the top grip, "
                         "with its sign.", "fig:model", r"\linewidth",
                         r"0.75\textheight"),
    ])


# --------------------------------------------------------------------------------------------- chapter 2, the physics

def physics_chapter(theory: bool, rec_deck, rec_solution, record: dict, rows, units: str, test_code: str, criteria: tuple[str, ...] = ()) -> str:
    out = [r"Our engine solves the coupon in two layers. Laminate theory turns each ply's elastic constants and angle into the laminate's "
           r"stiffness and, once the laminate's strain is known, gives every ply's stress in its own axes. The finite element kernel solves the "
           r"coupon as a whole: it divides it into elements, each carrying the laminate stiffness, enforces the grips and the loading, and finds the "
           r"strain everywhere. The failure criteria then compare every ply's stress with the material's strengths. The text and code below are "
           r"the same sources the engine manual prints, with the functions' real line numbers."]
    if theory:
        out += [r"The engine's equations follow I. M. Daniel and O. Ishai, \emph{Engineering Mechanics of Composite Materials}, 2nd edition "
                r"(Oxford University Press, 2006); an equation number such as Eq. 4.56 is theirs. The kernel's element follows K.-J. Bathe, "
                r"\emph{Finite Element Procedures}, 2nd edition (2014). Compressive strengths are positive magnitudes in the engine. "
                r"The engine's theory writes its examples with the load along $x$; this coupon is loaded along $y$, so an example's $N_x$ is "
                r"this coupon's $N_y$. The code listed here and the files printed later cite our decision records as ADR and a number; those "
                r"records are kept in our repository and say why a choice was made, and this document does not need them. Its Checks list what our tests assert; the tests run in our repository on every change, and this document "
                r"does not show their runs, so here the checks are UNVERIFIED. "
                r"The sections print the engine's whole theory of each part, more than this coupon needs: it is loaded in the plane only, with no "
                r"curvature and no temperature change, and its first-ply failure uses "
                + (escape(" and ".join(CRITERION.get(c, c) for c in criteria)) if criteria else "no criterion") + ".",
                r"\section{From plies to the laminate}", *(engine_theory(n) for n in ("1", "2", "3", "4")),
                r"\section{The finite element kernel}\label{sec:theory}", manual.theory("anisotropy_fea"),
                r"\section{Failure of a ply}", engine_theory("5")]
    else:
        out += [r"\section{The equations}\label{sec:theory}",
                r"Left out of this build (\texttt{--no-theory}); they are in \texttt{engine/docs/theory.md}, \texttt{fea/docs/theory.md} and the engine manual."]
    out += [r"\section{The hand check for this coupon}\label{sec:clt}", documents.clt_section(rec_deck, rec_solution, record, rows, units, test_code, r" (Chapter~\ref{ch:audit})")]
    return "\n\n".join(out)


def engine_theory(number: str) -> str:
    """One numbered section of the engine's theory, labelled sec:engine-<number> at its first heading so the text can point to it."""
    text = manual.theory("anisotropy_engine", only=(number,))
    first, _, rest = text.partition("\n")
    return first + rf"\label{{sec:engine-{number}}}" + "\n" + rest


# --------------------------------------------------------------------------------------------- chapter 3, our engine

def engine_chapter(src: Sources, deck, units: str, committed: Path) -> str:
    diff = [line for line in difflib.unified_diff(src.spec.read_text(encoding="utf-8").splitlines(), src.twin.read_text(encoding="utf-8").splitlines(),
                                                  src.spec.name, src.twin.name, n=0, lineterm="") if not line.startswith("@@")]
    comments = documents.header_comments(committed)
    return "\n\n".join([
        r"The model is not drawn by hand. One file, the spec, states the coupon: its name and card, dimensions, mesh seeds, layup, material "
        r"(a record of our library, or the team's own constants) with its out-of-plane constants, grips, loading, probes and output requests. "
        r"Every key is required and every invalid "
        r"combination is refused by name. The generator builds the model from it and writes the complete deck for each solver; the "
        r"kept decks must equal what it writes today, which a test of our code checks on every change (its runs are not shown here, so in "
        r"this document that is UNVERIFIED). The "
        r"spec and the decks are in the package, in \texttt{2-our-model/}.",
        r"\section{The spec}\label{sec:model}", documents.file_listing(src.spec, caption=f"2-our-model/spec/{src.spec.name}"),
        r"\section{The CalculiX twin}\label{sec:twin}",
        r"CalculiX reports no reaction at a coupled reference point (its node printout of our coupled decks holds none there), so the model "
        r"it runs is a twin: the same spec with the grips as direct "
        r"constraints on the tab nodes. These are the lines that differ:",
        r"\begin{plainfile}" + "\n" + documents.listing_text("\n".join(diff)) + "\n" + r"\end{plainfile}",
        r"\section{The generated model}",
        rf"The deck {code('2-our-model/abaqus/' + committed.name)} (SHA-256 {code(sha256_of(committed)[:16])}\ldots) opens with these header lines. "
        rf"They state the spec's values in SI units (m, Pa), as the generator holds them, and the library's citations in their source's units "
        rf"(GPa, MPa); the deck's own lines are in {escape(units)}, as its last header line says.",
        r"\begin{plainfile}" + "\n" + documents.listing_text("\n".join(comments)) + "\n" + r"\end{plainfile}",
        "Read back by our own deck reader, it holds:",
        documents.kv_table(documents.deck_facts(deck, units)),
    ])


def commands_appendix(src: Sources) -> str:
    """How we produced the package's files, for us: the team does not need it."""
    c = src.coupon
    commands = "\n".join([
        f"uv run python tools/regenerate_decks.py {c} {c}-nodal          # the decks, from the specs",
        f"uv run python tools/new_attempt.py {c}                          # a new attempt folder",
        f"uv run python examples/run_calculix.py ../.local/fea/{c}/ours/{c}-nodal.toml --out <attempt>/run/calculix",
        f"uv run python tools/record_from_dat.py ../.local/fea/{c}/ours/{c}-nodal.toml <attempt>/run/calculix/{c}-nodal-ccx.dat",
        "    --version <ccx -v> --run-by <who> --machine <which> --tolerance <the record's> --floor <the record's>",
        f"    --element-probes <the probes the record holds> --out ../.local/fea/{c}/ours/verification/{c}-calculix.toml",
        f"cd .. && uv run --project fea python docs/models/coupon.py {c}    # this document, from the repository root",
    ])
    return "\n\n".join([r"For us, not needed by the team: run from our repository's \texttt{fea/} folder, these commands make every file of this "
                        r"package again; the record's own lines (Appendix~\ref{app:record}) give the values of its options.",
                        r"\begin{plainfile}" + "\n" + documents.listing_text(commands) + "\n" + r"\end{plainfile}"])


# --------------------------------------------------------------------------------------------- chapter 4, Abaqus/CAE

def abaqus_chapter(src: Sources, spec, deck, solution, units: str, committed: Path, c, figures: Path) -> str:
    material = spec_material(spec)
    transverse = documents.transverse_text(spec.material.transverse, units)
    ccx = paths.deck_path(src.twin, "ccx")
    compared = paths.deck_path(src.twin, "abaqus")
    g = spec.geometry
    hole = (g.width / 2, g.length / 2, g.hole_diameter) if g.hole_diameter else None  # the spec's hole is central
    helpers = rebuild.Helpers(escape=escape, code=code, inline=inline, number=number, heading=heading, kv_table=documents.kv_table,
                              long_table=documents.long_table, listing_text=documents.listing_text, tools=("Abaqus/CAE",))
    context = rebuild.Context(facts=model_facts(deck, solution), deck=deck, units=units, kernel_deck=committed, reference_deck=ccx,
                              kernel_sha256=sha256_of(committed), reference_sha256=sha256_of(ccx), solver_name="calculix", spec_path=src.spec,
                              spec_material_lines=material.citation_lines, spec_material_source=f"{material.source}; rights class {material.rights}",
                              spec_transverse=transverse, record_title=spec.title, report_date=date.today().isoformat(), hole=hole,
                              compared_deck=compared if compared.is_file() else None,
                              compared_sha256=sha256_of(compared) if compared.is_file() else None)
    out = []
    if c is not None:
        out += [rf"The team built this coupon in Abaqus/CAE ({code(c.team_deck_path.name)}). The first section shows that our deck is the same "
                r"model, item by item; the second rebuilds it step by step.",
                r"\section{What the team built}\label{sec:models}", team.models_section(c, figures)]
    else:
        out.append(rf"The team has not built this coupon yet. The steps below build the model of our deck {code('2-our-model/abaqus/' + committed.name)}, "
                   r"which Abaqus/CAE can also import directly (File, Import, Model; this click path is not checked by us).")
    out += [r"\section{Step by step in Abaqus/CAE}\label{sec:rebuild}", rebuild.render(context, helpers)]
    return "\n\n".join(out)


# --------------------------------------------------------------------------------------------- chapter 5, our results

def results_chapter(spec, deck, solution, units: str, figures: Path) -> tuple[str, dict]:
    labels = documents.UNIT_LABEL[units]
    documents.plot_deck_module.plot_solution(deck, solution, units, figures / "solution.png", title=f"Our engine's solution, units {units}")
    out = [r"Our engine solved the model of Section~\ref{sec:model} while this document was built. Figure~\ref{fig:solution} shows the deformed "
           r"mesh, the three membrane strains, the axial section force and the maximum-stress failure index of every element.",
           documents.figure("figures/solution.png", r"Our engine's solution: the mesh with its deformed outline and the reactions at the "
                            r"reference points, the strains along the coupon ($\varepsilon_y$), across it ($\varepsilon_x$) and in shear "
                            r"($\gamma_{xy}$), the axial section force $N_y$, and the maximum-stress failure index $1/R$ with the first ply to fail "
                            r"by maximum stress marked x. The field panels show the free length, where the strain is: the gripped tabs move rigidly and carry none. A "
                            r"signed field is drawn red above zero and blue below; a field of one sign runs from white at zero.", "fig:solution",
                            r"\linewidth", r"0.55\textheight")]
    summary: dict = {}
    try:
        check = laminate_check(deck, solution)
    except KernelError as exc:
        out.append("No summary at a gauge element for this model: " + escape(str(exc)) + ".")
        check = None
    if check is not None:
        summary["reaction"] = from_si(check.kernel_reaction_N, "force", units)
        sense = "tension" if summary["reaction"] > 0 else "compression"
        out += [r"\section{The reaction}",
                rf"The top grip carries {number(abs(summary['reaction']), 6)} {escape(labels['force'])} in {sense} ($R_y = {documents.mnumber(summary['reaction'], 6)}$ "
                rf"{escape(labels['force'])}); the bottom grip carries the same force the other way. It is the coupon's force at the applied loading."]
        gauge = check.gauge
        state = [rf"{documents.MATH[name]} & -- & {number(float(check.kernel_strain[i]), 5)} \\" for i, name in enumerate(("eps_x", "eps_y", "gamma_xy"))]
        state += [rf"{documents.MATH[name]} & {escape(labels['force_per_length'])} & "
                  rf"{number(from_si(float(check.kernel_section_force[i]), 'force_per_length', units), 6)} \\" for i, name in enumerate(("N_x", "N_y", "N_xy"))]
        out += [rf"\section{{The state at our element {escape(gauge.name.rsplit('.', 1)[-1])}}}",
                escape(f"Our element {gauge.name} is {gauge_text(gauge, units)}. Its membrane strains and section forces:"),
                documents.long_table(["Quantity", "Unit", "Our engine"], state, r"Ylr")]
        angles = full_angles(spec)
        ply_rows = [rf"{k + 1} & {angles[k]:g} & " + " & ".join(number(from_si(float(check.kernel_ply_stress_12[k, i]), 'stress', units), 5) for i in range(3)) + r" \\"
                    for k in range(len(angles))]
        out += [rf"\section{{Every ply at our element {escape(gauge.name.rsplit('.', 1)[-1])}}}",
                rf"Stress in each ply's own axes, {escape(labels['stress'])}, bottom ply first:",
                documents.long_table(["Ply", "Angle (deg)", rf"$\sigma_1$ ({escape(labels['stress'])})", rf"$\sigma_2$ ({escape(labels['stress'])})",
                                      rf"$\tau_{{12}}$ ({escape(labels['stress'])})"], ply_rows, r"rrrrr")]
    criteria = spec.output.fpf_criteria
    if criteria and any(m.fail_stress for m in deck.materials.values()):
        applied = from_si(spec.loading.value, "length" if spec.loading.control == "displacement" else "force", units)  # signed: a shortening is negative
        unit = labels["length" if spec.loading.control == "displacement" else "force"]
        angles = full_angles(spec)
        rows, found, places, notes, at_grip = [], [], {}, [], False
        for criterion in criteria:
            field = strength_ratios(solution, criterion, deck_f12_star(deck))
            found.append((criterion, field.factor, field.ply, angles[field.ply - 1]))
            index = solution.mesh.element_keys.index(field.element)
            x, y = (from_si(float(v), "length", units) for v in solution.mesh.xy[solution.mesh.connectivity[index, :4]].mean(axis=0))
            name = CRITERION.get(criterion, criterion)
            place, grip, tied = fpf_place(deck, solution, field, units)
            places[criterion] = (place, tied)
            at_grip = at_grip or grip
            notes.append(f"By {name}: element {field.element[1]}, {place}" + (f"; plies {', '.join(map(str, tied))} tie there, and the bottom-most is "
                                                                               "named" if len(tied) > 1 else ""))
            ply_cell = f"{field.ply} ({angles[field.ply - 1]:g}°)" + (f"; {', '.join(map(str, tied))} tie" if len(tied) > 1 else "")
            rows.append(rf"{escape(name[:1].upper() + name[1:])} & {number(field.factor, 4)} & {number(field.factor * applied, 4)} {escape(unit)} & "
                        rf"{ply_cell} & {escape(str(field.element[1]))} ({x:.4g}, {y:.4g}), {escape(place)} & {escape(field.governing_mode)} \\")
        found.sort(key=lambda f: f[1])  # the earliest first: the cover and row C7 lead with it
        summary["fpf"], summary["fpf_others"], summary["fpf_places"], summary["fpf_notes"] = found[0], tuple(found[1:]), places, tuple(notes)
        out += [r"\needspace{16\baselineskip}" + r"\section{First-ply failure}",  # the section with its table
                rf"With the strengths {'from our library' if spec.material.library else 'the team gave'} the engine finds the first ply to fail. "
                r"The analysis is linear, so the factor scales the applied "
                r"loading: below 1, the first ply fails before the loading of the model is reached, and the stresses above are those of a linear model "
                r"past that point. No other solver has checked first-ply failure: CalculiX prints no failure index. Plies that reach a "
                r"criterion together tie (in a membrane model plies at the same angle always do, and plies whose stresses differ only in sign "
                r"can); the table names the bottom-most and lists the others. The mode "
                r"``interactive'' means the criterion combines the stress components, so no single one governs."
                + (r" An element at the edge of a gripped tab sits where the rigid tab meets the coupon, where the stress is not expected to "
                   r"settle as the mesh is refined (UNVERIFIED for this coupon): read its factor as first damage at the grip, not as a converged "
                   r"number (Chapter~\ref{ch:reading})."
                   if at_grip else ""),
                documents.long_table(["Criterion", "Factor", "Loading at failure", "Ply (angle)", f"Element (x, y in {escape(labels['length'])}), where", "Mode"],
                                     rows, r">{\raggedright\arraybackslash}p{2.1cm}rr>{\raggedright\arraybackslash}p{2cm}Y>{\raggedright\arraybackslash}p{1.9cm}")]
    return "\n\n".join(out), summary


# --------------------------------------------------------------------------------------------- chapter 6, verification

def verification_chapter(src: Sources, record: dict, rows, problems, summaries, units: str, map_drawn: bool, full_tables: bool, c, figures: Path,
                         coupled_reaction: float | None = None) -> str:
    solver = record["solver"]
    twin = next((r.kernel for r in rows if r.group == "rf" and r.name == "Grip-Top" and r.component == 1), None)
    same = ""
    if coupled_reaction is not None and twin is not None:
        unit = documents.UNIT_LABEL[units]["force"]
        same = (f" Our engine gives the coupled model of Chapter 5 and the twin the same reaction, {coupled_reaction:.6g} {unit}."
                if abs(coupled_reaction - twin) <= 1e-6 * abs(twin) else
                f" Our engine gives the coupled model of Chapter 5 a reaction of {coupled_reaction:.6g} {unit} and the twin {twin:.6g} {unit}.")
    missing = unrecorded_probes(src, rows, units)
    out = [r"Verification asks whether another solver gives the same answer on the same model. It is not validation: that needs a test of a real "
           r"coupon, and none exists yet for this one.",
           rf"\section{{CalculiX, an independent solver}}\label{{sec:summary}}",
           rf"CalculiX {escape(str(solver['version']))} is an open-source finite element program with its own element ({escape(solver['element_type'])}). "
           r"It ran the CalculiX twin of Section~\ref{sec:twin}; our kernel ran the same twin written as an Abaqus deck, "
           rf"{code(Path(record['deck_kernel']).name)}, and every number of the CalculiX record was compared. Both decks are in the package, in "
           rf"\texttt{{2-our-model/calculix/}}. The record holds values at {escape(record_points(rows, probe_names(src)))} only"
           + (escape(f"; the spec's {' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} not compared") if missing else "")
           + r". Elsewhere Chapter~\ref{ch:results} is our engine's alone." + escape(same) + r" The record and the solver's conventions file are kept with us; this "
           r"chapter and Appendix~\ref{app:record} print them.",
           documents.summary_section(record, rows, problems, summaries, units, METHOD),
           r"To see it yourself in PrePoMax 2.6: File, Import the CalculiX deck from the package (\texttt{2-our-model/calculix/}), run it, then File, "
           r"Open results (.frd).",
           r"\section{CalculiX: the solver and its deck}\label{sec:reference}", documents.reference_section(record, src.record, where=package_name),
           r"\section{CalculiX: every compared number}\label{sec:comparison}", documents.comparison_section(rows, summaries, units, map_drawn, full_tables, METHOD)]
    if c is not None:
        out += [r"\section{The team's Abaqus model, side by side}\label{sec:results}", team.results_section(c, figures)]
    return "\n\n".join(out)


METHOD = r"Appendix~\ref{sec:method}"  # where the coupon document explains the comparison rule


def package_name(path: Path) -> str:
    """How the coupon document names a file: by its copy in the package, or by its name when it is kept with us."""
    return f"2-our-model/calculix/{path.name}" if path.suffix == ".inp" else path.name


def probe_names(src: Sources) -> dict[str, str]:
    """The twin's probes: our node or element name ("CFRP-Coupon-1.446") -> probe name ("centre"), read from its Abaqus-format deck."""
    deck = parse_deck(paths.deck_path(src.twin, "abaqus").read_text(encoding="utf-8"), source_path="twin.inp")
    return {f"{keys[0][0]}.{keys[0][1]}": name[len("Probe-"):] for sets in (deck.nsets, deck.elsets) for name, keys in sets.items()
            if name.startswith("Probe-") and len(keys) == 1}


def unrecorded_probes(src: Sources, rows, units: str) -> list[str]:
    """The twin's probes the CalculiX record holds no values at, in words ("probe near_grip, our element 165")."""
    held = {r.name for r in rows if r.group in ("u", "strain")}
    return [f"probe {probe} (our {'element' if probe in load_spec(src.twin).probes.elements else 'node'} {name.rsplit('.', 1)[-1]})"
            for name, probe in probe_names(src).items() if name not in held]


def demoted(text: str) -> str:
    """A reading's own headings one level down, under the subsection that holds it."""
    return text.replace(r"\subsubsection{", r"\paragraph{").replace(r"\subsection{", r"\subsubsection{")


def reading_chapter(src: Sources, card: dict[str, str], c) -> str:
    reading, _ = documents.reading_section(src.record, title="Our reading of the CalculiX comparison")
    out = [r"\section{Reading}\label{sec:reading}", r"\subsection{The CalculiX comparison}", demoted(reading)]
    if c is not None:
        out += [r"\subsection{The team comparison}", demoted(team.reading_section(c))]
    out += [r"\section{What is not shown yet}\label{sec:open}",
            r"\begin{itemize}",
            r"\item " + escape(f"Test data: {card['Test data']}. Until a real coupon is tested, the results are verified against another solver, not validated."),
            r"\item " + escape(f"Standard: {card['Standard']}. Size from: {card['Size from']}."),
            r"\item The kernel is a membrane model: no bending, no buckling, no through-thickness stress (Section~\ref{sec:theory}).",
            r"\end{itemize}"]
    if c is not None:
        out += [r"From the team's side:", team.open_section(c)]
    return "\n\n".join(out)


def files_appendix(src: Sources, spec, c, package: Path) -> str:
    if c is not None:
        return team.files_section(c)
    rows = [[code(path), escape(what)] for path, what in package_contents(src, spec, package)]
    return "\n\n".join([rf"Everything is in the package folder {code(package.name)}, which goes to the team as it is. It holds no CalculiX results: "
                        r"run our decks to get them.",
                        team.table(["File", "What it is and how to open it"], rows, r">{\raggedright\arraybackslash}p{6.4cm}Y", r"\footnotesize")])


# --------------------------------------------------------------------------------------------- the title page

def record_points(rows, probes: dict[str, str] | None = None) -> str:
    """Where the CalculiX record has values, in words: the grips, then each node and element by our number and its probe's name."""
    probes = probes or {}
    def labels(group: str, word: str) -> str:
        names = sorted({r.name for r in rows if r.group == group}, key=lambda n: (len(n), n))
        return ", ".join(f"our {word} {n.rsplit('.', 1)[-1]}" + (f" ({probes[n]} probe)" if n in probes else "") for n in names)
    return ", ".join(p for p in ("the grips" if any(r.group == "rf" for r in rows) else "", labels("u", "node"), labels("strain", "element")) if p)


def title_page(card: dict[str, str], record: dict, rows, summary: dict, c, units: str, scored, rubric_version: str,
               probes: dict[str, str] | None = None) -> str:
    solver = record["solver"]
    reaction = next((r for r in rows if r.group == "rf" and r.name == "Grip-Top" and r.component == 1), None)
    labels = documents.UNIT_LABEL[units]
    verdict = []
    if "reaction" in summary:
        sense = "tension" if summary["reaction"] > 0 else "compression"
        text = rf"\textbf{{Our engine.}} The coupon carries {number(abs(summary['reaction']), 6)} {escape(labels['force'])} in {sense}"
        if "fpf" in summary:
            criterion, factor, ply, angle = summary["fpf"]  # the earliest of the criteria
            places = summary.get("fpf_places", {})
            where = lambda c2: escape(places[c2][0]) if c2 in places else ""  # noqa: E731
            tied = [p for p in places.get(criterion, ("", []))[1] if p != ply]
            others = "".join(rf" By {escape(CRITERION.get(c2, c2))} it fails at {number(f2, 3)}, {where(c2)}." for c2, f2, _, _ in summary.get("fpf_others", ()))
            text += (rf"; the first ply to fail is ply {ply} ({angle:g}°" + (f", tied with plies {', '.join(map(str, tied))}" if tied else "")
                     + rf") by {escape(CRITERION.get(criterion, criterion))}, at {number(factor, 3)} of the applied loading, {where(criterion)}"
                     + (", where it is not expected to settle as the mesh is refined (UNVERIFIED for this coupon; Chapter 7)"
                        if places.get(criterion, ("", []))[0] == "at the edge of a gripped tab" else "")
                     + (r", so the loading of this model is past first-ply failure" if factor < 1 else "") + "." + others
                     + r" No other solver has checked first-ply failure")
        verdict.append(text + ".")
    agreeing = sum(r.agrees for r in rows)
    expected = record["expected"]
    verdict.append(rf"\textbf{{Verified against CalculiX}} {escape(str(solver['version']))} ({escape(solver['element_type'])}) at "
                   rf"{escape(record_points(rows, probes))}, where our record of its run has values: {agreeing} of {len(rows)} compared values agree, each within "
                   rf"{number(100 * expected['tolerance'], 3)}\% of the larger of its CalculiX value and {number(100 * expected.get('floor', 0.0), 3)}\% "
                   r"of its group's largest value (Chapter~\ref{ch:verification})"
                   + (rf"; our engine's reaction is {abs(100 * (abs(reaction.kernel) - abs(reaction.reference)) / abs(reaction.reference)):.3g}\% "
                      rf"{'larger' if abs(reaction.kernel) >= abs(reaction.reference) else 'smaller'} than CalculiX's" if reaction else "") + ".")
    if c is not None:
        verdict.append(team.verdict(c))
    judged = [s for s in scored if s.result is not None]
    failed = [s.item.id for s in judged if s.result == "Fail"]
    counts = {r: sum(s.result == r for s in judged) for r in ("Pass", "Fail", "N/A", "Not checked")}
    verdict.append(rf"\textbf{{Audit}} (rubric {escape(rubric_version)}, Chapter~\ref{{ch:audit}}): of its {len(scored)} rows for this test, our tools "
                   rf"judge {len(judged)}: {counts['Pass']} pass, {counts['Fail']} fail" + (f" ({escape(', '.join(failed))})" if failed else "")
                   + rf", {counts['N/A']} do not apply and {counts['Not checked']} are not checked yet; the auditor judges the other {len(scored) - len(judged)}.")
    verdict.append(r"\textbf{Not validated.} " + escape(f"{card['Test data'][:1].upper()}{card['Test data'][1:]}."))
    facts = [(escape(label), escape(value)) for label, value in card.items() if label not in ("Coupon", "Test")]
    return "\n".join([
        r"\begin{titlepage}", r"\sffamily",
        r"{\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} COUPON REPORT}\par", r"\vspace*{1.6cm}",
        rf"{{\fontsize{{26}}{{32}}\selectfont\bfseries\color{{ink}} {escape(card['Coupon'])}}}\par", r"\vspace{0.3cm}",
        rf"{{\Large\bfseries\color{{ink}} {escape(card['Test'].capitalize())} coupon}}\par", r"\vspace{0.4cm}",
        r"{\large\color{muted} What was solved, the physics our engine uses, how the part is built in our engine and in \mbox{Abaqus/CAE}, "
        r"our results, and how they compare with other solvers}\par", r"\vspace{1cm}",
        r"{\small\begin{tabular}{@{}p{2.8cm}p{\dimexpr\linewidth-3.3cm}@{}}", *[rf"{label} & {value} \\[0.3ex]" for label, value in facts], r"\end{tabular}}\par",
        r"\vfill", r"\verdict{\raggedright " + " ".join(verdict) + r"}\par", r"\vspace{0.6cm}",  # each its own paragraph: no space inside a line
        rf"{{\small\raggedright\color{{muted}} Built {date.today().isoformat()} by \texttt{{docs/models/coupon.py}} (anisotropy-fea {fea_version}, commit "
        rf"{escape(documents.git_commit())}). Every number is computed while the document is built, from the coupon's spec (the one file our "
        r"model is generated from, Chapter 3), its decks, our record of the CalculiX run" + (" and, for the team's values, their exports"
                                                                                            if c is not None else "") + r", except in "
        r"the readings of Chapter 7, which are ours, "
        r"written by hand, and say where their numbers come from.\par}",
        r"\end{titlepage}",
    ])


# --------------------------------------------------------------------------------------------- the package

def package_contents(src: Sources, spec, package: Path) -> list[tuple[str, str]]:
    """The package of a coupon the team has not built, in the same numbered folders as one with a team model (ADR-0043 amendment 2),
    without 1-team-model/."""
    c = src.coupon
    out = [("README.txt", "this list, as plain text"), (f"{c}.pdf", "the coupon document"),
           (f"{package.name}-audit.xlsx", "the audit form: our tools' results locked; the auditor's results, observations and verdict to fill in"),
           (f"2-our-model/abaqus/{c}-abaqus.inp", "our deck, for Abaqus: File, Import, Model (this click path is not checked by us), or run it as a job"),
           (f"2-our-model/calculix/{paths.deck_path(src.twin, 'ccx').name}", "the CalculiX twin, with the grips as direct constraints. PrePoMax: File, "
                                                                            "Import, then run it"),
           (f"2-our-model/calculix/{paths.deck_path(src.twin, 'abaqus').name}", "the same twin in Abaqus format: what our engine solved for the "
                                                                               "comparison with CalculiX (Chapter 6); not the deck to build from"),
           (f"2-our-model/spec/{src.spec.name}", "the spec our generator builds the Abaqus deck from"),
           (f"2-our-model/spec/{src.twin.name}", "the spec of the CalculiX twin")]
    if material_file(spec) is not None:
        out.append(material_file(spec))
    out.append(("4-results/ours-all-plies.csv", "our S11, S22 and S12 in each ply's material axes, and Mises, for every ply of every element"))
    return out


def fill(folder: Path, src: Sources, spec, text: str, card: dict[str, str], c, deck, solution) -> None:
    """Every file of the package except the PDF, compiled into it afterwards, and the audit form."""
    if c is not None:
        c.attempt = accepted_attempt(src)
        team.fill_share(c, folder)  # the team's deck, our model, the material, the side-by-side files and the README
        return
    lib = library_material(spec.material.library, spec.material.dataset) if spec.material.library else None
    for sub in ("2-our-model/abaqus", "2-our-model/calculix", "2-our-model/spec", "3-material", "4-results"):
        (folder / sub).mkdir(parents=True)
    (folder / "2-our-model/abaqus" / f"{src.coupon}-abaqus.inp").write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(paths.deck_path(src.twin, "ccx"), folder / "2-our-model/calculix")
    shutil.copy2(paths.deck_path(src.twin, "abaqus"), folder / "2-our-model/calculix")
    shutil.copy2(src.spec, folder / "2-our-model/spec")
    shutil.copy2(src.twin, folder / "2-our-model/spec")
    if material_file(spec) is not None:
        team.write_material_csv(folder / material_file(spec)[0], lib, spec_material(spec), spec.units)
    team.write_all_plies(folder / "4-results" / "ours-all-plies.csv", solution, deck, spec.units)
    contents = package_contents(src, spec, folder)
    width = max(len(path) for path, _ in contents)
    lines = [team.README_MARK, f"{card['Coupon']}, {card['Test']}: our model and its document", "",
             *[f"{label + ':':14} {value}" for label, value in card.items()], "",
             f"Attempt:       {accepted_attempt(src) or 'none named'} (our attempt this package delivers)",
             f"Built {date.today().isoformat()} by docs/models/coupon.py (anisotropy-fea {fea_version}, commit {documents.git_commit()}).",
             "Start with the PDF. Numbers in the files are in mm, MPa and N.",
             "There is no 1-team-model folder: the team has not built this coupon yet.", "",
             *[f"{path.ljust(width)}  {what}" for path, what in contents]]
    (folder / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------------------------- the document

def build_document(src: Sources, pdf: bool, theory: bool, full_tables: bool = False, write_summary: bool = True) -> tuple[Path, Path]:
    """The coupon document (its PDF when Tectonic is installed and `pdf` is set, else the LaTeX) and the package folder; with
    `write_summary`, the team comparison's figures for the case page too (beside the model, so off for a scratch build)."""
    spec = load_spec(src.spec)
    card = dict(coupon_card(spec))
    if not card:
        raise SystemExit(f"{documents.rel(src.spec)} has no [coupon] table: a coupon document names its coupon (ADR-0038)")
    units = spec.units
    text = write_abaqus(build_model(spec))
    committed = paths.deck_path(src.spec, "abaqus")
    if committed.is_file() and committed.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
        raise SystemExit(f"{documents.rel(committed)} is not what the generator writes from {src.spec.name} today; run fea/tools/regenerate_decks.py first")
    deck_file = committed if committed.is_file() else src.latex / f"{src.spec.stem}-abaqus.inp"
    deck = to_si(parse_deck(text, source_path=deck_file.name), units)
    solution = solve_membrane(deck)
    record = load_record(src.record)
    rows, problems = comparison_rows(record)
    summaries = summarize(rows)
    rec_deck, rec_solution = solve_record(record)
    c = team.Comparison(src.manifest) if src.manifest is not None else None
    if c is not None and c.spec_path != src.spec.resolve():
        raise SystemExit(f"{documents.rel(src.manifest)}: ours.spec must be the coupon's spec {documents.rel(src.spec)}")

    out_dir = src.latex  # the LaTeX and its figures; what goes to the team is the package folder in documents/ (ADR-0043)
    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    if not committed.is_file():
        deck_file.write_text(text, encoding="utf-8", newline="\n")  # a spec without a committed deck (a fixture): the guide reads this copy
        committed = deck_file
    package = team.package_folder(src.documents, src.coupon)
    if c is not None:
        c.package = package
    documents.difference_figure(rows, figures / "differences.png")
    map_drawn = documents.element_map(rows, summaries, element_centroids(rec_solution, units), rec_solution, units, figures / "element-map.png")
    results, summary = results_chapter(spec, deck, solution, units, figures)
    abaqus = abaqus_chapter(src, spec, deck, solution, units, committed, c, figures)

    # the audit (ADR-0043): our tools score the rubric; the chapter and the form show the same rows
    rubric = load_rubric()
    attempt = accepted_attempt(src)
    b1 = next(item for item in rubric.items if item.id == "B1").tolerance.length_m  # the rebuilt deck is held to the model match's tolerance
    rebuilt = audit.compare_rebuilt(audit.rebuilt_deck(src.team_files), deck, units, b1)
    commit = documents.git_commit()
    lib = (f"{spec.material.library}, dataset {spec.material.dataset}" if spec.material.library
           else spec_material(spec).source if spec.material.source else None)  # the audit's B6 row states it
    fpf = summary.get("fpf")  # criterion, factor of the applied loading, ply, angle
    evidence = audit.gather(test_code=TEST_CODES[spec.kind][0], units=units, card=coupon_card(spec), deck=deck, solution=solution, material=lib,
                            guide=audit.guide_counts(abaqus, rebuild.tag), c=c, fpf=fpf, rebuilt=rebuilt, fpf_others=summary.get("fpf_others", ()),
                            fpf_notes=summary.get("fpf_notes", ()))
    scored = score(rubric, evidence)
    audited = audit.audited(card=card, package=package.name, attempt=attempt)
    compared = audit.files_compared(c=c, our_deck=f"2-our-model/abaqus/{c.spec_path.stem if c is not None else src.coupon}-abaqus.inp",
                                    spec=f"2-our-model/spec/{src.spec.name}",
                                    physics=tuple((s.item.check, "the auditor judges" if s.result is None else "not built yet" if s.result == "Not checked"
                                                   else "our tools judge") for s in scored if s.item.section == "D"))
    build_record = audit.build_record(team_deck=c.team_deck_path.name if c is not None else None, team_sha256=evidence.team_deck_sha256,
                                      fea_version=fea_version, commit=commit, run_by=operator(), built=date.today().isoformat())
    form = f"{package.name}-audit.xlsx"

    headline = f"{card['Coupon']}, {card['Test']}"
    parts = [
        r"\documentclass[11pt,letterpaper,oneside]{report}", documents.PREAMBLE, CHAPTER_STYLE,
        rf"\hypersetup{{pdftitle={{{escape(headline)}: coupon report}}}}",
        r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyhead[L]{{\sffamily\footnotesize\color{{muted}}Anisotropy AI \textperiodcentered{{}} Coupon report \textperiodcentered{{}} {escape(headline)}}}",
        r"\fancyhead[R]{\sffamily\footnotesize\color{muted}\thepage}",
        r"\fancyfoot[C]{\sffamily\scriptsize\color{muted}Compared with CalculiX at the probes of Chapter 6; not validated against a coupon test.}",
        r"\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\sffamily\scriptsize\color{muted}\thepage}\renewcommand{\headrulewidth}{0pt}}",
        r"\begin{document}",
        title_page(card, record, rows, summary, c, units, scored, rubric.version, probe_names(src)),
        r"\tableofcontents",
        r"\chapter{The problem}\label{ch:problem}", problem_chapter(spec, card, c, units, figures, src.spec),
        r"\chapter{The physics: how our engine solves it}\label{ch:physics}",
        physics_chapter(theory, rec_deck, rec_solution, record, rows, units, TEST_CODES[spec.kind][0], tuple(spec.output.fpf_criteria)),
        r"\chapter{Building the part in our engine}\label{ch:engine}", engine_chapter(src, deck, units, committed),
        r"\chapter{Building the part in Abaqus/CAE}\label{ch:abaqus}", abaqus,
        r"\chapter{Results from our engine}\label{ch:results}", results,
        r"\chapter{Verification against other solvers}\label{ch:verification}",
        verification_chapter(src, record, rows, problems, summaries, units, map_drawn, full_tables, c, figures, summary.get("reaction")),
        r"\chapter{What this shows and what it does not}\label{ch:reading}", reading_chapter(src, card, c),
        r"\chapter{The audit}\label{ch:audit}", audit.chapter(rubric, scored, audited + compared, form, units, escape, code, team.table, documents.kv_table,
                                                                    team_built=c is not None),
        r"\appendix",
        r"\chapter{How the CalculiX numbers were mapped and judged}\label{sec:method}",
        documents.method_section(record).replace(r"\subsection{", r"\section{"),  # sections of the appendix chapter, numbered A.1, A.2
        r"\chapter{The CalculiX record}\label{app:record}",
        rf"Our record of the CalculiX run, {code(src.record.name)}, is kept with us; it is printed here as it is.",
        documents.appendix_record(src.record, where=package_name),
        r"\chapter{The files in the package}\label{sec:files}", files_appendix(src, spec, c, package),
        r"\chapter{How we produced these files}", commands_appendix(src),
    ]
    if documents.truncated(rows, full_tables) and (full_tables or len(rows) <= documents.FULL_TABLE_LIMIT):
        parts += [r"\chapter{The full CalculiX comparison table}", documents.comparison_table(rows, units)]
    parts.append(r"\end{document}")
    tex = out_dir / f"{src.coupon}.tex"
    tex.write_text(for_the_team("\n\n".join(parts), theory) + "\n", encoding="utf-8")
    if manual.UNMAPPED:
        print("Characters without a LaTeX mapping (check how they render):", " ".join(sorted(manual.UNMAPPED)))
    print(f"{src.coupon}: LaTeX written to {tex}")

    def fill_package(folder: Path) -> None:
        fill(folder, src, spec, text, card, c, deck, solution)
        write_form(folder / form, rubric, scored, audited, units, tables=form_tables(rubric, evidence, scored), files=compared, record=build_record)

    team.write_package(package, fill_package)
    result = None
    if pdf:
        compiler = manual.tectonic()
        if compiler is None:
            print("Tectonic not found; no PDF.")
        else:
            subprocess.run([compiler, "--outdir", str(package), str(tex)], check=True)  # the one PDF, straight into the package
            result = package / f"{src.coupon}.pdf"
            print(f"{src.coupon}: document written to {result}")
    print(f"{src.coupon}: package written to {package}")
    if c is not None and write_summary:
        print(f"{src.coupon}: team comparison figures written to {team.write_team_summary(c)}")
    return (tex if result is None else result), package


VERBATIM = re.compile(r"(\\begin\{(plainfile|enginecode|lstlisting)\}.*?\\end\{\2\})", re.S)
ENGINE_SECTION = re.compile(r"engine theory, Sections? (\d)(?: and (\d))?")
DECISION = re.compile(r"\s*\((?:[^()]*?[;,]\s*)?(?:see )?ADR-\d{4}[^()]*\)|,? as in ADR-\d{4}")


def for_the_team(tex: str, theory: bool = True) -> str:
    """The prose the team reads, outside the verbatim listings of files and code: a pointer to the engine's theory becomes a reference to
    the section of this document that prints it (or, in a build without the theory, names the engine manual), and the numbers of our
    decision records go, since the team does not have them."""
    def section(m: re.Match) -> str:
        if not theory:
            return "the engine manual, " + m.group(0).removeprefix("engine theory, ")
        if m.group(2):
            return rf"Sections~\ref{{sec:engine-{m.group(1)}}} and~\ref{{sec:engine-{m.group(2)}}}"
        return rf"Section~\ref{{sec:engine-{m.group(1)}}}"

    def prose(text: str) -> str:
        return DECISION.sub("", ENGINE_SECTION.sub(section, text))
    pieces = VERBATIM.split(tex)
    out, i = [], 0
    while i < len(pieces):
        out.append(prose(pieces[i]))
        if i + 1 < len(pieces):
            out.append(pieces[i + 1])  # the whole verbatim block, as it is
        i += 3
    return "".join(out)


def check(src: Sources) -> list[str]:
    """The regression check: build the coupon again in a scratch folder and compare what our tools find now with the newest audit
    form that came back. Returns the items our tools passed then and do not pass now."""
    forms = sorted(src.team_files.glob("*/*-audit.xlsx")) if src.team_files.is_dir() else []
    if not forms:
        print(f"{src.coupon}: no audit form has come back, so there is nothing to compare with")
        return []
    baseline = read_form(forms[-1])
    before = {row.id: row.result for row in baseline.rows if row.judged_by == "our tools"}
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        _, package = build_document(dataclasses.replace(src, documents=scratch / paths.DOCUMENTS, latex=scratch / paths.LATEX), pdf=False,
                                    theory=False, write_summary=False)
        now = our_results(package / f"{package.name}-audit.xlsx")
    lost = regressions(before, now)
    passed = [item for item, result in before.items() if result == "Pass"]
    if lost:
        print(f"{src.coupon}: REGRESSION against the audit of {baseline.date} ({forms[-1].parent.name}): "
              + "; ".join(f"{item} passed, now {now[item]}" for item in lost))
    else:
        print(f"{src.coupon}: the {len(passed)} rows our tools passed in the audit of {baseline.date} still pass")
    return lost


def accepted_attempt(src: Sources) -> str | None:
    """The attempt the package delivers: the case page's accepted attempt, or None when the model folder has no case page."""
    try:
        return read_case(paths.MODELS / src.coupon).accepted
    except (OSError, ValueError):  # no README.md; CasePageError is a ValueError
        return None


def operator() -> str:
    """Who built the package: the git user of this checkout, or "not stated"."""
    try:
        return manual.run("git", "config", "user.name") or "not stated"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "not stated"

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # it prints characters from the library's text, which cp1252 pipes cannot encode
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("coupons", nargs="*", help="coupon folders under .local/fea/")
    parser.add_argument("--all", action="store_true", help="every coupon model under .local/fea/")
    parser.add_argument("--root", type=Path, default=paths.LOCAL, help="the folder holding one folder per coupon (default .local/fea)")
    parser.add_argument("--no-pdf", action="store_true", help="write the LaTeX and the package without its PDF")
    parser.add_argument("--no-theory", action="store_true", help="leave out the equations and code of Chapter 2")
    parser.add_argument("--full-tables", action="store_true", help="print every compared CalculiX number")
    parser.add_argument("--check", action="store_true", help="build nothing: compare our tools' results now with each coupon's newest returned "
                        "audit, and fail when a row they passed no longer passes (run before merging an engine change)")
    args = parser.parse_args()
    found = [d.name for d in paths.model_dirs()]  # the models are local (ADR-0042); a machine without them has none
    if args.all == bool(args.coupons):
        raise SystemExit(f"name coupons or give --all, not both and not neither; the coupons are {found}")
    unknown = sorted(set(args.coupons) - set(found))
    if unknown:
        raise SystemExit(f"no coupon model for {unknown} in .local/fea/; the coupons are {found}")
    chosen = found if args.all else args.coupons
    if args.check:
        lost = [coupon for coupon in chosen if check(sources(coupon, args.root))]
        if lost:
            raise SystemExit(f"regression in {', '.join(lost)}: a row our tools passed in the last audit no longer passes")
        return
    for coupon in chosen:
        if args.all and not calculix_record(paths.MODELS / coupon).is_file():
            print(f"{coupon}: no CalculiX record yet, so no document; run the twin and tools/record_from_dat.py first (its case page says how)")
            continue
        build_document(sources(coupon, args.root), pdf=not args.no_pdf, theory=not args.no_theory, full_tables=args.full_tables)


if __name__ == "__main__":
    main()
