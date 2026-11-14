import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DEFAULT_CHOICE, elementReadout, fieldOptions, hasFaces, loadAlongY, onFace, valuesFor, withField, worstFace } from "../lib/studio-fields";
import { printed } from "../lib/studio-colors";
import { modeWords } from "../lib/studio-answer";
import type { Fields } from "../lib/studio-api";

const fields: Fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8"));
const bending: Fields = JSON.parse(readFileSync("tests/fixtures/studio-bending/fields.json", "utf8"));
const at = (x: unknown, ...path: (string | number)[]): unknown => path.reduce<unknown>((o, k) => (o as Record<string | number, unknown>)[k], x);

test("the options follow what the package wrote", () => {
  const options = fieldOptions(fields);
  assert.ok(options.some((o) => o.id === "failure_index" && o.perCriterion));
  assert.equal(options.find((o) => o.id === "S11")?.unit, "MPa");
  assert.equal(options.find((o) => o.id === "N_y")?.unit, "N/mm");
  const none = fieldOptions({ ...fields, element: { ...fields.element, failure: {} } });
  assert.ok(!none.some((o) => o.id === "failure_index"));
  // the failure index opens as element values, the values the answer reports; averages stay an option (audit fea-run-42)
  assert.deepEqual(DEFAULT_CHOICE(fields), { id: "failure_index", ply: 1, face: 0, criterion: "tsai_hill", averaged: false });
  assert.equal(DEFAULT_CHOICE({ ...fields, element: { ...fields.element, failure: {} } }).averaged, true); // a strain opens averaged, for a smooth picture
  // only the failure index opens on element values: leaving it, a field is back on nodal averages; between two others, the engineer's choice stays
  const strain = withField(DEFAULT_CHOICE(fields), "eps_y");
  assert.equal(strain.id, "eps_y");
  assert.equal(strain.averaged, true);
  assert.equal(withField({ ...strain, averaged: false }, "N_y").averaged, false);
  assert.equal(withField(strain, "failure_index").averaged, false);
  assert.ok(!hasFaces(fields) && !options.some((o) => o.id === "u_z" || o.id === "M_y"));
});

test("a pulled coupon's x and y are named by the load: x across the width, y along the load (audit fea-run-11, uiux-fea-run-49)", () => {
  assert.ok(loadAlongY(fields) && !loadAlongY(bending));
  const label = (f: Fields, id: string) => fieldOptions(f).find((o) => o.id === id)?.label;
  assert.equal(label(fields, "u_x"), "Displacement ux (across)");
  assert.equal(label(fields, "u_y"), "Displacement uy (along the load)");
  assert.equal(label(fields, "eps_y"), "Membrane strain εy (along the load)");
  assert.equal(label(bending, "u_y"), "Displacement uy"); // a bending coupon is loaded through its thickness
  for (const option of fieldOptions(fields)) assert.doesNotMatch(option.label, /[\u1D67\u2093]/, option.id); // no gamma or x subscript for a coordinate
  const readout = elementReadout(fields, 0, DEFAULT_CHOICE(fields), printed);
  assert.equal(readout.rows[0][0], "Centroid (x across, y along)");
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
  assert.ok(stress.label.endsWith(", Ply 3 · −45°"), stress.label); // the one ply label (audit fea-run-22)
  const index = valuesFor(fields, { id: "failure_index", ply: 1, criterion: "max_stress", averaged: false });
  assert.ok(Math.abs(Math.max(...(index.values as number[])) - fields.summary.fpf.max_stress.index) < 1e-8); // arrays carry nine digits, the summary all
  assert.ok(index.label.endsWith(", Maximum stress"));
  const magnitude = valuesFor(fields, { id: "u_mag", ply: 1, criterion: "", averaged: false });
  assert.equal(magnitude.by, "node");
  assert.equal(magnitude.values[fields.summary.max_displacement.node], fields.summary.max_displacement.value);
});

test("the range of the chosen field is the package's, for what is shown (ADR-0063)", () => {
  const index = valuesFor(fields, { id: "failure_index", ply: 1, criterion: "tsai_hill", averaged: false });
  assert.deepEqual(index.range, at(fields.ranges, "failure_index", "tsai_hill", "element"));
  assert.equal(index.range![1], Math.max(...(index.values as number[])));
  const averaged = valuesFor(fields, { id: "eps_y", ply: 1, criterion: "tsai_hill", averaged: true });
  assert.deepEqual(averaged.range, at(fields.ranges, "eps_y", "nodal"));
  const stress = valuesFor(fields, { id: "S22", ply: 3, criterion: "tsai_hill", averaged: false });
  assert.deepEqual(stress.range, at(fields.ranges, "S22", "element", 2));
  assert.equal(stress.range![0], Math.min(...(stress.values as number[])));
  const top = valuesFor(bending, { id: "S11", ply: 2, face: 1, criterion: "tsai_hill", averaged: false });
  assert.deepEqual(top.range, at(bending.ranges, "S11", "element", 1, 1)); // ply 2, the top face
  assert.equal(top.range![1], Math.max(...(top.values as number[])));
  const perPly = valuesFor(bending, { id: "failure_index_ply", ply: 4, face: 0, criterion: "max_stress", averaged: false });
  assert.deepEqual(perPly.range, at(bending.ranges, "failure_index_ply", "max_stress", "element", 3));
  assert.equal(perPly.range![1], Math.max(...(perPly.values as number[]))); // the worse face of each ply
  const w = valuesFor(bending, { id: "u_z", ply: 1, face: 0, criterion: "tsai_hill", averaged: true });
  assert.deepEqual(w.range, at(bending.ranges, "u_z", "nodal"));
  assert.equal(valuesFor({ ...fields, ranges: undefined }, { id: "u_mag", ply: 1, criterion: "", averaged: true }).range, null); // a job solved before the ranges were written
});

test("the readout of the critical element names its ply, ratio and mode", () => {
  const critical = fields.summary.fpf.tsai_hill;
  const readout = elementReadout(fields, critical.element, { id: "S11", ply: critical.ply, criterion: "tsai_hill", averaged: false }, printed);
  assert.equal(readout.title, `Element ${critical.label.split(".").pop()}`);
  const row = readout.rows.find(([label]) => label.startsWith(`Tsai-Hill: Ply ${critical.ply} · `))!;
  assert.ok(row[1].startsWith(`${printed(critical.factor)}, ${printed(critical.index)}, `));
  assert.ok(row[1].endsWith(modeWords(critical.mode)), row[1]); // the mode in the words the answer uses (audit fea-run-21)
  assert.ok(readout.rows.some(([label]) => label === `Ply ${critical.ply} · ${critical.angle}° von Mises (MPa)`));
});


test("a bending coupon's fields carry the deflection, the moments and both faces of every ply (ADR-0053)", () => {
  assert.ok(hasFaces(bending) && bending.mesh.faces?.join(",") === "bottom,top" && bending.mesh.translations === 3 && bending.kernel === "shell");
  const options = fieldOptions(bending);
  for (const id of ["u_z", "theta_x", "kappa_y", "M_y", "Q_y", "S11"]) assert.ok(options.some((o) => o.id === id), id);
  assert.equal(options.find((o) => o.id === "M_y")?.unit, "N·mm/mm");
  assert.ok(options.find((o) => o.id === "S11")?.perFace);
  assert.deepEqual(DEFAULT_CHOICE(bending), { id: "failure_index", ply: 1, face: 0, criterion: "tsai_hill", averaged: false });
  const w = valuesFor(bending, { id: "u_z", ply: 1, face: 0, criterion: "tsai_hill", averaged: true });
  assert.equal(w.by, "node");
  assert.equal(w.values.length, bending.mesh.node_count);
  assert.equal(w.values[0], bending.nodal.displacement[0][2]);
  assert.ok(Math.min(...(w.values as number[])) < -0.9); // the nose pushed the coupon down 1 mm
  const moment = valuesFor(bending, { id: "M_y", ply: 1, face: 0, criterion: "tsai_hill", averaged: false });
  assert.equal(moment.values[3], bending.element.moment![3][1]);
  const top = valuesFor(bending, { id: "S11", ply: 8, face: 1, criterion: "tsai_hill", averaged: false });
  assert.equal(top.values[5], (bending.element.ply.stress_12[5][7] as number[][])[1][0]);
  assert.ok(top.label.includes("Ply 8 · 45°, top face"), top.label);
  const bottom = valuesFor(bending, { id: "S11", ply: 8, face: 0, criterion: "tsai_hill", averaged: false });
  assert.notEqual(bottom.values[5], top.values[5]); // the two faces differ under bending
  const index = valuesFor(bending, { id: "failure_index_ply", ply: 1, face: 0, criterion: "tsai_hill", averaged: false });
  const faces = bending.element.failure.tsai_hill.index[0][0] as number[];
  assert.equal(index.values[0], Math.max(...faces));
  assert.equal(worstFace(bending, faces), Math.max(...faces));
  assert.equal(onFace(bending, bending.element.ply.mises[2][0], 1), (bending.element.ply.mises[2][0] as number[])[1]);
  const readout = elementReadout(bending, 86, { id: "S11", ply: 1, face: 0, criterion: "tsai_hill", averaged: false }, printed);
  assert.ok(readout.rows.some(([k]) => k.startsWith("Mx, My, Mxy")));
  assert.ok(readout.rows.some(([k, v]) => k.includes("bottom face") && v.length > 0));
  assert.ok(bending.summary.fpf.tsai_hill.face === "bottom" && bending.summary.reaction.sense === "pressing the coupon down");
});
