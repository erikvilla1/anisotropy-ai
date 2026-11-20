"""The tools (ADR-0107). An MCP client starts this program and speaks to it over stdin and stdout; each tool asks the Anisotropy API on
this machine, so the engine and the fea package compute every number (ADR-0001) and a setup the API refuses is refused here in the same
words (ADR-0003). The client's own model writes the words the engineer reads, and no guard of ours runs on them: what this server can do
is hand it numbers with their units and their place, the theory section a reason rests on, and the rules below.

A live solve's fields run to megabytes, so a tool never returns them: the server keeps the last few results and answers questions about
them by an id. Nothing is written to disk and no port is opened.
"""

from __future__ import annotations

import json
import logging
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
4. Every number you state about a material, a setup or a result comes from a tool result of this server, with the unit it came with, printed as the tool wrote it to four significant figures at most. Do not compute, estimate, convert or interpolate one yourself.
5. A setup is the rows of the coupon form. Read describe_coupon_form once before the first setup. Pass only what the engineer stated. When a required row is missing, ask for every missing row in one short message. If the engineer asks for an example or tells you to choose, use the form's example and say plainly which values were chosen by you and not by them.
6. solve_coupon solves a preview: say so once, in a few words. The full run, with a mesh convergence study, a check by a second solver and a report, is started from the workspace page.
7. Which ply fails first is the gauge section's answer, the test's: the criterion, the ply and its angle, the factor on the applied loading and the load at that factor, as the tool gives them. A factor above 1 means the laminate holds at the applied loading. A criterion the tool reports reached earlier at a gripped tab's edge is no failure of the coupon, since a value at a clamped edge grows as the mesh is refined; say it in one line, apart, after the answer.
8. For a value at a place use result_values; for where a quantity is largest use result_extreme; for a formula, a derivation or a proof use show_working and show its formulas as written, with their symbols and notes. Its Tsai-Hill sum is not the failure index the results show (that index is 1/R); keep the two apart.
9. For why, use explain_result and answer in one to three sentences only from its facts and theory sections. Name the section you rest on. If the sections do not hold the reason, say that they do not; never fill the gap from general knowledge without saying it is not from Anisotropy's pages.
10. These tools read and solve a coupon. They do not change its shape beyond the form's rows, and they start no full run and write no report.
11. A question that leaves out the ply or the quantity means every ply and the stresses along the fibres, across them and in shear; ask back only for what has no such default, once, with the choices named. For an element that is not in the model, say the range in one line and give the values at the element where first ply failure is read, saying so. For the working of a criterion the result does not have, say in one line which it has and show the working of the one that fails first."""

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

    @server.tool(annotations=READS, structured_output=False)
    def show_working(result_id: Annotated[str, Field(description="The result_id solve_coupon returned")],
                     criterion: Annotated[str | None, Field(description="max_stress or tsai_hill; leave out for every criterion that has its working")] = None) -> str:
        """The working behind the first ply to fail: each step's formula, the same formula with the result's numbers put in, and the value
        it gives, written by the fea package (LaTeX). Show the formulas as written; do not redo the arithmetic."""
        working = (fields_of(result_id).get("summary") or {}).get("working")
        written = (working or {}).get("criteria") or {}
        if not written:
            raise ToolError("This result has no working written: it is written for the first ply to fail by maximum stress and Tsai-Hill, of a laminate of plies.")
        if criterion is not None and criterion not in written:
            raise ToolError(f"No working for {criterion!r}. This result has it for: {', '.join(written)}.")
        return said({"basis": working.get("basis"), "digits": working.get("digits"),
                "criteria": {criterion: written[criterion]} if criterion is not None else written,
                "note": "Each equation has its formula, the formula with the numbers put in (`substituted`) and its result. `source` names the theory section."})

    return server


def main() -> None:
    """Run over stdin and stdout, as an MCP client starts it. Nothing is printed to stdout but the protocol."""
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request to the API is noise in the client's log
    build(Api()).run("stdio")


if __name__ == "__main__":
    main()
