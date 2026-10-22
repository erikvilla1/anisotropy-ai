"""One document per homework set: the physics once, then one chapter per problem with the problem as its case gives it,
every step the engine takes with its numbers, and the key's answers beside the engine's (ADR-0040).

From the repository root:

    uv run --project fea python docs/problems/homework.py HW3
    uv run --project fea python docs/problems/homework.py --all           # every set with a committed case
    options: --root <folder> (the folder holding one folder per set; default .local/homework), --no-pdf, --no-theory

A set is HW<n>, whose problems are the cases `engine/validation/cases/se142-hw<n>-*.toml`, or course-reader
(`course-reader-*.toml`). The document goes to <root>/<set>/documents/: <set>.tex and <set>.pdf side by side. The
cases carry numbers and a source reference only, never the problem text (AGENTS.md); the reading of the set is the note
under docs/problems/readings/ that the per-problem documents use. Every number of the engine is computed while the document
is built; the key's numbers come from the case files.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOCAL = ROOT / ".local" / "homework"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


problems = load_module("anisotropy_problems_build", HERE / "build.py")
manual = problems.manual
escape, code, inline, number = problems.escape, problems.code, problems.inline, problems.number

from anisotropy_engine.cases import compare, load_case, solve_case  # noqa: E402

HW = re.compile(r"^se142-hw(?P<n>\d+)-")
PER_PROBLEM = ("summary", "problem", "steps", "comparison")  # labels each problem chapter has its own copy of
CHAPTER_STYLE = "\n".join([
    r"\titleformat{\chapter}[display]{\sffamily\huge\bfseries\color{ink}}{\color{accent}\large\MakeUppercase{\chaptertitlename}\ \thechapter}{0.6ex}{}",
    r"\titlespacing*{\chapter}{0pt}{0pt}{2.5ex}",
])


def set_of(case_path: Path) -> str | None:
    match = HW.match(case_path.stem)
    if match:
        return f"HW{match['n']}"
    return "course-reader" if case_path.stem.startswith("course-reader-") else None


def all_sets() -> list[str]:
    return sorted({s for path in problems.CASES.glob("*.toml") if (s := set_of(path))}, key=lambda s: (not s.startswith("HW"), s))


def cases_of(set_name: str) -> list[Path]:
    return sorted(path for path in problems.CASES.glob("*.toml") if set_of(path) == set_name)


def problem_chapter(case_path: Path) -> tuple[str, dict, int, int]:
    """The chapter of one problem, its labels made its own, with the number of compared values and how many agree."""
    case = load_case(case_path)
    units = problems.Units(case["units"])
    solution = solve_case(case)
    comparisons, issues = compare(case)
    body = "\n\n".join([
        r"\section{Does the engine reproduce the key?}\label{sec:summary}", problems.summary_section(case, comparisons, issues, units),
        r"\section{The problem}\label{sec:problem}", problems.problem_section(case, case_path, solution, units),
        r"\section{The solution, step by step}\label{sec:steps}",
        r"The equations of each step and the code that computes them are in Chapter~\ref{ch:physics}; here are the numbers this problem produced at "
        r"each step. In the matrices and vectors, an entry below $10^{-10}$ of the largest entry is floating-point residue and is printed as 0; the "
        r"comparison table in Section~\ref{sec:comparison} shows every value as computed.",
        problems.steps_section(case, solution, units, False),
        r"\section{Every compared number}\label{sec:comparison}", problems.comparison_section(comparisons, units),
    ])
    key = case_path.stem
    body = re.sub(r"\\(ref|label)\{sec:(" + "|".join(PER_PROBLEM) + r")\}", lambda m: "\\" + m[1] + "{sec:" + m[2] + "-" + key + "}", body)
    return body, case, len(comparisons), sum(c.agrees for c in comparisons)


def title_page(set_name: str, rows: list[tuple[Path, dict, int, int]]) -> str:
    total, agreeing = sum(r[2] for r in rows), sum(r[3] for r in rows)
    subtitle = (f"SE142/253A homework set {set_name[2:]}, solved by our engine" if set_name.startswith("HW")
                else "Course reader problems, solved by our engine")
    verdict = (rf"\textbf{{The engine reproduces every number the key states.}} {agreeing} of {total} compared values agree within each case's tolerance."
               if agreeing == total else
               rf"\textbf{{The engine does not reproduce every number the key states.}} {total - agreeing} of {total} compared values lie outside the "
               r"tolerance; each problem's chapter shows which.")
    table_rows = [rf"{k} & {inline(case['title'])} & {total_k} & {agreeing_k} \\" for k, (_, case, total_k, agreeing_k) in enumerate(rows, start=1)]
    return "\n".join([
        r"\begin{titlepage}", r"\sffamily",
        r"{\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} HOMEWORK SET}\par", r"\vspace*{1.6cm}",
        rf"{{\fontsize{{26}}{{32}}\selectfont\bfseries\color{{ink}} {escape(set_name)}}}\par", r"\vspace{0.3cm}",
        rf"{{\Large\bfseries\color{{ink}} {escape(subtitle)}}}\par", r"\vspace{0.4cm}",
        r"{\large\color{muted} The physics once, then for each problem: the problem as its case gives it, every step the engine takes with its "
        r"numbers, and the key's answers beside the engine's}\par", r"\vspace{1cm}",
        problems.long_table(["Chapter", "Problem", "Values", "Agree"], [rf"{k + 2} & " + row.split(" & ", 1)[1] for k, row in enumerate(table_rows)],  # chapter 1 is the physics
                            r"r>{\raggedright\arraybackslash}Xrr", r"\small"),
        r"\vfill", rf"\verdict{{{verdict}}}", r"\vspace{0.6cm}",
        rf"{{\small\color{{muted}} Built {date.today().isoformat()} by \texttt{{docs/problems/homework.py}} (anisotropy-engine {escape(problems.engine_version())}, "
        rf"commit {escape(problems.git_commit())}). The key's numbers come from the committed cases, every other number from running the engine.}}",
        r"\end{titlepage}",
    ])


def build(set_name: str, root: Path, pdf: bool, theory: bool) -> Path:
    cases = cases_of(set_name)
    if not cases:
        raise SystemExit(f"no committed case for {set_name}; the sets are {all_sets()}")
    documents = root / set_name / "documents"
    out_dir = documents  # built where it is looked for: one .tex and one .pdf (no copy)
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters, rows = [], []
    for k, case_path in enumerate(cases, start=1):
        body, case, total, agreeing = problem_chapter(case_path)
        rows.append((case_path, case, total, agreeing))
        chapters += [rf"\chapter{{{inline(case['title'])}}}\label{{ch:{case_path.stem}}}", body]
    reading, _ = problems.reading_section(cases[0])
    parts = [
        r"\documentclass[11pt,letterpaper,oneside]{report}", problems.PREAMBLE, CHAPTER_STYLE,
        rf"\hypersetup{{pdftitle={{{escape(set_name)}: solved by our engine}}}}",
        r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyhead[L]{{\sffamily\footnotesize\color{{muted}}Anisotropy AI \textperiodcentered{{}} Homework set \textperiodcentered{{}} {escape(set_name)}}}",
        r"\fancyhead[R]{\sffamily\footnotesize\color{muted}\thepage}",
        r"\fancyfoot[C]{\sffamily\scriptsize\color{muted}Agreement with an answer key is verification of the engine, not a test of a part.}",
        r"\fancypagestyle{plain}{\fancyhf{}\fancyfoot[C]{\sffamily\scriptsize\color{muted}\thepage}\renewcommand{\headrulewidth}{0pt}}",
        r"\begin{document}",
        title_page(set_name, rows),
        r"\tableofcontents",
        r"\chapter{The physics: how our engine solves these problems}\label{ch:physics}",
        (r"Every problem of this set is solved by classical laminate theory. The engine's theory follows, each equation with the function that computes "
         r"it, copied from the source with its real line numbers; the chapters after it give each problem's numbers step by step."
         + "\n\n" + manual.theory("anisotropy_engine")) if theory else
        r"Left out of this build (\texttt{--no-theory}); the equations and code are in \texttt{engine/docs/theory.md} and the engine manual.",
        *chapters,
        r"\chapter{Reading}\label{sec:reading}", reading,
        r"\appendix",
        r"\chapter{How the inputs were read and the numbers judged}\label{sec:method}", problems.method_section(),
        r"\chapter{The case files}", *[rf"\section{{{escape(path.stem)}}}" + "\n\n" + problems.file_listing(path) for path in cases],
        r"\end{document}",
    ]
    tex = out_dir / f"{set_name}.tex"
    tex.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    if manual.UNMAPPED:
        print("Characters without a LaTeX mapping (check how they render):", " ".join(sorted(manual.UNMAPPED)))
    total, agreeing = sum(r[2] for r in rows), sum(r[3] for r in rows)
    print(f"{set_name}: {len(cases)} problems, {agreeing} of {total} values agree; LaTeX written to {tex}")
    compiler = manual.tectonic()
    if pdf and compiler is not None:
        subprocess.run([compiler, "--outdir", str(out_dir), str(tex)], check=True)
        print(f"{set_name}: document written to {documents / f'{set_name}.pdf'}")
        return documents / f"{set_name}.pdf"
    if pdf:
        print("Tectonic not found; no PDF.")
    return tex


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("sets", nargs="*", help="HW<n> or course-reader")
    parser.add_argument("--all", action="store_true", help="every set with a committed case")
    parser.add_argument("--root", type=Path, default=LOCAL, help="the folder holding one folder per set (default .local/homework)")
    parser.add_argument("--no-pdf", action="store_true", help="write the LaTeX only")
    parser.add_argument("--no-theory", action="store_true", help="leave out the physics chapter's equations and code")
    args = parser.parse_args()
    if args.all == bool(args.sets):
        raise SystemExit(f"name sets or give --all, not both and not neither; the sets are {all_sets()}")
    for set_name in (all_sets() if args.all else args.sets):
        build(set_name, args.root, pdf=not args.no_pdf, theory=not args.no_theory)


if __name__ == "__main__":
    main()
