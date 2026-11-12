import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Fields } from "../lib/studio-api";
import { DEFAULT_CHOICE, fieldOptions, PROBE_COLUMNS, probeCsv, probeTable, valuesFor } from "../lib/studio-fields";

const fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8")) as Fields;

test("the viewer offers Tresca, the principal stresses, the pressure and the ply strains by plain names, element values only (ADR-0066 amendment 2, ADR-0091)", () => {
  const options = Object.fromEntries(fieldOptions(fields).map((o) => [o.id, o]));
  for (const id of ["tresca", "max_principal", "mid_principal", "min_principal", "pressure", "E11", "E22", "E12"]) {
    assert.ok(options[id], id);
    assert.equal(options[id].elementOnly, true, id);
    assert.equal(options[id].perPly, true, id);
  }
  assert.equal(options.tresca.label, "Ply Tresca stress");
  assert.equal(options.max_principal.label, "Ply max. principal stress");
  assert.equal(options.E11.label, "Ply strain ε₁");
  const k = 2; // ply 2, the 0 deg ply of [45/0/-45/90]s
  const tresca = valuesFor(fields, { ...DEFAULT_CHOICE(fields), id: "tresca", ply: k, averaged: true });
  assert.equal(tresca.by, "element", "no display average is written for an invariant, whatever the switch says");
  assert.deepEqual(tresca.values, fields.element.ply.invariants!.tresca.map((plies) => plies[k - 1]));
  assert.deepEqual(tresca.range, (fields.ranges as Record<string, { element: [number, number][] }>).tresca.element[k - 1]);
  const e22 = valuesFor(fields, { ...DEFAULT_CHOICE(fields), id: "E22", ply: k, averaged: false });
  assert.deepEqual(e22.values, fields.element.ply.strain_12.map((plies) => (plies[k - 1] as number[])[1]));
});

test("the probe table holds every ply of the element by its number in its instance, as CAE's Probe Values reads it", () => {
  const element = 0;
  const table = probeTable(fields, element);
  assert.equal(table.element, fields.mesh.element_labels[element]);
  assert.equal(`${table.instance}.${table.label}`, table.element);
  assert.equal(table.rows.length, fields.mesh.plies);
  assert.deepEqual(table.rows.map((r) => r.angle), fields.mesh.angles);
  const row = table.rows[1];
  const stress = fields.element.ply.stress_12[element][1] as number[];
  assert.deepEqual(row.values.slice(0, 3), stress);
  assert.equal(row.values[3], fields.element.ply.mises[element][1]);
  assert.equal(row.values[4], fields.element.ply.invariants!.tresca[element][1]);
  assert.deepEqual(row.values.slice(9), fields.element.ply.strain_12[element][1]);
  assert.match(table.note, /S13 and S23 are not modelled/);
  assert.equal(PROBE_COLUMNS.length, row.values.length);
});

test("the probe CSV carries the same numbers with Abaqus's column names and the units", () => {
  const table = probeTable(fields, 3);
  const lines = probeCsv(fields, table).trim().split("\n");
  assert.equal(lines.length, 1 + fields.mesh.plies);
  assert.match(lines[0], /^Element,Ply,Angle \(deg\),S11 \(MPa\),S22 \(MPa\),S12 \(MPa\),Mises \(MPa\),Tresca \(MPa\),.*E12 \(-\)$/);
  assert.equal(lines[1].split(",")[3], String(table.rows[0].values[0]));
});

test("a job solved before the invariants were written shows no invariant option and the probe leaves them blank", () => {
  const older = JSON.parse(JSON.stringify(fields)) as Fields;
  delete older.element.ply.invariants;
  assert.equal(fieldOptions(older).some((o) => o.id === "tresca"), false);
  assert.equal(probeTable(older, 0).rows[0].values[4], null);
});
