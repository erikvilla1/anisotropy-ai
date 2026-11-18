import assert from "node:assert/strict";
import test from "node:test";
import { changesBetween, comparison, MAX_VERSIONS, readVersions, withResult, withRun, withVersion, writeVersions } from "../lib/model-versions";
import { blankForm, fieldByKey } from "../lib/studio-form";
import { emptyPlate } from "../lib/studio-plate";

const at = "2026-11-18T07:40:00.000Z";
const form = { ...blankForm(), library: "im7-8552", ply_1: "45", ply_2: "0", ply_3: "-45", ply_4: "90", symmetric: "yes", element_size: "2", date: "2026-11-18" };

test("a settled change is a version, numbered, saying what changed in the rows' own labels; no change adds none (ADR-0113)", () => {
  let list = withVersion([], form, emptyPlate(), "you", null, at);
  assert.equal(list.length, 1);
  assert.deepEqual(list[0].changes, ["The setup as it started"]);
  assert.equal(withVersion(list, { ...form, date: "2026-11-19" }, emptyPlate(), "you", null, at), list, "the date is not a change");
  list = withVersion(list, { ...form, element_size: "4" }, emptyPlate(), "assistant", "use 4 mm elements", at);
  assert.equal(list[1].n, 2);
  assert.equal(list[1].by, "assistant");
  assert.equal(list[1].why, "use 4 mm elements");
  assert.deepEqual(list[1].changes, [`${fieldByKey.element_size.label}: 2 → 4`]);
  // the plies as one layup, and a plate's lists as their sentences
  const plate = { ...emptyPlate(), supports: [{ region: "Edge-Left", dofs: [1, 2, 3], value: "" }] };
  const changes = changesBetween({ form, plate: emptyPlate() }, { form: { ...form, ply_1: "0", ply_2: "90", ply_3: "", ply_4: "" }, plate });
  assert.deepEqual(changes, ["Layup: [45/0/-45/90]s → [0/90]s", "Added: Edge-Left holds x, y, z"]);
});

test("going back is a new version, nothing is overwritten, and the oldest go past the limit (ADR-0113)", () => {
  let list = withVersion([], form, emptyPlate(), "you", null, at);
  list = withVersion(list, { ...form, element_size: "4" }, emptyPlate(), "you", null, at);
  list = withVersion(list, list[0].form, list[0].plate, "you", "Back to version 1", at);
  assert.deepEqual(list.map((v) => v.n), [1, 2, 3]);
  assert.deepEqual(list[2].changes, [`${fieldByKey.element_size.label}: 4 → 2`]);
  for (let i = 0; i < MAX_VERSIONS + 5; i++) list = withVersion(list, { ...form, element_size: String(10 + i) }, emptyPlate(), "you", null, at);
  assert.equal(list.length, MAX_VERSIONS);
  assert.equal(list[list.length - 1].n, MAX_VERSIONS + 8);
});

test("a run marks the version it was made from, keeps its answer there, and two versions compare by setup and answer (ADR-0113)", () => {
  let list = withVersion([], form, emptyPlate(), "you", null, at);
  list = withRun(list, "job-1");
  list = withVersion(list, { ...form, element_size: "4" }, emptyPlate(), "you", null, at);
  list = withRun(withRun(list, "job-2"), "job-2");
  list = withResult(list, "job-1", { reaction: "16220 N", displacement: "1 mm", failure: "Holds, R = 1.033" });
  assert.deepEqual(list.map((v) => v.run?.job), ["job-1", "job-2"]);
  assert.equal(list[1].run?.result, null);
  const c = comparison(list[1], list[0]);
  assert.deepEqual(c.changes, [`${fieldByKey.element_size.label}: 2 → 4`]);
  assert.deepEqual(c.rows[0], ["First-ply failure", "Holds, R = 1.033", "not run"]);
});

test("versions are kept per project in this browser, and a blocked or odd store gives none (ADR-0113)", () => {
  const held = new Map<string, string>();
  const storage = { getItem: (k: string) => held.get(k) ?? null, setItem: (k: string, v: string) => void held.set(k, v) } as unknown as Storage;
  const list = withVersion([], form, emptyPlate(), "you", null, at);
  writeVersions(storage, "p1", list);
  assert.deepEqual(readVersions(storage, "p1"), list);
  assert.deepEqual(readVersions(storage, "p2"), []);
  held.set("anisotropy.versions.p3", "{not json");
  assert.deepEqual(readVersions(storage, "p3"), []);
  assert.deepEqual(readVersions(null, "p1"), []);
});
