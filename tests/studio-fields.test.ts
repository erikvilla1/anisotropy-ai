import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, hasFaces, onFace, valuesFor, worstFace } from "../lib/studio-fields";
import { printed } from "../lib/studio-colors";
import type { Fields } from "../lib/studio-api";

const fields: Fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8"));
const bending: Fields = JSON.parse(readFileSync("tests/fixtures/studio-bending/fields.json", "utf8"));

test("the options follow what the package wrote", () => {
  const options = fieldOptions(fields);
  assert.ok(options.some((o) => o.id === "failure_index" && o.perCriterion));
  assert.equal(options.find((o) => o.id === "S11")?.unit, "MPa");
  assert.equal(options.find((o) => o.id === "N_y")?.unit, "N/mm");
  const none = fieldOptions({ ...fields, element: { ...fields.element, failure: {} } });
  assert.ok(!none.some((o) => o.id === "failure_index"));
  assert.deepEqual(DEFAULT_CHOICE(fields), { id: "failure_index", ply: 1, face: 0, criterion: "tsai_hill", averaged: true });
  assert.ok(!hasFaces(fields) && !options.some((o) => o.id === "u_z" || o.id === "M_y"));
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


test("a bending coupon's fields carry the deflection, the moments and both faces of every ply (ADR-0053)", () => {
  assert.ok(hasFaces(bending) && bending.mesh.faces?.join(",") === "bottom,top" && bending.mesh.translations === 3 && bending.kernel === "shell");
  const options = fieldOptions(bending);
  for (const id of ["u_z", "theta_x", "kappa_y", "M_y", "Q_y", "S11"]) assert.ok(options.some((o) => o.id === id), id);
  assert.equal(options.find((o) => o.id === "M_y")?.unit, "N·mm/mm");
  assert.ok(options.find((o) => o.id === "S11")?.perFace);
  assert.deepEqual(DEFAULT_CHOICE(bending), { id: "failure_index", ply: 1, face: 0, criterion: "tsai_hill", averaged: true });
  const w = valuesFor(bending, { id: "u_z", ply: 1, face: 0, criterion: "tsai_hill", averaged: true });
  assert.equal(w.by, "node");
  assert.equal(w.values.length, bending.mesh.node_count);
  assert.equal(w.values[0], bending.nodal.displacement[0][2]);
  assert.ok(Math.min(...(w.values as number[])) < -0.9); // the nose pushed the coupon down 1 mm
  const moment = valuesFor(bending, { id: "M_y", ply: 1, face: 0, criterion: "tsai_hill", averaged: false });
  assert.equal(moment.values[3], bending.element.moment![3][1]);
  const top = valuesFor(bending, { id: "S11", ply: 8, face: 1, criterion: "tsai_hill", averaged: false });
  assert.equal(top.values[5], (bending.element.ply.stress_12[5][7] as number[][])[1][0]);
  assert.ok(top.label.includes("ply 8, 45°, top face"));
  const bottom = valuesFor(bending, { id: "S11", ply: 8, face: 0, criterion: "tsai_hill", averaged: false });
  assert.notEqual(bottom.values[5], top.values[5]); // the two faces differ under bending
  const index = valuesFor(bending, { id: "failure_index_ply", ply: 1, face: 0, criterion: "tsai_hill", averaged: false });
  const faces = bending.element.failure.tsai_hill.index[0][0] as number[];
  assert.equal(index.values[0], Math.max(...faces));
  assert.equal(worstFace(bending, faces), Math.max(...faces));
  assert.equal(onFace(bending, bending.element.ply.mises[2][0], 1), (bending.element.ply.mises[2][0] as number[])[1]);
  const readout = elementReadout(bending, 86, { id: "S11", ply: 1, face: 0, criterion: "tsai_hill", averaged: false }, printed);
  assert.ok(readout.rows.some(([k]) => k.startsWith("M_x, M_y, M_xy")));
  assert.ok(readout.rows.some(([k, v]) => k.includes("bottom face") && v.length > 0));
  assert.ok(bending.summary.fpf.tsai_hill.face === "bottom" && bending.summary.reaction.sense === "pressing the coupon down");
});
