"""The tools as an MCP client calls them (ADR-0107), in process, against a stand-in for the API that answers with the files the fea
package wrote. Each tool passes on what the API or the result holds; none computes a number."""

import asyncio
import json

import httpx
from mcp import Client

from anisotropy_mcp import results
from anisotropy_mcp.api import Api
from anisotropy_mcp.server import INSTRUCTIONS, RESULTS_KEPT, build, example_values, form_definition, form_rows
from conftest import SECTIONS, Refused, fixture

VALUES = {"filled_by": "A. Engineer", "date": "2026-11-17", "test": "unnotched tension", "size_from": "an example", "length": 250, "width": 25, "tab_length": 56,
          "angles": [45, 0, -45, 90], "symmetric": "yes", "library": "im7-8552", "G13": 4688.43, "G23": 3000.0, "control": "displacement", "value": 1.0}
FIELDS = fixture("fields.json")
EXPLANATION = fixture("explanation.json")
TOOLS = ["list_materials", "material_values", "describe_coupon_form", "check_setup", "solve_coupon", "result_values", "result_extreme", "explain_result", "show_working"]


def test_the_server_offers_its_tools_each_described_and_tells_the_clients_model_the_rules(fake):
    server = build(Api("http://127.0.0.1:8000", transport=httpx.MockTransport(fake)))

    async def listed():
        async with Client(server) as client:
            return (await client.list_tools()).tools

    tools = asyncio.run(listed())
    assert [tool.name for tool in tools] == TOOLS and all(tool.description and len(tool.description) > 60 for tool in tools)
    by_name = {tool.name: tool for tool in tools}
    assert by_name["result_extreme"].input_schema["properties"]["quantities"]["items"]["enum"] == list(results.COLUMNS)
    assert by_name["result_values"].annotations.read_only_hint is True and by_name["solve_coupon"].annotations.read_only_hint is False
    assert by_name["solve_coupon"].annotations.destructive_hint is False and by_name["solve_coupon"].input_schema["required"] == ["values"]
    assert fake.calls == []  # listing the tools asks the API nothing
    for rule in ("comes from a tool result of this server", "four significant figures", "When a required row is missing, ask", "a preview by our kernel",
                 "answer only from its facts and theory sections", "start no full run"):
        assert rule in INSTRUCTIONS
    assert server.instructions == INSTRUCTIONS


def test_the_materials_are_the_apis_marked_with_whether_a_setup_can_name_them(call, fake):
    listed, values, with_dataset, unknown, odd = call(("list_materials", {}), ("material_values", {"material_id": "im7-8552"}),
                                                      ("material_values", {"material_id": "im7-8552", "dataset": "ncamp-im7-8552-2019-rtd-measured-v1"}),
                                                      ("material_values", {"material_id": "nothing-1"}), ("material_values", {"material_id": "../v1/runs"}))
    im7, other = listed["materials"]
    assert im7["material_id"] == "im7-8552" and im7["coupon_library"] is True and im7["ply_thickness_given"] is True and im7["rights"] == "open-publisher"
    assert other["coupon_library"] is False and "ply_thickness_given" not in other  # a second dataset of a material is not on the form
    assert values["E1_pa"] == 162095743962.38818 and values["dataset_asked"] is None
    assert with_dataset["dataset_asked"] == "ncamp-im7-8552-2019-rtd-measured-v1"
    assert isinstance(unknown, Refused) and "unknown library material 'nothing-1'" in unknown
    assert isinstance(odd, Refused) and "letters, digits and hyphens" in odd and len(fake.calls) == 4  # an id that is not one never reaches the API
    assert all(headers["x-anisotropy-actor"] == "assistant" for _, _, _, headers in fake.calls)


def test_the_form_is_described_by_its_rows_with_what_this_api_offers_and_an_example_that_names_only_rows(call, fake):
    form, = call(("describe_coupon_form", {}))
    rows = {row["key"]: row for section in form["sections"] for row in section["rows"]}
    assert form["form_version"] == form_definition()["form_version"] and form["tests_offered"] == ["unnotched tension"] and form["symmetric_layups_only"] is True
    assert "unnotched tension coupon" in form["offered"] and form["units"]["default"] == "mm-MPa" and set(form["units"]["systems"]) == {"mm-MPa", "m-Pa", "in-psi", "in-ksi"}
    required = [key for key, row in rows.items() if row["required"]]
    assert required == ["filled_by", "date", "test", "size_from", "length", "width", "angles", "control", "value"]
    assert "ply_1" not in rows and "ply_16" not in rows and "bottom ply first" in rows["angles"]["help"] and rows["ply_thickness"]["kind"] == "number"
    assert rows["control"]["one_of"] == ["displacement", "force"] and rows["element_size"]["default"] == 2.0 and "G13 = G12" in rows["G13"]["help"]
    assert set(form["example"]) <= set(rows) and form["example"]["library"] == "im7-8552" and "not defaults" in form["example_note"]
    assert form["example"] == example_values(form_definition()) and len(json.dumps(form)) < 25_000
    fake.all_tests = True
    every, = call(("describe_coupon_form", {}))
    assert every["offered"] == "Every test of the form." and "plate" in every["tests_offered"] and every["symmetric_layups_only"] is False
    assert [row["key"] for row in form_rows(form_definition())[0]["rows"]] == ["filled_by", "date", "notes"]


def test_a_setup_is_checked_by_the_api_as_it_was_given_with_the_forms_version(call, fake):
    checked, nothing = call(("check_setup", {"values": VALUES}), ("check_setup", {"values": {}}))
    method, path, body, _ = fake.calls[0]
    assert (method, path) == ("POST", "/v1/coupon-jobs/check") and body == {"values": {"form_version": form_definition()["form_version"], **VALUES}}
    setup = checked["setup"]
    assert setup["state"] == "ready" and setup["designation"] == "IM7-UNT-L1" and setup["blocking"] == [] and setup["not_passed"] == [] and setup["full_run_only"] == []
    assert setup["passed"]["geometry"] == "250 by 25 mm, 56 mm tabs with a node row on each tab line" and "1 mm" in setup["passed"]["load"]
    assert checked["as_read"]["Layup"] == "[45/0/-45/90]s, 8 plies of 0.18288 mm, 1.46304 mm thick"
    assert isinstance(nothing, Refused) and "values is the setup" in nothing and len(fake.calls) == 1
    older, = call(("check_setup", {"values": {**VALUES, "form_version": "0.7"}}))  # a version the caller states is passed on for the API to judge
    assert fake.calls[-1][2]["values"]["form_version"] == "0.7" and older["setup"]["state"] == "ready"


def test_a_solve_returns_the_packages_answer_and_sentences_and_an_id_never_the_fields(call, fake):
    solved, = call(("solve_coupon", {"values": VALUES}))
    summary = FIELDS["summary"]
    assert fake.calls[0][:2] == ("POST", "/v1/coupon-jobs/live") and fake.calls[0][2]["values"]["angles"] == [45, 0, -45, 90]
    assert solved["solved"] is True and solved["result_id"] == "r1" and solved["solver"] == "kernel" and "no CalculiX cross-check" in solved["kind"]
    assert solved["answer"]["verdict"] == summary["verdict"] and solved["answer"]["first_ply_failure"] == summary["fpf_gauge"]
    assert solved["answer"]["first_ply_failure_basis"] == "the gauge section" and solved["answer"]["reaction"] == summary["reaction"]
    assert solved["answer"]["first_ply_failure"]["tsai_hill"]["ply"] == 4 and solved["answer"]["applied"] == summary["applied"]
    assert solved["sentences"] == EXPLANATION["sentences"] and solved["coupon"]["layup"] == "[45/0/-45/90]s"
    assert solved["can_be_asked"] == results.offer(FIELDS) and solved["setup"]["blocking"] == []
    assert "element" not in solved and "fields" not in solved and len(json.dumps(solved)) < 12_000  # megabytes stay in the server


def test_a_setup_that_does_not_pass_is_not_solved_and_says_which_rows_to_change(call, fake):
    fake.blocked = True
    blocked, asked = call(("solve_coupon", {"values": {k: v for k, v in VALUES.items() if k != "length"}}), ("result_values", {"result_id": "r1", "element": 1}))
    assert blocked["solved"] is False and "result_id" not in blocked and blocked["setup"]["blocking"] == ["geometry"]
    assert blocked["setup"]["not_passed"] == [{"id": "geometry", "label": "Geometry defined", "state": "missing", "message": "Length (mm): required", "rows": ["Length (mm)"]}]
    assert isinstance(asked, Refused) and "No result 'r1' is held" in asked and "It holds none yet" in asked


def test_questions_about_a_result_are_answered_from_the_result_the_server_holds(call, fake):
    _, values, extreme, no_element, no_ply, no_result = call(
        ("solve_coupon", {"values": VALUES}),
        ("result_values", {"result_id": "r1", "element": 183, "plies": [4], "quantities": ["S22", "S11"]}),
        ("result_extreme", {"result_id": "r1", "quantities": ["S12"], "sense": "largest"}),
        ("result_values", {"result_id": "r1", "element": 9999}),
        ("result_extreme", {"result_id": "r1", "quantities": ["S11"], "plies": [12]}),
        ("result_values", {"result_id": "r7", "element": 1}))
    assert values == results.values_at(FIELDS, 183, [4], ["S11", "S22"]) and values["rows"][0]["values"]["S22"] == FIELDS["element"]["ply"]["stress_12"][182][3][1]
    assert extreme == results.extremes(FIELDS, ["S12"], "largest") and extreme["region"] == "the gauge section"
    assert isinstance(no_element, Refused) and "This model has no element 9999. Its elements are numbered 1 to 250." in no_element
    assert isinstance(no_ply, Refused) and "there is no ply 12" in no_ply
    assert isinstance(no_result, Refused) and "No result 'r7' is held" in no_result and "It holds: r1." in no_result
    assert len(fake.calls) == 1  # one solve; every question after it is read from what the server holds


def test_why_is_answered_from_the_fact_sheet_and_the_theory_sections_the_question_finds(call, fake):
    _, why = call(("solve_coupon", {"values": VALUES}), ("explain_result", {"result_id": "r1", "question": "why does ply 4 fail first?"}))
    method, path, body, _ = fake.calls[-1]
    assert (method, path, body) == ("POST", "/v1/workspace/theory-sections", {"question": "why does ply 4 fail first?"})  # the question alone: no result leaves
    assert why["facts"] == EXPLANATION["facts"] and why["sentences"] == EXPLANATION["sentences"] and why["question"] == "why does ply 4 fail first?"
    assert why["theory"] == [{"id": "engine:5-failure", "from": "Laminate theory, 5. Failure", "text": SECTIONS[0]["text"]}]
    assert "name the section" in why["how_to_answer"] and "do not hold" not in why["how_to_answer"]
    fake.sections = []
    _, none = call(("solve_coupon", {"values": VALUES}), ("explain_result", {"result_id": "r1", "question": "zzz qqq?"}))
    assert none["theory"] == [] and "pages do not hold this reason" in none["how_to_answer"] and none["facts"] == EXPLANATION["facts"]


def test_the_working_is_the_packages_formulas_with_the_numbers_put_in(call):
    _, both, one, unknown = call(("solve_coupon", {"values": VALUES}), ("show_working", {"result_id": "r1"}),
                                 ("show_working", {"result_id": "r1", "criterion": "tsai_hill"}), ("show_working", {"result_id": "r1", "criterion": "tsai_wu"}))
    written = FIELDS["summary"]["working"]
    assert both["criteria"] == written["criteria"] and both["basis"] == written["basis"] and both["digits"] == written["digits"]
    assert one["criteria"] == {"tsai_hill": written["criteria"]["tsai_hill"]} and "substituted" in json.dumps(one)
    assert isinstance(unknown, Refused) and "No working for 'tsai_wu'. This result has it for: max_stress, tsai_hill." in unknown


def test_the_server_holds_the_last_few_results_and_says_so_of_one_it_let_go(call):
    answers = call(*[("solve_coupon", {"values": VALUES})] * (RESULTS_KEPT + 1), ("result_values", {"result_id": "r1", "element": 1}),
                   ("result_values", {"result_id": f"r{RESULTS_KEPT + 1}", "element": 1, "plies": [1], "quantities": ["S11"]}))
    assert [a["result_id"] for a in answers[:RESULTS_KEPT + 1]] == [f"r{i}" for i in range(1, RESULTS_KEPT + 2)]
    assert isinstance(answers[-2], Refused) and f"keeps the last {RESULTS_KEPT} solves" in answers[-2] and "It holds: r2, " in answers[-2]
    assert answers[-1]["rows"][0]["values"]["S11"] == FIELDS["element"]["ply"]["stress_12"][0][0][0]


def test_what_the_api_refuses_the_tool_refuses_in_the_same_words(call, fake):
    fake.refuse = (429, "Every live solver is busy. Try again in a moment.")
    busy, = call(("solve_coupon", {"values": VALUES}))
    assert isinstance(busy, Refused) and busy.endswith("Every live solver is busy. Try again in a moment.")
    fake.refuse = (422, [{"loc": ["body", "values"], "msg": "Input should be a valid dictionary"}])
    odd, = call(("check_setup", {"values": VALUES}))
    assert isinstance(odd, Refused) and "values: Input should be a valid dictionary" in odd
