"""The document for a model sent from Abaqus: "Compared with the uploaded Abaqus model" (ADR-0094 part 7, step 7).

From the repository root:

    uv run --project fea python docs/models/upload.py <comparison>.json --out <folder>
    options: --upload <id>, --run <words naming the run of ours>, --compared <when it was compared>, --no-pdf, --json <file>

`<comparison>.json` is what `fea/tools/abaqus_upload.py compare --json` wrote: the bundle's facts, the model item by item, the pairing,
the pull force, each zone's table, the criteria and the verdict. The document is written from that file and nothing else. Nothing is
solved, paired, judged or counted here (ADR-0001): every number printed is one the comparison wrote, shown to the digits the
comparison's own text uses, and the counts in the verdict are its `summary`.

`<folder>/comparison.tex` is written, one self-contained file with the preamble of every model document (`preamble.tex`), and
`<folder>/comparison.pdf` beside it when Tectonic is installed. The document is the upload's own: it is kept with the upload and read
by its owner, never put into the run's document, which every signed-in user reads (ADR-0094 part 6).

The words: this is one finite element model beside another, so it is "compared" and "verified", never "validated", which stays for a
coupon test (ADR-0089). Every text taken from the upload (a job's name, a part's name, a material's line) is escaped before it
reaches LaTeX, and nothing of the upload is executed.

Exit 0: written. 1: the LaTeX is written and its compiler stopped. 2: no document can be written from the file, with the reason (not a
comparison, or one that was refused). `--json` writes which, for the API (`anisotropy_api.uploads`).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


manual = load_module("anisotropy_manual_build", ROOT / "docs" / "manual" / "build.py")
escape, code, number = manual.escape, manual.code, manual.number
PREAMBLE = (HERE / "preamble.tex").read_text(encoding="utf-8")

TITLE = "Compared with the uploaded Abaqus model"
NAME = "comparison"  # the files written: comparison.tex and comparison.pdf
QUANTITIES = ("S11", "S22", "S12", "Mises", "Tresca", "Pressure", "Max. Principal", "Mid. Principal", "Min. Principal", "E11", "E22", "E12")
STRESSES = QUANTITIES[:9]  # the rest are strains, numbers without a unit
ZONES = ("gauge", "free length", "band", "tab line", "gripped")
# The words of the page's card for the same things (components/studio/abaqus-card.tsx, lib/abaqus-exchange.ts).
ZONE_WORDS = {"gauge": "Gauge section", "free length": "Between gauge and tabs", "band": "Within one width of a tab", "tab line": "At a tab line",
              "gripped": "Under the grips"}
JUDGED_ZONES = ("gauge", "free length")
ROLE_WORDS = {"deck": "The input file as solved", "every_output": "The results, every element and ply", "reactions": "The reactions",
              "provenance": "How the results were written", "journal": "The journal, kept as text", "model": "The model as built"}
CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
MINUS = re.compile(r"(?<![\w.$])-(?=\d)")
DIGITS = 6  # a value, as the comparison's own text prints it
PERCENT_DIGITS = 4
HEAD_LETTERS = 60  # of a job's name in the running head, which is one line


class NoDocument(Exception):
    """No document can be written from this file, and why."""


def text(value) -> str:
    """A text of the upload or of the comparison for LaTeX: control characters go, every special character is escaped, and a minus
    before a digit is set as a minus sign."""
    return MINUS.sub("$-$", escape(CONTROL.sub(" ", str(value)).strip()))


def value(x) -> str:
    """A number as the comparison's own text prints it, six significant digits; a zero is 0 whatever its sign."""
    return "" if x is None else "0" if float(x) == 0 else number(float(x), DIGITS)


def percent(fraction) -> str:
    """A share as the comparison's text prints it: four significant digits of the percentage."""
    return number(100.0 * float(fraction), PERCENT_DIGITS) + r"\,\%"


def table(header: list[str], rows: list[list[str]], spec: str, size: str = r"\small") -> str:
    """The table of every model document (`team.table`): the header repeats on a new page and the rule stays with the last row."""
    head = " & ".join(r"\textbf{" + h + "}" for h in header) + r" \\"
    body = [" & ".join(cells) + (r" \\*" if k == len(rows) - 1 else r" \\") for k, cells in enumerate(rows)]
    return "\n".join(["{" + size, rf"\begin{{xltabular}}{{\linewidth}}{{{spec}}}", r"\toprule", head, r"\midrule", r"\endhead",
                      r"\bottomrule", r"\endlastfoot", *body, r"\end{xltabular}", "}"])


def digest(sha) -> str:
    """A SHA-256 in the code face, breakable every eight characters so that it fits a table's column."""
    said = CONTROL.sub("", str(sha))  # escaped piece by piece: a break never falls inside an escaped character
    return r"\texttt{" + r"\allowbreak{}".join(escape(said[k:k + 8]) for k in range(0, len(said), 8)) + "}"


def facts_table(rows: list[tuple[str, str]]) -> str:
    return "\n".join([r"{\small\begin{tabular}{@{}p{2.6cm}p{\dimexpr\linewidth-3.1cm}@{}}", *[rf"{label} & {said} \\[0.3ex]" for label, said in rows],
                      r"\end{tabular}}\par"])


# ----------------------------------------------------------------------------------------------------------- the comparison

def checked(result) -> dict:
    """The comparison, when it is one a document can be written from. Raises `NoDocument` with the reason."""
    if not isinstance(result, dict) or "verdict" not in result:
        raise NoDocument("the file is not a comparison written by fea/tools/abaqus_upload.py compare")
    if result["verdict"] == "refused":
        reasons = "; ".join(str(p) for p in result.get("problems") or []) or "no reason given"
        raise NoDocument(f"the comparison was refused, so there is nothing to print: {reasons}")
    if result["verdict"] not in ("agrees", "differs", "incomplete"):
        raise NoDocument(f"the comparison's verdict is {result['verdict']!r}, which this document does not know")
    missing = [key for key in ("bundle", "units", "ours", "floor", "acceptance", "model", "pairing", "zones", "criteria", "summary") if key not in result]
    if missing:
        raise NoDocument("the comparison has no " + ", ".join(missing) + ": it was written by an older fea/tools/abaqus_upload.py; compare again")
    return result


def verdict_words(result: dict) -> str:
    """The answer first, in the card's words (lib/abaqus-exchange.ts `verdictOf`); the count is the comparison's own."""
    if result["verdict"] == "agrees":
        return "Agrees with ours"
    if result["verdict"] == "incomplete":
        return "Not every part could be compared"
    places = result["summary"]["places"]
    return "Differs in 1 place" if places == 1 else f"Differs in {places} places" if places > 1 else "Differs from ours"


def model_words(result: dict) -> str:
    model, said = result["model"], result["summary"]["model"]
    if model["compared"] == "not compared":
        return "The model was not compared: " + text(model.get("reason") or "no reason given") + "."
    how = "item by item" if model["compared"] == "item by item" else "without its mesh"
    if said["different"]:
        return (rf"The model, compared {how}: {said['different']} of {said['judged']} items judged differ "
                rf"(Section~\ref{{sec:model}}).")
    return rf"The model, compared {how}: the same as ours on every one of {said['judged']} items judged."


def state_of(criterion: dict) -> str:
    if not criterion.get("judged", True):
        return r"\textcolor{muted}{reported}"
    if criterion["met"] is True:
        return r"\textcolor{passgreen}{met}"
    if criterion["met"] is False:
        return r"\textcolor{accent}{\textbf{not met}}"
    return r"\textcolor{muted}{not judged}"


def verdict_box(result: dict) -> str:
    lines = [rf"\textbf{{{verdict_words(result)}.}} " + model_words(result)]
    for c in result["criteria"]:
        if c.get("judged", True):
            state = {True: "met", False: "not met", None: "not judged"}[c["met"]]
            lines.append(rf"{text(c['criterion'])}: {state} ({text(c['evidence'])}).")
        else:  # its evidence already says that it is reported and not judged
            lines.append(rf"{text(c['criterion'])}: {text(c['evidence'])}.")
    return r"\verdict{" + " ".join(lines) + "}"


def title_block(result: dict, upload: str | None, run: str | None, compared: str | None) -> str:
    b, ours, pairing, labels = result["bundle"], result["ours"], result["pairing"], result["summary"]["labels"]
    written = b.get("written_by") or {}
    yours = [f"job {b['job']}" if b.get("job") else "no job named", written.get("abaqus") or "the Abaqus version is not stated",
             f"written by the connector {written.get('connector') or '(not stated)'} on {b.get('created') or '(no time stated)'}", f"in {b['units']}"]
    moved = pairing.get("moved_by") or [0.0, 0.0]
    paired = f"{pairing['elements']} elements, {pairing['how']}"
    if any(abs(float(m)) > 0 for m in moved):
        paired += f"; your coupon was moved by ({float(moved[0]):.6g}, {float(moved[1]):.6g}) {labels['length']} onto ours"
    units = f"every value is shown in {result['units']}" + (f"; yours were written in {result['converted_from']} and converted" if result.get("converted_from") else "")
    by = result.get("compared_by") or {}
    how = [compared, by.get("api") and f"anisotropy-api {by['api']}", by.get("git_commit") and f"commit {str(by['git_commit'])[:12]}"]
    facts = [
        ("Your model", text(", ".join(yours))),
        ("The file", text(f"SHA-256 {b['sha256']}" + (f"; upload {upload}" if upload else ""))),
        ("Ours", text(f"{ours['coupon']}, written by {ours['written_by']}: {ours['elements']} {ours['element']} elements, {ours['layers']} plies"
                      + (f"; {run}" if run else ""))),
        ("Paired", text(paired)),
        ("Units", text(units)),
    ]
    if any(how):
        facts.append(("Compared", text(", ".join(h for h in how if h))))
    return "\n".join([
        r"\begin{center}", r"{\sffamily\color{accent}\bfseries\small ANISOTROPY AI \textperiodcentered{} YOUR ABAQUS MODEL AND OURS}\par\medskip",
        rf"{{\sffamily\fontsize{{20}}{{26}}\selectfont\bfseries\color{{ink}} {text(b.get('job') or 'The model sent')}}}\par\smallskip",
        rf"{{\sffamily\large\color{{ink}} {TITLE}}}\par\smallskip",
        rf"{{\sffamily\color{{muted}} Beside our run of {text(ours['coupon'])}: the two models item by item, the pull force, and the results zone by zone}}",
        r"\end{center}", r"\medskip", facts_table(facts), r"\medskip", verdict_box(result),
    ])


def rule_section(result: dict) -> str:
    acceptance, pairing = result["acceptance"], result["pairing"]
    floor = number(100.0 * float(result["floor"]), PERCENT_DIGITS) + r"\,\%"
    limits = {zone: number(100.0 * float(acceptance[zone]), PERCENT_DIGITS) + r"\,\%" for zone in ("reaction", *JUDGED_ZONES) if zone in acceptance}
    parts = [
        r"Nothing was solved for this comparison. Your results are the ones your own Abaqus wrote, read from the file you sent; ours are "
        r"the files of our finished run. Your value is the reference: a value of ours agrees within a tolerance when its difference from "
        rf"yours is within that share of your value, or, for a small value, within that share of {floor} of the quantity's largest magnitude in your "
        r"gauge section.",
        "The answer is judged on three things: the pull force, which is the reaction at the top grip," + (f" within {limits['reaction']}" if "reaction" in limits else "")
        + "; every value in the gauge section" + (f" within {limits['gauge']}" if "gauge" in limits else "")
        + "; and every value between gauge and tabs, the free length," + (f" within {limits['free length']}" if "free length" in limits else "")
        + ". The elements within one width of a tab and at a tab line, beside the clamped edges, and those under the grips are reported "
        "and not judged.",
    ]
    if pairing.get("same_mesh"):
        parts.append(rf"The two meshes are one mesh: {pairing['elements']} elements were paired {text(pairing['how'])}.")
    else:
        parts.append("The two meshes are not one mesh" + (f" ({text(pairing['why_not_element_by_element'])})" if pairing.get("why_not_element_by_element") else "")
                     + rf", so the results could not be paired element by element. {text(str(pairing['how']).capitalize())}. On two meshes the "
                     r"values between gauge and tabs are reported and not judged.")
    rows = [[text(c["criterion"]), state_of(c), text(c["evidence"])] for c in result["criteria"]]
    parts.append(table(["Criterion", "Result", "Evidence"], rows, r">{\raggedright\arraybackslash}p{6cm}>{\raggedright\arraybackslash}p{1.8cm}Y"))
    return "\n\n".join(parts)


def model_section(result: dict) -> str:
    model, said, labels = result["model"], result["summary"]["model"], result["summary"]["labels"]
    if model["compared"] == "not compared":
        return "The two models were not compared: " + text(model.get("reason") or "no reason given") + "."
    if model["compared"] == "item by item":
        how = ("Both input files were read by the same reader and compared item by item. Nodes are matched by position and elements by "
               "their corner nodes, so the two files may number them differently.")
        offset = model.get("largest_node_offset")
        if offset is not None:
            how += rf" The largest distance between a node of yours and the node of ours it was matched with is {value(offset)} {labels['length']}."
    else:
        how = ("Both input files were read by the same reader and compared without their meshes, because "
               + text(model.get("reason") or "the two meshes differ") + ". The mesh's own items are therefore not in the table.")
    notes = (r"A row reads ``same'' or ``differs'' when it was judged, and ``listed'' when it was not: a name does not change the solution, and a "
             r"strength is not read by a linear solve. A material constant is the same when the two numbers are one number at six significant "
             r"digits, the digits Abaqus/CAE writes to an input file. "
             rf"{said['judged']} of the {said['items']} items were judged" + (rf", and {said['different']} differ." if said["different"] else ", and none differs."))
    marks = {True: r"\textcolor{passgreen}{same}", False: r"\textcolor{accent}{\textbf{differs}}", None: r"\textcolor{muted}{listed}"}
    rows = [[text(i["item"]), text(i["yours"]), text(i["ours"]), marks[i["same"]]] for i in model["items"]]
    if not rows:
        return how + "\n\n" + "No item was compared."
    return "\n\n".join([how, notes, table(["Item", "Yours", "Ours", ""], rows,
                                         r">{\raggedright\arraybackslash}p{3.2cm}YY>{\raggedright\arraybackslash}p{1.1cm}", r"\footnotesize")])


def reaction_section(result: dict) -> str:
    rf, labels = result.get("reaction"), result["summary"]["labels"]
    if not rf:
        said = next((c["evidence"] for c in result["criteria"] if str(c["criterion"]).startswith("Reaction")), None)
        return "The pull force was not compared" + (f": {text(said)}." if said else ": the file holds no reactions.")
    rows = [("Yours", rf"{value(rf['yours'])} {labels['force']}, the reaction along the coupon summed over {rf['nodes']} nodes of the top grip"),
            ("Ours", rf"{value(rf['ours'])} {labels['force']}, over the same edge"),
            ("Difference", rf"ours {percent(rf['difference'])} from yours")]
    return (r"The pull force is the reaction at the top grip: every node at or above the top tab line, summed along the "
            "coupon.\n\n" + facts_table(rows))


def zone_table(zone_rows: dict) -> str:
    rows = []
    for q in QUANTITIES:
        t = zone_rows.get(q)
        if t is None:
            continue
        where = f"{t['your_element']}" + (f" (ours {t['our_element']})" if t.get("our_element") not in (None, t["your_element"]) else "") + f", ply {t['layer']}"
        rows.append([text(q), str(t["values"]), str(t["within_1"]), str(t["within_3"]), percent(t["worst"]), text(where), value(t["yours"]), value(t["ours"])])
    made = table(["Quantity", "Values", r"Within 1\,\%", r"Within 3\,\%", "Largest", "Where", "Yours", "Ours"], rows,
                 r">{\raggedright\arraybackslash}p{2.3cm}rrrr>{\raggedright\arraybackslash}Xrr", r"\footnotesize\setlength{\tabcolsep}{4pt}")
    return made


def results_section(result: dict) -> str:
    zones, labels = result["zones"], result["summary"]["labels"]
    if not zones:
        return "The results were not compared: " + text(result["pairing"]["how"]) + "."
    parts = [
        r"Every value of ours stands beside yours, element by element and ply by ply, for the stresses and strains in the ply's own axes "
        r"and the invariants Abaqus reports. For each zone of the coupon and each quantity the table counts the values compared, how many "
        r"agree within 1\,\% and within 3\,\%, the largest difference, where it is (your element and the ply; our element too when it has "
        rf"another number), and both numbers there. Stresses are in {labels['stress']}; strains have no unit."]
    for zone in ZONES:
        if zone not in zones:
            continue
        judged = zone in JUDGED_ZONES and all(c.get("judged", True) for c in result["criteria"] if str(c["criterion"]).lower().startswith(zone))
        parts += [rf"\subsection*{{{ZONE_WORDS[zone]}}}",
                  rf"{zones[zone].get('elements', '?')} elements; " + ("judged." if judged else "reported, not judged."), zone_table(zones[zone])]
    return "\n\n".join(parts)


def reading_section(result: dict) -> str:
    parts = [
        r"This document puts one finite element model beside another. Where they agree, the two programs give the same answer for the same "
        r"model, which verifies each against the other. It is not a validation: neither model has been compared with a coupon test here.",
        r"A difference in the model's items (Section~\ref{sec:model}) is the first place to look, since two models that are not the same "
        r"model are not expected to give the same results. A difference in the results where every item agrees and the mesh is one mesh comes "
        r"from something the items do not list, or from the two programs themselves.",
    ]
    if not result["pairing"].get("same_mesh"):
        parts.append("The two models are on different meshes, so a value of yours stands beside the value of ours nearest its place, and a "
                     "difference between them includes the difference between the two meshes.")
    if result["verdict"] == "incomplete":
        parts.append("Not every part could be compared, and a part that was not compared is neither agreement nor difference: the table of "
                     r"Section~\ref{sec:rule} says which, and why.")
    return "\n\n".join(parts)


def file_section(result: dict) -> str:
    b = result["bundle"]
    rows = [[text(ROLE_WORDS.get(role, role)), code(CONTROL.sub(" ", str(entry["path"]))), str(entry["bytes"]), digest(entry["sha256"])]
            for role, entry in (b.get("files") or {}).items()]
    parts = [rf"The file you sent is one zip in the exchange format, version {text(b.get('bundle_version', '?'))}, with a SHA-256 for each file in it. "
             r"Nothing in it was executed: a script or a journal in it is kept and read as text. The file is yours: only you and the Anisotropy "
             r"team can see it, and this document is kept with it."]
    if rows:
        parts.append(table(["What", "File", "Bytes", "SHA-256"], rows,
                           r">{\raggedright\arraybackslash}p{3.4cm}>{\raggedright\arraybackslash}p{4.4cm}rY", r"\footnotesize"))
    return "\n\n".join(parts)


# ----------------------------------------------------------------------------------------------------------- the document

def section(title: str, label: str) -> str:
    """A section's heading, kept with at least the first lines of its text: a heading alone at the foot of a page moves on."""
    return rf"\needspace{{9\baselineskip}}\section{{{title}}}\label{{sec:{label}}}"


def document(result: dict, upload: str | None = None, run: str | None = None, compared: str | None = None) -> str:
    """The LaTeX of the whole document, from the comparison alone. Raises `NoDocument`."""
    result = checked(result)
    job = CONTROL.sub(" ", str(result["bundle"].get("job") or "the model sent")).strip()
    head = text(f"{job if len(job) <= HEAD_LETTERS else job[:HEAD_LETTERS - 3] + '...'} beside {result['ours']['coupon']}")  # one line of the page's head
    parts = [
        r"\documentclass[11pt,letterpaper]{article}", PREAMBLE,
        rf"\hypersetup{{pdftitle={{{TITLE}: {head}}}}}",
        r"\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}",
        rf"\fancyhead[L]{{\sffamily\footnotesize\color{{muted}}Anisotropy AI \textperiodcentered{{}} {TITLE} \textperiodcentered{{}} {head}}}",
        r"\fancyhead[R]{\sffamily\footnotesize\color{muted}\thepage}",
        r"\fancyfoot[C]{\sffamily\scriptsize\color{muted}One finite element model beside another; not validated against a coupon test.}",
        r"\begin{document}",
        title_block(result, upload, run, compared),
        section("What was compared, and by which rule", "rule"), rule_section(result),
        section("The model, item by item", "model"), model_section(result),
        section("The pull force", "reaction"), reaction_section(result),
        section("The results, zone by zone", "results"), results_section(result),
        section("What this shows and what it does not", "reading"), reading_section(result),
        section("The file you sent", "file"), file_section(result),
        r"\end{document}",
    ]
    return "\n\n".join(parts) + "\n"


def build(result: dict, out: Path, pdf: bool = True, upload: str | None = None, run: str | None = None, compared: str | None = None) -> Path:
    """Write `<out>/comparison.tex`, and `<out>/comparison.pdf` when `pdf` is set and Tectonic is installed. Returns the PDF, else the
    LaTeX. Raises `NoDocument`."""
    tex = out / f"{NAME}.tex"
    source = document(result, upload, run, compared)
    out.mkdir(parents=True, exist_ok=True)
    tex.write_text(source, encoding="utf-8")
    if not pdf:
        return tex
    compiler = manual.tectonic()
    if compiler is None:
        return tex
    # the texts in it came with a user's file: escaped above, and compiled with every feature Tectonic calls insecure off
    subprocess.run([compiler, "--untrusted", "--outdir", str(out), str(tex)], check=True)
    return out / f"{NAME}.pdf"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("comparison", type=Path, help="the result fea/tools/abaqus_upload.py compare --json wrote")
    parser.add_argument("--out", type=Path, required=True, help="the folder comparison.tex and comparison.pdf are written to")
    parser.add_argument("--upload", default=None, help="the upload's id, printed beside the file's SHA-256")
    parser.add_argument("--run", default=None, help="words that name the run of ours, printed beside it")
    parser.add_argument("--compared", default=None, help="when the comparison was made, printed as given")
    parser.add_argument("--no-pdf", action="store_true", help="write the LaTeX only")
    parser.add_argument("--json", type=Path, default=None, help="write what was done to this file: the document's path, or the reason there is none")
    args = parser.parse_args(argv)

    def answer(found: dict, code_: int) -> int:
        if args.json is not None:
            args.json.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
        return code_

    try:
        result = json.loads(args.comparison.read_text(encoding="utf-8"))
        written = build(result, args.out, pdf=not args.no_pdf, upload=args.upload, run=args.run, compared=args.compared)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{args.comparison}: {exc}", file=sys.stderr)
        return answer({"written": None, "reason": f"the comparison could not be read: {exc}"}, 2)
    except NoDocument as exc:
        print(str(exc), file=sys.stderr)
        return answer({"written": None, "reason": str(exc)}, 2)
    except subprocess.CalledProcessError as exc:  # the LaTeX is written; its compiler stopped
        print(f"Tectonic stopped with exit code {exc.returncode}; the LaTeX is at {args.out / (NAME + '.tex')}", file=sys.stderr)
        return answer({"written": str(args.out / f"{NAME}.tex"), "pdf": False, "reason": f"Tectonic stopped with exit code {exc.returncode}"}, 1)
    if not args.no_pdf and written.suffix != ".pdf":
        print(f"Tectonic not found; the LaTeX is at {written}", file=sys.stderr)
        return answer({"written": str(written), "pdf": False, "reason": "Tectonic is not installed, so no PDF was written"}, 0)
    print(f"written to {written}")
    return answer({"written": str(written), "pdf": written.suffix == ".pdf"}, 0)


if __name__ == "__main__":
    sys.exit(main())
