import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, valuesFor } from "../lib/studio-fields";
import { printed } from "../lib/studio-colors";
import type { Fields } from "../lib/studio-api";

const fields: Fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8"));

test("the options follow what the package wrote", () => {
  const options = fieldOptions(fields);
  assert.ok(options.some((o) => o.id === "failure_index" && o.perCriterion));
  assert.equal(options.find((o) => o.id === "S11")?.unit, "MPa");
  assert.equal(options.find((o) => o.id === "N_y")?.unit, "N/mm");
  const none = fieldOptions({ ...fields, element: { ...fields.element, failure: {} } });
  assert.ok(!none.some((o) => o.id === "failure_index"));
  assert.deepEqual(DEFAULT_CHOICE(fields), { id: "failure_index", ply: 1, criterion: "tsai_hill", averaged: true });
});

test("the values are the package's arrays, per element or per node", () => {
  const perElement = valuesFor(fields, { id: "eps_y", ply: 1, criterion: "tsai_hill", averaged: false });
  assert.equal(perElement.by, "element");
  assert.equal(perElement.values.length, fields.mesh.element_count);
  assert.equal(perElement.values[0], fields.element.strain[0][1]);
  const perNode = valuesFor(fields, { id: "eps_y", ply: 1, criterion: "tsai_hill", averaged: true });
  assert.equal(perNode.by, "node");
  assert.equal(perNode.values.length, fields.mesh.node_count);
  const stress = valuesFor(fields, { id: "S22", ply: 3, criterion: "tsai_hill", averaged: false });
  assert.equal(stress.values[5], fields.element.ply.stress_12[5][2][1]);
  assert.ok(stress.label.includes("ply 3, -45°"));
  const index = valuesFor(fields, { id: "failure_index", ply: 1, criterion: "max_stress", averaged: false });
  assert.ok(Math.abs(Math.max(...(index.values as number[])) - fields.summary.fpf.max_stress.index) < 1e-8); // arrays carry nine digits, the summary all
  assert.ok(index.label.endsWith("by max stress"));
  const magnitude = valuesFor(fields, { id: "u_mag", ply: 1, criterion: "", averaged: false });
  assert.equal(magnitude.by, "node");
  assert.equal(magnitude.values[fields.summary.max_displacement.node], fields.summary.max_displacement.value);
});

test("the readout of the critical element names its ply, ratio and mode", () => {
  const critical = fields.summary.fpf.tsai_hill;
  const readout = elementReadout(fields, critical.element, { id: "S11", ply: critical.ply, criterion: "tsai_hill", averaged: false }, printed);
  assert.equal(readout.title, `Element ${critical.label.split(".").pop()}`);
  const row = readout.rows.find(([label]) => label.startsWith("tsai hill: ply"))!;
  assert.ok(row[1].startsWith(`${printed(critical.factor)}, ${printed(critical.index)}, `));
  assert.ok(row[1].endsWith(critical.mode));
});
