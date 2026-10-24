"""The audit of a coupon package (ADR-0043): its chapter in the coupon document and the form in the package.

Not a document of its own. docs/models/coupon.py gathers what our tools found (`gather`), scores it against the rubric
(`anisotropy_fea.audit.score`), prints the result as the document's audit chapter (`chapter`) and writes the same rows to the
audit form, `<package>-audit.xlsx` in the package folder (`anisotropy_fea.audit.write_form`). The auditor fills in the form;
a returned form goes in the coupon's `team/<date>/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.audit import Evidence, Rubric, Scored, tolerance_text
from anisotropy_fea.compare import sha256_of
from anisotropy_fea.equivalence import DeckEquivalence, EquivalenceError, deck_equivalence
from anisotropy_fea.model import DeckError

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


def gather(*, test_code: str, units: str, card: list[tuple[str, str]], deck, solution, material: str | None, commit: str, attempt: str | None,
           guide: tuple[int, int], c, fpf: tuple[str, float, int] | None, rebuilt: DeckEquivalence | str | None = None) -> Evidence:
    """What our tools found for the package; `c` is the team comparison (docs/models/team.py), None when the team has not built
    the coupon."""
    common = dict(test_code=test_code, units=units, card=tuple(card), engine_commit=commit, attempt=attempt, our_deck=deck, solution=solution,
                  material=material, fpf=fpf, guide=guide, rebuilt=rebuilt)
    if c is None:
        return Evidence(**common)
    lo, hi = c.bands["inner"]
    free = c.bands["free length"]
    excluded = (f"the graded band is y {lo:g} to {hi:g} {c.length_unit}: it leaves out {c.manifest.edge_band:g} {c.length_unit} beside each tab line "
                f"(edge_band in the comparison manifest, {c.manifest_path.name}); the free length, y {free[0]:g} to {free[1]:g} {c.length_unit}, is "
                "shown in the verification chapter but not graded")
    return Evidence(**common, team_deck=c.team_deck, team_deck_sha256=sha256_of(c.team_deck_path), equivalence=c.equivalence, paired=tuple(c.paired),
                    inner_band=(lo, hi), free_band=free, excluded=excluded)


def cover(*, card: dict[str, str], package: str, attempt: str | None, commit: str, run_by: str, built: str, team_deck: str | None,
          team_sha256: str | None) -> list[tuple[str, str]]:
    """The package's identity, as the form's cover and the chapter's first table state it."""
    return [("Coupon", card["Coupon"]), ("Test", card["Test"]), ("Package", package), ("Attempt", attempt or "none named"),
            ("Engine commit", commit), ("Team deck", team_deck or "none: the team has not built this coupon"),
            ("Team deck SHA-256", team_sha256 or "--"), ("Run by", run_by), ("Built", built)]


def chapter(rubric: Rubric, scored: tuple[Scored, ...], facts: list[tuple[str, str]], form: str, units: str, escape: Callable[[str], str],
            code: Callable[[str], str], table: Callable[..., str], kv_table: Callable[..., str]) -> str:
    """The audit chapter: what the audit is, the package's identity, and one table per rubric section."""
    tools = [s for s in scored if s.result is not None]
    counts = {r: sum(s.result == r for s in tools) for r in ("Pass", "Fail", "N/A", "Not checked")}
    auditor = [s for s in scored if s.result is None]
    out = [
        rf"Every package is audited against one rubric, version {escape(rubric.version)} ({escape(rubric.status)}; ADR-0043). Each row states what is "
        r"checked and what passes. Our tools judged the rows marked with a result, from the same computations as the chapters before; the rows "
        rf"marked \textcolor{{muted}}{{\textit{{the auditor}}}} are judged by the engineer who audits the package, on the form {code(form)} in this "
        r"package, where problems are also recorded as findings. Rows a Pass verdict does not need are marked ``no'' under Req.; a check the team's "
        r"export cannot support yet stays Not checked.",
        rf"Our tools: {counts['Pass']} pass, {counts['Fail']} fail, {counts['N/A']} not applicable and {counts['Not checked']} not checked, of "
        rf"{len(tools)}; {len(auditor)} rows are the auditor's. The verdict is the auditor's: Fail if a required row fails or a Blocker or Major "
        r"finding is open; Pass with observations if anything else failed or any finding is open; Pass otherwise. It needs every required row to have "
        r"a result other than Not checked.",
        r"\section{The package audited}",
        kv_table([(escape(label), escape(value)) for label, value in facts]),
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
            body.append([escape(s.item.id), check, "yes" if s.item.required else "no", MARK[s.result], escape(s.evidence) or "--"])
        out += [rf"\section{{{escape(section.id)}. {escape(section.title)}}}",
                table(["", "Check and what passes", "Req.", "Result", "What our tools found"], body,
                      r">{\raggedright\arraybackslash}p{0.6cm}>{\raggedright\arraybackslash}p{5.4cm}>{\raggedright\arraybackslash}p{0.7cm}"
                      r">{\raggedright\arraybackslash}p{1.6cm}Y", r"\footnotesize")]
    return "\n\n".join(out)
