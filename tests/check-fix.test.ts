import { test } from "node:test";
import assert from "node:assert/strict";
import { changedRows, fixEcho, fixRows, MOST_ROWS } from "../lib/check-fix";
import { PLY_KEYS, fields, type CheckItem } from "../lib/studio-form";

const item = (id: string, state: CheckItem["state"], rows: string[]): CheckItem => ({ id, label: id, state, message: "", rows });

test("each failing item offers the rows its check names, a row once, plies and unknown labels left to their panels", () => {
  const offered = fixRows([
    item("geometry", "missing", ["Narrow width (mm)", "Fillet radius (mm)"]),
    item("standard", "fail", ["Strain measurement", "Strain measurement length (mm)", "Narrow width (mm)"]),
    item("laminate", "fail", ["Ply 1 (bottom)"]),
    item("units", "warn", ["Length (mm)"]),
    item("identity", "fail", ["Not a row"]),
  ]);
  assert.deepEqual([...offered.keys()], ["geometry", "standard"]);
  assert.deepEqual(offered.get("geometry")!.map((f) => f.key), ["narrow_width", "radius"]);
  assert.deepEqual(offered.get("standard")!.map((f) => f.key), ["strain_device", "strain_length"], "a row named twice is offered under the first item");
  assert.ok(PLY_KEYS.includes("ply_1"));
});

test("a row is found by its label in any unit system, and an item naming too many rows is left to its panel", () => {
  assert.deepEqual(fixRows([item("geometry", "missing", ["Narrow width (in)"])]).get("geometry")!.map((f) => f.key), ["narrow_width"]);
  const many = fields.filter((f) => f.labels && !PLY_KEYS.includes(f.key)).slice(0, MOST_ROWS + 1).map((f) => f.label);
  assert.equal(fixRows([item("geometry", "fail", many)]).has("geometry"), false);
});

test("only the rows typed differently are applied, an emptied row clears, and the echo names each by its label", () => {
  const form = { narrow_width: "", radius: "", outer_radius: "25", width: "19" };
  const rows = changedRows(form, { narrow_width: " 13 ", radius: "76", outer_radius: "", width: "19" });
  assert.deepEqual(rows, { narrow_width: "13", radius: "76", outer_radius: "" });
  assert.equal(fixEcho(rows, "mm-MPa"), "Narrow width (mm): 13; Fillet radius (mm): 76; Outer radius (mm): cleared");
  assert.equal(fixEcho({ strain_length: "2" }, "in-psi"), "Strain measurement length (in): 2");
});
