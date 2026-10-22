"""One document per coupon: what was solved, the physics our engine uses, how the part is built in our engine and in
Abaqus/CAE, our results, and how they compare with other solvers (ADR-0041).

From the repository root:

    uv run --project fea python docs/models/coupon.py X840PW-UNT-L1        # one coupon
    uv run --project fea python docs/models/coupon.py --all                 # every coupon under fea/models/
    options: --root <folder> (the folder holding one folder per coupon; default .local/fea), --no-pdf, --no-theory

The document is written to <root>/<coupon>/documents/<coupon>.pdf with its LaTeX in documents/latex/<coupon>/, and one zip
beside it, <today>_<coupon>.zip, holds the PDF, the Abaqus deck to import, the CalculiX deck, the specs and the material
record. When <root>/<coupon>/comparison/team-comparison.toml exists, the team's Abaqus model is compared item by item and
side by side (docs/models/team.py): those sections join the document, their files join the zip, and the comparison's
figures are written to records/<coupon>-team-summary.toml for the case page. Chapters:

    1 The problem              the coupon card, the material from our library with its pages, supports and loading
    2 The physics              laminate theory, the finite element kernel and the failure criteria, each equation with the
                               code that computes it (engine/docs/theory.md, fea/docs/theory.md), and the hand check
    3 Building it, our engine  the spec, the CalculiX twin, the generated model
    4 Building it, Abaqus/CAE  what the team built (when they did) and the step-by-step guide (docs/models/rebuild.py)
    5 Results, our engine      the solution, the reaction, strains and ply stresses, first-ply failure
    6 Verification             CalculiX against our engine, and the team's Abaqus side by side
    7 What this shows          the readings, and what is not shown yet
    Appendices                 the mapping rule, the record, the files in the zip

Every number is computed while the document is built, from the committed spec, decks and record; nothing is typed in.
"""

from __future__ import annotations

import argparse
import difflib
import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

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
manual, rebuild = documents.manual, documents.rebuild
escape, code, inline, number, heading = documents.escape, documents.code, documents.inline, documents.number, documents.heading

from anisotropy_engine.library import library_material  # noqa: E402
from anisotropy_fea import __version__ as fea_version  # noqa: E402
from anisotropy_fea import paths  # noqa: E402
from anisotropy_fea.abaqus_reader import parse_deck  # noqa: E402
from anisotropy_fea.compare import load_record, sha256_of  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.membrane import solve_membrane  # noqa: E402
from anisotropy_fea.mesh import KernelError  # noqa: E402
from anisotropy_fea.model import to_si  # noqa: E402
from anisotropy_fea.recovery import deck_f12_star, strength_ratios  # noqa: E402
from anisotropy_fea.report import comparison_rows, element_centroids, laminate_check, model_facts, solve_record, summarize  # noqa: E402
from anisotropy_fea.spec import coupon_card, full_angles, load_spec, spec_material  # noqa: E402
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
    documents: Path  # where the PDF, its LaTeX and the zip go


def sources(coupon: str, root: Path) -> Sources:
    folder = paths.MODELS / coupon
    spec, record = folder / f"{coupon}.toml", folder / "records" / f"{coupon}-calculix.toml"
    for path in (spec, record):
        if not path.is_file():
            raise SystemExit(f"{coupon}: no {path.relative_to(ROOT).as_posix()}")
    twin = (record.parent / load_record(record)["spec"]).resolve()
    manifest = root / coupon / paths.COMPARISON / "team-comparison.toml"
    return Sources(coupon, spec, twin, record, manifest if manifest.is_file() else None, root / coupon / paths.DOCUMENTS)


# --------------------------------------------------------------------------------------------- chapter 1, the problem

def statement(spec, card: dict[str, str]) -> str:
    units = spec.units
    unit = units.split("-")[0]
    g, loading = spec.geometry, spec.loading
    tab = f"{from_si(g.tab_length, 'length', units):g} {unit}" if g.tab_length else None
    held = f"each end's {tab} tab" if tab and spec.grips and spec.grips.region == "tabs" else "each end's row of nodes"
    grips = ((f"{held} is tied to a reference point by a kinematic coupling, as the team's Abaqus models do" if spec.grips.kind == "coupling"
              else f"{held} is held directly") if spec.grips else "it rests on its supports")
    if loading.control == "displacement":
        value = from_si(abs(loading.value), "length", units)
        load = f"the top end is {'pulled' if loading.value > 0 else 'pushed'} {value:g} {unit} along the coupon while the bottom end is held"
    else:
        load = f"a force of {abs(loading.value):g} N is applied along the coupon at the top end while the bottom end is held"
    return escape(f"The {card['Test']} coupon {card['Coupon']}: {card['Size']}; layup {card['Layup']}; material {card['Material'].split(' (')[0]}. "
                  f"In the model, {grips}, and {load}. The questions our engine answers: what force the coupon carries, the strain and the stress in "
                  f"every ply, and at what share of the loading the first ply fails.")


def material_section(spec, units: str) -> str:
    """The material from our library with the page of every value; the team comparison's version adds the team's column."""
    mat = spec.material
    if mat.library is None:
        return "The material is given by explicit constants in the spec (listed in Section~\\ref{sec:model}); it is not a library record."
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
        rows.append([name, f"{number(from_si(value, 'stress', units), 6)} {stress_unit}", "stated in our spec"])
    return "\n\n".join([
        rf"Our model does not type its material in. The spec names a record of our material library, {code(lib.material_id)} "
        rf"(dataset {code(lib.dataset_id)}), and the generator writes its values, with their source and page, into the deck header. The source:",
        rf"\begin{{quote}}{escape(team.source_text(lib))}.\end{{quote}}",
        rf"Rights class {code(lib.rights)}: the values are cited by table and page and the source itself is not reproduced.",
        team.table(["Property", "Our library", "Source page"], rows, r">{\raggedright\arraybackslash}p{2.4cm}>{\raggedright\arraybackslash}p{3.6cm}Y"),
        rf"What the record does not give: {escape('; '.join(lib.not_provided) or 'nothing listed')}.",
    ])


def problem_chapter(spec, card: dict[str, str], c, units: str, figures: Path) -> str:
    documents.plot_model_module.plot_model(build_model(spec), figures / "model.png", units)
    grips = spec.grips
    return "\n\n".join([
        statement(spec, card),
        r"\section{The coupon}\label{sec:coupon}",
        documents.kv_table([(escape(label), escape(value)) for label, value in card.items()]),
        r"\section{The material, from our library}\label{sec:material}",
        team.material_section(c) if c is not None else material_section(spec, units),
        r"\section{Supports and loading}",
        escape(f"Grips: {grips.kind} on the {'whole tab regions' if grips.region == 'tabs' else 'end node rows'}. "
               f"Loading: {spec.loading.control}, {from_si(spec.loading.value, 'length' if spec.loading.control == 'displacement' else 'force', units):g} "
               f"{documents.UNIT_LABEL[units]['length' if spec.loading.control == 'displacement' else 'force']} at the top grip. "
               "The analysis is linear and static, in the plane of the laminate (a membrane: no bending, no buckling).") if grips else "",
        r"\begin{center}\includegraphics[width=0.6\linewidth,height=0.7\textheight,keepaspectratio]{figures/model.png}\end{center}",
        r"{\small\color{muted}The generated model: element sets, the gripped node sets, the probes and the loading at the moving grip.}",
    ])


# --------------------------------------------------------------------------------------------- chapter 2, the physics

def physics_chapter(theory: bool, rec_deck, rec_solution, record: dict, rows, units: str) -> str:
    out = [r"Our engine solves the coupon in two layers. Laminate theory turns each ply's elastic constants and angle into the laminate's "
           r"stiffness and, once the laminate's strain is known, gives every ply's stress in its own axes. The finite element kernel solves the "
           r"coupon as a whole: it divides it into elements, each carrying the laminate stiffness, enforces the grips and the loading, and finds the "
           r"strain everywhere. The failure criteria then compare every ply's stress with the material's strengths. The text and code below are "
           r"the same sources the engine manual prints, with the functions' real line numbers."]
    if theory:
        out += [r"\section{From plies to the laminate}", manual.theory("anisotropy_engine", only=("1", "2", "3")),
                r"\section{The finite element kernel}\label{sec:theory}", manual.theory("anisotropy_fea"),
                r"\section{Failure of a ply}", manual.theory("anisotropy_engine", only=("5",))]
    else:
        out += [r"\section{The equations}\label{sec:theory}",
                r"Left out of this build (\texttt{--no-theory}); they are in \texttt{engine/docs/theory.md}, \texttt{fea/docs/theory.md} and the engine manual."]
    out += [r"\section{The hand check for this coupon}\label{sec:clt}", documents.clt_section(rec_deck, rec_solution, record, rows, units)]
    return "\n\n".join(out)


# --------------------------------------------------------------------------------------------- chapter 3, our engine

def engine_chapter(src: Sources, deck, units: str, committed: Path) -> str:
    diff = [line for line in difflib.unified_diff(src.spec.read_text(encoding="utf-8").splitlines(), src.twin.read_text(encoding="utf-8").splitlines(),
                                                  src.spec.name, src.twin.name, n=0, lineterm="") if not line.startswith("@@")]
    comments = documents.header_comments(committed)
    c = src.coupon
    commands = "\n".join([
        f"uv run python tools/regenerate_decks.py {c} {c}-nodal          # the decks, from the specs",
        f"uv run python tools/new_attempt.py {c}                          # a folder for this try's runs",
        f"uv run python examples/run_calculix.py models/{c}/{c}-nodal.toml --out <attempt>/run/calculix",
        f"uv run python tools/record_from_dat.py models/{c}/{c}-nodal.toml <attempt>/run/calculix/{c}-nodal-ccx.dat ...",
        f"uv run --project fea python docs/models/coupon.py {c}          # this document, from the repository root",
    ])
    return "\n\n".join([
        r"The model is not drawn by hand. One file, the spec, states the coupon: its name and card, dimensions, mesh seeds, layup, material "
        r"from our library with its out-of-plane constants, grips, loading, probes and output requests. Every key is required and every invalid "
        r"combination is refused by name. The generator builds the model from it and writes the complete deck for each solver (ADR-0030); the "
        r"committed decks must equal what it writes today, which a test checks.",
        r"\section{The spec}\label{sec:model}", documents.file_listing(src.spec),
        r"\section{The CalculiX twin}",
        r"CalculiX reports no reaction at a coupled reference point, so the model it runs is a twin: the same spec with the grips as direct "
        r"constraints on the tab nodes. These are the lines that differ:",
        r"\begin{plainfile}" + "\n" + documents.listing_text("\n".join(diff)) + "\n" + r"\end{plainfile}",
        r"\section{The generated model}",
        rf"The deck {code(committed.name)} (SHA-256 {code(sha256_of(committed)[:16])}\ldots) opens with these header lines:",
        r"\begin{plainfile}" + "\n" + documents.listing_text("\n".join(comments)) + "\n" + r"\end{plainfile}",
        "Read back by our own deck reader, it holds:",
        documents.kv_table(documents.deck_facts(deck, units)),
        r"\section{Rebuilding it}", "From \\texttt{fea/}:",
        r"\begin{plainfile}" + "\n" + documents.listing_text(commands) + "\n" + r"\end{plainfile}",
    ])


# --------------------------------------------------------------------------------------------- chapter 4, Abaqus/CAE

def abaqus_chapter(src: Sources, spec, deck, solution, units: str, committed: Path, c, figures: Path) -> str:
    material = spec_material(spec)
    t = spec.material.transverse
    mpa = lambda v: from_si(v, "stress", units)  # noqa: E731  the loaded spec is in SI
    transverse = (f"G13 {mpa(t.G13):g}, G23 {mpa(t.G23):g} ({units.split('-')[1]}); "
                  + ("transverse isotropy stated (E3 = E2, nu13 = nu12)" if t.transverse_isotropy else f"E3 {mpa(t.E3):g}, nu13 {t.nu13:g} given")
                  + ("; plane_stress = true: nu13 = nu23 = 0 written for CalculiX" if t.plane_stress else f"; nu23 {t.nu23:g}"))
    ccx = paths.deck_path(src.twin, "ccx")
    helpers = rebuild.Helpers(escape=escape, code=code, inline=inline, number=number, heading=heading, kv_table=documents.kv_table,
                              long_table=documents.long_table, listing_text=documents.listing_text, tools=("Abaqus/CAE",))
    context = rebuild.Context(facts=model_facts(deck, solution), deck=deck, units=units, kernel_deck=committed, reference_deck=ccx,
                              kernel_sha256=sha256_of(committed), reference_sha256=sha256_of(ccx), solver_name="calculix", spec_path=src.spec,
                              spec_material_lines=material.citation_lines, spec_material_source=f"{material.source}; rights class {material.rights}",
                              spec_transverse=transverse, record_title=spec.title, report_date=date.today().isoformat())
    out = []
    if c is not None:
        out += [rf"The team built this coupon in Abaqus/CAE ({code(c.team_deck_path.name)}). The first section shows that our deck is the same "
                r"model, item by item; the second rebuilds it step by step.",
                r"\section{What the team built}\label{sec:models}", team.models_section(c, figures)]
    else:
        out.append(rf"The team has not built this coupon yet. The steps below build the model of our deck {code(committed.name)}, which Abaqus/CAE "
                   r"can also import directly (File, Import, Model; this click path is not checked by us).")
    out += [r"\section{Step by step in Abaqus/CAE}\label{sec:rebuild}", rebuild.render(context, helpers)]
    return "\n\n".join(out)


# --------------------------------------------------------------------------------------------- chapter 5, our results

def results_chapter(spec, deck, solution, units: str, figures: Path) -> tuple[str, dict]:
    labels = documents.UNIT_LABEL[units]
    documents.plot_deck_module.plot_solution(deck, solution, units, figures / "solution.png", title=f"Our engine's solution, units {units}")
    out = [r"Our engine solved the model of Section~\ref{sec:model} while this document was built. The figure shows the deformed mesh, the three "
           r"membrane strains, the axial section force and the maximum-stress first-ply-failure map.",
           r"\begin{center}\includegraphics[width=\linewidth,height=0.6\textheight,keepaspectratio]{figures/solution.png}\end{center}"]
    summary: dict = {}
    try:
        check = laminate_check(deck, solution)
    except KernelError as exc:
        out.append("No centre-element summary for this model: " + escape(str(exc)) + ".")
        check = None
    if check is not None:
        summary["reaction"] = from_si(check.kernel_reaction_N, "force", units)
        state = [rf"Reaction at the moving grip & {number(summary['reaction'], 6)} {escape(labels['force'])} \\"]
        for i, name in enumerate(("eps_x", "eps_y", "gamma_xy")):
            state.append(rf"{documents.MATH[name]} at the centre element & {number(float(check.kernel_strain[i]), 5)} \\")
        state.append(rf"{documents.MATH['N_y']} at the centre element & {number(from_si(float(check.kernel_section_force[1]), 'force_per_length', units), 6)} "
                     rf"{escape(labels['force_per_length'])} \\")
        out += [r"\section{The coupon as a whole}", documents.long_table(["Quantity", "Our engine"], state, r"Yr")]
        angles = full_angles(spec)
        ply_rows = [rf"{k + 1} & {angles[k]:g} & " + " & ".join(number(from_si(float(check.kernel_ply_stress_12[k, i]), 'stress', units), 5) for i in range(3)) + r" \\"
                    for k in range(len(angles))]
        out += [r"\section{Every ply, at the centre}",
                rf"Stress in each ply's own axes at the centre element ({escape(check.centre_element)}), {escape(labels['stress'])}, bottom ply first:",
                documents.long_table(["Ply", "Angle", r"$\sigma_1$", r"$\sigma_2$", r"$\tau_{12}$"], ply_rows, r"rrrrr")]
    criteria = spec.output.fpf_criteria
    if criteria and any(m.fail_stress for m in deck.materials.values()):
        applied = from_si(abs(spec.loading.value), "length" if spec.loading.control == "displacement" else "force", units)
        unit = labels["length" if spec.loading.control == "displacement" else "force"]
        angles = full_angles(spec)
        rows = []
        for criterion in criteria:
            field = strength_ratios(solution, criterion, deck_f12_star(deck))
            summary.setdefault("fpf", (criterion, field.factor, field.ply, angles[field.ply - 1]))
            rows.append(rf"{escape(criterion.replace('_', ' '))} & {number(field.factor, 4)} & {number(field.factor * applied, 4)} {escape(unit)} & "
                        rf"{field.ply} ({angles[field.ply - 1]:g}°) & {escape(str(field.element[1]))} & {escape(field.governing_mode)} \\")
        out += [r"\section{First-ply failure}",
                r"With the strengths from our library the engine finds the first ply to fail. The analysis is linear, so the factor scales the applied "
                r"loading: below 1, the first ply fails before the loading of the model is reached, and the stresses above are those of a linear model "
                r"past that point.",
                documents.long_table(["Criterion", "Factor", "Loading at failure", "Ply (angle)", "Element", "Mode"], rows, r"Yrrrrr")]
    return "\n\n".join(out), summary


# --------------------------------------------------------------------------------------------- chapter 6, verification

def verification_chapter(src: Sources, record: dict, rows, problems, summaries, units: str, map_drawn: bool, full_tables: bool, c, figures: Path) -> str:
    solver = record["solver"]
    out = [r"Verification asks whether another solver gives the same answer on the same model. It is not validation: that needs a test of a real "
           r"coupon, and none exists yet for this one.",
           rf"\section{{CalculiX, an independent solver}}\label{{sec:summary}}",
           rf"CalculiX {escape(str(solver['version']))} is an open-source finite element program with its own element ({escape(solver['element_type'])}). "
           r"It ran the CalculiX twin of Section~\ref{sec:model}; our kernel ran the same model, and every number of its record was compared:",
           documents.summary_section(record, rows, problems, summaries, units),
           r"To see it yourself in PrePoMax 2.6: File, Import the CalculiX deck from the zip (\texttt{calculix/}), run it, then File, Open results (.frd).",
           r"\section{CalculiX: the solver and its deck}\label{sec:reference}", documents.reference_section(record, src.record),
           r"\section{CalculiX: every compared number}\label{sec:comparison}", documents.comparison_section(rows, summaries, units, map_drawn, full_tables)]
    if c is not None:
        out += [r"\section{The team's Abaqus model, side by side}\label{sec:results}", team.results_section(c, figures)]
    return "\n\n".join(out)


def reading_chapter(src: Sources, card: dict[str, str], c) -> str:
    reading, _ = documents.reading_section(src.record)
    out = [r"\section{Reading}\label{sec:reading}", r"\subsection{The CalculiX comparison}", reading]
    if c is not None:
        out += [r"\subsection{The team comparison}", team.reading_section(c)]
    out += [r"\section{What is not shown yet}\label{sec:open}",
            r"\begin{itemize}",
            r"\item " + escape(f"Test data: {card['Test data']}. Until a real coupon is tested, the results are verified against other solvers, not validated."),
            r"\item " + escape(f"Standard: {card['Standard']}. Size from: {card['Size from']}."),
            r"\item The kernel is a membrane model: no bending, no buckling, no through-thickness stress (Section~\ref{sec:theory}).",
            r"\end{itemize}"]
    if c is not None:
        out += [r"From the team's side:", team.open_section(c)]
    return "\n\n".join(out)


def files_appendix(src: Sources, spec, c, archive: Path) -> str:
    if c is not None:
        return team.files_section(c)
    lib = library_material(spec.material.library, spec.material.dataset) if spec.material.library else None
    rows = [[code(path), escape(what)] for path, what in zip_contents(src, lib)]
    return "\n\n".join([rf"Everything is in {code(archive.name)}; unzipped, it is one folder, {code(src.coupon)}. It holds no CalculiX results: run our "
                        r"decks to get them.",
                        team.table(["File", "What it is and how to open it"], rows, r">{\raggedright\arraybackslash}p{6.4cm}Y", r"\footnotesize")])


# --------------------------------------------------------------------------------------------- the title page

def title_page(card: dict[str, str], record: dict, rows, summary: dict, c, units: str) -> str:
    solver = record["solver"]
    reaction = next((r for r in rows if r.group == "rf" and r.name == "Grip-Top" and r.component == 1), None)
    labels = documents.UNIT_LABEL[units]
    verdict = []
    if "reaction" in summary:
        text = rf"\textbf{{Our engine.}} The coupon carries {number(summary['reaction'], 6)} {escape(labels['force'])}"
        if "fpf" in summary:
            criterion, factor, ply, angle = summary["fpf"]
            text += (rf"; the first ply to fail is ply {ply} ({angle:g}°) by {escape(criterion.replace('_', ' '))}, at {number(factor, 3)} of the applied "
                     r"loading" + (r", so the loading of this model is past first-ply failure" if factor < 1 else ""))
        verdict.append(text + ".")
    agreeing = sum(r.agrees for r in rows)
    verdict.append(rf"\textbf{{Verified against CalculiX}} {escape(str(solver['version']))} ({escape(solver['element_type'])}): {agreeing} of {len(rows)} "
                   rf"compared values agree within {number(100 * record['expected']['tolerance'], 3)}\%"
                   + (rf"; the reaction differs by {number(100 * (reaction.kernel - reaction.reference) / abs(reaction.reference), 2)}\%" if reaction else "") + ".")
    if c is not None:
        verdict.append(team.verdict(c))
    verdict.append(r"\textbf{Not validated.} " + escape(f"{card['Test data']}."))
    facts = [(escape(label), escape(value)) for label, value in card.items() if label not in ("Coupon", "Test")]
    return "\n".join([
        r"\begin{titlepage}", r"\sffamily",
        r"{\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} COUPON REPORT}\par", r"\vspace*{1.6cm}",
        rf"{{\fontsize{{26}}{{32}}\selectfont\bfseries\color{{ink}} {escape(card['Coupon'])}}}\par", r"\vspace{0.3cm}",
        rf"{{\Large\bfseries\color{{ink}} {escape(card['Test'].capitalize())} coupon}}\par", r"\vspace{0.4cm}",
        r"{\large\color{muted} What was solved, the physics our engine uses, how the part is built in our engine and in Abaqus/CAE, "
        r"our results, and how they compare with other solvers}\par", r"\vspace{1cm}",
        r"{\small\begin{tabular}{@{}p{2.8cm}p{\dimexpr\linewidth-3.3cm}@{}}", *[rf"{label} & {value} \\[0.3ex]" for label, value in facts], r"\end{tabular}}\par",
        r"\vfill", r"\verdict{" + " ".join(verdict) + "}", r"\vspace{0.6cm}",
        rf"{{\small\color{{muted}} Built {date.today().isoformat()} by \texttt{{docs/models/coupon.py}} (anisotropy-fea {fea_version}, commit "
        rf"{escape(documents.git_commit())}). Every number is computed from the committed spec, decks and record while the document is built.}}",
        r"\end{titlepage}",
    ])


# --------------------------------------------------------------------------------------------- the zip

def zip_contents(src: Sources, lib) -> list[tuple[str, str]]:
    c = src.coupon
    out = [("README.txt", "this list, as plain text"), (f"{c}.pdf", "the coupon document"),
           (f"abaqus/{c}-abaqus.inp", "our deck, for Abaqus: File, Import, Model (this click path is not checked by us), or run it as a job"),
           (f"calculix/{paths.deck_path(src.twin, 'ccx').name}", "the CalculiX twin, with the grips as direct constraints. PrePoMax: File, Import, then run it"),
           (f"spec/{src.spec.name}", "the spec our generator builds the Abaqus deck from"), (f"spec/{src.twin.name}", "the spec of the CalculiX twin")]
    if lib is not None:
        out.append((f"material/{lib.material_id}.csv", "the material from our library: every value, its unit, basis and source page, and the source"))
    return out


def fill(folder: Path, src: Sources, spec, text: str, pdf: Path | None, card: dict[str, str], c) -> None:
    if c is not None:
        team.fill_share(c, pdf, folder)  # the team's deck, our model, the material, the side-by-side files and the README
        return
    lib = library_material(spec.material.library, spec.material.dataset) if spec.material.library else None
    for sub in ("abaqus", "calculix", "spec", "material"):
        (folder / sub).mkdir(parents=True)
    (folder / "abaqus" / f"{src.coupon}-abaqus.inp").write_text(text, encoding="utf-8", newline="\n")
    shutil.copy2(paths.deck_path(src.twin, "ccx"), folder / "calculix")
    shutil.copy2(src.spec, folder / "spec")
    shutil.copy2(src.twin, folder / "spec")
    if lib is not None:
        team.write_material_csv(folder / "material" / f"{lib.material_id}.csv", lib, spec_material(spec), spec.units)
    if pdf is not None and pdf.exists():
        shutil.copy2(pdf, folder / f"{src.coupon}.pdf")
    contents = zip_contents(src, lib)
    width = max(len(path) for path, _ in contents)
    lines = [team.README_MARK, f"{card['Coupon']}, {card['Test']}: our model and its document", "",
             *[f"{label + ':':14} {value}" for label, value in card.items()], "",
             f"Built {date.today().isoformat()} by docs/models/coupon.py (anisotropy-fea {fea_version}, commit {documents.git_commit()}).",
             "Start with the PDF. Numbers in the files are in mm, MPa and N.", "",
             *[f"{path.ljust(width)}  {what}" for path, what in contents]]
    (folder / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------------------------- the document

def build_document(src: Sources, pdf: bool, theory: bool, full_tables: bool = False) -> tuple[Path, Path]:
    """The coupon document (its PDF when Tectonic is installed and `pdf` is set, else the LaTeX) and the coupon's zip."""
    spec = load_spec(src.spec)
    card = dict(coupon_card(spec))
    if not card:
        raise SystemExit(f"{documents.rel(src.spec)} has no [coupon] table: a coupon document names its coupon (ADR-0038)")
    units = spec.units
    text = write_abaqus(build_model(spec))
    committed = paths.deck_path(src.spec, "abaqus")
    if committed.is_file() and committed.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
        raise SystemExit(f"{documents.rel(committed)} is not what the generator writes from {src.spec.name} today; run fea/tools/regenerate_decks.py first")
    deck_file = committed if committed.is_file() else src.documents / "latex" / src.coupon / f"{src.spec.stem}-abaqus.inp"
    deck = to_si(parse_deck(text, source_path=deck_file.name), units)
    solution = solve_membrane(deck)
    record = load_record(src.record)
    rows, problems = comparison_rows(record)
    summaries = summarize(rows)
    rec_deck, rec_solution = solve_record(record)
    c = team.Comparison(src.manifest) if src.manifest is not None else None
    if c is not None and c.spec_path != src.spec.resolve():
        raise SystemExit(f"{documents.rel(src.manifest)}: ours.spec must be the coupon's spec {documents.rel(src.spec)}")

    out_dir = src.documents / "latex" / src.coupon
    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    if not committed.is_file():
        deck_file.write_text(text, encoding="utf-8", newline="\n")  # a spec without a committed deck (a fixture): the guide reads this copy
        committed = deck_file
    archive = team.dated(src.documents / f"{src.coupon}.zip")
    if c is not None:
        c.zip = archive
    documents.difference_figure(rows, figures / "differences.png")
    map_drawn = documents.element_map(rows, summaries, element_centroids(rec_solution, units), rec_solution, units, figures / "element-map.png")
    results, summary = results_chapter(spec, deck, solution, units, figures)
    headline = f"{card['Coupon']}, {card['Test']}"
    parts = [
        r"\documentclass[11pt,letterpaper,oneside]{report}", documents.PREAMBLE, r"\usepackage{float}", CHAPTER_STYLE,
        rf"\hypersetup{{pdftitle={{{escape(headline)}: coupon report}}}}",
        r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyhead[L]{{\sffamily\footnotesize\color{{muted}}Anisotropy AI \textperiodcentered{{}} Coupon report \textperiodcentered{{}} {escape(headline)}}}",
        r"\fancyhead[R]{\sffamily\footnotesize\color{muted}\thepage}",
        r"\fancyfoot[C]{\sffamily\scriptsize\color{muted}Verified against other solvers; not validated against a coupon test.}",
        r"\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\sffamily\scriptsize\color{muted}\thepage}\renewcommand{\headrulewidth}{0pt}}",
        r"\begin{document}",
        title_page(card, record, rows, summary, c, units),
        r"\tableofcontents",
        r"\chapter{The problem}\label{ch:problem}", problem_chapter(spec, card, c, units, figures),
        r"\chapter{The physics: how our engine solves it}\label{ch:physics}", physics_chapter(theory, rec_deck, rec_solution, record, rows, units),
        r"\chapter{Building the part in our engine}\label{ch:engine}", engine_chapter(src, deck, units, committed),
        r"\chapter{Building the part in Abaqus/CAE}\label{ch:abaqus}", abaqus_chapter(src, spec, deck, solution, units, committed, c, figures),
        r"\chapter{Results from our engine}\label{ch:results}", results,
        r"\chapter{Verification against other solvers}\label{ch:verification}",
        verification_chapter(src, record, rows, problems, summaries, units, map_drawn, full_tables, c, figures),
        r"\chapter{What this shows and what it does not}\label{ch:reading}", reading_chapter(src, card, c),
        r"\appendix",
        r"\chapter{How the CalculiX numbers were mapped and judged}\label{sec:method}", documents.method_section(record),
        r"\chapter{The CalculiX record}", documents.appendix_record(src.record),
        r"\chapter{The files in the zip}\label{sec:files}", files_appendix(src, spec, c, archive),
    ]
    if len(rows) > 60 and (full_tables or len(rows) <= documents.FULL_TABLE_LIMIT):
        parts += [r"\chapter{The full CalculiX comparison table}", documents.comparison_table(rows, units)]
    parts.append(r"\end{document}")
    tex = out_dir / f"{src.coupon}.tex"
    tex.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    if manual.UNMAPPED:
        print("Characters without a LaTeX mapping (check how they render):", " ".join(sorted(manual.UNMAPPED)))
    print(f"{src.coupon}: LaTeX written to {tex}")
    result = None
    if pdf:
        compiler = manual.tectonic()
        if compiler is None:
            print("Tectonic not found; no PDF.")
        else:
            subprocess.run([compiler, "--outdir", str(out_dir), str(tex)], check=True)
            result = src.documents / f"{src.coupon}.pdf"
            shutil.copy2(out_dir / f"{src.coupon}.pdf", result)
            print(f"{src.coupon}: document written to {result}")
    archive = team.write_zip(archive, src.coupon, lambda folder: fill(folder, src, spec, text, result, card, c))
    print(f"{src.coupon}: zip written to {archive}")
    if c is not None:
        print(f"{src.coupon}: team comparison figures written to {team.write_team_summary(c)}")
    return (tex if result is None else result), archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("coupons", nargs="*", help="coupon folders under fea/models/")
    parser.add_argument("--all", action="store_true", help="every coupon under fea/models/")
    parser.add_argument("--root", type=Path, default=paths.LOCAL, help="the folder holding one folder per coupon (default .local/fea)")
    parser.add_argument("--no-pdf", action="store_true", help="write the LaTeX and the zip only")
    parser.add_argument("--no-theory", action="store_true", help="leave out the equations and code of Chapter 2")
    parser.add_argument("--full-tables", action="store_true", help="print every compared CalculiX number")
    args = parser.parse_args()
    found = sorted(d.name for d in paths.MODELS.iterdir() if d.is_dir() and (d / f"{d.name}.toml").is_file())
    if args.all == bool(args.coupons):
        raise SystemExit(f"name coupons or give --all, not both and not neither; the coupons are {found}")
    unknown = sorted(set(args.coupons) - set(found))
    if unknown:
        raise SystemExit(f"no model folder for {unknown}; the coupons are {found}")
    for coupon in (found if args.all else args.coupons):
        build_document(sources(coupon, args.root), pdf=not args.no_pdf, theory=not args.no_theory, full_tables=args.full_tables)


if __name__ == "__main__":
    main()
