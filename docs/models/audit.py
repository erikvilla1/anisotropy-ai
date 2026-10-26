"""The audit of a coupon package (ADR-0043): its chapter in the coupon document and the form in the package.

Not a document of its own. docs/models/coupon.py gathers what our tools found (`gather`), scores it against the rubric
(`anisotropy_fea.audit.score`), prints the result as the document's audit chapter (`chapter`) and writes the same rows to the
audit form, `<package>-audit.xlsx` in the package folder (`anisotropy_fea.audit.write_form`). The form's cover and the chapter's
first table say the same things: what is audited (`audited`) and which files are compared (`files_compared`); how the package was
built goes to the form's Record sheet (`build_record`). The auditor fills in the form; a returned form goes in the coupon's
`team/<date>/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.audit import Evidence, Rubric, Scored, tolerance_text
from anisotropy_fea.compare import sha256_of
from anisotropy_fea.equivalence import DeckEquivalence, EquivalenceError, deck_equivalence
from anisotropy_fea.model import DeckError
from anisotropy_fea.spec import TEST_CODES

TEST_WORDS = {code: words for code, words in TEST_CODES.values()}  # "OHT" -> "open-hole tension"

MARK = {"Pass": r"\textcolor{passgreen}{Pass}", "Fail": r"\textcolor{accent}{\textbf{Fail}}", "N/A": r"\textcolor{muted}{N/A}",
        "Not checked": r"\textcolor{muted}{Not checked}", None: r"\textcolor{muted}{\textit{the auditor}}"}


def guide_counts(text: str, tag: Callable[[str], str]) -> tuple[int, int]:
    """The rebuild guide's open items (the list that closes it) and the values it tags ASSUMED (its legend row not counted)."""
    closing = text.rsplit("Open items of this guide", 1)
    open_items = closing[1].count(r"\item ") if len(closing) == 2 else 0
    assumed = text.count(tag("ASSUMED")) - text.count(tag("ASSUMED") + " & ")
    return open_items, assumed


def rebuilt_deck(team_files: Path) -> Path | None:
    """The deck an auditor built in Abaqus/CAE from our guide: the one .inp in the newest `team/<date>/rebuilt/` folder."""
    folders = sorted(team_files.glob("*/rebuilt")) if team_files.is_dir() else []
    if not folders:
        return None
    decks = sorted(folders[-1].glob("*.inp"))
    if len(decks) != 1:
        raise SystemExit(f"{folders[-1]}: holds {len(decks)} .inp files; keep the one deck rebuilt from the guide there")
    return decks[0]


def compare_rebuilt(path: Path | None, ours, units: str, tolerance_m: float) -> DeckEquivalence | str | None:
    """The rebuilt deck against ours, item by item as the team's deck is (B1 to B9), or why the two cannot be matched."""
    if path is None:
        return None
    try:
        return deck_equivalence(read_deck(path, units=units), ours, tolerance_m, units)
    except (EquivalenceError, DeckError) as exc:
        return f"{path.name}: {exc}"


def gather(*, test_code: str, units: str, card: list[tuple[str, str]], deck, solution, material: str | None, guide: tuple[int, int], c,
           fpf: tuple[str, float, int, float] | None, rebuilt: DeckEquivalence | str | None = None,
           fpf_others: tuple[tuple[str, float, int, float], ...] = (), fpf_notes: tuple[str, ...] = ()) -> Evidence:
    """What our tools found for the package; `c` is the team comparison (docs/models/team.py), None when the team has not built
    the coupon."""
    common = dict(test_code=test_code, units=units, card=tuple(card), our_deck=deck, solution=solution, material=material, fpf=fpf, guide=guide,
                  rebuilt=rebuilt, fpf_others=fpf_others, fpf_notes=fpf_notes)
    if c is None:
        return Evidence(**common)
    lo, hi = c.bands["inner"]
    free = c.bands["free length"]
    excluded = (f"Graded band y {lo:g} to {hi:g} {c.length_unit}: it leaves out {c.manifest.edge_band:g} {c.length_unit} beside each tab line "
                "(the edge band of our comparison settings, which are kept with us)\n"
                f"Free length y {free[0]:g} to {free[1]:g} {c.length_unit}: shown in the verification chapter, not graded")
    return Evidence(**common, team_deck=c.team_deck, team_deck_sha256=sha256_of(c.team_deck_path), equivalence=c.equivalence, paired=tuple(c.paired),
                    inner_band=(lo, hi), free_band=free, excluded=excluded, team_reports=tuple(p.name for p in c.report_paths))


def audited(*, card: dict[str, str], package: str, attempt: str | None) -> list[tuple[str, str]]:
    """What is audited, as the form's cover and the chapter's first table state it."""
    return [("Coupon", card["Coupon"]), ("Test", card["Test"]), ("Attempt", attempt or "none named"), ("Package", package)]


SUB = "  "  # a label that starts with it is a row under the one above: the team's file, then ours, file names only


def files_compared(*, c, our_deck: str, spec: str, physics: tuple[tuple[str, str], ...]) -> list[tuple[str, str]]:
    """What the audit compares, one row per thing compared and under it one row for the team's file and one for ours, by file name
    (no folder paths, at the founder's request): the cover's block and the chapter's table. `our_deck` and `spec` are package paths;
    only their names are shown; `physics` gives each section D check that applies to the test with who judges it, or that it is not
    built yet."""
    our_deck, spec = Path(our_deck).name, Path(spec).name
    physics = ("Physics", "our engine on its own, no Abaqus involved (section D): "
               + "; ".join(f"{check[:1].lower() + check[1:]} ({status})" for check, status in physics))
    if c is None:
        return [("The model", "the team has not built this coupon, so our model stands alone and sections B and C cannot be checked"),
                (SUB + "Our deck", f"{our_deck}, written from the spec {spec}"),
                ("Other values", "the reaction force, the displacements and strains, the first ply to fail: our engine's values are given, for the team to "
                                 "compare with its own model (section C)"),
                (SUB + "Our values", "in the Ours column of the Rubric sheet, the numbers behind them on the Results sheet; every ply of every "
                                     "element in ours-all-plies.csv"),
                physics]
    m = c.manifest.team
    return [("The model", "nodes, elements, layup, section, material, grips, boundary conditions and loads, step (section B)"),
            (SUB + "Team's deck", f"{c.team_deck_path.name} ({m.solver}, run {m.run_date})"),
            (SUB + "Our deck", f"{our_deck}, written from the spec {spec}"),
            ("The stresses", f"{', '.join(c.quantities)} at the same elements and plies, in the graded band (section C)"),
            (SUB + "Team's reports", ", ".join(p.name for p in c.report_paths) + ": the team's own exports, not repeated in this package"),
            (SUB + "Our values", ", ".join(f"ours-{q}.csv" for q in c.quantities)),
            ("Other values", "the reaction force, the displacements and strains, the first ply to fail (section C)"),
            (SUB + "Team's values", "left blank, for the team to fill in"),
            (SUB + "Our values", "in the Ours column of the Rubric sheet, the numbers behind them on the Results sheet"),
            physics]


def build_record(*, team_deck: str | None, team_sha256: str | None, fea_version: str, commit: str, run_by: str, built: str) -> list[tuple[str, str]]:
    """How the package was built: the form's Record sheet. The team deck's digest and the engine's commit live here, not on the cover."""
    return [("Team deck", team_deck or "none: the team has not built this coupon"), ("Team deck SHA-256", team_sha256 or "--"),
            ("Engine", f"anisotropy-fea {fea_version}, commit {commit}"), ("Run by", run_by), ("Built", built)]


MATH = ((r"gamma\_xy", r"$\gamma_{xy}$"), (r"eps\_x", r"$\varepsilon_x$"), (r"eps\_y", r"$\varepsilon_y$"), (r"N\_xy", r"$N_{xy}$"),
        (r"N\_x", r"$N_x$"), (r"N\_y", r"$N_y$"))  # the plain names of the form, set as the document writes them


def mathed(text: str) -> str:
    """Escaped evidence with the strain and section-force names as symbols."""
    for plain, symbol in MATH:
        text = text.replace(plain, symbol)
    return text


def chapter(rubric: Rubric, scored: tuple[Scored, ...], facts: list[tuple[str, str]], form: str, units: str, escape: Callable[[str], str],
            code: Callable[[str], str], table: Callable[..., str], kv_table: Callable[..., str], team_built: bool = True) -> str:
    """The audit chapter: what the audit is, the package's identity and the files compared, and one table per rubric section."""
    tools = [s for s in scored if s.result is not None]
    counts = {r: sum(s.result == r for s in tools) for r in ("Pass", "Fail", "N/A", "Not checked")}
    auditor = [s for s in scored if s.result is None]
    out = [
        rf"Every package is audited against one rubric, version {escape(rubric.version)} ({escape(rubric.status)}). Each row states what is "
        r"checked and what passes. Our tools judged the rows marked with a result, from the same computations as the chapters before; the rows "
        rf"marked \textcolor{{muted}}{{\textit{{the auditor}}}} are judged by the engineer who audits the package, on the form {code(form)} in this "
        r"package, where the team's values, ours and the difference stand side by side. A row that fails is a finding: the auditor names its cause "
        r"on the row (engine, our input, their model, documentation or tolerance), which decides who fixes it. Rows a Pass verdict does not need are "
        r"marked ``no'' under Req.; a row whose team value is not in the export yet is the auditor's, with our value stated.",
        rf"Our tools: {counts['Pass']} pass, {counts['Fail']} fail, {counts['N/A']} not applicable and {counts['Not checked']} not checked, of "
        rf"{len(tools)}; {len(auditor)} rows are the auditor's. To pass, every required row must be Pass or N/A; a required row that fails fails the "
        r"audit; a failed row a Pass does not need, or an observation, makes it Pass with observations."
        + ("" if team_built else
           r" The team has not built this coupon, so the rows of sections B and C that set the team's model beside ours cannot pass yet: "
           r"those our tools judge are Not checked, and those the auditor judges give our values, with the team's side left blank until the "
           r"team's model exists. The audit cannot pass before then. What can be judged now is the coupon's identity (section A) and our "
           r"engine's own checks (section D)."),
        r"Words of the rubric: the inner band of rows C2 and C3 is the free length less a strip beside each tab line, where the grips' hold on "
        r"the width is felt" + (" (the graded band of Chapter 6)" if team_built else "") + r"; the coupon's manifest is our comparison "
        r"settings for a team model, kept with us: which of the team's files are compared, and how wide that strip is.",
        *([escape("Rows that do not apply to this test, so they are not in this audit: "
                   + "; ".join(f"{item.id} ({item.check.lower()}), for {' and '.join(TEST_WORDS.get(code, code) for code in item.applies_to)} only"
                               for item in rubric.items if item.id not in {s.item.id for s in scored}) + ".")]
          if any(item.id not in {s.item.id for s in scored} for item in rubric.items) else []),
        r"\section{The package audited}",
        kv_table([((r"\quad " + escape(label.strip())) if label.startswith(SUB) else escape(label), escape(value)) for label, value in facts]),
    ]
    for section in rubric.sections:
        rows = [s for s in scored if s.item.section == section.id]
        if not rows:
            continue
        body = []
        for s in rows:
            tol = tolerance_text(s.item, units)
            check = (rf"\textbf{{{escape(s.item.check)}}}. {escape(s.item.acceptance)}" + (f" (tolerance {escape(tol)})" if tol else "")
                     + (rf" \textcolor{{muted}}{{Needs: {escape(s.item.needs)}.}}" if s.item.needs else ""))
            parts = [(label, lines) for label, lines in (("Team", s.found.team), ("Ours", s.found.ours), ("Difference", s.found.difference)) if lines]
            found = (r" \newline ".join(rf"\textbf{{{label}:}} " + r" \newline ".join(mathed(escape(line)) for line in lines) for label, lines in parts)
                     if parts else "--")
            body.append([escape(s.item.id), check, "yes" if s.item.required else "no", MARK[s.result], found])
        out += [r"\needspace{12\baselineskip}" + rf"\section{{{escape(section.id)}. {escape(section.title)}}}",  # a heading stays with its table
                table(["", "Check and what passes", "Req.", "Result", "What our tools found: the team's values, ours, the difference"], body,
                      r">{\raggedright\arraybackslash}p{0.6cm}>{\raggedright\arraybackslash}p{5.4cm}>{\raggedright\arraybackslash}p{0.7cm}"
                      r">{\raggedright\arraybackslash}p{1.6cm}Y", r"\footnotesize")]
    return "\n\n".join(out)
