"""The working behind an answer (ADR-0103): the chain from the ply's strain to the loading at first-ply failure, written by the package
with every value its own or the engine's. Each step's result is the solve's, the values put in give that result when the step is repeated
by hand, and a chain that does not close is left out."""

from __future__ import annotations

import json
import math
import re

import numpy as np
import pytest

from anisotropy_fea import paths
from anisotropy_fea.abaqus_reader import read_deck
from anisotropy_fea.explain import DIGITS, explanation, printed
from anisotropy_fea.fields import field_data
from anisotropy_fea.kernel import solve_deck
from anisotropy_fea.membrane import solve_membrane
from anisotropy_fea.recovery import element_ply_states
from anisotropy_fea.working import GIVEN_DIGITS, SOURCES, WORKED, _max_stress_step, factor_tex, given, settled, tex, working_of

UNITS = "mm-MPa"
COUPON = {"designation": "IM7-UNT-L1", "test": "unnotched tension", "layup": "[45/0/-45/90]s"}


@pytest.fixture(scope="module")
def solved():
    deck = read_deck(paths.deck_path(paths.spec_path("unnotched-im7-8552-nodal"), "abaqus"), UNITS)
    return deck, solve_membrane(deck)


@pytest.fixture(scope="module")
def data(solved):
    deck, solution = solved
    return field_data(deck, solution, UNITS, coupon=COUPON)


def step(chain, name):
    return next(s for s in chain["steps"] if s["id"] == name)


def values(a_step):
    return {row["symbol"]: row["value"] for row in a_step["given"]}


def results(a_step):
    return {e["result"]["symbol"]: e["result"]["value"] for e in a_step["equations"] if e["result"]}


def close(by_hand: float, written: float) -> bool:
    """A step repeated with the values shown meets the result at the digits shown, within one unit of the last."""
    return abs(by_hand - written) <= 1.5 * 10 ** (math.floor(math.log10(abs(written))) - (DIGITS - 1)) if written else abs(by_hand) < 1e-12


def test_the_answers_working_is_written_for_each_criterion_on_the_answers_basis(data):
    working = data["summary"]["working"]
    table = data["summary"]["fpf_gauge"]
    assert working["basis"] == "gauge" == data["summary"]["verdict"]["basis"] and working["digits"] == {"given": GIVEN_DIGITS, "result": DIGITS}
    assert set(working["criteria"]) == {"max_stress", "tsai_hill"} <= set(WORKED)
    for criterion, chain in working["criteria"].items():
        entry = table[criterion]
        assert (chain["ply"], chain["angle"], chain["element"], chain["face"]) == (entry["ply"], entry["angle"], entry["label"].rsplit(".", 1)[-1], None)
        assert chain["factor"] == printed(entry["factor"]) and chain["where"] == f"ply {entry['ply']} (90°), element {chain['element']}"
        assert [s["id"] for s in chain["steps"]] == ["strain", "stress", "criterion", "loading"]
        assert [s["source"] for s in chain["steps"]] == [SOURCES[s["id"]] for s in chain["steps"]]


def test_every_result_is_the_solves_own(data):
    summary = data["summary"]
    for criterion, chain in summary["working"]["criteria"].items():
        entry = summary["fpf_gauge"][criterion]
        e, k = entry["element"], entry["ply"] - 1
        strain = data["element"]["ply"]["strain_12"][e][k]
        stress = data["element"]["ply"]["stress_12"][e][k]
        assert list(values(step(chain, "strain")).values())[:2] == [given(strain[0]), given(strain[1])]  # what the probe table shows
        got = results(step(chain, "stress"))
        assert got[r"\sigma_1"] == printed(stress[0]) and got[r"\sigma_2"] == printed(stress[1])
        assert got[r"\tau_{12}"] == printed(stress[2])
        assert results(step(chain, "criterion"))["R"] == printed(entry["factor"])
        assert results(step(chain, "criterion"))["1/R"] == printed(entry["index"])  # the failure index the results show (ADR-0103 am. 2)
        loading = results(step(chain, "loading"))
        assert loading[r"u_{\mathrm{FPF}}"] == printed(abs(entry["at_failure"]["applied"]))
        assert loading[r"F_{\mathrm{FPF}}"] == printed(abs(entry["at_failure"]["reaction"]))


def test_a_step_repeated_by_hand_with_the_values_shown_meets_its_result(data):
    for criterion, chain in data["summary"]["working"]["criteria"].items():
        strain, q = values(step(chain, "strain")), values(step(chain, "stress"))
        e1, e2, g12 = strain[r"\varepsilon_1"], strain[r"\varepsilon_2"], strain[r"\gamma_{12}"]
        stress = results(step(chain, "stress"))
        s1 = q["Q_{11}"] * e1 + q["Q_{12}"] * e2
        s2 = q["Q_{12}"] * e1 + q["Q_{22}"] * e2
        t12 = q["G_{12}"] * g12
        assert close(s1, stress[r"\sigma_1"]) and close(s2, stress[r"\sigma_2"]) and close(t12, stress[r"\tau_{12}"])
        assert s1 < 0 < s2  # the 90-degree ply of a pulled coupon: compressed along its fibres, pulled across them
        judged = step(chain, "criterion")
        f, r = values(judged), results(judged)
        if criterion == "max_stress":
            assert judged["title"] == "The maximum stress criterion" and "skipped" not in judged
            assert close(f["F_{1c}"] / -s1, r["R_1"]) and close(f["F_{2t}"] / s2, r["R_2"]) and close(f["F_6"] / abs(t12), r["R_6"])
            assert r["R"] == min(r["R_1"], r["R_2"], r["R_6"]) == r["R_2"] and "tension across the fibres" in judged["text"]
            assert close(s2 / f["F_{2t}"], r["1/R"]) and judged["equations"][-1]["formula"] == r"\frac{1}{R}"  # the largest stress over its strength
        else:
            index = (s1 / f["X"]) ** 2 - s1 * s2 / f["X"] ** 2 + (s2 / f["Y"]) ** 2 + (t12 / f["F_6"]) ** 2
            assert close(index, r[r"\mathrm{FI}"]) and close(1 / math.sqrt(index), r["R"])
            assert close(math.sqrt(index), r["1/R"]) and r["1/R"] > r[r"\mathrm{FI}"]  # the index the results show is the root of the sum
            assert judged["equations"][-1]["formula"] == r"\frac{1}{R} = \sqrt{\mathrm{FI}}" and "Tsai-Hill sum" in judged["note"]
            assert "F1c" in judged["given"][0]["what"] and "F2t" in judged["given"][1]["what"]  # the strengths by the sign of each stress
        last = step(chain, "loading")
        at, load = values(last), results(last)
        assert close(at["R"] * at["u"], load[r"u_{\mathrm{FPF}}"]) and close(at["R"] * at[r"F_{\mathrm{reaction}}"], load[r"F_{\mathrm{FPF}}"])


def test_the_values_written_in_a_formula_are_the_values_listed(data):
    """A substituted line is its formula with the step's own values in place of the symbols, and ends on the result."""
    for chain in data["summary"]["working"]["criteria"].values():
        strain, stress, last = step(chain, "strain"), step(chain, "stress"), step(chain, "loading")
        e, q = values(strain), values(stress)
        first = stress["equations"][0]
        assert first["formula"] == r"\sigma_1 = Q_{11}\,\varepsilon_1 + Q_{12}\,\varepsilon_2"
        assert first["substituted"] == (rf"\sigma_1 = {factor_tex(q['Q_{11}'])} \times {factor_tex(e[chr(92) + 'varepsilon_1'])} + {factor_tex(q['Q_{12}'])} \times "
                                        rf"{factor_tex(e[chr(92) + 'varepsilon_2'])} = {tex(first['result']['value'], DIGITS)}")
        assert "(-" in first["substituted"]  # a negative factor is written in brackets
        at = values(last)
        assert last["equations"][0]["substituted"] == rf"u_{{\mathrm{{FPF}}}} = {tex(at['R'])} \times {tex(at['u'])} = {tex(last['equations'][0]['result']['value'], DIGITS)}"
        for a_step in chain["steps"]:
            for equation in a_step["equations"]:
                assert equation["substituted"].count("{") == equation["substituted"].count("}")
                assert equation["formula"] is None or equation["formula"].count("{") == equation["formula"].count("}")


def test_working_that_does_not_close_is_left_out(solved, data):
    deck, solution = solved
    field = element_ply_states(solution)
    summary = json.loads(json.dumps(data["summary"]))
    summary.pop("working")
    assert set(working_of(solution, field, summary, UNITS)["criteria"]) == {"max_stress", "tsai_hill"}
    summary["fpf_gauge"]["tsai_hill"]["factor"] *= 1.001  # a factor the ply's stress does not give
    assert set(working_of(solution, field, summary, UNITS)["criteria"]) == {"max_stress"}
    summary["fpf_gauge"]["max_stress"]["ply"] = 2  # another ply's stress does not give this factor either
    assert working_of(solution, field, summary, UNITS) is None
    assert working_of(solution, field, {**data["summary"], "isotropic": True}, UNITS) is None


def test_a_result_with_no_criterion_has_no_working_and_the_explanation_still_reads(solved):
    deck, solution = solved
    none = field_data(deck, solution, UNITS, criteria=(), coupon=COUPON)
    assert "working" not in none["summary"]
    assert explanation(none["summary"], COUPON, UNITS, none["labels"])["sentences"]


def test_a_bending_coupon_is_worked_on_the_face_that_fails_first():
    """A shell state has two faces per ply (ADR-0053): the working is the governing face's, on the whole model."""
    deck = read_deck(paths.deck_path(paths.spec_path("three-point-im7-8552"), "abaqus"), UNITS)
    data = field_data(deck, solve_deck(deck), UNITS)
    working = data["summary"]["working"]
    assert working["basis"] == "whole"
    for criterion, chain in working["criteria"].items():
        entry = data["summary"]["fpf"][criterion]
        assert chain["face"] == entry["face"] in ("bottom", "top") and chain["where"].endswith(f"{entry['face']} face")
        face = ("bottom", "top").index(entry["face"])
        stress = data["element"]["ply"]["stress_12"][entry["element"]][entry["ply"] - 1][face]
        assert results(step(chain, "stress"))[r"\sigma_1"] == printed(stress[0])
        assert results(step(chain, "criterion"))["R"] == printed(entry["factor"])


def test_a_stress_that_is_zero_to_the_solvers_precision_is_written_as_zero_and_sets_no_limit():
    assert settled(np.array([-333.4, 60.6, 7.1e-15])).tolist() == [-333.4, 60.6, 0.0]
    assert settled(np.array([-0.0021751, 0.00741066, 1.5e-18])).tolist() == [-0.0021751, 0.00741066, 0.0]
    strengths = {"F1t": 2326.0, "F1c": 1731.0, "F2t": 64.05, "F2c": 285.7, "F6": 91.15}
    judged = _max_stress_step(np.array([-333.4, 60.6, 0.0]), strengths, 64.05 / 60.6, "transverse tension", "MPa")
    assert judged["skipped"] == [r"\tau_{12}"] and "left out" in judged["note"]
    assert [e["result"]["symbol"] for e in judged["equations"]] == ["R_1", "R_2", "R", "1/R"] and judged["equations"][-2]["formula"] == r"R = \min(R_1, R_2)"


def test_numbers_are_written_plainly_and_as_a_power_of_ten_outside_the_plain_range():
    assert [tex(v) for v in (162996.0, -0.0021751, 0.0, 64.0523, 1.0)] == ["162996", "-0.0021751", "0", "64.0523", "1"]
    assert tex(1.51788e-18) == r"1.51788 \times 10^{-18}" and tex(2.5e9) == r"2.5 \times 10^{9}" and tex(16742.07, DIGITS) == "16740"
    assert given(1.0320569813947693) == 1.03206 and given(0.0) == 0.0


def test_each_step_names_a_section_the_theory_pages_hold_and_no_program():
    pages = {"Laminate theory": (paths.ROOT / "engine/docs/theory.md").read_text(encoding="utf-8"),
             "Finite element theory": (paths.ROOT / "fea/docs/theory.md").read_text(encoding="utf-8")}
    for source in SOURCES.values():
        document, title = source.split(", ", 1)
        assert re.search(rf"^## {re.escape(title)}(?: \(`[^`]*`\))?$", pages[document], re.MULTILINE), source
    text = (paths.ROOT / "fea/src/anisotropy_fea/working.py").read_text(encoding="utf-8")
    strings = " ".join(re.findall(r'"([^"]*)"', text.split('"""', 2)[2]))
    assert not any(name in strings for name in ("Abaqus", "CalculiX", "PrePoMax"))


def test_the_pages_example_carries_the_working_the_package_writes_today(tmp_path):
    """`tests/fixtures/studio/fields.json` is what the page's tests show; its working must be the package's answer to `values.json` today
    (rewrite it from `uv run python tools/studio_tool.py live ../tests/fixtures/studio/values.json --out <dir>`, `summary.json`'s `working`)."""
    import subprocess
    import sys

    fixtures = paths.ROOT / "tests" / "fixtures" / "studio"
    done = subprocess.run([sys.executable, str(paths.ROOT / "fea" / "tools" / "studio_tool.py"), "--root", str(tmp_path / "none"), "live",
                           str(fixtures / "values.json"), "--out", str(tmp_path / "out")], capture_output=True, text=True, timeout=300, check=False)
    assert done.returncode == 0, done.stderr
    today = json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))["working"]
    assert json.loads((fixtures / "fields.json").read_text(encoding="utf-8"))["summary"]["working"] == today
    explained = json.loads((tmp_path / "out" / "explanation.json").read_text(encoding="utf-8"))
    assert today["criteria"]["tsai_hill"]["factor"] == explained["facts"]["tsai_hill_factor"]  # the working ends on the answer the sentences give
