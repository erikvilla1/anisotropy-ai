import { test } from "node:test";
import assert from "node:assert/strict";
import { blankDraft, type LaminateDraft } from "../lib/laminate-chat";
import { couponOffer, couponRowsFrom, laminateDraftFrom, laminateOffer, laminateUnit, laminateUnitNeeded } from "../lib/proposals";
import { readProposalAnswer, type Proposal } from "../lib/studio-api";
import { blankForm, exampleForm } from "../lib/studio-form";

const p = (key: string, value: string, unit: string | null = null, label = key): Proposal =>
  ({ key, label, value, unit, written_value: value, written_unit: unit, quote: `${key} ${value}` });

test("a coupon offers its choices, its numbers in its own system's units, the layup and the loading, and shows the model no name or source", () => {
  const form = { ...exampleForm("2026-11-10"), filled_by: "A. Engineer", notes: "for the review", own_name: "X-Lamina", own_source: "a datasheet" };
  const { rows, form: view } = couponOffer(form);
  const byKey = Object.fromEntries(rows.map((r) => [r.key, r]));
  assert.deepEqual([byKey.length.unit, byKey.own_E1.unit, byKey.force.unit, byKey.displacement.unit], ["mm", "MPa", "N", "mm"]);
  assert.equal(byKey.own_nu12.unit, undefined);
  assert.equal(byKey.test.kind, "choice");
  assert.ok(byKey.test.choices!.some((c) => c.value === "open-hole tension" && c.label === "Open-hole tension"));
  assert.ok(byKey.library.choices!.some((c) => c.value === "im7-8552"));
  assert.equal(byKey.layup.kind, "notation");
  for (const key of ["value", "units", "filled_by", "own_name", "own_source", "notes", "ply_1", "mesh_nx", "tab_bevel", "name_part"]) assert.equal(byKey[key], undefined, key);
  assert.equal(view.layup, "[45/0/-45/90]s");
  for (const key of ["filled_by", "notes", "own_name", "own_source", "date", "ply_1"]) assert.equal(view[key], undefined, key);
  const inches = couponOffer({ ...blankForm("in-ksi"), units: "in-ksi" }).rows;
  assert.deepEqual(["length", "own_E1", "force"].map((k) => inches.find((r) => r.key === k)!.unit), ["in", "ksi", "lbf"]);
});

test("ticked coupon proposals fill the ply rows from the notation and set the loading type with its value", () => {
  const { rows, notes } = couponRowsFrom([p("layup", "[0/90]2s"), p("force", "10000", "N"), p("length", "250", "mm"), p("test", "open-hole tension")]);
  assert.deepEqual(notes, []);
  assert.equal(rows.ply_1, "0");
  assert.equal(rows.ply_4, "90");
  assert.equal(rows.ply_5, "");
  assert.equal(rows.symmetric, "yes");
  assert.deepEqual([rows.control, rows.value, rows.length, rows.test], ["force", "10000", "250", "open-hole tension"]);
  assert.deepEqual(couponRowsFrom([p("displacement", "1", "mm")]).rows, { control: "displacement", value: "1" });
  const bad = couponRowsFrom([p("layup", "quasi-isotropic")]);
  assert.deepEqual(bad.rows, {});
  assert.match(bad.notes[0], /not laminate notation/);
});

test("a laminate offers each number with the dimension of its units, the conditions that are off, and the problem with no name", () => {
  const draft: LaminateDraft = { ...blankDraft(), system: "SI", material: { own: { name: "X-Lamina", source: "a datasheet", E1: { value: "147", unit: "GPa" }, E2: { value: "", unit: "" },
    G12: { value: "", unit: "" }, nu12: "0.27", F1t: { value: "", unit: "" }, F1c: { value: "", unit: "" }, F2t: { value: "", unit: "" }, F2c: { value: "", unit: "" }, F6: { value: "", unit: "" } } } };
  const offer = laminateOffer(draft);
  const byKey = Object.fromEntries(offer.rows.map((r) => [r.key, r]));
  assert.deepEqual([byKey.E1.dimension, byKey.Nx.dimension, byKey.Mxy.dimension, byKey.delta_T.dimension, byKey.alpha1.dimension, byKey.ply_thickness.dimension],
    ["pressure", "force_per_length", "moment_per_length", "temperature_change", "expansion", "length"]);
  assert.equal(byKey.nu12.dimension, undefined);
  assert.equal(byKey.system.kind, "choice");
  assert.deepEqual(offer.conditions.map((c) => c.id), ["temperature"]);
  assert.deepEqual(offer.form, { system: "SI", E1: "147 GPa", nu12: "0.27" });
  assert.deepEqual(laminateOffer({ ...draft, conditions: ["temperature"] }).conditions, []);
});

test("ticked laminate proposals go in with the unit written, or the system's; a temperature change turns its condition on", () => {
  const { next, notes } = laminateDraftFrom({ ...blankDraft(), system: "SI" }, [
    p("E1", "147", "GPa"), p("E2", "10.3"), p("nu12", "0.27"), p("layup", "[0/90]s"), p("Nx", "100", "N/mm"), p("delta_T", "-270", "degF"),
    p("alpha2", "27", "1e-6/degF"),
  ], []);
  assert.deepEqual(notes, []);
  assert.ok(next.material && "own" in next.material);
  const own = (next.material as { own: Record<string, unknown> }).own;
  assert.deepEqual([own.E1, own.E2, own.nu12], [{ value: "147", unit: "GPa" }, { value: "10.3", unit: "GPa" }, "0.27"]);
  assert.deepEqual(next.layup, { notation: "[0/90]s", angles: [0, 90, 90, 0], symmetric: true });
  assert.deepEqual(next.loads!.Nx, { value: "100", unit: "N/mm" });
  assert.deepEqual(next.loads!.Ny, { value: "", unit: "N/m" });
  assert.deepEqual(next.delta_T, { value: "-270", unit: "degF" });
  assert.deepEqual(next.alphas, { alpha1: { value: "", unit: "1e-6/degC" }, alpha2: { value: "27", unit: "1e-6/degF" } });
  assert.deepEqual(next.conditions, ["temperature"]);
});

test("with no system and no unit written a laminate value is held back, and a ticked condition comes on without a value", () => {
  const { next, notes } = laminateDraftFrom(blankDraft(), [p("E2", "10.3", null, "E2")], ["temperature"]);
  assert.equal(next.material, null);
  assert.match(notes[0], /^E2: no unit written; pick the units/);
  assert.deepEqual(next.conditions, ["temperature"]);
  assert.equal(laminateUnit(p("E2", "10.3"), ""), null);
  assert.equal(laminateUnit(p("E2", "10.3"), "US"), "Msi");
  assert.equal(laminateUnitNeeded("nu12"), false);
  assert.equal(laminateUnitNeeded("Mx"), true);
  const picked = laminateDraftFrom(blankDraft(), [p("system", "mm-MPa"), p("E2", "10300")], []).next;
  assert.equal(picked.system, "mm-MPa");
  assert.deepEqual((picked.material as { own: Record<string, unknown> }).own.E2, { value: "10300", unit: "MPa" });
});

test("the proposals' answer is read only in the shape the API gives", () => {
  const good = { run_id: null, writer: "anthropic", model: "m", proposals: [p("length", "250", "mm")], conditions: [{ id: "temperature", title: "Temperature change", quote: "cooled" }],
    question: null, dropped: [{ key: "width", reason: "not a row on offer" }], reason: null };
  assert.deepEqual(readProposalAnswer(good), good);
  assert.throws(() => readProposalAnswer({ ...good, proposals: [{ key: "length", value: 250 }] }), /could not be read/); // the reason to the console only
  assert.throws(() => readProposalAnswer({ ...good, dropped: null }), /could not be read/);
});
