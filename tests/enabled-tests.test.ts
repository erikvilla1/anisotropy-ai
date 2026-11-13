import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ENABLED, enabledStandards, enabledTests, enabledWords, hiddenReason, HIDDEN_ROW_KEYS, isRowEnabled, isStandardEnabled, isTestEnabled, notAvailable,
  understoodWithout, withoutHidden,
} from "../lib/enabled-tests";
import { couponOffer } from "../lib/proposals";
import { exampleForm, fieldByKey, NO_STANDARD, STANDARDS, standardsFor } from "../lib/studio-form";

const D3039 = "ASTM D3039/D3039M-17";

test("the list the fea package writes: unnotched tension, under D3039 or no standard, with plies, no dog-bone (ADR-0089)", () => {
  assert.deepEqual(ENABLED.tests, ["unnotched tension"]);
  assert.deepEqual(ENABLED.standards, [D3039]);
  assert.deepEqual(ENABLED.material_kinds, ["plies"]);
  assert.equal(ENABLED.dogbone, false);
  assert.ok(ENABLED.tests.every((t) => fieldByKey.test.words.includes(t)), "every enabled test is a Test row word");
  assert.ok(ENABLED.standards.every((d) => STANDARDS.some((p) => p.designation === d)), "every enabled standard is a profile");
});

test("with the list closed only tension is offered, and with the switch on every test is", () => {
  const words = fieldByKey.test.words;
  assert.deepEqual(enabledTests(words, false), ["unnotched tension"]);
  assert.deepEqual(enabledTests(words, true), words);
  assert.ok(!isTestEnabled("open-hole tension", false) && isTestEnabled("open-hole tension", true));
  assert.deepEqual(enabledStandards(standardsFor("unnotched tension"), false).map((p) => p.designation), [D3039]);
  assert.deepEqual(enabledStandards(standardsFor("unnotched tension"), true).map((p) => p.designation), standardsFor("unnotched tension").map((p) => p.designation));
  assert.ok(isStandardEnabled(NO_STANDARD, false) && isStandardEnabled("", false) && !isStandardEnabled("ASTM D638-22", false));
  assert.deepEqual(enabledWords("material_kind", ["plies", "isotropic"], false), ["plies"]);
  assert.deepEqual(enabledWords("units", ["mm-MPa", "in-psi"], false), ["mm-MPa", "in-psi"], "other rows keep their words");
  for (const key of ["hole_diameter", "span", "narrow_width", "own_E", "material_kind", "specimen"]) assert.ok(!isRowEnabled(key, false) && isRowEnabled(key, true), key);
  for (const key of ["length", "width", "tab_length", "library", "ply_1", "strain_length"]) assert.ok(isRowEnabled(key, false), key);
});

test("a form says why it cannot be set up with the list closed, and nothing with the switch on", () => {
  const tension = exampleForm("2026-11-11");
  assert.equal(hiddenReason(tension, false), null);
  assert.equal(hiddenReason({ ...tension, standard: D3039 }, false), null);
  assert.match(hiddenReason({ ...tension, test: "open-hole tension" }, false) ?? "", /^Open-hole tension is not available yet: the workspace offers the unnotched tension coupon/);
  assert.match(hiddenReason({ ...tension, standard: "ASTM D638-22" }, false) ?? "", /^ASTM D638-22 is not available yet/);
  assert.match(hiddenReason({ ...tension, material_kind: "isotropic" }, false) ?? "", /^One isotropic material is not available yet/);
  assert.match(hiddenReason({ ...tension, narrow_width: "13" }, false) ?? "", /^A dog-bone is not available yet/);
  assert.equal(hiddenReason({ ...tension, test: "fibre tow tension" }, true), null);
  assert.equal(notAvailable("plate"), `Plate is ${ENABLED.not_available}.`);
});

test("rows read from a message lose a hidden test and the hidden tests' rows, and the note says so", () => {
  const read = { test: "open-hole tension", hole_diameter: "6", width: "36", standard: "ASTM C1869-18(2023)" };
  const { rows, notes, dropped } = withoutHidden(read, false);
  assert.deepEqual(rows, { width: "36" });
  assert.deepEqual([...dropped].sort(), ["hole_diameter", "standard", "test"]);
  assert.deepEqual(understoodWithout(["test: open-hole tension", "hole 6 mm", "width 36 mm", "standard: ASTM C1869-18(2023)"], dropped), ["width 36 mm"]);
  assert.equal(notes.length, 2);
  assert.match(notes[0], /^Open-hole tension is not available yet/);
  assert.deepEqual(withoutHidden(read, true), { rows: read, notes: [], dropped: [] });
  assert.deepEqual(withoutHidden({ test: "unnotched tension", standard: D3039, length: "250" }, false).rows, { test: "unnotched tension", standard: D3039, length: "250" });
});

test("the model is offered only what the page offers: tension, D3039 or none, and no hidden rows", () => {
  const form = exampleForm("2026-11-11");
  const closed = Object.fromEntries(couponOffer(form, false).rows.map((r) => [r.key, r]));
  assert.deepEqual(closed.test.choices?.map((c) => c.value), ["unnotched tension"]);
  assert.deepEqual(closed.standard.choices?.map((c) => c.value), [NO_STANDARD, D3039]);
  for (const key of HIDDEN_ROW_KEYS) assert.equal(closed[key], undefined, key);
  assert.ok(closed.length && closed.width && closed.library && closed.layup && closed.force);
  const open = Object.fromEntries(couponOffer(form, true).rows.map((r) => [r.key, r]));
  assert.equal(open.test.choices?.length, fieldByKey.test.words.length);
  assert.ok(open.hole_diameter && open.material_kind);
});
