import test from "node:test";
import assert from "node:assert/strict";
import { buildAnalysisRequest, exampleForm } from "../lib/laminate-api";
import {
  calculatorHandoffKey, DEFAULT_LAYUP, DEFAULT_LIBRARY, defaultHeroState, heroForm, loadsEntered, readCalculatorHandoff, zeroLoads,
} from "../lib/home-calculator";
import { expandLayup } from "../lib/layup";

test("the default stack is the IM7/8552 NCAMP dataset at its ply thickness, a quasi-isotropic layup and no loads", () => {
  const state = defaultHeroState();
  assert.equal(state.library, DEFAULT_LIBRARY);
  assert.equal(state.layup, DEFAULT_LAYUP);
  assert.equal(state.thickness_mm, "0.18288");
  assert.equal(state.loads, null);
  assert.equal(loadsEntered(state.loads), false);
});

test("the hero form sends the dataset reference, one thickness per expanded ply and zeros for the loads not given", () => {
  const state = defaultHeroState();
  const angles = expandLayup(state.layup).layup!.angles;
  const form = heroForm(state, angles)!;
  assert.equal(form.plies.length, 8);
  assert.deepEqual(form.plies[0], { angle_deg: "45", thickness_mm: "0.18288" });
  assert.deepEqual(form.loads, zeroLoads());
  const built = buildAnalysisRequest(form);
  assert.ok(built.request);
  assert.deepEqual(built.request.material, { library_id: "im7-8552", dataset_id: "ncamp-im7-8552-2019-rtd-measured-v1" });
  assert.deepEqual(built.request.plies.map((ply) => ply.angle_deg), [45, -45, 0, 90, 90, 0, -45, 45]);
  assert.ok(Math.abs(built.request.plies[0].thickness_m - 0.00018288) < 1e-18); // 0.18288 mm to m, floating point
  assert.equal(built.request.loads.Nx, 0);
  assert.equal(heroForm({ ...state, library: "nowhere::none" }, angles), null);
});

test("loads count as entered only when one of them is not zero, blanks aside", () => {
  assert.equal(loadsEntered({ ...zeroLoads(), Nx: "25000" }), true);
  assert.equal(loadsEntered({ ...zeroLoads(), Mx: " " }), false);
  assert.equal(loadsEntered(zeroLoads()), false);
  assert.equal(loadsEntered({ ...zeroLoads(), Ny: "-1e3" }), true);
});

test("the handoff reads back exactly the form it stored and rejects anything else", () => {
  const form = exampleForm();
  const stored = JSON.stringify({ form });
  assert.deepEqual(readCalculatorHandoff(stored), form);
  assert.deepEqual(readCalculatorHandoff({ form }), form);
  assert.equal(calculatorHandoffKey, "laminate-calculator-handoff");
  for (const bad of [null, "", "{", "[]", JSON.stringify({}), JSON.stringify({ form: { material: {} } }),
    JSON.stringify({ form: { ...form, plies: [] } }), JSON.stringify({ form: { ...form, plies: [{ angle_deg: 45 }] } }),
    JSON.stringify({ form: { ...form, loads: { Nx: "1" } } })]) {
    assert.equal(readCalculatorHandoff(bad), null, String(bad));
  }
});
