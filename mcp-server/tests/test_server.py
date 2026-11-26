"""The tools as an MCP client calls them (ADR-0107), in process, against a stand-in for the API that answers with the files the fea
package wrote. Each tool passes on what the API or the result holds; none computes a number."""

import asyncio
import json
import re
from pathlib import Path

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
TOOLS = ["list_materials", "material_values", "describe_coupon_form", "check_setup", "solve_coupon", "result_values", "result_extreme", "explain_result",
         "read_wing", "wing_results", "wing_rules", "wing_strengths", "search_wing_references", "preview_wing_change",
         "read_repair", "repair_results", "preview_repair_change", "sweep_repair", "search_repair_references", "show_working"]
EXAMPLE_WING = (Path(__file__).resolve().parents[2] / "engine" / "examples" / "example-wing.toml").read_text(encoding="utf-8")


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
    for rule in ("Lead with the answer in one short line", "Answer only what was asked", "Never name these tools, a solver program",
                 "comes from a tool result of this server", "four significant figures at most", "When a required row is missing, ask for every missing row",
                 "solve_coupon solves a preview", "is no failure of the coupon", "only from its facts and theory sections", "start no full run",
                 "ask back only for what has no such default", "never by the rows' keys", "show the working of the one that fails first",
                 "pass it as step and show that step alone", "then give the tool's basis_line as it is written", "Say each symbol's meaning in words",
                 "a formula from show_working keeps the numbers as it wrote them"):
        assert rule in INSTRUCTIONS
    assert not re.search(r"calculix|prepomax|abaqus|\bkernel\b", INSTRUCTIONS + "".join(tool.description for tool in tools), re.I)  # ADR-0091
    assert server.instructions == INSTRUCTIONS


def test_the_materials_are_the_apis_marked_with_whether_a_setup_can_name_them(call, fake):
    listed, values, with_dataset, unknown, odd = call(("list_materials", {}), ("material_values", {"material_id": "im7-8552"}),
                                                      ("material_values", {"material_id": "im7-8552", "dataset": "ncamp-im7-8552-2019-rtd-measured-v1"}),
                                                      ("material_values", {"material_id": "nothing-1"}), ("material_values", {"material_id": "../v1/runs"}))
    im7, other = listed["materials"]
    assert im7["material_id"] == "im7-8552" and im7["coupon_library"] is True and im7["ply_thickness_given"] is True and im7["rights"] == "open-publisher"
    assert other["coupon_library"] is False and "ply_thickness_given" not in other  # a second dataset of a material is not on the form
    assert values["E1_pa"] == 162095743962.38818 and "dataset_asked" not in values and {v["role"] for v in values["values"]} >= {"F1t", "F2t", "F6"}
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


def test_a_preview_of_a_setup_that_asks_for_nonlinear_geometry_says_it_is_a_linear_solve(call, fake):
    """A preview is a linear solve whatever the setup asks (ADR-0142): a plate's shape is followed only by a full run on the page."""
    plain, asked = call(("solve_coupon", {"values": VALUES}), ("solve_coupon", {"values": {**VALUES, "nonlinear_geometry": True}}))
    assert "note" not in plain and fake.calls[-1][2]["values"]["nonlinear_geometry"] is True  # the row goes to the API as given
    assert "this preview is a linear solve" in asked["note"] and "does not scale with the load" in asked["note"]
    assert not re.search(r"calculix|prepomax|abaqus|\bkernel\b", asked["note"], re.I)  # ADR-0091


def test_a_solve_returns_the_packages_answer_and_sentences_and_an_id_never_the_fields(call, fake):
    solved, = call(("solve_coupon", {"values": VALUES}))
    summary = FIELDS["summary"]
    assert fake.calls[0][:2] == ("POST", "/v1/coupon-jobs/live") and fake.calls[0][2]["values"]["angles"] == [45, 0, -45, 90]
    assert solved["solved"] is True and solved["result_id"] == "r1" and "solver" not in solved and "no check by a second solver" in solved["kind"]
    assert not re.search(r"calculix|prepomax|tectonic|\bkernel\b|[A-Z]:\\\\", json.dumps(solved), re.I)  # no program of the machine, nor its path (ADR-0091)
    assert "solver" not in solved["setup"]["passed"] and "document" not in solved["setup"]["passed"]
    first, outside = solved["answer"]["first_ply_failure"], solved["answer"]["verdict"]["outside_earlier"]
    assert {**solved["answer"]["verdict"], "outside_earlier": summary["verdict"]["outside_earlier"]} == summary["verdict"]
    assert {c: {**entry, "element": summary["fpf_gauge"][c]["element"]} for c, entry in first.items()} == summary["fpf_gauge"]
    # every element by its own number, as the page, the working and result_values give it; the package's 182 is its place in a list (ADR-0107 am. 5)
    assert first["tsai_hill"]["element"] == first["max_stress"]["element"] == "183" == FIELDS["summary"]["working"]["criteria"]["tsai_hill"]["element"]
    assert summary["fpf_gauge"]["tsai_hill"]["element"] == 182 and "182" not in json.dumps(solved["answer"])
    assert outside["element"] == "56" and outside["label"] == "Strip-1.56" and summary["verdict"]["outside_earlier"]["element"] == 55
    assert solved["answer"]["first_ply_failure_basis"] == "the gauge section" and solved["answer"]["reaction"] == summary["reaction"]
    assert solved["answer"]["gauge_section_read"] == summary["gauge_reading"] and summary["gauge_reading"]["stand_off"] == 6.25  # ADR-0108
    assert solved["answer"]["first_ply_failure"]["tsai_hill"]["ply"] == 4 and solved["answer"]["applied"] == summary["applied"]
    assert len(solved["sentences"]) == len(EXPLANATION["sentences"]) and solved["coupon"]["layup"] == "[45/0/-45/90]s"
    assert any("PrePoMax" in said for said in EXPLANATION["sentences"])  # the package's aside, cut as the page cuts it
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
    assert why["facts"] == EXPLANATION["facts"] and why["question"] == "why does ply 4 fail first?"
    assert len(why["sentences"]) == len(EXPLANATION["sentences"]) and not any("PrePoMax" in said for said in why["sentences"])
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
    assert both["fails_first"] == "tsai_hill" and both["basis_line"] == (
        "Tsai-Hill, factor 1.032 on the applied loading: ply 4 (90°), element 183, in the gauge section, in the preview.")
    assert one["basis_line"] == both["basis_line"]
    assert one["criteria"] == {"tsai_hill": written["criteria"]["tsai_hill"]} and "substituted" in json.dumps(one)
    assert isinstance(unknown, Refused) and "No working for 'tsai_wu'. This result has it for: max_stress, tsai_hill." in unknown


def test_one_step_of_the_working_is_the_one_the_engineer_named_of_the_criterion_that_fails_first(call):
    # "equation for stress" asked through an MCP client got all four steps, as the page did (ADR-0103 amendment 1, ADR-0107 amendment 4)
    _, stress, named, flawed = call(("solve_coupon", {"values": VALUES}), ("show_working", {"result_id": "r1", "step": "stress"}),
                                    ("show_working", {"result_id": "r1", "step": "criterion", "criterion": "max_stress"}),
                                    ("show_working", {"result_id": "r1", "step": "stress", "criterion": "tsai_wu"}))
    written = FIELDS["summary"]["working"]["criteria"]
    assert FIELDS["summary"]["verdict"]["earliest"] == "tsai_hill"
    [chain] = stress["criteria"].values()
    assert list(stress["criteria"]) == ["tsai_hill"] and chain["steps"] == [written["tsai_hill"]["steps"][1]]
    assert chain["steps"][0]["title"] == "The ply's stress from its strain" and chain["ply"] == written["tsai_hill"]["ply"]
    assert "the criterion that fails first" in stress["note"] and stress["whole_working"] == "show_working without step"
    assert named["criteria"]["max_stress"]["steps"] == [written["max_stress"]["steps"][2]] and "fails first" not in named["note"]
    assert stress["basis_line"].startswith("Tsai-Hill, factor 1.032") and "fails first" not in stress["basis_line"]
    # a criterion asked for that does not fail first says which does, so its factor is never taken for the answer (the real run's
    # "show the working for max stress" headed "Max stress governs at R = 1.057")
    assert named["basis_line"] == ("Maximum stress, factor 1.057 on the applied loading: ply 4 (90°), element 183, in the gauge section, "
                                   "in the preview. Tsai-Hill fails first, at a factor of 1.032.")
    assert isinstance(flawed, Refused) and "No working for 'tsai_wu'" in flawed


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


# The wing's tools (ADR-0128): each reads a wing file by its path or `example`, asks the API, and passes on what the engine answered.
WING = fixture("example-answer.json", Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "wing")


def test_a_wing_is_read_from_its_file_or_the_example_and_sent_as_its_text(call, fake, tmp_path):
    kept = tmp_path / "my-wing.toml"
    kept.write_text(EXAMPLE_WING, encoding="utf-8")
    read, by_path = call(("read_wing", {"wing": "example"}), ("read_wing", {"wing": str(kept)}))
    assert read["wing"] == WING["wing"] and "half stack lists the plies from the outside in" in read["note"]
    assert by_path == read
    assert [c[2] for c in fake.calls] == [{"toml": EXAMPLE_WING}, {"toml": EXAMPLE_WING}]
    assert all(c[3]["x-anisotropy-actor"] == "assistant" for c in fake.calls)
    other = tmp_path / "notes.txt"
    other.write_text("x", encoding="utf-8")
    for given in (str(other), str(tmp_path / "missing.toml"), "../../etc/passwd"):
        refused = call(("read_wing", {"wing": given}))[0]
        assert isinstance(refused, Refused) and ("wing file" in refused), refused
    assert len(fake.calls) == 2, "a file that is not a wing file is never sent"


def test_the_results_are_the_reports_values_picked_out_with_their_case_and_place(call):
    found = call(("wing_results", {"wing": "example"}))[0]
    report = WING["report"]
    assert found["passes"] is True and found["cases_run"] == 34 and found["strengths"] == "B-basis"
    printed = round(report["governing"]["margin_ultimate"], 3)  # a margin as the wing page prints it, +0.059
    assert found["governing"] == {**report["governing"], "margin_ultimate": printed} and printed == 0.059
    skin = found["lowest_by_check"]["skin plies"]
    assert skin["margin_ultimate"] == printed and skin["case"] == 6 and skin["member"] == "upper skin"
    tip = max(report["cases"], key=lambda c: abs(c["tip_deflection"]))
    assert found["largest_tip_deflection"] == {"value": tip["tip_deflection"], "case": tip["number"], "label": tip["label"]}
    assert found["design"]["mass"] == report["design"]["mass"] and "stretches" not in found["design"]
    assert found["units"]["mass"] == "kg" and "no ribs" in found["note"]


def test_the_rules_and_the_strengths_are_the_wings_own(call):
    every, skin, caps, strengths = call(("wing_rules", {"wing": "example"}), ("wing_rules", {"wing": "example", "part": "skin"}),
                                        ("wing_rules", {"wing": "example", "part": "cap"}), ("wing_strengths", {"wing": "example"}))
    assert every["limits"] == {"min_percent": 10.0, "max_in_a_row": 4, "drop_ratio": 20.0, "max_dropped": 2} and every["rules"] == WING["report"]["rules"]
    assert {r["part"] for r in skin["rules"]} == {"skin"} and not next(r for r in skin["rules"] if r["rule"] == "ten_percent")["met"]
    assert caps["rules"] == [] and "no such part" in caps["note"]
    material = strengths["material"]
    assert material["strength_basis"] == "B-basis" and material["estimates"] == ["F1c", "F6"] and strengths["stress_unit"] == "MPa"
    assert next(s for s in material["strengths"] if s["role"] == "F1c")["page"] == 46


def test_a_question_finds_the_wings_reference_sections_and_never_a_value_from_them(call, fake):
    found = call(("search_wing_references", {"question": "what ply drop ratio should I use?"}))[0]
    assert fake.calls[-1][2] == {"question": "what ply drop ratio should I use?", "about": "wing", "limit": 3}
    assert found["sections"][0]["from"] == "Design rules for laminates, Ply drops: How long the run-out is"  # the API's own search of the wing's pages
    assert "never from a section" in found["how_to_answer"]


def test_a_change_is_previewed_never_applied_and_one_the_wing_cannot_take_is_refused_in_the_engines_words(call, fake):
    change = {"action": "add_plies", "part": "skin", "angle": 0, "count": 2, "start": 0, "end": 0.4}
    previewed, caps, odd = call(("preview_wing_change", {"wing": "example", **change}),
                                ("preview_wing_change", {"wing": "example", **change, "part": "spar_caps"}),
                                ("preview_wing_change", {"wing": "example", **change, "count": 1}))
    assert fake.calls[0][2] == {"toml": EXAMPLE_WING, "change": {**change, "placement": "beside"}}
    assert previewed["words"].startswith("Two 0° plies added to the skin from the root to 40 % of the half span")
    assert previewed["applied"] is False and previewed["table_as_changed"]["zones"][0]["end"] == 0.4
    assert previewed["after"]["lowest"]["skin plies"] > previewed["before"]["lowest"]["skin plies"]
    assert previewed["before"]["governing"]["margin_ultimate"] == 0.059 and previewed["after"]["strength_basis"] == "B-basis"
    assert all(round(value, 3) == value for value in previewed["after"]["lowest"].values()), "margins as the wing page prints them"
    assert isinstance(caps, Refused) and caps.endswith(": The wing has no spar caps: add them on the Layup step first.")
    assert isinstance(odd, Refused) and len(fake.calls) == 2, "an odd count is refused before the API is asked"


# The repair's tools (ADR-0136): each reads a repair file by its path or an example's name, asks the API, and passes on what the engine
# and the solved slice answered, every number to the four figures the repair's page prints.
REPAIRS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "repair"
REPAIR = fixture("example-answer.json", REPAIRS)
EXAMPLE_REPAIR = (Path(__file__).resolve().parents[2] / "engine" / "examples" / "example-patch-repair.toml").read_text(encoding="utf-8")


def test_the_rules_for_a_repair_keep_the_elastic_limit_apart_from_a_strength():
    for rule in ("No tool gives the repair's strength, a failure load, a margin, an allowable or a verdict",
                 'never "the repair carries", "is good for", "restores" or "is strong enough for"', "the engine converts; you never do",
                 "Give the tool's `answer`, then what its `check` says, then its `cautions`, each as written",
                 "never call it a design, a recommendation, a minimum step length or a strength", "A value is never taken from a section"):
        assert rule in INSTRUCTIONS


def test_a_repair_is_read_from_its_file_or_an_example_and_sent_as_its_text(call, fake, tmp_path):
    kept = tmp_path / "my-repair.toml"
    kept.write_text(EXAMPLE_REPAIR, encoding="utf-8")
    read, by_path, on_top = call(("read_repair", {"repair": "example"}), ("read_repair", {"repair": str(kept)}), ("read_repair", {"repair": "example-external"}))
    assert read["repair"] == REPAIR["repair"] and read["kind"] == "flush" and read["sizes"]["repair_diameter"] == 125.0 and read["solve_still_needs"] == []
    assert read["sizes"]["thickness"] == 1.463, "a size as the repair's page prints it, to four figures"
    assert by_path == read and on_top["kind"] == "external"
    assert [c[1] for c in fake.calls] == ["/v1/repairs/analyze"] * 3 and fake.calls[0][2] == {"toml": EXAMPLE_REPAIR} and fake.calls[0][3]["x-anisotropy-actor"] == "assistant"
    for given in ("repair.json", str(tmp_path / "missing.toml")):
        refused = call(("read_repair", {"repair": given}))[0]
        assert isinstance(refused, Refused) and "repair file" in refused, refused
    assert len(fake.calls) == 3, "a file that is not a repair file is never sent"


def test_a_repairs_results_are_the_hand_calculations_and_the_solved_slice_only_when_asked(call, fake):
    hand = call(("repair_results", {"repair": "example"}))[0]
    by_hand = hand["by_hand"]
    assert by_hand["largest_bondline_shear"] == {"value": 12.58, "at": "Ledge of step 1", "end": "inner end"} and by_hand["elastic_limit_load"] == 238.5
    assert by_hand["load"] == 100.0 and by_hand["repair_width"] == 125.0 and hand["units"]["force"] == "N/mm"
    assert by_hand["patch_force_at_the_inner_end_of_each_step"] == {"Cover overlap": 8.608, "Ledge of step 1": 24.66, "Ledge of step 2": 47.58,
                                                                    "Ledge of step 3": 52.24, "Floor": 53.03}
    assert "not the repair's strength" in hand["not_a_strength"] and isinstance(hand["solved_slice"], str)
    assert [c[1] for c in fake.calls] == ["/v1/repairs/analyze"], "the slice is solved only when it is asked for"
    solved = call(("repair_results", {"repair": "example", "solve": True}))[0]["solved_slice"]
    assert fake.calls[-1][1] == "/v1/repairs/solve" and fake.calls[-1][2] == {"toml": EXAMPLE_REPAIR, "cut_faces": "open"}
    assert solved["largest_bondline_shear"] == {"value": 11.5, "r": 37.29, "part": "Adhesive on the ledge of step 2"}
    assert solved["largest_peel_stress"] == {"value": 4.112, "r": 62.45, "part": "Adhesive under the cover plies"}
    assert solved["elastic_limit_load_in_shear"] == 260.8 and solved["first_as_the_load_grows"] == {"what": "adhesive", "load": 260.8}
    assert solved["first_ply"] == {"name": "Laminate ply 6 (-45°)", "mode": "transverse tension", "load": 466.1}
    assert solved["headline"].endswith("first, the adhesive reaches its elastic limit in shear at 260.8 N/mm")
    text = json.dumps(solved)
    assert not re.search(r"calculix|ccx|CPE8R|abaqus", text, re.I), "the program and its element are not handed to the client's model (ADR-0091)"
    # a slice that cannot be solved leaves the hand calculation whole and says why
    fake.no_solver = True
    kept = call(("repair_results", {"repair": "example", "solve": True}))[0]
    assert kept["by_hand"] == by_hand and kept["solved_slice"] == {"not_solved": "The slice cannot be solved right now. Try again in a minute."}


def test_a_change_to_a_repair_is_previewed_never_applied_with_its_unit_as_written(call, fake):
    added, longer, nine, none = call(("preview_repair_change", {"repair": "example", "action": "add_steps", "count": 1}),
                                     ("preview_repair_change", {"repair": "example", "action": "set", "quantity": "step_length", "value": 0.5, "unit": "in"}),
                                     ("preview_repair_change", {"repair": "example", "action": "set_steps", "count": 9}),
                                     ("preview_repair_change", {"repair": "example", "action": "set_steps", "count": 0}))
    assert fake.calls[0][2] == {"toml": EXAMPLE_REPAIR, "change": {"action": "add_steps", "count": 1}}, "only what was stated is sent"
    assert fake.calls[1][2]["change"] == {"action": "set", "quantity": "step_length", "value": 0.5, "unit": "in"}, "the unit goes as written: the engine converts"
    assert added["words"].startswith("Five steps in place of four") and added["applied"] is False
    assert (added["before"]["steps"], added["after"]["steps"], added["after"]["repair_diameter"]) == (4, 5, 150.0)
    assert added["after"]["peak_shear"] == {"value": 12.58, "name": "Ledge of step 1", "end": "end"} and added["after"]["elastic_limit_load"] == 238.5
    assert longer["words"] == "The step length goes from 12.5 mm to 12.7 mm (0.5 in as written)." and longer["after"]["repair_diameter"] == 126.2
    assert isinstance(nine, Refused) and nine.endswith("9 steps of 1 plies remove 9 plies, and the laminate has 8")
    assert isinstance(none, Refused) and len(fake.calls) == 3, "a count below one is refused before the API is asked"


def test_a_sweep_gives_its_answer_its_check_and_its_cautions_and_never_a_strength(call, fake):
    swept = call(("sweep_repair", {"repair": "example", "quantity": "step_length", "start": 3, "end": 25, "unit": "mm", "load": 230, "load_unit": "N/mm"}))[0]
    assert fake.calls[0][1] == "/v1/repairs/sweeps" and fake.calls[0][2]["sweep"] == {"quantity": "step_length", "start": 3, "end": 25, "unit": "mm", "load": 230, "load_unit": "N/mm"}
    assert swept["answer"] == ["The smallest of these whose adhesive is still elastic at 230 N/mm: a step length of 4 mm, the repair 74 mm across. "
                               "Its adhesive reaches its elastic limit at 233.5 N/mm."]
    assert swept["check"]["state"] == "solved" and swept["check"]["holds"] is True and swept["check"]["words"][-1] == "That is at or above the 230 N/mm named: the slice holds the pick."
    assert swept["cautions"][0].startswith("Not the repair's strength") and "not a rule for choosing a step length" in swept["cautions"][1]
    assert swept["pick"] == {"value": 4.0, "steps": 4, "plies_per_step": 1, "repair_diameter": 74.0,
                             "peak_shear": {"value": 12.85, "name": "Ledge of step 1", "end": "end"}, "elastic_limit_load": 233.5, "elastic": True, "current": False}
    assert [row["value"] for row in swept["rows"] if row.get("current")] == [12.5], "the repair as it stands is marked among the rows"
    assert len(swept["rows"]) == 24 and swept["rows"][0]["elastic"] is False and swept["rows"][-1] == {"value": 25.0, "refused": swept["rows"][-1]["refused"]}
    assert swept["applied"] is False and swept["load_named"] == 230 and swept["load_stated"] == 100.0
    text = json.dumps(swept)
    assert not re.search(r"\bmargin|\bsafe\b|strong enough|\bcarries\b|recommend", text, re.I)
    assert not re.search(r"calculix|ccx|abaqus", text, re.I)
    refused = call(("sweep_repair", {"repair": "example", "quantity": "bondline"}))[0]
    assert isinstance(refused, Refused)  # what the API refuses is passed on in its words


def test_a_question_finds_the_repairs_reference_sections_and_never_a_value_from_them(call, fake):
    found = call(("search_repair_references", {"question": "why does the shear stress peak at the ends of a step?"}))[0]
    assert fake.calls[-1][2] == {"question": "why does the shear stress peak at the ends of a step?", "about": "repair", "limit": 3}
    assert found["sections"][0]["from"] == "Bonded repairs, Why the shear stress peaks at the ends of a step"
    assert "never from a section" in found["how_to_answer"]
