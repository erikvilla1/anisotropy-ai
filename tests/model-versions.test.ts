import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { changesBetween, comparison, MAX_VERSIONS, readVersions, setupKey, withResult, withRun, withVersion, writeVersions } from "../lib/model-versions";
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

test("the server's versions are read in their shape only, and this browser's newer ones follow them, numbered after (ADR-0143)", async () => {
  const { mergeVersions, readServerVersions, runsToSend, unsent, versionUpload } = await import("../lib/model-versions");
  let local = withVersion([], form, emptyPlate(), "you", null, at);
  local = withVersion(local, { ...form, element_size: "4" }, emptyPlate(), "you", null, at);
  local = withRun(local, "job-4");
  const server = readServerVersions([
    { n: 7, at, by: "assistant", why: "clamp the bottom edge", changes: ["Added: Edge-Bottom holds x, y, z, rx, ry, rz"], form, plate: emptyPlate(), run: null },
    { n: 8, at, by: "you", why: null, changes: ["Element size (mm): 2 → 4"], form: { ...form, element_size: "4" }, plate: emptyPlate() },
    { n: "9", at, by: "you", why: null, changes: [], form, plate: emptyPlate() }, // not a version: left out
    { n: 10, at, by: "robot", why: null, changes: [], form, plate: emptyPlate() },
  ]);
  assert.deepEqual(server.map((v) => v.n), [7, 8]);
  assert.deepEqual(readServerVersions({ detail: "no" }), []);
  // the server holds this browser's last setup: nothing to send, and the run marked here is kept on the server's version until it hears of it
  assert.deepEqual(unsent(local, server), []);
  const merged = mergeVersions(server, local);
  assert.deepEqual(merged.map((v) => [v.n, v.by, v.run?.job ?? null]), [[7, "assistant", null], [8, "you", "job-4"]]);
  assert.deepEqual(runsToSend(server, merged), [{ n: 8, job: "job-4", result: null }]);
  // a change made here after the server's last is sent, and shown numbered after it
  local = withVersion(local, { ...form, element_size: "1" }, emptyPlate(), "you", null, at);
  assert.deepEqual(unsent(local, server).map((v) => v.form.element_size), ["1"]);
  assert.deepEqual(mergeVersions(server, local).map((v) => v.n), [7, 8, 9]);
  // a server with none takes every version this browser holds; a server whose last this browser never held takes the current setup only
  assert.equal(unsent(local, []).length, 3);
  assert.deepEqual(unsent(local, [{ ...server[0], form: { ...form, element_size: "9" } }]).map((v) => v.form.element_size), ["1"]);
  assert.deepEqual(Object.keys(versionUpload(local[0])).sort(), ["by", "changes", "form", "plate", "why"]);
});

test("a setup read back from the server, its keys in the database's order, is the same setup: nothing is sent again (ADR-0143)", async () => {
  const { mergeVersions, readServerVersions, unsent } = await import("../lib/model-versions");
  // the page writes a plate's lists as supports, loads, regions; the server keeps them as JSON and answers with its own order of keys
  const mine = { supports: [{ region: "Edge-Bottom", dofs: [1, 2, 3, 4, 5, 6], value: "" }], loads: [{ region: "Edge-Top", kind: "force" as const, dof: 2, total: "2000" }], regions: [] };
  const theirs = { loads: [{ dof: 2, kind: "force", total: "2000", region: "Edge-Top" }], regions: [], supports: [{ dofs: [1, 2, 3, 4, 5, 6], value: "", region: "Edge-Bottom" }] };
  assert.equal(setupKey(form, mine), setupKey(form, theirs as never));
  // a coupon's project too: its three empty lists come back in the database's order
  assert.equal(setupKey(form, { supports: [], loads: [], regions: [] }), setupKey(form, { loads: [], regions: [], supports: [] } as never));
  assert.notEqual(setupKey(form, mine), setupKey(form, { ...mine, supports: [] })); // a list that differs is still another setup
  assert.notEqual(setupKey(form, { ...mine, supports: [{ ...mine.supports[0], dofs: [2, 1, 3, 4, 5, 6] }] }), setupKey(form, mine)); // a list's own order is the setup's
  const local = withVersion([], form, mine, "assistant", "clamp the bottom edge", at);
  const server = readServerVersions([{ n: 3, at, by: "assistant", why: "clamp the bottom edge", changes: ["Edge-Bottom: fixed (encastre)"], form, plate: theirs }]);
  assert.deepEqual(unsent(local, server), []); // the server holds it: before, the last version was sent again without end
  assert.deepEqual(mergeVersions(server, local).map((v) => v.n), [3]);
  assert.equal(withVersion(server, form, mine, "you", null, at), server); // and the page's own copy of it is no new version
});

test("the page counts as one setup what the server does, a missing list read as empty: the shared fixture (ADR-0143)", () => {
  // api/tests/test_setup_tools.py holds the server's setup_key to the same file
  type Group = { name: string; setups: { form: Record<string, string>; plate?: unknown }[] };
  const held = JSON.parse(readFileSync("tests/fixtures/setup-tools/setup-keys.json", "utf8")) as { same: Group[]; different: Group[] };
  const keys = (group: Group) => new Set(group.setups.map((s) => setupKey(s.form, s.plate as never)));
  for (const group of held.same) assert.equal(keys(group).size, 1, group.name);
  for (const group of held.different) assert.equal(keys(group).size, group.setups.length, group.name);
  assert.deepEqual([held.same.length, held.different.length], [5, 3]);
  // the reviewer's case: another client kept the setup with no list of regions
  assert.equal(setupKey(form, { supports: [], loads: [] } as never), setupKey(form, emptyPlate()));
});
