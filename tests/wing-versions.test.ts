import { test } from "node:test";
import assert from "node:assert/strict";
import { EXAMPLE_WING, newSparCaps, newZone, withValue, withZones } from "../lib/wing";
import {
  MAX_WING_VERSIONS, readWingVersions, wingChanges, wingKey, wingVersionsKey, withWingCheck, withWingCheckResult, withWingVersion, writeWingVersions,
} from "../lib/wing-versions";

function memory() {
  const map = new Map<string, string>();
  return { map, getItem: (k: string) => map.get(k) ?? null, setItem: (k: string, v: string) => { map.set(k, v); } };
}

test("a wing's change is said in the page's labels: a half stack as its laminate, a library entry by its name (ADR-0122)", () => {
  assert.deepEqual(wingChanges(null, EXAMPLE_WING), ["The wing as it started"]);
  let changed = withValue(EXAMPLE_WING, "geometry.chord", 0.5);
  changed = withValue(changed, "skin.half_stack", [0, 45, -45, 0, 0]);
  changed = withValue(changed, "skin.core", "divinycell-h250");
  changed = withValue(changed, "geometry.rib_spacing", undefined);
  changed = withValue(changed, "design_rules.max_in_a_row", 3);
  changed = withValue(changed, "source", "Another note"); // where it came from is not a change
  assert.deepEqual(wingChanges(EXAMPLE_WING, changed), [
    "Chord: 0.45 → 0.5",
    "Rib spacing: 0.5 → blank",
    "Skin layup: [0/45/-45/0]s → [0/45/-45/0/0]s",
    "Core: Divinycell H45 → Divinycell H250",
    "Most plies of one angle in a row: blank → 3",
  ]);
  assert.equal(wingKey(withValue(EXAMPLE_WING, "source", "x")), wingKey(EXAMPLE_WING));
});

test("spar caps and zones along the span are said in the page's labels: each zone by its stretch of the span and its laminate (ADR-0124)", () => {
  const capped = { ...EXAMPLE_WING, spar_caps: newSparCaps(EXAMPLE_WING) };
  assert.deepEqual(wingChanges(EXAMPLE_WING, capped), [
    "Front cap width: blank → 0.045", "Rear cap width: blank → 0.045", "Spar cap layup: blank → [0/0/45/-45/0]s",
  ]);
  const zoned = withZones(capped, "spar_caps", [{ ...newZone(capped, "spar_caps"), half_stack: [0, 0, 0, 45, -45, 0] }]);
  assert.deepEqual(wingChanges(capped, zoned), ["Spar cap zones along the span: blank → root to 40 % [0/0/0/45/-45/0]s"]);
  const two = withZones(zoned, "spar_caps", [...(zoned.spar_caps as { zones: never[] }).zones, newZone(zoned, "spar_caps")]);
  assert.deepEqual(wingChanges(zoned, two), [
    "Spar cap zones along the span: root to 40 % [0/0/0/45/-45/0]s → root to 40 % [0/0/0/45/-45/0]s; 40 to 80 % [0/0/45/-45/0]s",
  ]);
  assert.deepEqual(wingChanges(zoned, withZones(zoned, "spar_caps", [])), ["Spar cap zones along the span: root to 40 % [0/0/0/45/-45/0]s → blank"]);
});

test("versions count up, an unchanged wing adds none, the oldest go past the limit, and a check is kept on its version", () => {
  let list = withWingVersion([], EXAMPLE_WING, "you", null, "2026-11-20T10:00:00.000Z");
  assert.equal(list.length, 1);
  assert.equal(withWingVersion(list, { ...EXAMPLE_WING }, "you", null, "t"), list); // the same description is no version
  list = withWingVersion(list, withValue(EXAMPLE_WING, "geometry.chord", 0.5), "assistant", "make the chord 0.5 m", "2026-11-20T10:01:00.000Z");
  assert.deepEqual(list.map((v) => [v.n, v.by, v.why]), [[1, "you", null], [2, "assistant", "make the chord 0.5 m"]]);
  list = withWingCheck(list, "job-1");
  assert.deepEqual(list[1].check, { job: "job-1", headline: null });
  assert.equal(withWingCheck(list, "job-1"), list);
  list = withWingCheckResult(list, "job-1", "Lowest margin +0.146");
  assert.deepEqual(list[1].check, { job: "job-1", headline: "Lowest margin +0.146" });
  assert.equal(list[0].check, undefined);

  let many = list;
  for (let i = 0; i < MAX_WING_VERSIONS + 5; i++) many = withWingVersion(many, withValue(EXAMPLE_WING, "geometry.chord", 1 + i / 100), "you", null, "t");
  assert.equal(many.length, MAX_WING_VERSIONS);
  assert.equal(many[many.length - 1].n, MAX_WING_VERSIONS + 7);

  const store = memory();
  writeWingVersions(store, "w1", list);
  assert.ok(store.map.has(wingVersionsKey("w1")));
  assert.deepEqual(readWingVersions(store, "w1"), list);
  assert.deepEqual(readWingVersions(store, "w2"), []);
  store.setItem(wingVersionsKey("w3"), "not json");
  assert.deepEqual(readWingVersions(store, "w3"), []);
  assert.deepEqual(readWingVersions(null, "w1"), []);
});
