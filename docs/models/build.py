"""Builds one model comparison document per comparison record: the model, the mathematics, the code, the reference
solver, every compared number with its error, and the reading (ADR-0031).

From the repository root:

    uv run --project fea python docs/models/build.py fea/models/tension-coupon/records/tension-coupon-calculix.toml
    uv run --project fea python docs/models/build.py --all                 # every committed record
    uv run --project fea python docs/models/build.py .local/fea/tension-coupon/comparison/tension-test-abaqus.toml

A committed record's document is written to docs/models/build/<record>/ (git-ignored, rebuilt like the manual); a
record under .local/ goes to report/<record>/ beside the record (ADR-0032) and stays there, since its material may not be public. The
LaTeX file is self-contained; when Tectonic is installed the PDF is compiled next to it. The prose, equations and code
listings come from the same converters as the engine manual (docs/manual/build.py), so the two cannot disagree. Every
number in the document is the reference solver's, the kernel's, or the engine's, computed while the document is built.
"""

from __future__ import annotations

import argparse
import importlib.util
import math
import re
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
from anisotropy_fea import paths as fea_paths  # where the files live (ADR-0036)
PREAMBLE = (HERE / "preamble.tex").read_text(encoding="utf-8")
FULL_TABLE_LIMIT = 400  # rows: a longer comparison table goes to the appendix only with --full-tables
MAP_ELEMENTS = 20  # draw the errors on the mesh when the record covers at least this many elements
INK, MUTED, ACCENT, GRID = "#1C1F22", "#5D636A", "#9A5A00", "#D9DCE0"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


manual = load_module("anisotropy_manual_build", ROOT / "docs/manual/build.py")
rebuild = load_module("anisotropy_models_rebuild", HERE / "rebuild.py")
plot_model_module = load_module("anisotropy_fea_plot_model", ROOT / "fea/examples/plot_model.py")
plot_deck_module = load_module("anisotropy_fea_plot_deck", ROOT / "fea/examples/plot_deck.py")
# The manual lists the kernel's modules; a comparison document also lists the record machinery and the readers.
manual.PACKAGES["anisotropy_fea"] = (manual.PACKAGES["anisotropy_fea"][0],
                                     manual.FEA_MODULES + ("compare", "calculix", "abaqus_report", "spec", "femodel", "mesher", "report"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from anisotropy_fea import __version__ as fea_version  # noqa: E402
from anisotropy_fea.compare import load_record, record_disagreements  # noqa: E402
from anisotropy_fea.femodel import build_model  # noqa: E402
from anisotropy_fea.mesh import KernelError  # noqa: E402
from anisotropy_fea.model import coupled_nodes, expanded_layers, node_name, reference_node  # noqa: E402
from anisotropy_fea.report import (COMPONENTS, GROUP_KIND, ComparisonRow, GroupSummary, comparison_rows, element_centroids,  # noqa: E402
                                   laminate_check, model_facts, not_reported, solve_record, summarize)
from anisotropy_fea.spec import coupon_card, load_spec, spec_material  # noqa: E402
from anisotropy_fea.units import from_si  # noqa: E402

escape, code, inline, number, convert, heading = manual.escape, manual.code, manual.inline, manual.number, manual.convert, manual.heading

UNIT_LABEL = {"mm-MPa": {"force": "N", "length": "mm", "stress": "MPa", "force_per_length": "N/mm", "modulus": "GPa", "stiffness": "N/mm"},
              "m-Pa": {"force": "N", "length": "m", "stress": "Pa", "force_per_length": "N/m", "modulus": "GPa", "stiffness": "N/m"}}
GROUP_TITLE = {"rf": "Reactions", "u": "Displacements", "strain": "Membrane strain at element centroids",
               "section_force": "Section forces", "ply_stress_local": "Ply stresses in material axes",
               "ply_strain_local": "Ply strains in material axes", "ply_mises": "Ply von Mises stress", "fpf": "First-ply failure"}
GROUP_SHORT = {"rf": "Reactions", "u": "Displacements", "strain": "Strain", "section_force": "Section forces", "ply_stress_local": "Ply stresses",
               "ply_strain_local": "Ply strains", "ply_mises": "Ply Mises", "fpf": "First-ply failure"}
MATH = {"RF_x": r"$R_x$", "RF_y": r"$R_y$", "u": "$u$", "v": "$v$", "eps_x": r"$\varepsilon_x$", "eps_y": r"$\varepsilon_y$",
        "gamma_xy": r"$\gamma_{xy}$", "N_x": "$N_x$", "N_y": "$N_y$", "N_xy": "$N_{xy}$", "sigma_1": r"$\sigma_1$",
        "sigma_2": r"$\sigma_2$", "tau_12": r"$\tau_{12}$", "eps_1": r"$\varepsilon_1$", "eps_2": r"$\varepsilon_2$",
        "gamma_12": r"$\gamma_{12}$", "sigma_M": r"$\sigma_\mathrm{M}$", "ratio": "$R$"}


# --------------------------------------------------------------------------------------------- small helpers

def percent(x: float, digits: int = 3) -> str:
    return "--" if math.isnan(x) else f"{100 * x:.{digits}f}" + r"\%"


def mnumber(value: float, digits: int = 6) -> str:
    """A number inside math mode (manual.number wraps exponents in $...$ for text)."""
    text = f"{value:.{digits}g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        return rf"{mantissa}\times10^{{{int(exponent)}}}"
    return text


def compact(value: float, digits: int = 5) -> str:
    """A table number: `digits` significant digits, three when it needs an exponent (the record holds the full value)."""
    return number(value, 3 if "e" in f"{value:.{digits}g}" else digits)


def key_code(key: str) -> str:
    """A comparison label as code that may break after each bracket."""
    return code(key).replace("]", r"]\allowbreak{}")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def listing_text(text: str) -> str:
    """Text for a listings environment: Latin Modern Mono has Latin-1; other characters are replaced, not dropped silently."""
    return "".join(ch if ord(ch) < 256 else {"—": "--", "–": "-", "’": "'"}.get(ch, "?") for ch in text)


def file_listing(path: Path, caption: str | None = None, first: int | None = None, last: int | None = None, python: bool = False) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    first = first or 1
    last = min(last or len(lines), len(lines))
    body = listing_text("\n".join(lines[first - 1:last]))
    env = "enginecode" if python else "plainfile"
    options = f"[firstnumber={first}]" if python else ""
    where = f", lines {first}--{last}" if (first, last) != (1, len(lines)) else ""
    return (rf"\filefrom{{{code(caption or rel(path))}{escape(where)}}}" + "\n" + rf"\begin{{{env}}}{options}" + "\n" + body + "\n" + rf"\end{{{env}}}")


def listing(name: str) -> str:
    return manual.listing(name, "anisotropy_fea")


def kv_table(rows: list[tuple[str, str]], spec: str = r">{\raggedright\arraybackslash}p{3.6cm}Y") -> str:
    body = "\n".join(rf"{label} & {value} \\" for label, value in rows)
    return "\n".join([r"{\small", rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", body, r"\bottomrule", r"\end{xltabular}", "}"])


def long_table(header: list[str], rows: list[str], spec: str, size: str = r"\small") -> str:
    head = " & ".join(r"\textbf{" + h + "}" for h in header) + r" \\"
    return "\n".join(["{" + size, rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", head, r"\midrule", r"\endhead",
                      *rows, r"\bottomrule", r"\end{xltabular}", "}"])


def header_comments(path: Path, limit: int = 60) -> list[str]:
    """The comment lines a deck opens with (after *Heading), before its first data keyword."""
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("*heading") or not stripped:
            continue
        if stripped.startswith("**"):
            out.append(stripped[2:].strip())
        elif not stripped.startswith("*"):
            out.append(stripped)  # the *HEADING text line of a CalculiX deck
        else:
            break
        if len(out) >= limit:
            break
    return out


def git_commit() -> str:
    try:
        commit = manual.run("git", "rev-parse", "--short", "HEAD")
        if manual.run("git", "status", "--porcelain", "--untracked-files=no"):
            commit += " + local changes"
        return commit
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


# --------------------------------------------------------------------------------------------- figures

def difference_figure(rows: list[ComparisonRow], path: Path) -> None:
    """Every compared number as a point: its difference as a fraction of what the record allows, one row per group."""
    groups = list(dict.fromkeys(row.group for row in rows))
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(groups) + 1.6), constrained_layout=True)
    fig.patch.set_facecolor("white")
    rng = np.random.default_rng(0)
    for k, group in enumerate(groups):
        members = [row for row in rows if row.group == group]
        x = np.array([max(row.of_allowed, 1e-6) for row in members])
        y = k + rng.uniform(-0.18, 0.18, size=x.size)
        agree = np.array([row.agrees for row in members])
        ax.plot(x[agree], y[agree], linestyle="none", marker="o", markersize=3.5, color=INK, alpha=0.7)
        if (~agree).any():
            ax.plot(x[~agree], y[~agree], linestyle="none", marker="x", markersize=6, color=ACCENT, markeredgewidth=1.4)
    ax.axvline(1.0, color=ACCENT, linewidth=1.2, linestyle="--")
    ax.text(1.0, len(groups) - 0.45, "allowed", color=ACCENT, fontsize=8, ha="right", va="bottom")
    ax.set_xscale("log")
    ax.set_xlim(1e-6, max(10.0, max(row.of_allowed for row in rows) * 2))
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([f"{GROUP_SHORT.get(g, g)} ({sum(r.group == g for r in rows)})" for g in groups], fontsize=8, color=INK)
    ax.set_ylim(-0.6, len(groups) - 0.4)
    ax.invert_yaxis()
    ax.set_xlabel("|kernel − reference| / allowed difference (log scale; 1 = the record's tolerance)", fontsize=8, color=INK)
    ax.tick_params(colors=MUTED, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.grid(axis="x", color=GRID, linewidth=0.5)
    ax.set_title("Every compared number: dots agree, crosses do not", color=INK, fontsize=10, loc="left")
    fig.savefig(path, dpi=160)
    plt.close(fig)


def element_map(rows: list[ComparisonRow], summaries: list[GroupSummary], centroids: dict[str, tuple[float, float]], solution, units: str,
                path: Path) -> bool:
    """The largest error of each compared element, as a fraction of its group's largest magnitude, drawn on the mesh."""
    scale = {s.group: s.scale for s in summaries}
    worst: dict[str, float] = {}
    for row in rows:
        if row.name in centroids and scale.get(row.group):
            worst[row.name] = max(worst.get(row.name, 0.0), abs(row.difference) / scale[row.group])
    if len(worst) < MAP_ELEMENTS:
        return False
    mesh = solution.mesh
    xy = np.vectorize(lambda v: from_si(v, "length", units))(mesh.xy)
    polys = [xy[nodes] for nodes in mesh.connectivity[:, :4]]
    names = [f"{key[0]}.{key[1]}" for key in mesh.element_keys]
    values = np.array([100 * worst.get(name, math.nan) for name in names])
    covered = ~np.isnan(values)
    cmap = LinearSegmentedColormap.from_list("one_hue", ["#E8EEF5", "#1F4E79"])
    aspect = float(np.ptp(xy[:, 1])) / (float(np.ptp(xy[:, 0])) or 1.0)
    fig, ax = plt.subplots(figsize=(min(9.0, 8.0 / max(aspect, 0.5) + 2.5), 9), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.add_collection(PolyCollection([p for p, c in zip(polys, covered) if not c], facecolors="#F6F7F5", edgecolors=GRID, linewidths=0.3))
    collection = PolyCollection([p for p, c in zip(polys, covered) if c], edgecolors="white", linewidths=0.3, cmap=cmap)
    collection.set_array(values[covered])
    collection.set_clim(0, max(float(np.nanmax(values)), 1e-9))
    ax.add_collection(collection)
    bar = fig.colorbar(collection, ax=ax, fraction=0.05, pad=0.03)
    bar.set_label("largest |kernel − reference| of the element, % of the group's largest magnitude", fontsize=8, color=INK)
    bar.ax.tick_params(colors=MUTED, labelsize=8)
    ax.autoscale()
    ax.set_aspect("equal")
    ax.set_xlabel(f"x ({UNIT_LABEL[units]['length']})", fontsize=8, color=INK)
    ax.set_ylabel(f"y ({UNIT_LABEL[units]['length']})", fontsize=8, color=INK)
    ax.tick_params(colors=MUTED, labelsize=8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_title(f"Where the errors are: {int(covered.sum())} of {len(names)} elements compared; grey elements are not in the record",
                 color=INK, fontsize=9, loc="left", wrap=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return True


# --------------------------------------------------------------------------------------------- sections

def record_coupon(record: dict, record_path: Path) -> dict[str, str]:
    """The identity card of the coupon the record's spec builds (ADR-0038); empty for a hand-built deck or a spec without one."""
    if record["spec"].startswith("none"):
        return {}
    spec_path = (record_path.parent / record["spec"]).resolve()
    return dict(coupon_card(load_spec(spec_path))) if spec_path.is_file() else {}


def title_page(record: dict, record_path: Path, rows: list[ComparisonRow], problems: list[str]) -> str:
    solver = record["solver"]
    card = record_coupon(record, record_path)
    agreeing = sum(row.agrees for row in rows)
    disagreeing = len(rows) - agreeing
    worst = max(rows, key=lambda row: row.of_allowed) if rows else None
    if problems:
        verdict = (rf"\textbf{{The comparison could not be completed.}} {len(problems)} problem(s): " + "; ".join(escape(p) for p in problems))
    elif disagreeing:
        verdict = (rf"\textbf{{The kernel does not reproduce this record.}} {disagreeing} of {len(rows)} numbers lie outside the allowed "
                   rf"difference; the largest is {key_code(worst.key)} at {number(worst.of_allowed, 3)} times what is allowed.")
    else:
        verdict = (rf"\textbf{{The kernel reproduces every number of this record.}} {len(rows)} of {len(rows)} compared values agree within the "
                   rf"record's tolerance; the one closest to the limit is {key_code(worst.key)} at {number(worst.of_allowed, 3)} of what is allowed "
                   rf"(reference {number(worst.reference)}, kernel {number(worst.kernel)}).")
    facts = [
        ("Record", code(rel(record_path))),
        ("Reference solver", escape(f"{solver['name']} {solver['version']}, element {solver['element_type']}, read from its .{solver['source']}")),
        ("Run by", escape(f"{solver['run_by']} on {solver['run_date']}, {solver['machine']}")),
        ("Our kernel", escape(f"anisotropy-fea {fea_version}: bilinear four-node membrane element on the engine's laminate stiffness")),
        ("Compared", escape(f"{len(rows)} numbers, tolerance {100 * record['expected']['tolerance']:g} %, floor {100 * record['expected'].get('floor', 0.0):g} %"
                            + (f"; {not_reported(record)} components not reported by the solver and skipped" if not_reported(record) else ""))),
        ("Source commit", code(git_commit())),
        ("Built", escape(date.today().isoformat())),
    ]
    if card:  # the coupon's name is the title; the record's own title, after the name, is the subtitle
        facts = [(label, escape(value)) for label, value in card.items() if label not in ("Coupon", "Test")] + facts
        heading = [rf"{{\fontsize{{22}}{{28}}\selectfont\bfseries\color{{ink}} {escape(card['Coupon'])}}}\par", r"\vspace{0.3cm}",
                   rf"{{\large\bfseries\color{{ink}} {escape(card['Test'].capitalize())} coupon}}\par", r"\vspace{0.3cm}",
                   rf"{{\color{{ink}} {inline(record['title'].split(': ', 1)[1])}}}\par", r"\vspace{0.6cm}"]
    else:
        heading = [rf"{{\fontsize{{22}}{{28}}\selectfont\bfseries\color{{ink}} {inline(record['title'])}}}\par", r"\vspace{0.6cm}"]
    return "\n".join([
        r"\hypersetup{pageanchor=false}", r"\begin{titlepage}", r"\sffamily",
        r"{\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} MODEL COMPARISON}\par", r"\vspace*{2.5cm}",
        *heading,
        r"{\large\color{muted} The model, its mathematics and code, the reference solver, every compared number with its error, and the reading}\par",
        r"\vspace{1cm}" if card else r"\vspace{2cm}", r"{\small\begin{tabular}{@{}p{3cm}p{\dimexpr\linewidth-3.5cm}@{}}",
        *[rf"{label} & {value} \\[0.3ex]" for label, value in facts], r"\end{tabular}}\par", r"\vfill",
        rf"\verdict{{{verdict}}}\par", r"\vspace{0.8cm}",
        r"{\small\color{muted} This document is generated from the repository by \texttt{docs/models/build.py}: its equations and prose come from "
        r"\texttt{fea/docs/theory.md}, its code listings from the \texttt{fea} source with real line numbers, the reference numbers from the "
        r"record, and every kernel and laminate-theory number from running the code while it was built. To change it, change those sources "
        r"and rebuild.}", r"\end{titlepage}", r"\hypersetup{pageanchor=true}",
    ])


def about_section(reading_exists: bool) -> str:
    rows = [
        (r"\ref{sec:summary}", "Does the kernel reproduce the reference solver on this model?", "the record and the kernel, run during the build"),
        (r"\ref{sec:model}", "What exactly was modelled?", r"the spec, the generated decks and the kernel's solution"),
        (r"\ref{sec:rebuild}", "How do I rebuild it by hand in Abaqus/CAE or PrePoMax?", r"the deck's facts (\texttt{report.model\_facts}), the team's report template, the PrePoMax 2.6.0 manual"),
        (r"\ref{sec:clt}", "What does classical laminate theory say the answer is?", "the engine, run during the build"),
        (r"\ref{sec:theory}", "What are the kernel's equations and code?", r"\texttt{fea/docs/theory.md} and the \texttt{fea} source"),
        (r"\ref{sec:reference}", "What did the reference solver run, and how does its element differ?", "the record's provenance and the reference deck"),
        (r"\ref{sec:method}", "How were the two sets of numbers mapped and judged?", r"\texttt{compare.py}, the readers and the record tool"),
        (r"\ref{sec:comparison}", "Every compared number and its error", "the record and the kernel"),
        (r"\ref{sec:reading}", "What do we make of it, and what remains unverified?", "the reading note beside the record" if reading_exists else "no reading has been written yet"),
    ]
    body = "\n".join(rf"{a} & {b} & {c} \\" for a, b, c in rows)
    return ("\n".join([
        "Every comparison of one of our finite element models with an independent solver has a document like this one, separate from the "
        "engine manual, so that the argument for a model can be read on its own: what was modelled, what mathematics and code produced our "
        "numbers, what the other solver produced, how far apart the two are and why. Values marked as the kernel's or the engine's were "
        "computed while this document was built; the reference solver's values are the record's, with their provenance.",
        r"\begin{xltabular}{\linewidth}{lYY}\toprule\textbf{Section} & \textbf{Question} & \textbf{Where the content comes from} \\\midrule",
        body, r"\bottomrule\end{xltabular}"]))


def summary_section(record: dict, rows: list[ComparisonRow], problems: list[str], summaries: list[GroupSummary], units: str) -> str:
    expected = record["expected"]
    tolerance, floor = float(expected["tolerance"]), float(expected.get("floor", 0.0))
    labels = UNIT_LABEL[units]
    table_rows = []
    for s in summaries:
        kind = GROUP_KIND.get(s.group)
        unit = escape(labels[kind]) if kind else "--"
        table_rows.append(rf"{escape(GROUP_SHORT.get(s.group, s.group))} & {s.count} & {s.agreeing} & {number(s.scale, 4)} {unit} & "
                          rf"{percent(s.mean_relative_to_scale)} & {percent(s.max_relative_to_scale)} & {key_code(s.worst.key)} & {number(s.worst.of_allowed, 3)} \\")
    out = [
        rf"The record allows a difference of {number(100 * tolerance, 3)}\% of each reference value, but never less than "
        rf"{number(100 * tolerance, 3)}\% of {number(100 * floor, 3)}\% of the group's largest magnitude (the floor rule: a roundoff-sized shear "
        r"stress beside a large axial stress is judged against the group, not against itself; Section~\ref{sec:method}). "
        rf"Errors below are the kernel's value minus the reference solver's, as a fraction of the group's largest magnitude, so that every "
        r"component of a group is on one scale.",
        long_table(["Group", "N", "Agree", "Largest magnitude", "Mean error", "Largest error", "Closest to the limit", "Of allowed"],
                   table_rows, r">{\hsize=0.75\hsize}Yrrlrr>{\hsize=1.25\hsize}Yr", r"\scriptsize\setlength{\tabcolsep}{4pt}"),
    ]
    if problems:
        out.append(r"\textbf{Problems.} " + "; ".join(escape(p) for p in problems) + ".")
    failing = [row for row in rows if not row.agrees]
    if failing:
        out.append(rf"\textbf{{Numbers outside the allowed difference ({len(failing)}).}}")
        out.append(comparison_table(failing, units))
    out.append(r"\begin{center}\includegraphics[width=0.95\linewidth,height=0.4\textheight,keepaspectratio]{figures/differences.png}\end{center}")
    return "\n\n".join(out)


def model_section(record: dict, record_path: Path, deck, solution, units: str, figures: Path) -> str:
    base = record_path.parent
    out = []
    spec_path = (base / record["spec"]).resolve() if not record["spec"].startswith("none") else None
    labels = UNIT_LABEL[units]
    length = lambda v: number(from_si(v, "length", units), 6)  # noqa: E731
    if spec_path is not None and spec_path.is_file():
        spec = load_spec(spec_path)
        model = build_model(spec)
        plot_model_module.plot_model(model, figures / "model.png", units)
        out.append(heading(1, "The spec the model is generated from"))
        out.append("The model is not drawn by hand: one file states the coupon kind, dimensions, mesh controls, layup, material with its "
                   "out-of-plane constants, grips, loading, probes and output requests, and the writers generate the complete deck for each solver "
                   "from it (ADR-0030). Every key is required and every invalid combination is refused by name. The file, as committed:")
        out.append(file_listing(spec_path))
        out.append(r"\begin{center}\includegraphics[width=0.62\linewidth,height=0.8\textheight,keepaspectratio]{figures/model.png}\end{center}")
        out.append(r"{\small\color{muted}The generated model before any solve: element sets, grip node sets, probes, and the loading at the moving grip.}")
    else:
        out.append(heading(1, "The deck"))
        out.append("This model was not generated from a spec: both solvers ran the same hand-built deck, read by our reader "
                   r"(\texttt{abaqus\_reader.py}) into the kernel. " + escape(record["spec"]) + ".")
    kernel_deck = (base / record["deck_kernel"]).resolve()
    out.append(heading(1, "What the kernel read"))
    comments = header_comments(kernel_deck)
    if comments:
        out.append(rf"The deck {code(rel(kernel_deck))} (SHA-256 {code(record['deck_kernel_sha256'][:16])}\ldots) opens with these header lines:")
        out.append(r"\begin{plainfile}" + "\n" + listing_text("\n".join(comments)) + "\n" + r"\end{plainfile}")
    facts: list[tuple[str, str]] = []
    for part in deck.parts.values():
        elements = f"{len(part.elements)} {part.elements.element_type}" if part.elements is not None else "no"
        facts.append((escape(f"Part {part.name}"), escape(f"{len(part.nodes)} nodes, {elements} elements, {len(part.nsets)} node sets, {len(part.elsets)} element sets")))
        for section in part.sections:
            layers = expanded_layers(section)
            angles = ", ".join(f"{layer.angle_deg:g}" for layer in layers)
            thickness = from_si(layers[0].thickness, "length", units) if layers else 0.0
            facts.append((escape(f"Shell section on {section.elset}"),
                          escape(f"{len(layers)} plies" + (", listed as the symmetric half" if section.symmetric else "") + f", orientation {section.orientation or 'global'}; "
                                 f"angles bottom-first [{angles}]; ply thickness {thickness:g} {labels['length']}")))
    for name, material in deck.materials.items():
        if material.elastic is not None:
            e = material.elastic
            stress = lambda v: from_si(v, "stress", units)  # noqa: E731
            text = (f"{e.kind}: E1 = {stress(e.E1):g}, E2 = {stress(e.E2):g}, nu12 = {e.nu12:g}, G12 = {stress(e.G12):g}"
                    + (f", G13 = {stress(e.G13):g}, G23 = {stress(e.G23):g}" if e.G13 is not None else "") + f" ({labels['stress']})")
            if material.fail_stress is not None:
                f = material.fail_stress
                text += (f"; fail stress Xt = {stress(f.Xt):g}, Xc = {stress(f.Xc):g}, Yt = {stress(f.Yt):g}, Yc = {stress(f.Yc):g}, S = {stress(f.S):g}"
                         + (f", f* = {f.f_star:g}" if f.f_star is not None else ""))
            facts.append((escape(f"Material {name}"), escape(text)))
    facts.append(("Assembly reference nodes", escape(str(len(deck.assembly_nodes)))))
    for coupling in deck.couplings:
        facts.append((escape(f"Coupling {coupling.name}"),
                      escape(f"reference node {node_name(reference_node(deck, coupling))} drives {len(coupled_nodes(deck, coupling))} nodes (dofs 1 and 2; the reference node's rotations are fixed)")))
    for boundary in deck.model_boundaries + tuple(b for step in deck.steps for b in step.boundaries):
        target = boundary.target if isinstance(boundary.target, str) else node_name(boundary.target)
        value = f" = {from_si(boundary.value, 'length', units):g} {labels['length']}" if boundary.value else ""
        facts.append((escape(f"Boundary on {target}"), escape(f"dofs {boundary.dof_first} to {boundary.dof_last}{value}")))
    for step in deck.steps:
        for load in step.cloads:
            target = load.target if isinstance(load.target, str) else node_name(load.target)
            facts.append((escape(f"Load on {target}"), escape(f"dof {load.dof}, {from_si(load.value, 'force', units):g} {labels['force']}")))
        facts.append((escape(f"Step {step.name}"), escape("linear static" + (", nlgeom" if step.nlgeom else ""))))
    if deck.ignored_keywords:
        facts.append(("Skipped output requests", escape(", ".join(sorted({k.split(': ')[1] for k in deck.ignored_keywords})))))
    for note in deck.notes:
        facts.append(("Reader note", escape(note)))
    out.append(kv_table(facts))
    plot_deck_module.plot_solution(deck, solution, units, figures / "solution.png", title=f"The kernel's solution, units {units}")
    out.append(heading(1, "The kernel's solution"))
    mesh = solution.mesh
    out.append(escape(f"{mesh.node_count} nodes, {mesh.element_count} elements, {len(mesh.sections)} section(s). The largest axial displacement is "
                      f"{from_si(float(np.max(np.abs(solution.displacement[:, 1]))), 'length', units):.6g} {labels['length']}; the sum of all reactions is "
                      f"[{from_si(solution.total_reaction[0], 'force', units):.3g}, {from_si(solution.total_reaction[1], 'force', units):.3g}] {labels['force']} "
                      f"and the largest residual at a free degree of freedom {solution.free_residual:.3g} N, both roundoff when the model is in equilibrium."))
    out.append(r"\begin{center}\includegraphics[width=\linewidth,height=0.6\textheight,keepaspectratio]{figures/solution.png}\end{center}")
    out.append(r"{\small\color{muted}Mesh and deformed shape, the three membrane strains, the axial section force and the maximum-stress first-ply-failure map, all computed by the kernel while this document was built.}")
    return "\n\n".join(out)


def rebuild_section(record: dict, record_path: Path, deck, solution, units: str) -> str:
    """The step-by-step guide to recreating the model in Abaqus/CAE and PrePoMax, from the deck's facts (rebuild.py)."""
    base = record_path.parent
    spec_path = (base / record["spec"]).resolve() if not record["spec"].startswith("none") else None
    material_lines, material_source, transverse = (), None, None
    if spec_path is not None and spec_path.is_file():
        spec = load_spec(spec_path)
        material = spec_material(spec)
        material_lines, material_source = material.citation_lines, f"{material.source}; rights class {material.rights}"
        t = spec.material.transverse
        mpa = lambda v: from_si(v, "stress", units)  # noqa: E731  the loaded spec is in SI
        transverse = (f"G13 {mpa(t.G13):g}, G23 {mpa(t.G23):g} ({units.split('-')[1]}); "
                      + ("transverse isotropy stated (E3 = E2, nu13 = nu12)" if t.transverse_isotropy else f"E3 {mpa(t.E3):g}, nu13 {t.nu13:g} given")
                      + ("; plane_stress = true: nu13 = nu23 = 0 written for CalculiX" if t.plane_stress else f"; nu23 {t.nu23:g}"))
    else:
        spec_path = None
    helpers = rebuild.Helpers(escape=escape, code=code, inline=inline, number=number, heading=heading, kv_table=kv_table, long_table=long_table,
                              listing_text=listing_text)
    context = rebuild.Context(facts=model_facts(deck, solution), deck=deck, units=units, kernel_deck=(base / record["deck_kernel"]).resolve(),
                              reference_deck=(base / record["deck_reference"]).resolve(), kernel_sha256=record["deck_kernel_sha256"],
                              reference_sha256=record["deck_reference_sha256"], solver_name=record["solver"]["name"], spec_path=spec_path,
                              spec_material_lines=material_lines, spec_material_source=material_source, spec_transverse=transverse,
                              record_title=record["title"], report_date=date.today().isoformat())
    return rebuild.render(context, helpers)


def clt_section(deck, solution, record: dict, rows: list[ComparisonRow], units: str) -> str:
    labels = UNIT_LABEL[units]
    try:
        check = laminate_check(deck, solution)
    except KernelError as exc:
        return ("Classical laminate theory gives no closed form for this deck: " + escape(str(exc)) + ". The comparison below stands on the kernel alone.")
    stiffness = lambda v: v / {"mm-MPa": 1e3, "m-Pa": 1.0}[units]  # noqa: E731  N/m to N/mm, or unchanged
    A = check.A
    a_rows = "\n".join(r" & ".join(mnumber(stiffness(A[i, j]), 6) for j in range(3)) + r" \\" for i in range(3))
    c = check.constants
    gpa = lambda v: f"{v / 1e9:.3f}"  # noqa: E731
    out = [
        "Before any finite element, the engine's classical laminate theory predicts the coupon as a uniaxial test with free lateral edges: "
        r"the laminate's membrane stiffness $\mathbf{A}$ from its plies, then the strain state with $N_x = N_{xy} = 0$ and "
        + (r"$\varepsilon_y$ set by the pull over the free length between the gripped node rows" if check.control == "displacement"
           else r"$N_y$ set by the applied load over the width")
        + r", the section force $N_y$, the reaction $N_y w$, and every ply's stress in material axes from $\bar{\mathbf{Q}}^{(k)}\boldsymbol{\varepsilon}$ "
        r"(engine theory, Sections 3 and 4). Grips that hold the whole tab also prevent lateral contraction there, so the kernel's reaction is "
        r"expected above this value and its centre-element state close to it; how close is a check on both solvers.",
        escape(f"Read from the deck: width {from_si(check.width_m, 'length', units):g} {labels['length']}, free length between the gripped groups "
               f"{from_si(check.free_length_m, 'length', units):g} {labels['length']}, applied "
               + (f"pull {from_si(check.applied, 'length', units):g} {labels['length']}" if check.control == "displacement" else f"load {check.applied:g} N")
               + f", laminate thickness {from_si(check.thickness_m, 'length', units):g} {labels['length']}, {len(check.plies)} plies. "
               f"The kernel's centre element is {check.centre_element}, the element whose centroid is nearest the coupon's centre."),
        r"\textbf{Membrane stiffness} $\mathbf{A}$ in " + escape(labels["stiffness"]) + r" and engineering constants:",
        r"\begin{equation*}\mathbf{A} = \begin{bmatrix}" + "\n" + a_rows + "\n" + r"\end{bmatrix},\end{equation*}"
        + rf"\begin{{equation*}}E_x = {gpa(c.Ex)}\ \text{{GPa}},\quad E_y = {gpa(c.Ey)}\ \text{{GPa}},\quad G_{{xy}} = {gpa(c.Gxy)}\ \text{{GPa}},\end{{equation*}}"
        + rf"\begin{{equation*}}\nu_{{xy}} = {c.nu_xy:.4f},\quad \nu_{{yx}} = {c.nu_yx:.4f},\quad \eta_{{xs}} = {c.eta_xs:.4f},\quad \eta_{{ys}} = {c.eta_ys:.4f}.\end{{equation*}}",
    ]
    # the state: CLT | kernel centre | reference at the centre element, when the record has it
    reference_strain = next((r for r in rows if r.group == "strain" and r.name == check.centre_element), None)
    def ref(group: str, component: int, ply: int | None = None) -> str:
        for r in rows:
            if r.group == group and r.name == check.centre_element and r.component == component and r.ply == ply:
                return number(r.reference)
        return "--"
    def diff(a: float, b: float, scale: float) -> str:
        """Relative to the laminate-theory value; -- when that value is zero against its vector (roundoff, not a prediction)."""
        return percent(abs(b - a) / abs(a)) if abs(a) > 1e-9 * scale else "--"
    state_rows = []
    strain_scale = float(np.max(np.abs(check.strain)))
    for i, name in enumerate(("eps_x", "eps_y", "gamma_xy")):
        clt, kernel = float(check.strain[i]), float(check.kernel_strain[i])
        state_rows.append(rf"{MATH[name]} & -- & {number(clt)} & {number(kernel)} & {diff(clt, kernel, strain_scale)} & {ref('strain', i)} \\")
    force_scale = float(np.max(np.abs(check.section_force)))
    for i, name in enumerate(("N_x", "N_y", "N_xy")):
        clt, kernel = from_si(float(check.section_force[i]), "force_per_length", units), from_si(float(check.kernel_section_force[i]), "force_per_length", units)
        state_rows.append(rf"{MATH[name]} & {escape(labels['force_per_length'])} & {number(clt)} & {number(kernel)} & {diff(clt, kernel, force_scale)} & {ref('section_force', i)} \\")
    reaction_ref = next((number(r.reference) for r in rows if r.group == "rf" and r.component == 1 and r.reference > 0), "--")
    state_rows.append(rf"Reaction $R_y$ of the pulled group & {escape(labels['force'])} & {number(from_si(check.reaction_N, 'force', units))} & "
                      rf"{number(from_si(check.kernel_reaction_N, 'force', units))} & {diff(check.reaction_N, check.kernel_reaction_N, abs(check.reaction_N))} & {reaction_ref} \\")
    out.append(long_table(["Quantity", "Unit", "Laminate theory", "Kernel, centre element", "Difference", "Reference solver"], state_rows,
                          r"Ylrrrr", r"\footnotesize"))
    ply_rows = []
    stress_scale = float(np.max(np.abs(check.ply_stress_12)))
    for k, ply in enumerate(check.plies):
        for i, name in enumerate(("sigma_1", "sigma_2", "tau_12")):
            clt, kernel = from_si(float(check.ply_stress_12[k, i]), "stress", units), from_si(float(check.kernel_ply_stress_12[k, i]), "stress", units)
            ply_rows.append(rf"{k + 1} & {ply.angle_deg:g} & {MATH[name]} & {number(clt)} & {number(kernel)} & {diff(clt, kernel, stress_scale)} & {ref('ply_stress_local', i, k + 1)} \\")
    out.append(rf"\textbf{{Ply stresses in material axes}} at the centre element, {escape(labels['stress'])} (bottom ply first; "
               r"a difference marked -- is a component whose laminate-theory value is zero):")
    out.append(long_table(["Ply", "Angle", "Comp.", "Laminate theory", "Kernel", "Difference", "Reference solver"], ply_rows,
                          r"rrlrrr>{\raggedleft\arraybackslash}X", r"\footnotesize"))
    if reference_strain is None:
        out.append(r"{\small\color{muted}The record holds no values at the kernel's centre element, so the last column is empty; the per-element comparison is in Section~\ref{sec:comparison}.}")
    return "\n\n".join(out)


def theory_section() -> str:
    return ("These are the equations our number for every quantity in this document went through, each followed by the function that computes it, "
            r"copied from the \texttt{fea} source with its real line numbers. The text is \texttt{fea/docs/theory.md}, the same source the engine manual prints."
            + "\n\n" + manual.theory("anisotropy_fea"))


def reference_section(record: dict, record_path: Path) -> str:
    solver = record["solver"]
    base = record_path.parent
    facts = [(escape(k.replace("_", " ").capitalize()), escape(str(v))) for k, v in solver.items()]
    out = [kv_table(facts)]
    known = record.get("known_differences", {})
    if known:
        out.append(heading(1, "Known differences between the two formulations"))
        out.append(kv_table([("Our kernel", escape(known.get("kernel", ""))), ("Reference", escape(known.get("reference", "")))], "p{2.5cm}Y"))
    conventions_name = solver.get("conventions")
    if conventions_name:
        conventions_path = (base / conventions_name) if (base / conventions_name).is_file() else fea_paths.CONVENTIONS
        if conventions_path.is_file():
            conventions = tomllib.loads(conventions_path.read_text(encoding="utf-8"))
            out.append(heading(1, "How the solver reports composite results (detected, not assumed)"))
            out.append(rf"The mapping from the solver's output to our per-ply quantities depends on its layer order, integration-point order, axes and shear-strain "
                       rf"convention. They were detected by running the solver and are recorded in {code(rel(conventions_path))}; the record tool refuses a run on another "
                       r"major version until the detection is repeated (ADR-0030, risk R-18). The file, with the evidence for each item in its comments:")
            out.append(file_listing(conventions_path))
    reference_deck = (base / record["deck_reference"]).resolve()
    out.append(heading(1, "The deck the reference solver ran"))
    if record["deck_reference"] == record["deck_kernel"]:
        out.append(r"The same deck as the kernel's, described in Section~\ref{sec:model}.")
        out.append(kv_table([("File", code(rel(reference_deck))), ("SHA-256", code(record["deck_reference_sha256"]))]))
    else:
        comments = header_comments(reference_deck)
        out.append(kv_table([("File", code(rel(reference_deck))), ("SHA-256", code(record["deck_reference_sha256"]))]))
        out.append("Its header states what was written and why:")
        if comments:
            out.append(r"\begin{plainfile}" + "\n" + listing_text("\n".join(comments)) + "\n" + r"\end{plainfile}")
    return "\n\n".join(out)


def method_section(record: dict) -> str:
    solver = record["solver"]
    out = [
        r"A record stores the reference solver's numbers in the deck's units with their provenance and both decks' digests; the kernel is run on the kernel "
        r"deck while the comparison is made and every number is judged by the rule"
        r"\begin{equation*} |\,\text{kernel} - \text{reference}\,| \le \text{tolerance} \times \max\bigl(|\text{reference}|,\ \text{floor} \times \max_\text{group} |\text{reference}|\bigr), \end{equation*}"
        r"so a component that is small against its group (a roundoff-sized shear stress beside the axial stress of a 0-degree ply) is judged against the group's "
        r"largest magnitude and not against itself. A component the solver did not report is written \texttt{nan} and skipped. A changed deck is noticed by its "
        r"digest before any number is compared. The code:",
        listing("validate_record"), listing("compare_record"), listing("record_disagreements"),
    ]
    if solver["source"] == "dat":
        out.append(heading(1, "From the CalculiX .dat to our quantities"))
        out.append(r"CalculiX prints nodal forces, displacements and the stresses, strains and coordinates of every integration point of the probe elements. The grip "
                   r"reaction is the printed total over the grip node set; the per-ply values are the mean of each layer's integration points, grouped by their "
                   r"$z$ coordinate using the detected conventions, then rotated into the ply's material axes with the engine's transformations; the printed tensor "
                   r"shear strain is doubled into engineering shear.")
        out.append(listing("parse_dat"))
        out.append(listing("layer_values"))
        out.append(listing("reference_quantities"))
        out.append(file_listing(ROOT / "fea/tools/record_from_dat.py", python=True))
    elif solver["source"] == "csv":
        out.append(heading(1, "From the Abaqus/CAE field report to our quantities"))
        out.append(r"Abaqus/CAE writes one row per element and section point (Report, Field Output). The reader requires the integration point to be 1, so the "
                   r"value is the element centroid's, takes the layer from the section-point text with layer 1 at the bottom, accepts repeated header blocks, and "
                   r"refuses anything else by line. Several reports map into the record's ply tables; a component no report holds is \texttt{nan}; Mises goes to its own group.")
        out.append(listing("read_field_report"))
        out.append(listing("report_quantities"))
        out.append(listing("ply_mises"))
        out.append(file_listing(ROOT / "fea/tools/record_from_report.py", python=True))
    return "\n\n".join(out)


def comparison_table(rows: list[ComparisonRow], units: str, size: str = r"\scriptsize") -> str:
    labels = UNIT_LABEL[units]
    body = []
    for row in rows:
        kind = GROUP_KIND.get(row.group)
        unit = escape(labels[kind]) if kind else "--"
        where = escape(row.name) + (f", ply {row.ply}" if row.ply is not None else "")
        body.append(rf"{where} & {MATH[row.component_name]} ({unit}) & {compact(row.reference)} & {compact(row.kernel)} & {compact(row.difference, 3)} & "
                    rf"{percent(row.relative, 2)} & {row.of_allowed:.2f} & " + (r"\textcolor{passgreen}{yes}" if row.agrees else r"\textcolor{red}{\textbf{no}}") + r" \\")
    return long_table(["Where", "Component (unit)", "Reference", "Kernel", "Kernel $-$ ref.", "Rel. to ref.", "Of allowed", "Agrees"], body,
                      r">{\raggedright\arraybackslash}p{2.9cm}lrrrrrY", size + r"\setlength{\tabcolsep}{2.5pt}")


def comparison_section(rows: list[ComparisonRow], summaries: list[GroupSummary], units: str, map_drawn: bool, full_tables: bool) -> str:
    out = [r"Reference values are the record's; kernel values were computed during the build. ``Rel. to ref.'' is $|$kernel $-$ reference$|$ divided by "
           r"$|$reference$|$ (-- when the reference is zero); ``Of allowed'' is $|$kernel $-$ reference$|$ divided by the difference the record's rule allows "
           r"for that number, so below 1 agrees. Names read instance.label for nodes and elements; ply 1 is the bottom ply."]
    if map_drawn:
        out.append(r"\begin{center}\includegraphics[width=0.7\linewidth,height=0.75\textheight,keepaspectratio]{figures/element-map.png}\end{center}")
    for s in summaries:
        members = [row for row in rows if row.group == s.group]
        out.append(heading(1, GROUP_TITLE.get(s.group, s.group)))
        out.append(escape(f"{s.count} numbers, {s.agreeing} agree; the largest magnitude in the group is {s.scale:.6g}; the mean error is "
                          f"{100 * s.mean_relative_to_scale:.3f} % and the largest {100 * s.max_relative_to_scale:.3f} % of it."))
        if len(members) <= 60 or full_tables and len(rows) <= FULL_TABLE_LIMIT:
            out.append(comparison_table(members, units))
        else:
            worst = sorted(members, key=lambda row: row.of_allowed, reverse=True)[:20]
            out.append(rf"The twenty numbers closest to the allowed difference (of {len(members)}):")
            out.append(comparison_table(worst, units))
    return "\n\n".join(out)


def reading_section(record_path: Path) -> tuple[str, bool]:
    note = record_path.with_suffix(".md")
    if not note.is_file():
        return (rf"No reading has been written for this record yet. To add one, write {code(rel(note))} in Markdown beside the record: what the numbers "
                r"show, what explains each difference, what is verified and what is UNVERIFIED, and what would settle it. This section then prints it.", False)
    text = note.read_text(encoding="utf-8")
    title = re.search(r"^# (.+)$", text, re.M)
    body = text.split("\n", 1)[1] if title else text
    return (rf"{{\small\color{{muted}}From {code(rel(note))}" + (rf": {inline(title.group(1))}" if title else "") + ".}\n\n" + convert(body), True)


def appendix_record(record_path: Path) -> str:
    lines = record_path.read_text(encoding="utf-8").splitlines()
    if len(lines) <= FULL_TABLE_LIMIT:
        return file_listing(record_path)
    return (rf"The record has {len(lines)} lines; its first 40 follow and the whole file is {code(rel(record_path))}." + "\n\n"
            + file_listing(record_path, last=40))


# --------------------------------------------------------------------------------------------- the document

def output_dir(record_path: Path, requested: Path | None) -> Path:
    if requested is not None:
        return requested
    if ".local" in record_path.resolve().parts:
        return record_path.parent / "report" / record_path.stem
    return HERE / "build" / record_path.stem


def build(record_path: Path, out: Path | None, pdf: bool, full_tables: bool, theory: bool) -> Path:
    record_path = record_path.resolve()
    record = load_record(record_path)
    units = record["units"]
    out_dir = output_dir(record_path, out)
    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    rows, problems = comparison_rows(record)
    summaries = summarize(rows)
    deck, solution = solve_record(record)
    difference_figure(rows, figures / "differences.png")
    map_drawn = element_map(rows, summaries, element_centroids(solution, units), solution, units, figures / "element-map.png")
    reading, reading_exists = reading_section(record_path)
    stem = record_path.stem
    short = record["title"].split(":")[0]
    parts = [
        r"\documentclass[11pt,letterpaper]{article}", PREAMBLE,
        rf"\hypersetup{{pdftitle={{{escape(record['title'])}}}}}",
        r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyhead[L]{{\sffamily\footnotesize\color{{muted}}Anisotropy AI \textperiodcentered{{}} Model comparison \textperiodcentered{{}} {inline(short)}}}",
        r"\fancyhead[R]{\sffamily\footnotesize\color{muted}\thepage}",
        r"\fancyfoot[C]{\sffamily\scriptsize\color{muted}Internal use. A solver-to-solver comparison is verification, not validation against a coupon test.}",
        r"\begin{document}",
        title_page(record, record_path, rows, problems),
        r"\tableofcontents\clearpage",
        r"\section{About this document}", about_section(reading_exists),
        r"\section{Does the kernel reproduce the reference solver?}\label{sec:summary}", summary_section(record, rows, problems, summaries, units),
        r"\section{The model}\label{sec:model}", model_section(record, record_path, deck, solution, units, figures),
        r"\section{How to rebuild this model, step by step}\label{sec:rebuild}", rebuild_section(record, record_path, deck, solution, units),
        r"\section{Classical laminate theory, the hand check}\label{sec:clt}", clt_section(deck, solution, record, rows, units),
        r"\section{The kernel: equations and code}\label{sec:theory}",
        theory_section() if theory else r"Omitted in this build (\texttt{--no-theory}); the equations and code are in \texttt{fea/docs/theory.md} and the engine manual.",
        r"\section{The reference solver}\label{sec:reference}", reference_section(record, record_path),
        r"\section{How the numbers were mapped and judged}\label{sec:method}", method_section(record),
        r"\section{Every compared number}\label{sec:comparison}", comparison_section(rows, summaries, units, map_drawn, full_tables),
        r"\section{Reading}\label{sec:reading}", reading,
        r"\appendix", r"\section{The record}", appendix_record(record_path),
    ]
    if len(rows) > 60 and (full_tables or len(rows) <= FULL_TABLE_LIMIT):
        parts += [r"\section{The full comparison table}", comparison_table(rows, units)]
    parts.append(r"\end{document}")
    tex = out_dir / f"{stem}.tex"
    tex.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    if manual.UNMAPPED:
        print("Characters without a LaTeX mapping (check how they render):", " ".join(sorted(manual.UNMAPPED)))
    print(f"{len(rows)} numbers compared, {sum(r.agrees for r in rows)} agree; LaTeX written to {tex}")
    compiler = manual.tectonic()
    if not pdf:
        return tex
    if compiler is None:
        print("Tectonic not found; no PDF.")
        return tex
    subprocess.run([compiler, "--outdir", str(out_dir), str(tex)], check=True)
    print("Document written to", out_dir / f"{stem}.pdf")
    return out_dir / f"{stem}.pdf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record", type=Path, nargs="?", help="a comparison record (TOML)")
    parser.add_argument("--all", action="store_true", help="every committed record (fea/models/*/records, fea/checks/*/records)")
    parser.add_argument("--out", type=Path, default=None, help="output folder (default: docs/models/build/<record>, or <record folder>/report/<record> for a local record)")
    parser.add_argument("--no-pdf", action="store_true", help="write the LaTeX only")
    parser.add_argument("--no-theory", action="store_true", help="leave out the kernel theory and code section")
    parser.add_argument("--full-tables", action="store_true", help=f"print every compared number even when there are more than {FULL_TABLE_LIMIT}")
    args = parser.parse_args()
    if args.all == (args.record is not None):
        raise SystemExit("give a record or --all, not both and not neither")
    records = fea_paths.all_records() if args.all else [args.record]
    for path in records:
        build(path, args.out if not args.all else None, pdf=not args.no_pdf, full_tables=args.full_tables, theory=not args.no_theory)


if __name__ == "__main__":
    main()
