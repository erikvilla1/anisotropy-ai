"""The tools (ADR-0107; the wing's, ADR-0128). An MCP client starts this program and speaks to it over stdin and stdout; each tool asks the Anisotropy API on
this machine, so the engine and the fea package compute every number (ADR-0001) and a setup the API refuses is refused here in the same
words (ADR-0003). The client's own model writes the words the engineer reads, and no guard of ours runs on them: what this server can do
is hand it numbers with their units and their place, the theory section a reason rests on, and the rules below.

A live solve's fields run to megabytes, so a tool never returns them: the server keeps the last few results and answers questions about
them by an id. Nothing is written to disk and no port is opened.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import OrderedDict
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from . import results
from .api import Api, ApiRefused

REPO = Path(__file__).resolve().parents[3]
FORM = REPO / "lib" / "coupon-form-definition.json"  # the form the page is built from, written by fea/tools/export_form_definition.py
EXAMPLE_WING = REPO / "engine" / "examples" / "example-wing.toml"  # Anisotropy's example wing, the wing tools' `example`
EXAMPLE_REPAIRS = {"example": REPO / "engine" / "examples" / "example-patch-repair.toml",  # the repair tools' examples: a flush stepped repair
                   "example-external": REPO / "engine" / "examples" / "example-external-patch-repair.toml"}  # and a patch bonded on top
MAX_WING_FILE = 200_000  # characters, as the API takes a wing file's text
RESULTS_KEPT = 8
RUN_ONLY = ("solver", "document")  # setup items that concern the full run alone; the preview's solve goes ahead without them (ADR-0086)
PREVIEW = ("A preview of the rows as they stand: no mesh convergence study, no check by a second solver and no report. The full run with "
           "those is started from the workspace page.")
# An aside of the package's sentences about another program's viewer, which the workspace page cuts too (lib/studio-copy.ts, ADR-0091).
VIEWER_ASIDE = re.compile(r";\s*these are element centroids[^.;]*?,?\s*not the [^.;]*?a viewer such as PrePoMax shows\.")

INSTRUCTIONS = """Anisotropy analyses composite test coupons. These tools ask its analysis; you never compute.

Rules:
1. Lead with the answer in one short line: the value with its unit, the ply that fails first, or yes or no. Then at most three short lines of basis: the place (element, gauge section), the ply and its angle, the criterion, and that it is a preview. Give more only when the engineer asks for it.
2. Answer only what was asked. A question of one value gets that value, not the failure factors or the setup beside it.
3. Never name these tools, a solver program, a vendor, a file path or a model to the engineer. Say "the preview" for what solve_coupon solves and "the full run" for the one started from the workspace page.
4. Every number you state about a material, a setup or a result comes from a tool result of this server, with the unit it came with, printed as the tool wrote it to four significant figures at most; a formula from show_working keeps the numbers as it wrote them. Do not compute, estimate, convert or interpolate one yourself.
5. A setup is the rows of the coupon form. Read describe_coupon_form once before the first setup. Pass only what the engineer stated. When a required row is missing, ask for every missing row in one short message, in words and never by the rows' keys, with the form's default or example beside each row that has one, so the engineer can answer yes. If the engineer asks for an example or tells you to choose, use the form's example and say plainly which values were chosen by you and not by them.
6. solve_coupon solves a preview: say so once, in a few words. The full run, with a mesh convergence study, a check by a second solver and a report, is started from the workspace page.
7. Which ply fails first is the gauge section's answer, the test's: the criterion, the ply and its angle, the factor on the applied loading and the load at that factor, as the tool gives them. A factor above 1 means the laminate holds at the applied loading. A criterion the tool reports reached earlier at a gripped tab's edge is no failure of the coupon, since a value at a clamped edge grows as the mesh is refined; say it in one line, apart, after the answer.
8. For a value at a place use result_values; for where a quantity is largest use result_extreme; for a formula, a derivation or a proof use show_working and show its formulas as written, with their symbols and notes. When the engineer names one quantity and no criterion (the stress, the strain, the failure index, the load at failure), pass it as step and show that step alone, saying in a few words that the whole working is there if wanted. Lead with what was asked (the formula, or the step named), then give the tool's basis_line as it is written: it names the criterion, the ply and the place, and which criterion fails first when it is another. Say each symbol's meaning in words the first time it appears, from the tool's `what` and step titles. Its Tsai-Hill sum is not the failure index the results show (that index is 1/R); keep the two apart.
9. For why, use explain_result and answer in one to three sentences only from its facts and theory sections. Name the section you rest on. If the sections do not hold the reason, say that they do not; never fill the gap from general knowledge without saying it is not from Anisotropy's pages.
10. These tools read and solve a coupon. They do not change its shape beyond the form's rows, and they start no full run and write no report.
11. A question that leaves out the ply or the quantity means every ply and the stresses along the fibres, across them and in shear; ask back only for what has no such default, once, with the choices named. For an element that is not in the model, say the range in one line and give the values at the element where first ply failure is read, saying so. For the working of a criterion the result does not have, say in one line which it has and show the working of the one that fails first.

A wing: the wing tools read a wing file on this machine by its full path, or `example` for Anisotropy's example wing, and the API works it by hand in under a second.
12. A number about the wing comes from wing_results (margins, mass, deflection, frequencies), wing_rules (the design rules and their limits) or wing_strengths (the strengths the margins use, each with its basis and the report's page). A margin is given as the wing page prints it, with its sign and three decimals (+0.059); write it so. Name the strengths' basis beside a margin: B-basis, B-estimate or test mean.
13. Answer a wing question the way the wing page does: the answer first, in one sentence (the part, yes or no, or the value, with its basis), then at most three short lines of what it rests on. No table and nothing the engineer did not ask about unless they ask for more. Say parts and checks in words; never name a tool's fields.
14. For why, how, a design rule's purpose, a test method or an allowable, use search_wing_references and answer from its sections, naming the section. A value is never taken from a section: a rule's limit comes from wing_rules, a strength from wing_strengths.
15. A change of plies is previewed with preview_wing_change: plies of one angle added to or taken from one part over a stretch of the half span, in pairs (a symmetric laminate). Pass only what the engineer stated; when the count, the angle or the part is missing, ask. Report the engine's sentence, the lowest margin before and after, the mass and the rules the change leaves unmet. Nothing is applied: the engineer applies it on the wing page or in the file.

A bonded patch repair: the repair tools read a repair file on this machine by its full path, or `example` for Anisotropy's example of a flush stepped repair (`example-external` for a patch bonded on top), and the API works it by hand in under a second.
16. A number about the repair comes from repair_results (the hand calculation: the largest shear stress in the adhesive, where, and the load at which the adhesive reaches its elastic limit; with solve, the solved slice too: the peel stress, each ply, and what reaches its limit first), from preview_repair_change or from sweep_repair. Write it as the tool gives it, with its unit. Answer the way the repair's page does: the answer first in one sentence, then at most three short lines of what it rests on.
17. No tool gives the repair's strength, a failure load, a margin, an allowable or a verdict. The load at which the adhesive reaches its elastic limit is where it starts to yield, not where the repair fails: say "the adhesive reaches its elastic limit at ...", never "the repair carries", "is good for", "restores" or "is strong enough for". Asked whether a repair is strong enough or safe, say in one line that these tools give no strength or verdict, then what they do give.
18. A change is previewed with preview_repair_change, one change at a time: a quantity set to a value, with the unit as the engineer wrote it (the engine converts; you never do), or steps added, removed or regrouped. Pass only what the engineer stated; when the value is missing, ask for it. Report the engine's sentence and the numbers before and after. Nothing is applied: the engineer applies it on the repair's page or in the file.
19. A sweep (sweep_repair) works the repair by hand at every value of one quantity. With a load named it picks the smallest repair whose adhesive is still elastic at that load, and the tool solves that pick as a slice. Give the tool's `answer`, then what its `check` says, then its `cautions`, each as written. A pick is the model's answer: never call it a design, a recommendation, a minimum step length or a strength.
20. For why, how or what a thing is (why the shear peaks at the ends of a step, peel stress, what a pick means), use search_repair_references and answer from its sections, naming the section. A value is never taken from a section."""

Step = Literal["strain", "stress", "criterion", "loading"]  # the steps of the fea package's working, in order (ADR-0103)
Quantity = Literal["S11", "S22", "S12", "Mises", "Tresca", "Max. Principal", "Mid. Principal", "Min. Principal", "Pressure", "E11", "E22", "E12"]
READS = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
ASKS = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)  # a run record is written when the API keeps records


class Results:
    """The results the server holds, newest last, by a short id; the oldest goes when there are more than `kept`."""

    def __init__(self, kept: int = RESULTS_KEPT) -> None:
        self.kept = kept
        self.held: OrderedDict[str, dict] = OrderedDict()
        self.count = 0

    def keep(self, result: dict) -> str:
        self.count += 1
        name = f"r{self.count}"
        self.held[name] = result
        while len(self.held) > self.kept:
            self.held.popitem(last=False)
        return name

    def of(self, name: str) -> dict:
        if name not in self.held:
            have = f" It holds: {', '.join(self.held)}." if self.held else " It holds none yet."
            raise ToolError(f"No result {name!r} is held: this server keeps the last {self.kept} solves of this session.{have} Solve the coupon again with solve_coupon.")
        return self.held[name]


def form_definition(path: Path = FORM) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(f"The coupon form's definition could not be read at {path}: {exc}. This server runs from a checkout of the repository.") from exc


def form_rows(definition: dict) -> list[dict]:
    """The form's rows as a setup names them: each section's rows with their help, the sixteen ply rows as one `angles` list."""
    sections = []
    for section in definition["sections"]:
        rows = []
        for field in section["fields"]:
            if field["key"].startswith("ply_") and field["key"] != "ply_thickness":
                if field["key"] == "ply_1":
                    rows.append({"key": "angles", "kind": "list of angles in degrees", "required": True,
                                 "help": "the fibre angle of each ply, bottom ply first, counted from the coupon's length axis, the direction it is "
                                         "pulled: 0 = fibres along the pull. With symmetric = yes, list the lower half only. At most 16 entries."})
                continue
            row = {"key": field["key"], "label": field["label"], "kind": field["kind"], "required": bool(field.get("required")), "help": field.get("help") or ""}
            if field.get("default") is not None:
                row["default"] = field["default"]
            if field["kind"] == "list" and field.get("words"):
                row["one_of"] = field["words"]
            rows.append(row)
        sections.append({"section": section.get("title") or "", "rows": rows})
    return sections


def example_values(definition: dict) -> dict:
    """A setup that passes the check, on a public library material: an example to show the shape, never values to assume for an engineer."""
    tension = definition.get("tension", {})
    return {"filled_by": "<the engineer's name>", "date": "<today, YYYY-MM-DD>", "test": "unnotched tension", "standard": "none",
            "size_from": "<where the length, width and tabs come from, in the engineer's words>", "length": 250, "width": 25, "tab_length": 56,
            "angles": [45, 0, -45, 90], "symmetric": "yes", "library": "im7-8552", "G13": 4688.43, "G23": 3000.0,
            "control": tension.get("control", "displacement"), "value": tension.get("value", 1.0), "element_size": 2.0}


def setup_of(checklist: dict) -> dict:
    """The setup check as the tool reports it: what each passed item read, the items that did not pass with the rows to change, and
    which of those stop a solve."""
    items = checklist.get("items", [])
    return {"state": checklist.get("state"), "designation": checklist.get("designation"),
            # a full run's own items name this machine's programs and their paths: the preview needs neither, and the engineer is not told them
            "passed": {item["id"]: item.get("message") for item in items if item.get("state") == "pass" and item.get("id") not in RUN_ONLY},
            "not_passed": [{"id": item.get("id"), "label": item.get("label"), "state": item.get("state"), "message": item.get("message"),
                            **({"rows": item["rows"]} if item.get("rows") else {})}
                           for item in items if item.get("state") not in ("pass", "pending")],
            "not_judged": [item.get("id") for item in items if item.get("state") == "pending"],
            "problems": list(checklist.get("problems", [])),
            "blocking": [item["id"] for item in items if item.get("state") in ("fail", "missing") and item.get("id") not in RUN_ONLY],
            "full_run_only": [item["id"] for item in items if item.get("state") != "pass" and item.get("id") in RUN_ONLY]}


def as_read(found: dict) -> dict:
    """The coupon's card as the check read the rows: material, layup, size."""
    card = ((found.get("preview") or {}).get("coupon") or {}).get("card") or []
    return {"as_read": {row[0]: row[1] for row in card if isinstance(row, list) and len(row) == 2}} if card else {}


def sentences_of(explanation: dict) -> list[str]:
    """The package's sentences as the workspace page shows them: an aside about another program's viewer is cut (ADR-0091)."""
    return [VIEWER_ASIDE.sub(".", sentence) for sentence in explanation.get("sentences", [])]


def said(result: dict) -> str:
    """A tool's answer as the client's model reads it: compact JSON, the numbers as the API wrote them."""
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def answer_of(summary: dict) -> dict:
    """The solve's answer as the package wrote it (ADR-0085): the verdict, the first ply to fail by each criterion in the gauge section
    where the coupon has one (the verdict names a criterion reached earlier outside it), where that section is read (ADR-0108: at least
    `stand_off` from each tab line, the same distance on every mesh), the loading and the reaction."""
    gauge = summary.get("fpf_gauge")
    return {key: value for key, value in {
        "verdict": summary.get("verdict"),
        "first_ply_failure": gauge if gauge else summary.get("fpf"),
        "first_ply_failure_basis": "the gauge section" if gauge else "the whole model",
        "gauge_section_read": summary.get("gauge_reading") if gauge else None,
        "applied": summary.get("applied"), "reaction": summary.get("reaction"), "max_displacement": summary.get("max_displacement"),
    }.items() if value is not None}


WING = "The wing file (.toml) on this machine, by its full path, or example for Anisotropy's example wing"


def wing_text(wing: str) -> str:
    """A wing file's text, read from this machine: `example` is Anisotropy's own; any other is a .toml file by its path."""
    path = EXAMPLE_WING if wing.strip().lower() == "example" else Path(wing.strip()).expanduser()
    if path.suffix.lower() != ".toml":
        raise ToolError("A wing is given as a wing file (.toml) on this machine, by its full path, or as example for Anisotropy's example wing.")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ToolError(f"No wing file could be read at {path}: give its full path on this machine.") from exc
    if not text.strip() or len(text) > MAX_WING_FILE:
        raise ToolError(f"{path} is {'empty' if not text.strip() else 'larger than a wing file'}.")
    return text


REPAIR = ("The repair file (.toml) on this machine, by its full path, or example for Anisotropy's example of a flush stepped repair, or "
          "example-external for its example of a patch bonded on top")
MAX_REPAIR_FILE = 200_000  # characters, as the API takes a repair file's text
NOT_A_STRENGTH = ("The load at the adhesive's elastic limit is where the adhesive starts to yield, not the repair's strength: the adhesive "
                  "yields before it fails, and the hand calculation has no peel stress.")


def repair_text(repair: str) -> str:
    """A repair file's text, read from this machine: `example` and `example-external` are Anisotropy's own; any other is a .toml file
    by its path."""
    path = EXAMPLE_REPAIRS.get(repair.strip().lower()) or Path(repair.strip()).expanduser()
    if path.suffix.lower() != ".toml":
        raise ToolError("A repair is given as a repair file (.toml) on this machine, by its full path, or as example or example-external for "
                        "Anisotropy's two example repairs.")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ToolError(f"No repair file could be read at {path}: give its full path on this machine.") from exc
    if not text.strip() or len(text) > MAX_REPAIR_FILE:
        raise ToolError(f"{path} is {'empty' if not text.strip() else 'larger than a repair file'}.")
    return text


def four(value: Any) -> Any:
    """A tool's answer with every number as the repair's page prints it, to four significant figures: a client's model writes what it
    is given, and two programs that print the same result must agree to the digit (ADR-0136)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float):
        return float(f"{value:.4g}") if math.isfinite(value) else value
    if isinstance(value, dict):
        return {key: four(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [four(item) for item in value]
    return value


def hand_results(report: dict) -> dict:
    """The hand calculation of a repair as a client's model reads it: values picked out of the engine's report, never derived."""
    lap = report.get("lap") or {}
    answer = lap.get("answer")
    sizes = report.get("sizes") or {}
    found: dict[str, Any] = {"kind": report.get("kind"), "repair_width": sizes.get("repair_diameter"), "patch_width": sizes.get("patch_diameter"),
                             "plies_removed": sizes.get("plies_removed"), "plies_left_under_the_patch": sizes.get("plies_left"), "load": lap.get("load")}
    if not answer:
        return {**found, "bondline": "Not worked: the repair states no load per unit width."}
    peak = answer.get("peak_shear") or {}
    steps = [step.get("name") for step in lap.get("steps") or []]
    at = steps[peak["step"] - 1] if isinstance(peak.get("step"), int) and 0 < peak["step"] <= len(steps) else None  # as the page names it
    return {**found,
            "largest_bondline_shear": {"value": abs(peak["value"]) if peak.get("value") is not None else None, "at": at,
                                       "end": "inner end" if peak.get("end") == "end" else "outer end"},
            "elastic_limit_load": answer.get("elastic_limit_load", "Not given: the adhesive states no shear strength."),
            "patch_force_at_the_inner_end_of_each_step": dict(zip(steps, (answer.get("boundary_forces") or [])[1:], strict=False))}


def slice_results(solved: dict) -> dict:
    """A solved slice as a client's model reads it: the solve in one line, the largest shear and peel stress with their places, the
    loads at which the adhesive reaches its limits, the first ply and what comes first. The program and its mesh are left out."""
    report = solved.get("report") or {}
    bond = report.get("bond") or {}
    model = report.get("model") or {}
    return {"headline": solved.get("headline"), "load": report.get("load"),
            "largest_bondline_shear": bond.get("peak_shear"), "largest_peel_stress": bond.get("peak_peel"),
            "elastic_limit_load_in_shear": report.get("elastic_limit_load"),
            "load_at_the_peel_strength": report.get("peel_limit_load") if report.get("peel_limit_load") is not None else "Not judged: the adhesive states no peel strength.",
            "first_ply": report.get("first_ply") and {key: report["first_ply"].get(key) for key in ("name", "mode", "load")},
            "first_as_the_load_grows": report.get("first"), "cut_faces": model.get("cut_faces"),
            "note": "`r` is the distance from the repair's middle. Stresses in the adhesive are means over a short stretch of it, since a stress at "
                    "a corner grows as the mesh is refined. A ply is checked by maximum stress."}


CRITERION_NAMES = {"max_stress": "Maximum stress", "tsai_hill": "Tsai-Hill", "tsai_wu": "Tsai-Wu", "max_strain": "Maximum strain"}


def basis_line(criterion: str, chain: dict, first: str, chains: dict, basis: str | None) -> str:
    """The one line a working answer opens with (ADR-0107 amendment 4): the criterion and its factor, the ply and the place, the section
    it is read in and that it is a preview; and, when another criterion fails first, which and at what factor, so this one is never
    taken for the answer."""
    name = CRITERION_NAMES.get(criterion, criterion)
    line = f"{name}, factor {chain.get('factor')} on the applied loading: {chain.get('where')}, " \
           f"{'in the gauge section' if basis == 'gauge' else 'over the whole model'}, in the preview."
    if first != criterion and first in chains:
        line += f" {CRITERION_NAMES.get(first, first)} fails first, at a factor of {chains[first].get('factor')}."
    return line


def first_to_fail(summary: dict, basis: str | None, written: list[str]) -> str:
    """The criterion whose working the page shows when none is named: the answer's earliest, else the first written (ADR-0103)."""
    earliest = (summary.get("verdict") or {}).get("earliest") or summary.get("earliest_gauge" if basis == "gauge" else "earliest")
    return earliest if earliest in written else written[0]


def margin(value: float | None) -> float | None:
    """A margin as the wing page prints it: three decimals (ADR-0128)."""
    return None if value is None else round(value, 3)


def summary_shown(summary: dict | None) -> dict | None:
    """A preview's summary with its margins as the wing page prints them; every other value as the engine gave it."""
    if not summary:
        return summary
    governing = summary.get("governing")
    return {**summary, "lowest": {name: margin(value) for name, value in (summary.get("lowest") or {}).items()},
            "governing": governing and {**governing, "margin_ultimate": margin(governing.get("margin_ultimate"))}}


def results_of(report: dict) -> dict:
    """The wing's hand calculation as a client's model reads it: the verdict, what governs and where, each check's lowest margin with its
    case, the largest tip deflection and twist, the design summary, the aeroelastic speeds and the cases waiting. Values are picked out of
    the report, never derived."""
    cases = report.get("cases") or []
    lowest = {}
    for case in cases:
        for name, check in (case.get("checks") or {}).items():
            ultimate = (check or {}).get("margin_ultimate")
            if ultimate is not None and (name not in lowest or ultimate < lowest[name]["margin_ultimate"]):
                lowest[name] = {"margin_ultimate": ultimate, "case": case["number"], "label": case["label"],
                                **{key: check.get(key) for key in ("member", "station", "ply_angle", "mode")}, "margin_proof": check.get("margin_proof")}
    for found in lowest.values():  # margins as the wing page prints them, once the lowest are found on the engine's own numbers
        found["margin_ultimate"], found["margin_proof"] = margin(found["margin_ultimate"]), margin(found["margin_proof"])
    governing = report.get("governing")
    governing = governing and {**governing, "margin_ultimate": margin(governing.get("margin_ultimate"))}

    def largest(key: str) -> dict | None:
        top = max(cases, key=lambda c: abs(c.get(key) or 0.0), default=None)
        return None if top is None else {"value": top.get(key), "case": top["number"], "label": top["label"]}

    design = {key: value for key, value in (report.get("design") or {}).items() if key != "stretches"}
    material = report.get("material") or {}
    return {"wing": report.get("wing"), "units": report.get("units"), "passes": report.get("passes"), "cases_run": len(cases),
            "strengths": material.get("strength_basis"), "governing": governing, "lowest_by_check": lowest,
            "largest_tip_deflection": largest("tip_deflection"), "largest_tip_twist": largest("tip_twist"), "design": design,
            "aeroelastic": report.get("aeroelastic"), "cases_waiting": report.get("not_run"),
            "note": "The hand calculation: the box between the spars as a thin-walled beam. Margins are at ultimate load; a margin is the strength "
                    "ratio over the factor of safety, less one. Mass is one side of the wing, the box alone (no ribs). The finite element check "
                    "is started from the wing page."}


def build(api: Api, form_path: Path = FORM) -> MCPServer:
    """The server with its tools, asking `api`. The results it holds live as long as it does."""
    server = MCPServer("anisotropy", title="Anisotropy", instructions=INSTRUCTIONS, version="0.1.0")
    held = Results()

    def ask(call, *args):
        try:
            return call(*args)
        except ApiRefused as exc:
            raise ToolError(str(exc)) from exc

    def values_sent(values: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(values, dict) or not values:
            raise ToolError("values is the setup: an object of the coupon form's rows by key. Read describe_coupon_form for the rows.")
        # the form's version says which rows the keys mean; it is the form's, not a value of the coupon
        return {"form_version": form_definition(form_path)["form_version"], **values}

    def fields_of(result_id: str) -> dict:
        return held.of(result_id)["fields"]

    @server.tool(annotations=READS, structured_output=False)
    def list_materials() -> str:
        """The materials of Anisotropy's library, each with its dataset, its source's rights class, and whether a coupon setup can name it
        (the `library` row takes that id). Use material_values for a material's constants."""
        definition = form_definition(form_path)
        on_form = {(entry["Id"], entry.get("Dataset")): entry for entry in definition.get("library", [])}
        listed = []
        for record in ask(api.get, "/v1/materials"):
            entry = on_form.get((record.get("material_id"), record.get("dataset_id")))
            listed.append({**record, "coupon_library": entry is not None,
                           **({"ply_thickness_given": entry.get("Ply thickness (mm)") is not None} if entry is not None else {})})
        return said({"materials": listed, "note": "A coupon setup names a material by material_id in its `library` row; only those with coupon_library true. "
                     "Where ply_thickness_given is false the setup must state ply_thickness."})

    @server.tool(annotations=READS, structured_output=False)
    def material_values(material_id: Annotated[str, Field(description="A material_id from list_materials, e.g. im7-8552")],
                        dataset: Annotated[str | None, Field(description="A dataset_id of that material; leave out for its primary dataset")] = None) -> str:
        """The values the engine would use for a library material, in SI units, each with the page of its source."""
        if not material_id.replace("-", "").replace("_", "").isalnum() or (dataset and not dataset.replace("-", "").replace("_", "").replace(".", "").isalnum()):
            raise ToolError("A material's id and a dataset's id are letters, digits and hyphens, as list_materials gives them.")
        return said(ask(api.get, f"/v1/materials/{material_id}" + (f"?dataset={dataset}" if dataset else "")))

    @server.tool(annotations=READS, structured_output=False)
    def describe_coupon_form() -> str:
        """The rows a coupon setup is made of: each row's key, what it means, whether it is required, its choices and its default; which
        tests this API offers; and an example. Read it once before check_setup or solve_coupon."""
        definition = form_definition(form_path)
        every = bool(ask(api.get, "/v1/coupon-tests").get("all"))
        enabled = definition.get("enabled", {})
        return said({
            "form_version": definition["form_version"],
            "offered": "Every test of the form." if every else enabled.get("offered", ""),
            "tests_offered": next((r["one_of"] for s in form_rows(definition) for r in s["rows"] if r["key"] == "test"), []) if every else enabled.get("tests", []),
            "symmetric_layups_only": False if every else bool(enabled.get("symmetric_only")),
            "units": {"default": definition.get("units"), "systems": {name: system.get("words") for name, system in (definition.get("unit_systems") or {}).items()},
                      "note": "every number of a setup is in the unit system its `units` row names; results come back in the same units"},
            "sections": form_rows(definition),
            "materials": "the `library` row takes a material_id that list_materials marks coupon_library; or give the own_* rows with a source",
            "example": example_values(definition),
            "example_note": "The example shows the shape of a setup. Its numbers are an example's, not defaults: use them only when the engineer "
                            "asks for an example or tells you to choose, and then say which values you chose.",
        })

    @server.tool(annotations=ASKS, structured_output=False)
    def check_setup(values: Annotated[dict[str, Any], Field(description="The setup: the coupon form's rows by key (describe_coupon_form), e.g. "
                                                                    "{\"test\": \"unnotched tension\", \"angles\": [45, 0, -45, 90], \"symmetric\": \"yes\", ...}")]) -> str:
        """Judge a coupon setup without solving it: item by item (units, geometry, material, laminate, constraints, load, mesh), as the
        full run would judge it, with the rows to change where an item fails."""
        found = ask(api.post, "/v1/coupon-jobs/check", {"values": values_sent(values)})
        return said({"setup": setup_of(found.get("checklist") or {}), **as_read(found)})

    @server.tool(annotations=ASKS, structured_output=False)
    def solve_coupon(values: Annotated[dict[str, Any], Field(description="The setup: the coupon form's rows by key (describe_coupon_form)")]) -> str:
        """Check a coupon setup and, when nothing blocks, solve it as a preview. Returns the answer (which ply fails first, by which
        criterion, where, and at what multiple of the applied loading), the setup as it was read, the package's own sentences, and a
        result_id to ask further questions with. A preview: no mesh study, no check by a second solver, no report."""
        found = ask(api.post, "/v1/coupon-jobs/live", {"values": values_sent(values)})
        setup = setup_of(found.get("checklist") or {})
        fields = found.get("fields")
        if not fields:
            return said({"solved": False, "setup": setup, **as_read(found),
                         "note": "Nothing was solved: the setup items named in `blocking` do not pass. Their messages and rows say what to change."})
        explanation = found.get("explanation") or {}
        result_id = held.keep({"fields": fields, "explanation": explanation, "designation": found.get("designation")})
        return said({"solved": True, "result_id": result_id, "kind": PREVIEW, "seconds": found.get("seconds"),
                     "coupon": fields.get("coupon"), "setup": setup, **as_read(found),
                     "answer": answer_of(fields.get("summary") or {}), "sentences": sentences_of(explanation),
                     "can_be_asked": results.offer(fields)})

    @server.tool(annotations=READS, structured_output=False)
    def result_values(
        result_id: Annotated[str, Field(description="The result_id solve_coupon returned")],
        element: Annotated[int, Field(description="The element's number as the model labels it, e.g. 183")],
        plies: Annotated[list[int] | None, Field(description="Plies counted from the bottom face, starting at 1; leave out for every ply")] = None,
        quantities: Annotated[list[Quantity] | None, Field(description="Leave out for every quantity")] = None,
    ) -> str:
        """The stresses and strains of one element, ply by ply, in each ply's fibre axes, as the solve stored them, with what each failure
        criterion says of that ply there. S11, S22, S12: stress along the fibres, across them, and in-plane shear. E11, E22, E12: the strains."""
        try:
            return said(results.values_at(fields_of(result_id), element, plies, list(quantities) if quantities else None))
        except results.NotInResult as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=READS, structured_output=False)
    def result_extreme(
        result_id: Annotated[str, Field(description="The result_id solve_coupon returned")],
        quantities: Annotated[list[Quantity], Field(min_length=1, description="The quantities to find the extreme of")],
        sense: Annotated[Literal["largest", "smallest", "magnitude"], Field(description="largest: with its sign, the most tensile; smallest: the most "
                         "compressive; magnitude: the largest absolute value. Shear, Mises and Tresca are always read by magnitude.")] = "magnitude",
        region: Annotated[str, Field(description="default (the gauge section where the coupon has one, else the whole model), gauge, whole, or a "
                                                 "region's name from can_be_asked.regions")] = "default",
        plies: Annotated[list[int] | None, Field(description="Plies counted from the bottom face, starting at 1; leave out for every ply")] = None,
    ) -> str:
        """Where a stress or a strain is largest: the value, its ply and element, the plies tied at that value, and each ply's own extreme.
        A stored value is picked out; nothing is averaged or derived."""
        try:
            return said(results.extremes(fields_of(result_id), list(quantities), sense, region, plies))
        except results.NotInResult as exc:
            raise ToolError(str(exc)) from exc

    @server.tool(annotations=ASKS, structured_output=False)
    def explain_result(result_id: Annotated[str, Field(description="The result_id solve_coupon returned")],
                       question: Annotated[str, Field(min_length=1, max_length=2000, description="The engineer's question of why, in their words")]) -> str:
        """What to answer a question of why from: the result's fact sheet (the numbers the engine computed), the package's own sentences,
        and the sections of Anisotropy's theory pages the question's words find, with their text. Answer only from these, and name the section."""
        result = held.of(result_id)
        facts = result["explanation"].get("facts") or {}
        sections = ask(api.post, "/v1/workspace/theory-sections", {"question": question}).get("sections", [])
        return said({"question": question, "facts": facts, "sentences": sentences_of(result["explanation"]),
                "theory": [{"id": s["id"], "from": f"{s['document']}, {s['title']}", "text": s["text"]} for s in sections],
                "how_to_answer": ("Answer from the facts and the theory sections alone, and name the section the reason rests on. Every number in the "
                                  "answer is one of the facts. " + ("" if sections else "No section of the theory pages shares a word with this question: "
                                  "say that Anisotropy's pages do not hold this reason, and answer from the facts alone."))})

    def wing_answer(wing: str) -> dict:
        return ask(api.post, "/v1/wings/analyze", {"toml": wing_text(wing)})

    @server.tool(annotations=ASKS, structured_output=False)
    def read_wing(wing: Annotated[str, Field(description=WING)]) -> str:
        """The wing as the engine reads its file: its title, units, geometry, material and the strengths' basis, each part's half stack
        (the outer half of a symmetric laminate; a sandwich's is one face) and its zones along the span, the design rule limits and the
        flight envelope. Read it to say what the wing is before answering about it."""
        found = wing_answer(wing)
        return said({"wing": found.get("wing"), "note": "A half stack lists the plies from the outside in; the other half mirrors it. A zone is a stretch "
                     "of the half span, start and end as fractions from the root, with its own half stack; outside its zones a part has its own."})

    @server.tool(annotations=ASKS, structured_output=False)
    def wing_results(wing: Annotated[str, Field(description=WING)]) -> str:
        """The wing's hand calculation: whether it passes the flight cases run, what governs and where, each check's lowest margin at
        ultimate load with its case and place, the largest tip deflection and twist, the mass and stiffness, the first bending frequency,
        divergence and aileron reversal, and the cases that wait for inputs. Margins are on the strengths wing_strengths lists."""
        report = wing_answer(wing)["report"]
        return said(results_of(report))

    @server.tool(annotations=ASKS, structured_output=False)
    def wing_rules(wing: Annotated[str, Field(description=WING)],
                   part: Annotated[Literal["skin", "spar", "cap", "rib"] | None, Field(description="skin, spar (the webs), cap (the spar caps) or rib; leave "
                                                                                            "out for every part")] = None) -> str:
        """The design rules judged on each layup of the wing and at each ply drop along the span: the 10 % rule, plies of one angle in a
        row, balance, symmetry, plies ending at one place, the ply drop ratio and the outside ply over the drop, each met or not with the
        wing's own sentence, and the limits the wing sets."""
        report = wing_answer(wing)["report"]
        rules = [rule for rule in report.get("rules", []) if part is None or rule.get("part") == part]
        return said({"limits": report.get("rule_limits"), "rules": rules,
                     "note": "A rule not met is a warning: no margin changes with it. The limits are the wing file's [design_rules], or the defaults "
                             "(10 %, 4 in a row, 20 to 1, 2 per place); `span` is the stretch a layup holds over and `at` a ply drop's place, as "
                             "fractions of the half span." + ("" if rules else " No rule of this part: the wing has no such part, or no ply drop.")})

    @server.tool(annotations=ASKS, structured_output=False)
    def wing_strengths(wing: Annotated[str, Field(description=WING)]) -> str:
        """The ply strengths the wing's margins use: the material, the basis (B-basis from the material's public qualification report, or
        test means, which are not design values), the dataset, the report, and each strength in the file's stress unit with its basis
        (B-basis or B-estimate), its value in the report's unit and the report's page and link. Every part uses the one ply material."""
        report = wing_answer(wing)["report"]
        return said({"material": report.get("material"), "stress_unit": (report.get("units") or {}).get("stress"),
                     "roles": {"F1t": "tension along the fibres", "F1c": "compression along the fibres", "F2t": "tension across the fibres",
                               "F2c": "compression across the fibres", "F6": "in-plane shear"},
                     "note": "A B-estimate is the report's basis number from data that do not meet every statistical requirement; it is used where the "
                             "report recommends no value. Room temperature, dry: hot and wet strengths are not worked."})

    @server.tool(annotations=ASKS, structured_output=False)
    def search_wing_references(question: Annotated[str, Field(min_length=1, max_length=2000, description="The engineer's question, in their words")]) -> str:
        """The sections of Anisotropy's pages a question's words find: the wing's theory and three reference pages written in our own
        words, design rules for laminates, the test methods behind a strength and allowables, each section ending with its sources. For
        why, how, a rule's purpose, a test method or a basis. A section explains; its numbers are not the wing's."""
        sections = ask(api.post, "/v1/workspace/theory-sections", {"question": question, "about": "wing", "limit": 3}).get("sections", [])
        return said({"question": question, "sections": [{"id": s["id"], "from": f"{s['document']}, {s['title']}", "text": s["text"]} for s in sections],
                     "how_to_answer": ("Explain from these sections and name the one you rest on. A number about the wing, a rule's limit or a strength "
                                       "comes from wing_results, wing_rules or wing_strengths, never from a section. " + ("" if sections else
                                       "No section shares a word with this question: say that Anisotropy's pages do not hold it."))})

    @server.tool(annotations=ASKS, structured_output=False)
    def preview_wing_change(
        wing: Annotated[str, Field(description=WING)],
        action: Annotated[Literal["add_plies", "remove_plies"], Field(description="add_plies or remove_plies")],
        part: Annotated[Literal["skin", "spar", "spar_caps"], Field(description="skin, spar (the webs) or spar_caps")],
        angle: Annotated[float, Field(ge=-90, le=180, description="The plies' angle in degrees from the span, e.g. 0, 45, -45, 90")],
        count: Annotated[int, Field(ge=2, le=40, description="Plies of the whole laminate, both halves: 2 is one each side of the middle (one on each face "
                                                             "of a sandwich). Always even")],
        start: Annotated[float, Field(ge=0, lt=1, description="Where the change starts, as a fraction of the half span from the root: 0 is the root")] = 0.0,
        end: Annotated[float, Field(gt=0, le=1, description="Where it ends, as a fraction of the half span: 0.4 is 40 % span, 1 the tip")] = 1.0,
        placement: Annotated[Literal["beside", "middle"], Field(description="beside: next to the plies of that angle nearest the outside (the default); "
                                                                             "middle: at the middle of the laminate")] = "beside",
    ) -> str:
        """Preview a change of plies on the wing, never applied: the engine makes it on a copy of the wing file (splitting the part into
        zones where it covers a stretch) and works the wing as it is and as changed. Returns the change in one sentence with the stacks it
        gives, the summary before and after (the lowest margin and where, each check's lowest margin, mass, tip deflection, first bending
        frequency, the strengths' basis), the design rules of the part changed, and the part's table as changed."""
        change = {"action": action, "part": part, "angle": angle, "count": count, "start": start, "end": end, "placement": placement}
        found = ask(api.post, "/v1/wings/changes", {"toml": wing_text(wing), "change": change})
        return said({"words": found.get("words"), "before": summary_shown(found.get("before")), "after": summary_shown(found.get("after")),
                     "units": found.get("units"), "rules": found.get("rules"), "table_as_changed": (found.get("wing") or {}).get(part),
                     "applied": False, "note": "Nothing is applied. The engineer applies it with Apply on the wing page, or by changing the wing file "
                                               "themselves. Margins are at ultimate load, on the strengths' basis each summary names."})

    def repair_sent(repair: str) -> dict:
        return {"toml": repair_text(repair)}

    @server.tool(annotations=ASKS, structured_output=False)
    def read_repair(repair: Annotated[str, Field(description=REPAIR)]) -> str:
        """The repair as the engine reads its file: its kind (flush in a stepped cut, or a patch bonded on top), units, the laminate and
        its layup, the damage, the steps, the patch, the cover plies, the adhesive, the panel and the load, with the sizes they work out
        to (the depth of the cut, the plies removed and left, the patch's and the repair's width). Read it to say what the repair is."""
        found = ask(api.post, "/v1/repairs/analyze", repair_sent(repair))
        report = found.get("report") or {}
        return said(four({"repair": found.get("repair"), "kind": report.get("kind"), "units": report.get("units"), "sizes": report.get("sizes"),
                          "patch_layup": report.get("patch_layup"), "solve_still_needs": [need.get("words") for need in found.get("needs") or []],
                          "note": "Layups are listed from the bottom face up; the patch's from the deepest ply up (from the laminate upward for a patch "
                                  "bonded on top). Lengths, stresses and the load per unit width are in the file's own units."}))

    @server.tool(annotations=ASKS, structured_output=False)
    def repair_results(repair: Annotated[str, Field(description=REPAIR)],
                       solve: Annotated[bool, Field(description="true also solves the slice through the repair (a few seconds): the peel stress, each "
                                                                "ply's check and what reaches its limit first. Leave false for the hand calculation alone")] = False) -> str:
        """The repair's bondline worked by hand: the largest shear stress in the adhesive under the load stated, the step and the end it is
        at, the force the patch carries at the inner end of each step, and the load at which the adhesive reaches its elastic limit in
        shear. With solve, the solved slice beside it: the largest shear and peel stress and where, the first ply to reach a strength, and
        which comes first as the load grows. None of these is the repair's strength or a failure load."""
        sent = repair_sent(repair)
        report = ask(api.post, "/v1/repairs/analyze", sent).get("report") or {}
        answer = four({"by_hand": hand_results(report), "units": report.get("units"), "not_a_strength": NOT_A_STRENGTH})
        if solve:
            try:
                solved = api.post("/v1/repairs/solve", {**sent, "cut_faces": "open"})
                answer["solved_slice"] = four(slice_results(solved))
            except ApiRefused as exc:
                answer["solved_slice"] = {"not_solved": str(exc)}
        else:
            answer["solved_slice"] = "Not asked for: call again with solve true for the peel stress, the plies and what comes first."
        return said(answer)

    @server.tool(annotations=ASKS, structured_output=False)
    def preview_repair_change(
        repair: Annotated[str, Field(description=REPAIR)],
        action: Annotated[Literal["set", "add_steps", "remove_steps", "set_steps", "regroup", "regroup_steps"], Field(description=(
            "set: one quantity to a value. add_steps, remove_steps: count steps more or fewer. set_steps: the number of steps is count. "
            "regroup: the same plies in steps of count plies each. regroup_steps: the same plies cut in count steps"))],
        quantity: Annotated[Literal["step_length", "bondline", "load", "damage", "cover_overlap", "patch_overlap"] | None, Field(description=(
            "For set: step_length, bondline (the adhesive's thickness), load (per unit width), damage (its diameter), cover_overlap "
            "(a flush repair's cover plies) or patch_overlap (a patch bonded on top)"))] = None,
        value: Annotated[float | None, Field(description="For set: the value, as the engineer wrote it")] = None,
        unit: Annotated[str | None, Field(max_length=20, description="The unit the engineer wrote the value in (mm, in, N/mm, lb/in, ...); leave out "
                                                                     "when none was written and the file's own unit is meant. Never convert")] = None,
        count: Annotated[int | None, Field(ge=1, le=40, description="For the steps' actions: how many steps, or plies per step for regroup")] = None,
        angles: Annotated[list[float] | None, Field(max_length=40, description="For add_steps or set_steps where the patch's plies are listed: the "
                                                                                "angles of a new step's plies, in degrees")] = None,
    ) -> str:
        """Preview one change to the repair, never applied: the engine makes it on a copy of the repair file and works the repair by hand
        as it is and as changed. Returns the change in one sentence and, before and after, the steps, the repair's width, the load, the
        largest shear stress in the adhesive and where, and the load at the adhesive's elastic limit."""
        change = {key: value_ for key, value_ in {"action": action, "quantity": quantity, "value": value, "unit": unit, "count": count,
                                                   "angles": angles}.items() if value_ is not None}
        found = ask(api.post, "/v1/repairs/changes", {**repair_sent(repair), "change": change})
        return said(four({"words": found.get("words"), "before": found.get("before"), "after": found.get("after"), "units": found.get("units"),
                          "applied": False, "not_a_strength": NOT_A_STRENGTH,
                          "note": "Nothing is applied. The engineer applies it with Apply on the repair's page, or by changing the repair file "
                                  "themselves. The numbers are the hand calculation's: the solved slice is asked for with repair_results."}))

    @server.tool(annotations=ASKS, structured_output=False)
    def sweep_repair(
        repair: Annotated[str, Field(description=REPAIR)],
        quantity: Annotated[Literal["step_length", "bondline", "cover_overlap", "patch_overlap", "steps"], Field(description=(
            "What is varied: step_length, bondline (the adhesive's thickness), cover_overlap, patch_overlap, or steps (the same plies cut in "
            "every number of steps that divides them)"))],
        start: Annotated[float | None, Field(gt=0, description="The range's first value, with end; leave both out for a fifth of the value to twice it")] = None,
        end: Annotated[float | None, Field(gt=0, description="The range's last value")] = None,
        unit: Annotated[str | None, Field(max_length=20, description="The unit the range was written in; leave out for the file's own")] = None,
        load: Annotated[float | None, Field(gt=0, description="The load per unit width the adhesive is to stay elastic at, when the engineer names "
                                                               "one: the sweep then picks the smallest repair that does")] = None,
        load_unit: Annotated[str | None, Field(max_length=20, description="The unit the load was written in (N/mm, lb/in, ...); leave out for the file's own")] = None,
    ) -> str:
        """Work the repair by hand at every value of one quantity, about 25 of them: each row is a whole repair, with its width, its largest
        shear stress in the adhesive and the load at the adhesive's elastic limit. With a load, the pick is the smallest repair whose
        adhesive is still elastic at it (the nearest to the repair as it stands when the quantity leaves the width alone), and that pick is
        solved as a slice: `check` says what the slice gives and whether it holds the pick. Nothing is applied."""
        sweep = {key: value for key, value in {"quantity": quantity, "start": start, "end": end, "unit": unit, "load": load,
                                               "load_unit": load_unit}.items() if value is not None}
        found = ask(api.post, "/v1/repairs/sweeps", {**repair_sent(repair), "sweep": sweep})
        rows = [{"value": row.get("value"), "refused": row["refused"]} if row.get("refused") is not None else
                {key: row.get(key) for key in ("value", "steps", "plies_per_step", "repair_diameter", "peak_shear", "elastic_limit_load", "elastic", "current")
                 if row.get(key) is not None} for row in found.get("rows") or []]
        pick = found.get("pick")
        check = found.get("check")
        return said(four({"answer": found.get("answer"), "check": check and {key: check.get(key) for key in ("state", "holds", "words", "needs") if check.get(key) is not None},
                          "cautions": found.get("cautions"), "swept": found.get("words"), "quantity": found.get("quantity"), "units": found.get("units"),
                          "load_stated": found.get("load"), "load_named": found.get("target"), "pick": None if pick is None else rows[pick], "rows": rows,
                          "applied": False,
                          "note": "Every row is the hand calculation's, under the load the repair states; `elastic` says whether the adhesive is still "
                                  "elastic at the load named. The pick is the model's answer, not a design: give `answer`, `check` and `cautions` as "
                                  "written. Nothing is applied."}))

    @server.tool(annotations=ASKS, structured_output=False)
    def search_repair_references(question: Annotated[str, Field(min_length=1, max_length=2000, description="The engineer's question, in their words")]) -> str:
        """The sections of Anisotropy's pages a question about a bonded repair finds: the theory of the stepped lap and of the solved
        slice, and the page Bonded repairs, written in our own words, each section ending with its sources. For why, how or what a thing
        is: why the shear stress peaks at the ends of a step, why a longer step stops helping, peel stress, why the elastic limit is not
        the strength, what a sweep's pick means. A section explains; its numbers are not the repair's."""
        sections = ask(api.post, "/v1/workspace/theory-sections", {"question": question, "about": "repair", "limit": 3}).get("sections", [])
        return said({"question": question, "sections": [{"id": s["id"], "from": f"{s['document']}, {s['title']}", "text": s["text"]} for s in sections],
                     "how_to_answer": ("Explain from these sections and name the one you rest on. A number about the repair comes from repair_results, "
                                       "preview_repair_change or sweep_repair, never from a section. " + ("" if sections else
                                       "No section shares a word with this question: say that Anisotropy's pages do not hold it."))})

    @server.tool(annotations=READS, structured_output=False)
    def show_working(result_id: Annotated[str, Field(description="The result_id solve_coupon returned")],
                     criterion: Annotated[str | None, Field(description="max_stress or tsai_hill; leave out for every criterion that has its working")] = None,
                     step: Annotated[Step | None, Field(description="One step alone, when the engineer names one quantity: strain (the ply's strain in its "
                                                        "fibre axes), stress (the ply's stress from its strain), criterion (the failure index) or "
                                                        "loading (the load at first ply failure); leave out for the whole working")] = None) -> str:
        """The working behind the first ply to fail: each step's formula, the same formula with the result's numbers put in, and the value
        it gives, written by the fea package (LaTeX). Show the formulas as written; do not redo the arithmetic. With `step`, that one step
        of the criterion named, or of the criterion that fails first."""
        summary = fields_of(result_id).get("summary") or {}
        working = summary.get("working")
        written = (working or {}).get("criteria") or {}
        if not written:
            raise ToolError("This result has no working written: it is written for the first ply to fail by maximum stress and Tsai-Hill, of a laminate of plies.")
        if criterion is not None and criterion not in written:
            raise ToolError(f"No working for {criterion!r}. This result has it for: {', '.join(written)}.")
        note = "Each equation has its formula, the formula with the numbers put in (`substituted`) and its result. `source` names the theory section."
        first = first_to_fail(summary, working.get("basis"), list(written))
        lines = {c: basis_line(c, chain, first, written, working.get("basis")) for c, chain in written.items()}
        if step is None:
            shown = {criterion: written[criterion]} if criterion is not None else written
            return said({"basis": working.get("basis"), "digits": working.get("digits"), "fails_first": first,
                         "basis_line": lines[criterion] if criterion is not None else lines[first],
                         "criteria": shown, "note": note})
        chosen = criterion or first
        chain = written[chosen]
        found = [s for s in chain.get("steps") or [] if s.get("id") == step]
        if not found:
            raise ToolError(f"The working for {chosen} has no {step} step. It has: {', '.join(s.get('id', '?') for s in chain.get('steps') or [])}.")
        return said({"basis": working.get("basis"), "digits": working.get("digits"), "fails_first": first, "basis_line": lines[chosen],
                     "criteria": {chosen: {**chain, "steps": found}},
                     "whole_working": "show_working without step", "note": f"The {step} step alone, of {chosen}"
                     + (", the criterion that fails first" if criterion is None else "") + ". " + note})

    return server


def main() -> None:
    """Run over stdin and stdout, as an MCP client starts it. Nothing is printed to stdout but the protocol."""
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request to the API is noise in the client's log
    build(Api()).run("stdio")


if __name__ == "__main__":
    main()
