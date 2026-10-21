"""Builds one document per solved problem: the problem as the validation case states it, every step the engine takes
with its equation and the code that computes it, every intermediate number, the source's answers next to the engine's,
and the reading (ADR-0033).

From the repository root:

    uv run --project fea python docs/problems/build.py engine/validation/cases/se142-hw3-p3a-boron-symmetric.toml
    uv run --project fea python docs/problems/build.py --all                 # every committed case, plus an index
    uv run --project fea python docs/problems/build.py .local/homework/code/course-reader/cr-5-9-as4.toml

A committed case's document is written to docs/problems/build/<case>/ (git-ignored, rebuilt like the manual; CI uploads
the PDFs); a case under .local/ goes to report/<case>/ beside the case and stays there. The LaTeX file is self-contained;
with Tectonic installed the PDF is compiled next to it. The prose, equations and code listings come from the same
converters as the engine manual (docs/manual/build.py) and the same theory file (engine/docs/theory.md), so the two
cannot disagree. Every number in the document is the source's (from the case file) or the engine's, computed while the
document is built; nothing is typed in.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import math
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ROOT / "engine/validation/cases"
READINGS = HERE / "readings"
PREAMBLE = (ROOT / "docs/models/preamble.tex").read_text(encoding="utf-8")
THEORY = ROOT / "engine/docs/theory.md"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


manual = load_module("anisotropy_manual_build", ROOT / "docs/manual/build.py")
# The manual lists the engine's physics modules; a problem document also lists the case runner that produced its numbers.
manual.PACKAGES["anisotropy_engine"] = (manual.PACKAGES["anisotropy_engine"][0], manual.ENGINE_MODULES + ("cases",))

from anisotropy_engine.cases import (APPLIED_KINDS, LOAD_NAMES, buckling_result, compare, first_ply_failures, load_case,  # noqa: E402
                                     solve_case)
from anisotropy_engine.engineering import engineering_constants  # noqa: E402
from anisotropy_engine.lamina import reduced_compliance, reduced_stiffness  # noqa: E402
from anisotropy_engine.laminate import abd_matrices, ply_interfaces  # noqa: E402
from anisotropy_engine.response import abd_compliance  # noqa: E402
from anisotropy_engine.rotation import transformed_compliance, transformed_reduced_stiffness  # noqa: E402
from anisotropy_engine.thermal import thermal_expansion_xy  # noqa: E402
from anisotropy_engine.units import UNIT_SYSTEMS  # noqa: E402

escape, code, inline, number, heading = manual.escape, manual.code, manual.inline, manual.number, manual.heading

STEP_WIDTH = 5  # significant digits for matrices and tables; the comparison table uses six
KIND_DESCRIPTION = {
    "loads": "mechanical force and moment resultants $N_x, N_y, N_{xy}, M_x, M_y, M_{xy}$",
    "stress": r"a stress averaged through the thickness, $\sigma_x, \sigma_y, \tau_{xy}$, so $N = \sigma h$",
    "strains": r"mid-plane strains and curvatures $\varepsilon^0_x, \varepsilon^0_y, \gamma^0_{xy}, \kappa_x, \kappa_y, \kappa_{xy}$",
    "local_stress": r"a stress in the fiber axes of the single lamina, $\sigma_1, \sigma_2, \tau_{12}$",
    "local_strain": r"a strain in the fiber axes of the single lamina, $\varepsilon_1, \varepsilon_2, \gamma_{12}$",
    "forces_curvature": r"known force resultants $N_x, N_y, N_{xy}$ with prescribed curvatures $\kappa_x, \kappa_y, \kappa_{xy}$; the moments are solved",
    "mixed": "one known quantity of each load-deformation pair; the other quantity of each pair is solved",
}
SYMBOL = {"Nx": "N_x", "Ny": "N_y", "Nxy": "N_{xy}", "Mx": "M_x", "My": "M_y", "Mxy": "M_{xy}",
          "sigma_x": r"\sigma_x", "sigma_y": r"\sigma_y", "tau_xy": r"\tau_{xy}", "eps_x": r"\varepsilon^0_x", "eps_y": r"\varepsilon^0_y",
          "gamma_xy": r"\gamma^0_{xy}", "kappa_x": r"\kappa_x", "kappa_y": r"\kappa_y", "kappa_xy": r"\kappa_{xy}"}
PAIR_UNIT = {"Nx": "N", "Ny": "N", "Nxy": "N", "Mx": "M", "My": "M", "Mxy": "M", "sigma_x": "stress", "sigma_y": "stress", "tau_xy": "stress",
             "eps_x": None, "eps_y": None, "gamma_xy": None, "kappa_x": "kappa", "kappa_y": "kappa", "kappa_xy": "kappa"}



# --------------------------------------------------------------------------------------------- small helpers

def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def mnumber(value: float, digits: int = STEP_WIDTH) -> str:
    """A number inside math mode."""
    if math.isnan(value):
        return r"\text{--}"
    text = f"{value:.{digits}g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        return rf"{mantissa}\times10^{{{int(exponent)}}}"
    return text


def unit_math(label: str) -> str:
    """A unit label from units.py inside math mode: '10^6 lb/in' -> 10^{6}\\,\\text{lb/in}; 'lb*in/in' -> \\text{lb}\\cdot\\text{in/in}."""
    if not label:
        return ""
    prefix = ""
    power = re.match(r"10\^(\d+) (.*)", label)
    if power:
        prefix, label = rf"10^{{{power[1]}}}\,", power[2]
    # \ensuremath: the same unit string follows a closed $...$ in running text and sits inside display matrices
    return r"\ensuremath{\ " + prefix + r"\cdot".join(rf"\text{{{escape(part)}}}" for part in label.split("*")) + "}"


RESIDUE = 1e-10  # entries smaller than this fraction of the largest in the same matrix or table are printed as 0


def tidy(values, reference: float | None = None) -> np.ndarray:
    """Floating-point residue (a 1e-15 shear coupling in a balanced laminate) printed as 0, judged against the group's largest magnitude."""
    values = np.asarray(values, dtype=float)
    scale = reference if reference is not None else (float(np.abs(values).max()) if values.size else 0.0)
    if scale == 0.0:
        return values
    out = values.copy()
    out[np.abs(out) < RESIDUE * scale] = 0.0
    return out


def matrix(name: str, values: np.ndarray, unit: str = "") -> str:
    rows = r" \\ ".join(" & ".join(mnumber(float(v)) for v in row) for row in np.atleast_2d(tidy(values)))
    return rf"\[ {name} = \begin{{bmatrix}} {rows} \end{{bmatrix}}{unit} \]"


def vector(name: str, values, unit: str = "") -> str:
    body = r" \\ ".join(mnumber(float(v)) for v in np.atleast_1d(tidy(values)))
    return rf"\[ {name} = \begin{{Bmatrix}} {body} \end{{Bmatrix}}{unit} \]"


def kv_table(rows: list[tuple[str, str]], spec: str = r">{\raggedright\arraybackslash}p{4.2cm}Y") -> str:
    body = "\n".join(rf"{label} & {value} \\" for label, value in rows)
    return "\n".join([r"{\small", rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", body, r"\bottomrule", r"\end{xltabular}", "}"])


def long_table(header: list[str], rows: list[str], spec: str, size: str = r"\small") -> str:
    head = " & ".join(r"\textbf{" + h + "}" for h in header) + r" \\"
    return "\n".join(["{" + size, rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", head, r"\midrule", r"\endhead",
                      *rows, r"\bottomrule", r"\end{xltabular}", "}"])


def file_listing(path: Path) -> str:
    text = manual_listing_text(path.read_text(encoding="utf-8"))
    return rf"\filefrom{{{code(rel(path))}}}" + "\n" + r"\begin{plainfile}" + "\n" + text + "\n" + r"\end{plainfile}"


def manual_listing_text(text: str) -> str:
    return "".join(ch if ord(ch) < 256 else {"—": "--", "–": "-", "’": "'"}.get(ch, "?") for ch in text)


def git_commit() -> str:
    try:
        commit = manual.run("git", "rev-parse", "--short", "HEAD")
        if manual.run("git", "status", "--porcelain", "--untracked-files=no"):
            commit += " + local changes"
        return commit
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def engine_version() -> str:
    try:
        return importlib.metadata.version("anisotropy-engine")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


# --------------------------------------------------------------------------------------------- the theory, by section

def theory_fragments() -> dict[str, str]:
    """engine/docs/theory.md split at its ## and ### headings: {title without numbering or module name: body}."""
    fragments: dict[str, str] = {}
    current, body = None, []
    for line in THEORY.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^(#{2,3}) (.+)$", line)
        if match:
            if current is not None:
                fragments[current] = "\n".join(body)
            title = re.sub(r"^\d+\.\s*", "", match.group(2))
            current, body = re.sub(r"\s*\(`[^`]*`\)\s*$", "", title).strip(), []
        elif current is not None:
            body.append(line)
    if current is not None:
        fragments[current] = "\n".join(body)
    return fragments


FRAGMENTS = theory_fragments()


def render_theory(title: str) -> str:
    """One section of the theory as LaTeX, with each marked function's source where its marker is."""
    if title not in FRAGMENTS:
        raise SystemExit(f"{rel(THEORY)} has no section titled {title!r}; sections: {sorted(FRAGMENTS)}")
    out = []
    for kind, payload in manual.blocks(FRAGMENTS[title]):
        if kind == "heading":
            continue
        if kind == "paragraph":
            out.append(inline(payload))
        elif kind == "code-ref":
            out.extend(manual.listing(name, "anisotropy_engine") for name in payload)
        else:
            out.append(manual.convert_block(kind, payload))
    return (rf"{{\small\color{{muted}}From {code(rel(THEORY))}, section ``{escape(title)}'', with the code each marker names.}}" + "\n\n" + "\n\n".join(out))


# --------------------------------------------------------------------------------------------- the units of a case

class Units:
    def __init__(self, system: str):
        self.system = system
        self.table = UNIT_SYSTEMS[system]

    def shown(self, value_si, kind: str | None):
        value = np.asarray(value_si, dtype=float)
        return value if kind is None else value / self.table[kind][0]

    def label(self, kind: str | None) -> str:
        return "" if kind is None else self.table[kind][1]

    def math(self, kind: str | None) -> str:
        return unit_math(self.label(kind))

    def text(self, kind: str | None) -> str:
        return "--" if kind is None else manual.unit_label(self.label(kind))


# --------------------------------------------------------------------------------------------- sections

def title_page(case: dict, case_path: Path, comparisons, problems: list[str]) -> str:
    agreeing = sum(c.agrees for c in comparisons)
    disagreeing = len(comparisons) - agreeing
    if problems:
        verdict = rf"\textbf{{The comparison could not be completed.}} {len(problems)} problem(s): " + "; ".join(escape(p) for p in problems)
    elif disagreeing:
        worst = max((c for c in comparisons if not c.agrees), key=lambda c: abs(c.engine - c.expected) / c.allowed)
        verdict = (rf"\textbf{{The engine does not reproduce this source.}} {disagreeing} of {len(comparisons)} numbers lie outside the case's "
                   rf"tolerance; the largest difference is {code(worst.key)}: source {number(worst.expected)}, engine {number(worst.engine)}.")
    else:
        closest = max(comparisons, key=lambda c: abs(c.engine - c.expected) / c.allowed if c.allowed else 0.0)
        ratio = abs(closest.engine - closest.expected) / closest.allowed if closest.allowed else 0.0
        verdict = (rf"\textbf{{The engine reproduces every number the source states.}} {len(comparisons)} of {len(comparisons)} compared values agree "
                   rf"within the case's tolerance of {number(100 * case['expected']['tolerance'], 3)}\%; the one closest to the limit is {code(closest.key)} "
                   rf"at {number(ratio, 3)} of what is allowed (source {number(closest.expected)}, engine {number(closest.engine)}).")
    facts = [
        ("Case", code(rel(case_path))),
        ("Source of the answers", inline(case["source"].rstrip("."))),
        ("Units of the case", escape(case["units"])),
        ("Engine", escape(f"anisotropy-engine {engine_version()}: classical laminate theory, every function listed in this document")),
        ("Compared", escape(f"{len(comparisons)} numbers, tolerance {100 * case['expected']['tolerance']:g} % of each source value")),
        ("Source commit", code(git_commit())),
        ("Built", escape(date.today().isoformat())),
    ]
    return "\n".join([
        r"\hypersetup{pageanchor=false}", r"\begin{titlepage}", r"\sffamily",
        r"{\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} SOLVED PROBLEM}\par", r"\vspace*{2.5cm}",
        rf"{{\fontsize{{22}}{{28}}\selectfont\bfseries\color{{ink}} {inline(case['title'])}}}\par", r"\vspace{0.6cm}",
        r"{\large\color{muted} The problem as the case states it, every step the engine takes with its equation and code, "
        r"the source's answers next to the engine's, and the reading}\par",
        r"\vspace{2cm}", r"{\small\begin{tabular}{@{}p{3.4cm}p{\dimexpr\linewidth-3.9cm}@{}}",
        *[rf"{label} & {value} \\[0.3ex]" for label, value in facts], r"\end{tabular}}\par", r"\vfill",
        rf"\verdict{{{verdict}}}\par", r"\vspace{0.8cm}",
        r"{\small\color{muted} This document is generated from the repository by \texttt{docs/problems/build.py}: its equations and prose come from "
        r"\texttt{engine/docs/theory.md}, its code listings from the \texttt{engine} source with real line numbers, the source's answers from the "
        r"case file, and every other number from running the engine while it was built. Nothing in it is typed in. To change it, change those "
        r"sources and rebuild.}", r"\end{titlepage}", r"\hypersetup{pageanchor=true}",
    ])


def about_section(reading_exists: bool) -> str:
    rows = [
        (r"\ref{sec:summary}", "Does the engine reproduce the source's answers?", "the case file and the engine, run during the build"),
        (r"\ref{sec:problem}", "What exactly was the problem?", "the case file: materials, plies, loading, what the source states"),
        (r"\ref{sec:steps}", "How did the engine solve it, step by step?", r"\texttt{engine/docs/theory.md}, the \texttt{engine} source, and the numbers computed on the way"),
        (r"\ref{sec:comparison}", "Every compared number", "the case file (source) and the engine"),
        (r"\ref{sec:method}", "How were the inputs read and the numbers judged?", r"\texttt{anisotropy\_engine/cases.py}, listed"),
        (r"\ref{sec:reading}", "What do we make of it, and what remains open?", "a reading note written by a person" if reading_exists else "no reading has been written yet"),
    ]
    body = "\n".join(rf"{a} & {b} & {c} \\" for a, b, c in rows)
    return "\n".join([
        "Every problem the engine has been checked against has a document like this one, separate from the engine manual, so that the "
        "argument for one solved problem can be read on its own: what the problem was, which equations and code produced each number, what "
        "the source says the answer is, and how far apart the two are. The source's numbers come from the case file, where they were copied "
        "from the answer key or the book with a reference; every other number was computed by the engine while this document was built.",
        r"\begin{xltabular}{\linewidth}{lYY}\toprule\textbf{Section} & \textbf{Question} & \textbf{Where the content comes from} \\\midrule",
        body, r"\bottomrule\end{xltabular}"])


def comparison_rows(comparisons, units: Units) -> list[str]:
    rows = []
    for c in comparisons:
        base = c.key.split("[")[0]
        kind = manual.unit_kind(base)
        difference = abs(c.engine - c.expected)
        relative = f"{100 * difference / abs(c.expected):.3f}" + r"\%" if c.expected else number(difference, 2)
        of_allowed = difference / c.allowed if c.allowed else 0.0
        rows.append(rf"{code(c.key).replace(']', ']' + chr(92) + 'allowbreak{}')} & {units.text(kind)} & {number(c.expected)} & {number(c.engine)} & {relative} & "
                    rf"{of_allowed:.2f} & " + (r"\textcolor{passgreen}{yes}" if c.agrees else r"\textcolor{red}{\textbf{no}}") + r" \\")
    return rows


def summary_section(case: dict, comparisons, problems: list[str], units: Units) -> str:
    tolerance = case["expected"]["tolerance"]
    out = [rf"The case allows a difference of {number(100 * tolerance, 3)}\% of each source value; where the source states zero, the engine's value is "
           r"judged against the largest magnitude in the same group of results (a shear coupling term beside the axial stiffnesses, say). "
           r"``Of allowed'' is the difference divided by what the rule allows for that number, so below 1 agrees. Units are the case's."]
    if problems:
        out.append(r"\textbf{Problems.} " + "; ".join(escape(p) for p in problems) + ".")
    failing = [c for c in comparisons if not c.agrees]
    if failing:
        out.append(rf"\textbf{{Numbers outside the allowed difference ({len(failing)}).}}")
        out.append(long_table(["Result", "Unit", "Source", "Engine", "Difference", "Of allowed", "Agrees"], comparison_rows(failing, units),
                              r">{\raggedright\arraybackslash}p{3.6cm}lrrrrY", r"\scriptsize\setlength{\tabcolsep}{3pt}"))
    else:
        out.append(rf"All {len(comparisons)} compared values agree. The full table is Section~\ref{{sec:comparison}}.")
    return "\n\n".join(out)


def material_rows(name: str, lamina, units: Units, solution) -> list[tuple[str, str]]:
    rows = [(r"$E_1$", number(float(units.shown(lamina.E1, "modulus"))) + " " + units.text("modulus")),
            (r"$E_2$", number(float(units.shown(lamina.E2, "modulus"))) + " " + units.text("modulus")),
            (r"$G_{12}$", number(float(units.shown(lamina.G12, "modulus"))) + " " + units.text("modulus")),
            (r"$\nu_{12}$", number(lamina.nu12)), (r"$\nu_{21} = \nu_{12} E_2 / E_1$", number(lamina.nu21))]
    if lamina.thermal_expansion is not None:
        rows += [(r"$\alpha_1$", number(float(units.shown(lamina.thermal_expansion.alpha1, "alpha"))) + " " + units.text("alpha")),
                 (r"$\alpha_2$", number(float(units.shown(lamina.thermal_expansion.alpha2, "alpha"))) + " " + units.text("alpha"))]
    if lamina.strengths is not None:
        s = lamina.strengths
        rows += [(rf"${label}$", number(float(units.shown(getattr(s, field), "stress"))) + " " + units.text("stress"))
                 for label, field in (("F_{1t}", "F1t"), ("F_{1c}", "F1c"), ("F_{2t}", "F2t"), ("F_{2c}", "F2c"), ("F_6", "F6"))]
    if lamina.strain_limits is not None:
        lim = lamina.strain_limits
        rows += [(rf"${label}$", number(float(getattr(lim, field)))) for label, field in
                 ((r"\varepsilon_{1t}", "eps1t"), (r"\varepsilon_{1c}", "eps1c"), (r"\varepsilon_{2t}", "eps2t"), (r"\varepsilon_{2c}", "eps2c"), (r"\gamma_{12}", "gamma12"))]
    library = solution.library.get(name)
    if library is not None:
        rows.append(("Library dataset", escape(f"{library.material_id} / {library.dataset_id} (record {library.record_revision}); rights class {library.rights}; {library.citation}")))
        rows += [("Cited value", escape(f"{v.role} = {v.source_value:g} {v.source_unit} ({v.basis}), page {v.page}: {v.reference_url}")) for v in library.values]
    return rows


def problem_section(case: dict, case_path: Path, solution, units: Units) -> str:
    out = [rf"Source of the answers: {inline(case['source'].rstrip('.'))}. The case file is {code(rel(case_path))}; it is printed in full in the appendix. "
           rf"Numbers below are in the case's units ({escape(case['units'])}); the engine converts them to SI on entry and back on exit (ADR-0002)."]
    out.append(heading(1, "Materials"))
    for name, lamina in solution.materials.items():
        out.append(rf"\textbf{{{escape(name)}}}" + ("" if len(solution.materials) == 1 else ""))
        out.append(kv_table(material_rows(name, lamina, units, solution)))
    out.append(heading(1, "Laminate"))
    z = ply_interfaces(solution.plies)
    rows = [rf"{k + 1} & {number(ply.angle_deg)} & {escape(name)} & {number(float(units.shown(ply.thickness_m, 'length')))} & "
            rf"{number(float(units.shown(z[k], 'length')))} & {number(float(units.shown(z[k + 1], 'length')))} \\"
            for k, (ply, name) in enumerate(zip(solution.plies, solution.ply_materials))]
    h = sum(ply.thickness_m for ply in solution.plies)
    out.append(rf"{len(solution.plies)} plies, listed from the bottom face up (ADR-0004); angles counterclockwise from $x$ to the fibers; total thickness "
               rf"$h = {mnumber(float(units.shown(h, 'length')))}${units.math('length')}. $z$ is measured from the mid-plane, positive upwards.")
    out.append(long_table(["Ply", r"Angle ($^\circ$)", "Material", f"Thickness ({units.text('length')})", f"$z$ bottom ({units.text('length')})", f"$z$ top ({units.text('length')})"],
                          rows, "rrlrrr"))
    out.append(heading(1, "Loading"))
    applied = case["applied"]
    kind = solution.kind
    out.append(rf"The case applies {KIND_DESCRIPTION[kind]}.")
    if kind == "mixed":
        rows = [rf"${SYMBOL[name]}$ & {number(float(value))} & {units.text(PAIR_UNIT[name])} \\" for name, value in applied["mixed"].items() if name != "delta_T"]
        out.append(long_table(["Known quantity", "Value", "Unit"], rows, "lrl"))
    else:
        values = np.asarray(applied[kind], dtype=float)
        names = {"loads": LOAD_NAMES, "stress": ("sigma_x", "sigma_y", "tau_xy"), "strains": ("eps_x", "eps_y", "gamma_xy", "kappa_x", "kappa_y", "kappa_xy"),
                 "local_stress": (r"\sigma_1", r"\sigma_2", r"\tau_{12}"), "local_strain": (r"\varepsilon_1", r"\varepsilon_2", r"\gamma_{12}"),
                 "forces_curvature": ("Nx", "Ny", "Nxy", "kappa_x", "kappa_y", "kappa_xy")}[kind]
        kinds = {"loads": ("N",) * 3 + ("M",) * 3, "stress": ("stress",) * 3, "strains": (None,) * 3 + ("kappa",) * 3, "local_stress": ("stress",) * 3,
                 "local_strain": (None,) * 3, "forces_curvature": ("N",) * 3 + ("kappa",) * 3}[kind]
        rows = [rf"${SYMBOL.get(name, name)}$ & {number(float(v))} & {units.text(k)} \\" for name, v, k in zip(names, values, kinds)]
        out.append(long_table(["Quantity", "Value", "Unit"], rows, "lrl"))
    if solution.delta_T is not None:
        out.append(rf"A uniform temperature change $\Delta T = {mnumber(float(units.shown(solution.delta_T, 'delta_T')))}${units.math('delta_T')} is applied with the loads; "
                   r"the engine never assumes one (ADR-0014).")
    if "failure" in case:
        fixed, variable = case["failure"]["fixed"], case["failure"]["variable"]
        out.append(r"First-ply failure is asked with fixed and variable loading (ADR-0017): the fixed resultants stay as they are and the variable ones scale "
                   r"until the first ply fails; the strength ratio is the factor on the variable part.")
        out.append(long_table(["Resultant", "Fixed", "Variable (per unit factor)", "Unit"],
                              [rf"${SYMBOL[n]}$ & {number(float(f))} & {number(float(v))} & {units.text('N' if n.startswith('N') else 'M')} \\"
                               for n, f, v in zip(LOAD_NAMES, fixed, variable)], "lrrl"))
    elif first_ply_failures(case, solution):
        out.append(r"First-ply failure is checked with the mechanical loads scaling and any temperature change held fixed (ADR-0017).")
    if "f12_star" in case:
        out.append(rf"Tsai-Wu interaction term $f_{{12}}^* = {number(case['f12_star'])}$, stated by the case (ADR-0021).")
    if "plate" in case:
        plate, buckling = case["plate"], case["buckling"]
        out.append(rf"Plate buckling: a simply supported plate $a = {number(plate['a'])}$ by $b = {number(plate['b'])}$ {units.text('length')} under the reference "
                   rf"loads $[{', '.join(number(float(v)) for v in buckling['loads'])}]$ {units.text('N')}" + (f", {buckling['terms']} Ritz terms" if "terms" in buckling else "") + ".")
    return "\n\n".join(out)


def steps_section(case: dict, solution, units: Units, theory: bool) -> str:
    """The engine's steps in order, each with the theory section, its code, and the numbers this problem produced."""
    plies = solution.plies
    materials = solution.materials
    out = []

    def step(title: str, fragment: str, body: list[str]) -> None:
        out.append(heading(1, title))
        if theory:
            out.append(render_theory(fragment))
            out.append(r"\paragraph{For this problem.}")
        out.extend(body)

    # 1 ply stiffness
    body = []
    for name, lamina in materials.items():
        tag = "" if len(materials) == 1 else rf"\ (\text{{{escape(name)}}})"
        body.append(matrix(rf"\mathbf{{Q}}{tag}", units.shown(reduced_stiffness(lamina), "modulus"), units.math("modulus")))
        body.append(matrix(rf"\mathbf{{S}}{tag}", units.shown(reduced_compliance(lamina), "compliance"), units.math("compliance")))
    step("Step 1. Ply stiffness in the fiber axes", "Ply stiffness", body)

    # 2 rotation
    combos = list(dict.fromkeys((name, ply.angle_deg) for ply, name in zip(plies, solution.ply_materials)))
    body = []
    for name, angle in combos:
        tag = rf"\ (\theta = {mnumber(angle)}^\circ" + ("" if len(materials) == 1 else rf",\ \text{{{escape(name)}}}") + ")"
        body.append(matrix(rf"\bar{{\mathbf{{Q}}}}{tag}", units.shown(transformed_reduced_stiffness(materials[name], angle), "modulus"), units.math("modulus")))
        if len(plies) == 1:
            body.append(matrix(rf"\bar{{\mathbf{{S}}}}{tag}", units.shown(transformed_compliance(materials[name], angle), "compliance"), units.math("compliance")))
    step("Step 2. Rotation to the laminate axes", "Rotation", body)

    # 3 laminate stiffness
    A, B, D = abd_matrices(plies)
    body = [matrix(r"\mathbf{A}", units.shown(A, "A"), units.math("A")), matrix(r"\mathbf{B}", units.shown(B, "B"), units.math("B")),
            matrix(r"\mathbf{D}", units.shown(D, "D"), units.math("D"))]
    if np.allclose(B, 0.0, atol=1e-9 * max(float(np.abs(A).max()), 1.0)):
        body.append(r"$\mathbf{B} = 0$: the layup is symmetric, so in-plane loads produce no curvature and moments produce no mid-plane strain.")
    a, b, d = abd_compliance(plies)
    body += [matrix(r"\mathbf{a}", units.shown(a, "a"), units.math("a")), matrix(r"\mathbf{b}", units.shown(b, "b"), units.math("b")),
             matrix(r"\mathbf{d}", units.shown(d, "d"), units.math("d"))]
    step("Step 3. Laminate stiffness and compliance", "Laminate stiffness", body)

    # 4 temperature
    if solution.delta_T is not None:
        body = []
        for name, angle in combos:
            body.append(vector(rf"\boldsymbol{{\alpha}}_{{xy}}\ (\theta = {mnumber(angle)}^\circ" + ("" if len(materials) == 1 else rf",\ \text{{{escape(name)}}}") + ")",
                               units.shown(thermal_expansion_xy(materials[name], angle), "alpha"), units.math("alpha")))
        body.append(vector(r"\mathbf{N}^T", units.shown(solution.N_T, "N"), units.math("N")))
        body.append(vector(r"\mathbf{M}^T", units.shown(solution.M_T, "M"), units.math("M")))
        step("Step 4. Temperature change: thermal resultants", "Temperature change", body)

    # 5 response
    n = 5 if solution.delta_T is not None else 4
    N = solution.loads.as_vector()
    body = []
    if solution.kind in ("loads", "stress", "local_stress"):
        fragment = "Response to loads"
        body.append(r"The mechanical resultants (as given, or the applied stress times the thickness):")
        body.append(vector(r"\mathbf{N}", units.shown(N[:3], "N"), units.math("N")) + vector(r"\mathbf{M}", units.shown(N[3:], "M"), units.math("M")))
        if solution.delta_T is not None:
            body.append(r"With the temperature change, the thermal resultants are added to the mechanical ones before inverting (Step 4 and section 7 of the theory).")
    elif solution.kind == "forces_curvature":
        fragment = "Known forces and prescribed curvature"
        body.append(r"The forces are known and the curvatures prescribed; the mid-plane strains and the moments that hold the curvature are solved:")
        body.append(vector(r"\mathbf{N}", units.shown(N[:3], "N"), units.math("N")) + vector(r"\mathbf{M}\ (\text{solved})", units.shown(N[3:], "M"), units.math("M")))
    elif solution.kind == "mixed":
        fragment = "Mixed load and deformation conditions"
        body.append(rf"Known quantities: {', '.join(rf'${SYMBOL[k]}$' for k in solution.mixed.known)}. The solver returns the other member of each pair:")
        body.append(vector(r"\mathbf{N}", units.shown(N[:3], "N"), units.math("N")) + vector(r"\mathbf{M}", units.shown(N[3:], "M"), units.math("M")))
    else:
        fragment = "Response to loads"
        body.append(r"The deformations are given; the resultants follow from the ABD matrix (the thermal resultants, if any, are removed so the mechanical part is reported):")
        body.append(vector(r"\mathbf{N}", units.shown(N[:3], "N"), units.math("N")) + vector(r"\mathbf{M}", units.shown(N[3:], "M"), units.math("M")))
    body.append(vector(r"\boldsymbol{\varepsilon}^0", solution.eps0) + vector(r"\boldsymbol{\kappa}", units.shown(solution.kappa, "kappa"), units.math("kappa")))
    h = sum(ply.thickness_m for ply in plies)
    body.append(rf"Average stress $\mathbf{{N}}/h$: $[{', '.join(mnumber(float(v)) for v in units.shown(N[:3] / h, 'stress'))}]${units.math('stress')}.")
    step(f"Step {n}. Mid-plane strains and curvatures", fragment, body)

    # 6 ply surfaces
    n += 1
    strain_rows, stress_rows = [], []
    strain_scale = max(float(np.abs(np.concatenate([s.strain_xy, s.strain_12])).max()) for s in solution.surfaces)
    stress_scale = max(float(np.abs(np.concatenate([s.stress_xy, s.stress_12])).max()) for s in solution.surfaces)
    for s in solution.surfaces:
        face = "bottom" if s is solution.surfaces[2 * s.ply_index] else "top"
        zz = number(float(units.shown(s.z_m, "length")))
        strains = tidy(np.concatenate([s.strain_xy, s.strain_12]), strain_scale)
        stresses = units.shown(tidy(np.concatenate([s.stress_xy, s.stress_12]), stress_scale), "stress")
        strain_rows.append(rf"{s.ply_index + 1} & {face} & {zz} & " + " & ".join(number(float(v), STEP_WIDTH) for v in strains) + r" \\")
        stress_rows.append(rf"{s.ply_index + 1} & {face} & {zz} & " + " & ".join(number(float(v), STEP_WIDTH) for v in stresses) + r" \\")
    body = [rf"Both faces of every ply, bottom ply first; $z$ in {units.text('length')}, stresses in {units.text('stress')}. Entries below "
            rf"$10^{{-10}}$ of the largest in the table are floating-point residue and are printed as 0."
            + (" With a temperature change the strains are total strains and the stresses come from the mechanical strain, the total minus the free thermal strain." if solution.delta_T is not None else ""),
            long_table(["Ply", "Face", "$z$", r"$\varepsilon_x$", r"$\varepsilon_y$", r"$\gamma_{xy}$", r"$\varepsilon_1$", r"$\varepsilon_2$", r"$\gamma_{12}$"], strain_rows,
                       "rlrrrrrrr", r"\scriptsize\setlength{\tabcolsep}{3pt}"),
            long_table(["Ply", "Face", "$z$", r"$\sigma_x$", r"$\sigma_y$", r"$\tau_{xy}$", r"$\sigma_1$", r"$\sigma_2$", r"$\tau_{12}$"], stress_rows,
                       "rlrrrrrrr", r"\scriptsize\setlength{\tabcolsep}{3pt}")]
    step(f"Step {n}. Strain and stress in every ply", "Ply surface recovery", body)

    # 7 failure
    failures = first_ply_failures(case, solution)
    if failures:
        n += 1
        body = []
        for criterion, fpf in failures.items():
            g = fpf.governing
            loads = fpf.failure_loads.as_vector()
            body.append(rf"\textbf{{{escape(criterion.replace('_', ' '))}.}} Strength ratio $R = {mnumber(fpf.strength_ratio)}$ on the variable loading; first failure in ply "
                        rf"{g.ply_index + 1} ({mnumber(g.angle_deg)}$^\circ$) at $z = {mnumber(float(units.shown(g.z_m, 'length')))}${units.math('length')}, "
                        rf"{escape(g.mode)}. Loads at failure: $\mathbf{{N}} = [{', '.join(mnumber(float(v)) for v in units.shown(loads[:3], 'N'))}]${units.math('N')}, "
                        rf"$\mathbf{{M}} = [{', '.join(mnumber(float(v)) for v in units.shown(loads[3:], 'M'))}]${units.math('M')}.")
            check_scale = max(float(np.abs(c.stress_12).max()) for c in fpf.checks)
            rows = [rf"{c.ply_index + 1} & {number(c.angle_deg)} & {number(float(units.shown(c.z_m, 'length')))} & "
                    + " & ".join(number(float(v), STEP_WIDTH) for v in units.shown(tidy(c.stress_12, check_scale), "stress"))
                    + rf" & {number(c.strength_ratio, STEP_WIDTH)} & {escape(c.mode)} \\" for c in fpf.checks]
            body.append(long_table(["Ply", r"Angle ($^\circ$)", f"$z$ ({units.text('length')})", r"$\sigma_1$", r"$\sigma_2$", r"$\tau_{12}$", "Ratio $R$", "Governing mode"], rows,
                                   r"rrrrrrr>{\raggedright\arraybackslash}p{3cm}", r"\scriptsize\setlength{\tabcolsep}{3pt}"))
        out.append(heading(1, f"Step {n}. First-ply failure"))
        if theory:
            out.append(render_theory("Failure"))
            out.append(render_theory("Fixed and variable loading"))
            out.append(r"\paragraph{For this problem.}")
        out.extend(body)

    # 8 engineering constants
    n += 1
    constants = engineering_constants(plies)
    body = [kv_table([(r"$E_x$", number(float(units.shown(constants.Ex, "modulus"))) + " " + units.text("modulus")),
                      (r"$E_y$", number(float(units.shown(constants.Ey, "modulus"))) + " " + units.text("modulus")),
                      (r"$G_{xy}$", number(float(units.shown(constants.Gxy, "modulus"))) + " " + units.text("modulus")),
                      (r"$\nu_{xy}$", number(float(tidy([constants.nu_xy], 1.0)[0]))), (r"$\nu_{yx}$", number(float(tidy([constants.nu_yx], 1.0)[0]))),
                      (r"$\eta_{xs}$", number(float(tidy([constants.eta_xs], 1.0)[0]))), (r"$\eta_{ys}$", number(float(tidy([constants.eta_ys], 1.0)[0])))])]
    body.append(r"The coupling ratios $\eta$ are printed as 0 when they are below $10^{-10}$: floating-point residue of a balanced laminate.")
    step(f"Step {n}. Laminate engineering constants", "Laminate engineering constants", body)

    # 9 buckling
    buckling = buckling_result(case, solution)
    if buckling is not None:
        n += 1
        body = [rf"Load factor on the reference loads: ${mnumber(buckling.load_factor)}$; critical loads "
                rf"$[{', '.join(mnumber(float(v)) for v in units.shown(buckling.critical_loads, 'N'))}]${units.math('N')}"
                + (f"; mode (half-waves) {tuple(int(m) for m in buckling.mode)}" if buckling.mode is not None else "")
                + (rf"; orthotropic factor ${mnumber(buckling.orthotropic_factor)}$" if buckling.orthotropic_factor is not None else "") + "."]
        step(f"Step {n}. Plate buckling", "Plate buckling", body)
    return "\n\n".join(out)


def comparison_section(comparisons, units: Units) -> str:
    return "\n\n".join([
        r"Source values are the case file's; engine values were computed during the build. ``Difference'' is $|$engine $-$ source$|$ relative to the source "
        r"(absolute when the source is zero); ``Of allowed'' is the difference divided by what the case's rule allows for that number, so below 1 agrees. "
        r"Labels read like the case keys; \texttt{[ply k]} names ply $k$ from the bottom and \texttt{[i]} or \texttt{[i,j]} the component.",
        long_table(["Result", "Unit", "Source", "Engine", "Difference", "Of allowed", "Agrees"], comparison_rows(comparisons, units),
                   r">{\raggedright\arraybackslash}p{3.6cm}lrrrrY", r"\scriptsize\setlength{\tabcolsep}{3pt}")])


def method_section() -> str:
    return "\n\n".join([
        r"A case file holds the inputs and only the numbers the source states, with a reference to where they came from (ADR-0007). The runner builds the "
        r"laminate, solves it once in SI, derives every result the inputs determine, converts back to the case's units, and judges each expected value by "
        r"\begin{equation*} |\,\text{engine} - \text{source}\,| \le \text{tolerance} \times \bigl(|\text{source}|\ \text{or, when the source is zero, the largest magnitude of its group}\bigr). \end{equation*}"
        r"The same runner is what the test suite executes on every case at every change. Its code:",
        manual.listing("load_case", "anisotropy_engine"), manual.listing("solve_case", "anisotropy_engine"),
        manual.listing("engine_results", "anisotropy_engine"), manual.listing("compare", "anisotropy_engine")])


def reading_note(case_path: Path) -> Path | None:
    """`<case>.md` beside the case, else the reading under docs/problems/readings/ whose name is the longest prefix of the case's name."""
    beside = case_path.with_suffix(".md")
    if beside.is_file():
        return beside
    candidates = [p for p in READINGS.glob("*.md") if case_path.stem.startswith(p.stem)] if READINGS.is_dir() else []
    return max(candidates, key=lambda p: len(p.stem)) if candidates else None


def reading_section(case_path: Path) -> tuple[str, bool]:
    note = reading_note(case_path)
    if note is None:
        return (rf"No reading has been written for this problem yet. To add one, write {code(rel(case_path.with_suffix('.md')))} beside the case, or a note "
                rf"under {code(rel(READINGS))} whose file name is a prefix of the case's name (one note can cover a homework set). This section then prints it.", False)
    text = note.read_text(encoding="utf-8")
    title = re.search(r"^# (.+)$", text, re.M)
    body = text.split("\n", 1)[1] if title else text
    return (rf"{{\small\color{{muted}}From {code(rel(note))}" + (rf": {inline(title.group(1))}" if title else "") + ".}\n\n" + manual.convert(body), True)


# --------------------------------------------------------------------------------------------- the document

def output_dir(case_path: Path, requested: Path | None) -> Path:
    if requested is not None:
        return requested
    if ".local" in case_path.resolve().parts:
        return case_path.parent / "report" / case_path.stem
    return HERE / "build" / case_path.stem


def build(case_path: Path, out: Path | None, pdf: bool, theory: bool) -> tuple[Path, int, int]:
    case_path = case_path.resolve()
    case = load_case(case_path)
    units = Units(case["units"])
    solution = solve_case(case)
    comparisons, problems = compare(case)
    out_dir = output_dir(case_path, out)
    out_dir.mkdir(parents=True, exist_ok=True)
    reading, reading_exists = reading_section(case_path)
    stem = case_path.stem
    short = case["title"] if len(case["title"]) <= 70 else case["title"][:67].rstrip() + "..."
    parts = [
        r"\documentclass[11pt,letterpaper]{article}", PREAMBLE,
        rf"\hypersetup{{pdftitle={{{escape(case['title'])}}}}}",
        r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyhead[L]{{\sffamily\footnotesize\color{{muted}}Anisotropy AI \textperiodcentered{{}} Solved problem \textperiodcentered{{}} {inline(short)}}}",
        r"\fancyhead[R]{\sffamily\footnotesize\color{muted}\thepage}",
        r"\fancyfoot[C]{\sffamily\scriptsize\color{muted}Internal use. Agreement with an answer key or a textbook is verification of the engine, not a test of a part.}",
        r"\begin{document}",
        title_page(case, case_path, comparisons, problems),
        r"\tableofcontents\clearpage",
        r"\section{About this document}", about_section(reading_exists),
        r"\section{Does the engine reproduce the source?}\label{sec:summary}", summary_section(case, comparisons, problems, units),
        r"\section{The problem}\label{sec:problem}", problem_section(case, case_path, solution, units),
        r"\section{The solution, step by step}\label{sec:steps}",
        ("Each step prints the theory the engine follows, the function that computes it, copied from the source with its line numbers, and the numbers this "
         "problem produced at that step." if theory else r"Theory and code are omitted in this build (\texttt{--no-theory}); the numbers of every step follow.")
        + r" In the matrices and vectors, an entry below $10^{-10}$ of the largest entry is floating-point residue and is printed as 0; the comparison "
        r"table in Section~\ref{sec:comparison} shows every value as computed.",
        steps_section(case, solution, units, theory),
        r"\section{Every compared number}\label{sec:comparison}", comparison_section(comparisons, units),
        r"\section{How the inputs were read and the numbers judged}\label{sec:method}", method_section(),
        r"\section{Reading}\label{sec:reading}", reading,
        r"\appendix", r"\section{The case file}", file_listing(case_path),
        r"\end{document}",
    ]
    tex = out_dir / f"{stem}.tex"
    tex.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    if manual.UNMAPPED:
        print("Characters without a LaTeX mapping (check how they render):", " ".join(sorted(manual.UNMAPPED)))
    agreeing = sum(c.agrees for c in comparisons)
    print(f"{len(comparisons)} numbers compared, {agreeing} agree; LaTeX written to {tex}")
    compiler = manual.tectonic()
    if pdf and compiler is not None:
        subprocess.run([compiler, "--outdir", str(out_dir), str(tex)], check=True)
        print("Document written to", out_dir / f"{stem}.pdf")
    elif pdf:
        print("Tectonic not found; no PDF.")
    return tex, len(comparisons), agreeing


def write_index(results: list[tuple[Path, dict, int, int]]) -> Path:
    """index.md beside the built documents: one row per solved problem, the evidence an engineer asks for."""
    rows = ["| Document | Problem | Source | Values | Agree |", "| --- | --- | --- | --- | --- |"]
    for case_path, case, total, agreeing in results:
        rows.append(f"| [{case_path.stem}]({case_path.stem}/{case_path.stem}.pdf) | {case['title']} | {case['source'].rstrip('.')} | {total} | {agreeing} |")
    total = sum(r[2] for r in results)
    agreeing = sum(r[3] for r in results)
    text = ("# Solved problems\n\n"
            f"Built {date.today().isoformat()} from commit {git_commit()}. {len(results)} problems, {agreeing} of {total} source values reproduced by the engine. "
            "One document per problem, generated by `docs/problems/build.py` from the case files under `engine/validation/cases/` (ADR-0033).\n\n"
            + "\n".join(rows) + "\n")
    path = HERE / "build" / "index.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("case", type=Path, nargs="?", help="a validation case (TOML)")
    parser.add_argument("--all", action="store_true", help="every committed case under engine/validation/cases, and index.md")
    parser.add_argument("--out", type=Path, default=None, help="output folder (default: docs/problems/build/<case>, or <case folder>/report/<case> for a local case)")
    parser.add_argument("--no-pdf", action="store_true", help="write the LaTeX only")
    parser.add_argument("--no-theory", action="store_true", help="leave out the theory text and code listings of every step")
    args = parser.parse_args()
    if args.all == (args.case is not None):
        raise SystemExit("give a case or --all, not both and not neither")
    paths = sorted(p for p in CASES.glob("*.toml") if not p.name.startswith("_")) if args.all else [args.case]
    results = []
    for path in paths:
        _, total, agreeing = build(path, args.out if not args.all else None, pdf=not args.no_pdf, theory=not args.no_theory)
        results.append((path, load_case(path), total, agreeing))
    if args.all:
        print("Index written to", write_index(results))


if __name__ == "__main__":
    main()
