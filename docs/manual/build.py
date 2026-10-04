"""Builds the engine manual (PDF) from the repository's documents, code and engine results.

From the repository root:

    uv run --project engine python docs/manual/build.py

LaTeX fragments are written to docs/manual/generated/. When Tectonic is installed the PDF
is compiled to docs/manual/build/anisotropy-engine-manual.pdf. Change the Markdown sources
and the code, never the generated files.
"""

import importlib
import inspect
import re
import shutil
import subprocess
import sys
import textwrap
import tomllib
from datetime import date
from pathlib import Path

from anisotropy_engine.cases import compare, load_case
from anisotropy_engine.engineering import engineering_constants
from anisotropy_engine.failure import first_ply_failure, margin_of_safety
from anisotropy_engine.lamina import Lamina, Strengths
from anisotropy_engine.laminate import Ply
from anisotropy_engine.response import Loads
from anisotropy_engine.units import UNIT_SYSTEMS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GENERATED = HERE / "generated"
BUILD = HERE / "build"
REPO_URL = "https://github.com/erikvilla1/anisotropy-ai/blob/main/"
ENGINE_MODULES = ("lamina", "rotation", "laminate", "response", "failure", "engineering", "thermal", "mixed")

# --------------------------------------------------------------------- text to LaTeX

SPECIAL = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
           "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
UNICODE = {"–": "--", "—": "---", "−": "$-$", "×": r"$\times$", "·": r"$\cdot$", "≥": r"$\geq$",
           "≤": r"$\leq$", "→": r"$\rightarrow$", "±": r"$\pm$", "…": r"\ldots{}", "θ": r"$\theta$",
           "≈": r"$\approx$", "’": "'", "“": "``", "”": "''"}
UNMAPPED: set[str] = set()


def escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in SPECIAL:
            out.append(SPECIAL[ch])
        elif ch in UNICODE:
            out.append(UNICODE[ch])
        else:
            if ord(ch) > 127 and ch != "°":
                UNMAPPED.add(ch)
            out.append(ch)
    return "".join(out)


def code(text: str) -> str:
    """Inline code that may break after slashes, underscores and hyphens."""
    breakable = escape(text).replace("/", r"/\allowbreak{}").replace(r"\_", r"\_\allowbreak{}").replace("-", r"-\allowbreak{}")
    return r"\texttt{" + breakable + "}"


INLINE = re.compile(r"\$`(?P<math>.+?)`\$|`(?P<code>[^`]+)`|\[(?P<label>[^\]]+)\]\((?P<url>[^)]+)\)"
                    r"|\*\*(?P<bold>.+?)\*\*|\*(?P<italic>[^*\s][^*]*)\*")


def inline(text: str) -> str:
    """Markdown inline text (math, code, links, bold, italic) to LaTeX."""
    out, pos = [], 0
    for m in INLINE.finditer(text):
        out.append(escape(text[pos:m.start()]))
        if m["math"] is not None:
            out.append(f"${m['math']}$")
        elif m["code"] is not None:
            out.append(code(m["code"]))
        elif m["label"] is not None:
            label, url = inline(m["label"]), m["url"]
            out.append(rf"\href{{{url.replace('#', '%23')}}}{{{label}}}" if url.startswith("http") else label)
        elif m["bold"] is not None:
            out.append(r"\textbf{" + inline(m["bold"]) + "}")
        else:
            out.append(r"\emph{" + inline(m["italic"]) + "}")
        pos = m.end()
    out.append(escape(text[pos:]))
    return "".join(out)


def heading(level: int, title: str) -> str:
    command = {1: "subsection", 2: "subsubsection"}.get(level, "paragraph")
    title = re.sub(r"^\d+\.\s*", "", title)
    plain = escape(re.sub(r"[`*]", "", title))
    return rf"\{command}{{\texorpdfstring{{{inline(title)}}}{{{plain}}}}}"


CODE_MARKER = re.compile(r"<!--\s*code:\s*(.+?)\s*-->")


def blocks(md: str):
    """Split Markdown into (kind, payload) blocks: heading, paragraph, list, enum, table, math, code-ref.

    A line `<!-- code: name, other -->` (invisible on GitHub) marks where the manual shows
    the source of those engine functions. Other HTML comments are skipped.
    """
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif line.lstrip().startswith("<!--"):
            marker = CODE_MARKER.search(line)
            if marker:
                yield "code-ref", [name.strip() for name in marker.group(1).split(",")]
            i += 1
        elif line.startswith("```"):
            j = i + 1
            while not lines[j].startswith("```"):
                j += 1
            yield ("math" if line.startswith("```math") else "code"), "\n".join(lines[i + 1:j])
            i = j + 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            yield "heading", (level, line[level:].strip())
            i += 1
        elif line.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            rows = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in lines[i:j]]
            rows = [row for row in rows if not all(re.fullmatch(r":?-+:?", cell) for cell in row)]
            yield "table", (rows[0], rows[1:])
            i = j
        elif re.match(r"- |\d+\. ", line):
            kind = "list" if line.startswith("- ") else "enum"
            items = []
            while i < len(lines) and re.match(r"- |\d+\. ", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i]))
                i += 1
            yield kind, items
        else:
            paragraph = []
            while i < len(lines) and lines[i].strip() and not re.match(r"#|\||```|- |\d+\. ", lines[i]):
                paragraph.append(lines[i].strip())
                i += 1
            yield "paragraph", " ".join(paragraph)


def table(header: list[str], rows: list[list[str]], keep: list[str] | None = None, size: str = r"\small",
          spec: str | None = None) -> str:
    columns = [header.index(name) for name in keep] if keep else list(range(len(header)))
    header = [header[c] for c in columns]
    rows = [[row[c] for c in columns] for row in rows]
    if spec is None:
        widths = [max(len(cell) for cell in column) for column in zip(header, *rows)]
        spec = "".join("Y" if width > 16 else "l" for width in widths)
        if "Y" not in spec:
            spec = spec[:-1] + "Y"
    head = " & ".join(r"\textbf{" + inline(cell) + "}" for cell in header) + r" \\"
    body = [" & ".join(inline(cell) for cell in row) + r" \\" for row in rows]
    return "\n".join(["{" + size, rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", head,
                      r"\midrule", r"\endhead", *body, r"\bottomrule", r"\end{xltabular}", "}"])


def convert(md: str) -> str:
    """Markdown body to LaTeX. Top-level headings (#) are dropped; ## and ### become subsections."""
    out = []
    for kind, payload in blocks(md):
        if kind == "heading":
            level, title = payload
            if level > 1:
                out.append(heading(level - 1, title))
        elif kind == "paragraph":
            out.append(inline(payload))
        elif kind in ("list", "enum"):
            environment = "itemize" if kind == "list" else "enumerate"
            items = "\n".join(r"\item " + inline(item) for item in payload)
            out.append(rf"\begin{{{environment}}}" + "\n" + items + "\n" + rf"\end{{{environment}}}")
        elif kind == "table":
            out.append(table(*payload))
        elif kind == "math":
            out.append(r"\begin{equation*}" + "\n" + payload + "\n" + r"\end{equation*}")
        elif kind == "code":
            out.append(r"\begin{verbatim}" + "\n" + payload + "\n" + r"\end{verbatim}")
    return "\n\n".join(out)


def sections(md: str) -> dict[str, str]:
    """Markdown split at its ## headings: {heading: body}. The text before the first ## is under ""."""
    parts = re.split(r"^## (.+)$", md, flags=re.M)
    found = {"": parts[0]}
    for title, body in zip(parts[1::2], parts[2::2]):
        found[title.strip()] = body
    return found


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


# ------------------------------------------------------------------- theory and code

FUNCTION_REFERENCE = re.compile(r"(?:[Cc]omputed|[Cc]hecked) by ((?:`[\w.]+`(?:,\s*|\s+and\s+)?)+)")


def find(name: str):
    head, _, attribute = name.partition(".")
    for module_name in ENGINE_MODULES:
        module = importlib.import_module(f"anisotropy_engine.{module_name}")
        if hasattr(module, head):
            target = getattr(module, head)
            if attribute:
                target = inspect.getattr_static(target, attribute)
                target = target.fget if isinstance(target, property) else getattr(target, "wrapped", target)
            return target
    raise LookupError(f"theory.md names {name}, which is not in the engine")


def listing(name: str) -> str:
    target = find(name)
    lines, start = inspect.getsourcelines(target)
    path = Path(inspect.getsourcefile(target)).resolve().relative_to(ROOT).as_posix()
    end = start + len(lines) - 1
    source = textwrap.dedent("".join(lines)).rstrip()
    return (rf"\codefrom{{{escape(name)}}}{{{code(path)}}}{{{start}--{end}}}" + "\n"
            + rf"\begin{{enginecode}}[firstnumber={start}]" + "\n" + source + "\n" + r"\end{enginecode}")


def theory() -> str:
    """engine/docs/theory.md, with each function's source where its `<!-- code: ... -->` marker is."""
    md = read("engine/docs/theory.md")
    named = {name for match in FUNCTION_REFERENCE.finditer(md) for name in re.findall(r"`([\w.]+)`", match.group(1))}
    marked = {name for marker in CODE_MARKER.finditer(md) for name in map(str.strip, marker.group(1).split(","))}
    if named != marked:
        raise SystemExit("theory.md: every function it says computes or checks something needs a code marker, and "
                         f"every marker needs that sentence. Without a marker: {sorted(named - marked)}. "
                         f"Without a sentence: {sorted(marked - named)}.")
    out = []
    for kind, payload in blocks(md):
        if kind == "heading":
            level, title = payload
            if level > 1:
                out.append(heading(level - 1, title))
        elif kind == "paragraph":
            out.append(inline(payload))
        elif kind == "code-ref":
            out.extend(listing(name) for name in payload)
        else:
            out.append(convert_block(kind, payload))
    return "\n\n".join(out)


def convert_block(kind: str, payload) -> str:
    if kind == "math":
        return r"\begin{equation*}" + "\n" + payload + "\n" + r"\end{equation*}"
    if kind in ("list", "enum"):
        environment = "itemize" if kind == "list" else "enumerate"
        return rf"\begin{{{environment}}}" + "\n" + "\n".join(r"\item " + inline(item) for item in payload) + "\n" + rf"\end{{{environment}}}"
    if kind == "table":
        return table(*payload)
    return r"\begin{verbatim}" + "\n" + payload + "\n" + r"\end{verbatim}"


# ------------------------------------------------------------------- numbers

def unit_label(text: str) -> str:
    """Unit labels such as '10^6 lb/in' or 'N*m' as typeset text."""
    text = text.replace("*", "·")
    power = re.match(r"10\^(\d+) (.*)", text)
    return rf"$10^{{{power[1]}}}$ " + escape(power[2]) if power else escape(text)


def number(value: float, digits: int = 6) -> str:
    text = f"{value:.{digits}g}"
    if "e" in text:
        mantissa, exponent = text.split("e")
        return rf"${mantissa}\times10^{{{int(exponent)}}}$"
    return text.replace("-", "$-$")


UNIT_OF = {"stress_global": "stress", "stress_local": "stress", "Ex": "modulus", "Ey": "modulus",
           "Gxy": "modulus", "curvature": "kappa", "moments": "M", "N_T": "N", "M_T": "M",
           "Nx": "N", "Ny": "N", "Nxy": "N", "Mx": "M", "My": "M", "Mxy": "M",
           "sigma_x": "stress", "sigma_y": "stress", "tau_xy": "stress",
           "kappa_x": "kappa", "kappa_y": "kappa", "kappa_xy": "kappa",
           **{f"fpf_{part}_{criterion}": kind for criterion in ("max_stress", "tsai_wu")
              for part, kind in (("forces", "N"), ("moments", "M"), ("z", "length"))}}
MATRIX_UNITS = ((r"[ABDabd][126]{2}", None), (r"(Q|Qbar)[126]{2}", "modulus"), (r"(S|Sbar)[126]{2}", "compliance"))


def unit_kind(base: str) -> str | None:
    """The units.py quantity of a result key; None for dimensionless results."""
    for pattern, kind in MATRIX_UNITS:
        if re.fullmatch(pattern, base):
            return kind or base[0]  # A, B, D and the inverse blocks a, b, d have their own units
    return "stress" if base.startswith("ply_stress") else UNIT_OF.get(base)


def validation() -> str:
    paths = sorted(p for p in (ROOT / "engine/validation/cases").glob("*.toml") if not p.name.startswith("_"))
    out, total, agreeing = [], 0, 0
    for path in paths:
        case = load_case(path)
        comparisons, problems = compare(case)
        if problems:
            raise SystemExit(f"{path.name}: " + "; ".join(problems))
        units = UNIT_SYSTEMS[case["units"]]
        rows = []
        for c in comparisons:
            base = c.key.split("[")[0]
            kind = unit_kind(base)
            unit = unit_label(units[kind][1]) if kind else "--"
            difference = abs(c.engine - c.expected)
            relative = f"{100 * difference / abs(c.expected):.3f}" + r"\%" if c.expected else number(difference, 2)
            rows.append(rf"{code(c.key)} & {unit} & {number(c.expected)} & {number(c.engine)} & {relative} & "
                        + (r"\textcolor{passgreen}{yes}" if c.agrees else r"\textcolor{red}{\textbf{no}}") + r" \\")
            total += 1
            agreeing += c.agrees
        tolerance = case["expected"]["tolerance"]
        source = case["source"].rstrip(".")
        out.append(rf"\subsubsection{{{inline(case['title'])}}}" + "\n"
                   + rf"{{\small\color{{muted}}Source: {inline(source)}. File: {code(path.relative_to(ROOT).as_posix())}. "
                   + rf"Tolerance {number(100 * tolerance, 3)}\%.}}" + "\n\n"
                   + r"{\small\begin{xltabular}{\linewidth}{lllllY}\toprule" + "\n"
                   + r"\textbf{Result} & \textbf{Unit} & \textbf{Source} & \textbf{Engine} & \textbf{Difference} & \textbf{Agrees} \\\midrule\endhead" + "\n"
                   + "\n".join(rows) + "\n" + r"\bottomrule\end{xltabular}}")
    summary = (rf"The engine was run on every validation case while this manual was built. "
               rf"{agreeing} of {total} values from {len(paths)} cases agree with their sources within each case's tolerance. "
               rf"Cases are stored in {code('engine/validation/cases')}; see {code('engine/validation/README.md')} to add one.")
    return summary + "\n\n" + "\n\n".join(out)


def coupon_example() -> str:
    strengths = Strengths(F1t=2280e6, F1c=1725e6, F2t=57e6, F2c=228e6, F6=76e6)
    as4 = Lamina(E1=147e9, E2=10.3e9, G12=7e9, nu12=0.27, strengths=strengths)
    half = [45, -45, 0, 90] * 2
    layup = half + half[::-1]
    t, width, load = 0.13e-3, 25e-3, 20e3
    plies = [Ply(material=as4, angle_deg=a, thickness_m=t) for a in layup]
    loads = Loads(Nx=load / width)
    c = engineering_constants(plies)
    h = t * len(plies)
    stress = load / (width * h)
    max_stress = first_ply_failure(plies, loads)
    tsai_wu = first_ply_failure(plies, loads, "tsai_wu", f12_star=-0.5)
    g = max_stress.governing
    rows = [
        ("Laminate modulus $E_x$", f"{c.Ex / 1e9:.2f} GPa"),
        (r"Poisson ratio $\nu_{xy}$", f"{c.nu_xy:.3f}"),
        ("Average stress at 20 kN", f"{stress / 1e6:.1f} MPa"),
        ("Predicted axial strain at 20 kN", f"{stress / c.Ex * 1e6:.0f} microstrain"),
        ("First-ply failure, maximum stress", f"{max_stress.strength_ratio * load / 1e3:.2f} kN"),
        ("Governing ply and mode", f"ply {g.ply_index + 1} ({g.angle_deg:g}°), {g.mode}"),
        (r"First-ply failure, Tsai-Wu ($f_{12}^{*} = -\tfrac12$)", f"{tsai_wu.strength_ratio * load / 1e3:.2f} kN"),
        ("Margin of safety at 20 kN, FS = 1.5", f"{margin_of_safety(max_stress.strength_ratio, 1.5):+.3f}".replace("-", "−")),
    ]
    inputs = (r"AS4/3501-6 (Daniel and Ishai Table A.4): $E_1 = 147$ GPa, $E_2 = 10.3$ GPa, $G_{12} = 7$ GPa, "
              r"$\nu_{12} = 0.27$; $F_{1t} = 2280$, $F_{1c} = 1725$, $F_{2t} = 57$, $F_{2c} = 228$, $F_6 = 76$ MPa. "
              r"Layup [45/$-$45/0/90]\textsubscript{2s}, 16 plies of 0.13 mm (2.08 mm), coupon 25 mm wide, "
              r"tension load 20 kN, so $N_x = P/w = 800$ kN/m.")
    body = "\n".join(rf"{label} & {escape(value)} \\" for label, value in rows)
    return (r"This example is computed by the engine each time the manual is built, using the same functions "
            r"listed in Section~\ref{sec:theory}." + "\n\n" + r"\textbf{Inputs.} " + inputs + "\n\n"
            + r"\begin{xltabular}{\linewidth}{Yr}\toprule\textbf{Result} & \textbf{Value} \\\midrule" + "\n"
            + body + "\n" + r"\bottomrule\end{xltabular}" + "\n\n"
            + r"At 20 kN the 90\textdegree{} plies have already reached their transverse tensile strength, while "
              r"the 0\textdegree{} fibers are far from breaking. First-ply failure is the onset of cracking, not "
              r"the load a D3039 test reports as ultimate strength.")


def units_table() -> str:
    names = {"modulus": "Modulus", "stress": "Stress", "length": "Length", "N": "Force per width $N$",
             "M": "Moment per width $M$", "kappa": r"Curvature $\kappa$", "A": r"$\mathbf{A}$",
             "B": r"$\mathbf{B}$", "D": r"$\mathbf{D}$", "alpha": r"Thermal expansion $\alpha$",
             "delta_T": r"Temperature change $\Delta T$", "compliance": r"Compliance $\mathbf{S}$, $\bar{\mathbf{S}}$",
             "a": r"Inverse ABD block $\mathbf{a}$", "b": r"Inverse ABD block $\mathbf{b}$",
             "d": r"Inverse ABD block $\mathbf{d}$"}
    rows = [rf"{label} & " + " & ".join(unit_label(UNIT_SYSTEMS[s][kind][1]) for s in ("SI", "US", "psi")) + r" \\"
            for kind, label in names.items()]
    return (r"The engine works in SI. These systems convert values where they enter and leave "
            + "(" + code("engine/src/anisotropy_engine/units.py") + "; ADR-0002)." + "\n\n"
            + r"\begin{xltabular}{\linewidth}{Ylll}\toprule\textbf{Quantity} & \textbf{SI} & \textbf{US} & \textbf{psi} \\\midrule"
            + "\n" + "\n".join(rows) + "\n" + r"\bottomrule\end{xltabular}")


# ------------------------------------------------------------------- documents

def overview() -> str:
    parts = sections(read("docs/00_system_overview.md"))
    keep = ["Purpose", "Key principle", "Layers", "How a result is produced today"]
    return "\n\n".join(heading(1, name) + "\n\n" + convert(parts[name]) for name in keep)


def verification() -> str:
    report_path = sorted((ROOT / "docs/evaluations").glob("*.md"))[-1]
    report = report_path.read_text(encoding="utf-8")
    parts = sections(report)
    title = re.search(r"^# (.+)$", report, re.M).group(1)
    intro = convert(parts[""].split("\n", 1)[1])
    body = "\n\n".join(heading(2, name) + "\n\n" + convert(text) for name, text in parts.items() if name)
    return (heading(1, "Validation cases") + "\n\n" + validation() + "\n\n"
            + heading(1, title) + "\n\n" + rf"{{\small\color{{muted}}Recorded report: {code(report_path.relative_to(ROOT).as_posix())}}}"
            + "\n\n" + intro + "\n\n" + body)


def decisions() -> str:
    out = []
    for path in sorted((ROOT / "docs/decisions").glob("ADR-*.md")):
        text = path.read_text(encoding="utf-8")
        parts = sections(text)
        title = re.search(r"^# (.+)$", text, re.M).group(1)
        status = re.search(r"^- Status: (.+)$", text, re.M).group(1)
        dated = re.search(r"^- Date: (.+)$", text, re.M).group(1)
        url = REPO_URL + path.relative_to(ROOT).as_posix()
        out.append(heading(1, title) + "\n" + rf"\adrmeta{{{escape(status)}}}{{{escape(dated)}}}{{{url}}}")
        for name, label in (("Context", "Context"), ("Options considered", "Options considered"), ("Decision", "Decision"),
                            ("Why (evidence)", "Evidence"), ("How we will know it was wrong", "Revisit when")):
            out.append(rf"\adrpart{{{label}}}" + "\n" + convert(parts[name]))
    return "\n\n".join(out)


def limits() -> str:
    overview_parts = sections(read("docs/00_system_overview.md"))
    risk_parts = sections(read("docs/risks/risk_register.md"))
    risk_table = next(payload for kind, payload in blocks(risk_parts[""]) if kind == "table")
    return (heading(1, "Known limitations") + "\n\n" + convert(overview_parts["Known limitations"]) + "\n\n"
            + heading(1, "Risk register") + "\n\n"
            + r"{\small\color{muted}From \texttt{docs/risks/risk\_register.md}. Owners, areas and NIST functions are in the source file.}"
            + "\n\n" + table(*risk_table, keep=["ID", "Risk", "Likelihood", "Impact", "Mitigation", "Status"],
                             size=r"\footnotesize", spec=r"l>{\hsize=0.95\hsize}Y>{\hsize=0.6\hsize}Yl>{\hsize=1.45\hsize}Yl"))


# ------------------------------------------------------------------- build

def run(*command: str) -> str:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def metadata() -> str:
    version = tomllib.loads(read("engine/pyproject.toml"))["project"]["version"]
    commit = run("git", "rev-parse", "--short", "HEAD")
    if run("git", "status", "--porcelain", "--untracked-files=no"):
        commit += " + local changes"
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "engine/tests"],
                           cwd=ROOT, capture_output=True, text=True)
    summary = tests.stdout.strip().splitlines()[-1] if tests.stdout.strip() else "no output"
    if tests.returncode != 0:
        raise SystemExit("Engine tests fail, so the manual is not built:\n" + tests.stdout[-2000:])
    summary = re.sub(r" in [\d.]+s.*", "", summary)
    return "\n".join([rf"\newcommand{{\EngineVersion}}{{{escape(version)}}}",
                      rf"\newcommand{{\GitCommit}}{{{escape(commit)}}}",
                      rf"\newcommand{{\BuildDate}}{{{date.today().isoformat()}}}",
                      rf"\newcommand{{\TestSummary}}{{{escape(summary)}}}"])


def tectonic() -> str | None:
    found = shutil.which("tectonic")
    fallback = Path.home() / "AppData/Local/Programs/tectonic/tectonic.exe"
    return found or (str(fallback) if fallback.exists() else None)


def main() -> None:
    GENERATED.mkdir(exist_ok=True)
    fragments = {"meta": metadata(), "overview": overview(), "theory": theory(), "verification": verification(),
                 "decisions": decisions(), "limits": limits(), "example": coupon_example(), "units": units_table()}
    for name, text in fragments.items():
        (GENERATED / f"{name}.tex").write_text(text + "\n", encoding="utf-8")
    if UNMAPPED:
        print("Characters without a LaTeX mapping (check how they render):", " ".join(sorted(UNMAPPED)))
    compiler = tectonic()
    if compiler is None:
        print("Tectonic not found. LaTeX written to", GENERATED)
        return
    BUILD.mkdir(exist_ok=True)
    subprocess.run([compiler, "--outdir", str(BUILD), str(HERE / "main.tex")], check=True)
    pdf = BUILD / "anisotropy-engine-manual.pdf"
    (BUILD / "main.pdf").replace(pdf)
    print("Manual written to", pdf)


if __name__ == "__main__":
    main()
