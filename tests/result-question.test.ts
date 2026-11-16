import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Fields } from "../lib/studio-api";
import { applyMessage } from "../lib/studio-chat";
import { printed } from "../lib/studio-colors";
import { bannedIn } from "../lib/studio-copy";
import { exampleForm } from "../lib/studio-form";
import { PROBE_COLUMNS, probeTable } from "../lib/studio-fields";
import { answerResultQuestion, readResultQuestion, RESULT_COLUMNS, resultSentence, resultUnit, type ResultValues } from "../lib/result-question";

const fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8")) as Fields;
/** The mesh index of the element the fixture labels `Strip-1.<number>`. */
const indexOf = (number: number) => fields.mesh.element_labels.indexOf(`Strip-1.${number}`);
const values = (answer: ReturnType<typeof answerResultQuestion>): ResultValues => {
  assert.equal(answer.kind, "values");
  return answer as ResultValues;
};

test("a question about a result names a quantity and a place; the reader holds the place and the columns, never a number of the result (ADR-0099)", () => {
  assert.deepEqual(readResultQuestion("What is the stress on ply 5 at element 1212?"), { element: 1212, ply: 5, columns: ["S11", "S22", "S12"] });
  assert.deepEqual(readResultQuestion("stress in ply 5"), { element: null, ply: 5, columns: ["S11", "S22", "S12"] });
  assert.deepEqual(readResultQuestion("longitudinal stress in ply 3 at element 125"), { element: 125, ply: 3, columns: ["S11"] });
  assert.deepEqual(readResultQuestion("transverse strain at el. 7"), { element: 7, ply: null, columns: ["E22"] });
  assert.deepEqual(readResultQuestion("shear stress and shear strain, layer 2, element #40"), { element: 40, ply: 2, columns: ["S12", "E12"] });
  assert.deepEqual(readResultQuestion("σ₁ and ε₂ here"), { element: "picked", ply: null, columns: ["S11", "E22"] });
  assert.deepEqual(readResultQuestion("S22 at this element"), { element: "picked", ply: null, columns: ["S22"] });
  assert.deepEqual(readResultQuestion("sigma 12 in ply 4 at element 9"), { element: 9, ply: 4, columns: ["S12"] });
  assert.deepEqual(readResultQuestion("von Mises stress here, ply 1"), { element: "picked", ply: 1, columns: ["Mises"] });
  assert.deepEqual(readResultQuestion("principal stresses at element 12"), { element: 12, ply: null, columns: ["Max. Principal", "Mid. Principal", "Min. Principal"] });
  assert.deepEqual(readResultQuestion("stress and strain at the selected element"),
    { element: "picked", ply: null, columns: ["S11", "S22", "S12", "E11", "E22", "E12"] });
  for (const question of ["stress in ply 2 at element 3", "E11 here", "tresca at element 4"]) {
    assert.ok(readResultQuestion(question)!.columns.every((c) => PROBE_COLUMNS.includes(c) && RESULT_COLUMNS[c]), question);
  }
});

test("a message that states the setup is not a question about a result, and the setup's own patterns still read it", () => {
  const setup = ["strain gauge length 50 mm", "make it [0/90]2s", "10 kN", "ply thickness 0.125", "250 x 25 mm, 56 mm tabs", "AS4/8552", "1 mm pull",
    "make ply 5 a 90", "apply a stress of 100 MPa at element 3", "what is the stress?", "run", "check", "unnotched tension, ASTM D3039, IM7/8552, [45/0/-45/90]s, 1 mm pull"];
  for (const message of setup) assert.equal(readResultQuestion(message), null, message);
  const form = exampleForm("2026-11-16");
  for (const message of ["make it [0/90]2s", "10 kN", "250 x 25 mm, 56 mm tabs"]) assert.ok(applyMessage(form, message).understood.length, message);
});

test("the answer is the fields' own numbers at the element by its number, the same cells as the probe table", () => {
  const element = indexOf(125), k = 5;
  const answer = values(answerResultQuestion(fields, readResultQuestion("What is the stress on ply 5 at element 125?")!, null));
  assert.equal(answer.element, element);
  assert.equal(answer.label, "125");
  assert.equal(answer.instance, "Strip-1");
  assert.deepEqual(answer.columns, ["S11", "S22", "S12"]);
  assert.equal(answer.rows.length, 1);
  assert.deepEqual([answer.rows[0].ply, answer.rows[0].angle, answer.rows[0].face], [k, fields.mesh.angles[k - 1], null]);
  assert.deepEqual(answer.rows[0].values, fields.element.ply.stress_12[element][k - 1]);
  assert.deepEqual(answer.centroid, [fields.element.centroids[element][0], fields.element.centroids[element][1]]);
  assert.ok(answer.sets.every((name) => fields.mesh.element_sets[name].includes(element)));
  const table = probeTable(fields, element);
  assert.equal(answer.note, table.note);
  assert.deepEqual(answer.rows[0].values, table.rows[k - 1].values.slice(0, 3));

  const strain = values(answerResultQuestion(fields, readResultQuestion("strain at element 125")!, null));
  assert.equal(strain.rows.length, fields.mesh.plies);
  strain.rows.forEach((row, i) => assert.deepEqual(row.values, fields.element.ply.strain_12[element][i]));
  const mises = values(answerResultQuestion(fields, readResultQuestion("mises in ply 2 at element 125")!, null));
  assert.deepEqual(mises.rows[0].values, [fields.element.ply.mises[element][1]]);
});

test("“here” is the element clicked on the model; with none clicked the answer asks for one and gives no number", () => {
  const question = readResultQuestion("shear strain here, ply 3")!;
  const asked = answerResultQuestion(fields, question, null);
  assert.equal(asked.kind, "ask");
  const picked = indexOf(40);
  const answer = values(answerResultQuestion(fields, question, picked));
  assert.equal(answer.label, "40");
  assert.deepEqual(answer.rows[0].values, [(fields.element.ply.strain_12[picked][2] as number[])[2]]);
  assert.equal(answerResultQuestion(fields, question, fields.mesh.element_labels.length).kind, "ask", "an index outside the mesh shown is no element");
  // a ply named with no element reads the clicked element too
  assert.equal(values(answerResultQuestion(fields, readResultQuestion("stress in ply 5")!, picked)).label, "40");
});

test("a place the model does not hold is refused with what it holds", () => {
  const none = answerResultQuestion(fields, readResultQuestion("stress on ply 5 at element 1212")!, null);
  assert.deepEqual(none, { kind: "refused", text: "This model has no element 1212. Its elements are numbered 1 to 250." });
  const ply = answerResultQuestion(fields, readResultQuestion("stress on ply 9 at element 12")!, null);
  assert.deepEqual(ply, { kind: "refused", text: "This laminate has 8 plies, counted from the bottom face; there is no ply 9." });
  const twice: Fields = { ...fields, mesh: { ...fields.mesh, element_labels: fields.mesh.element_labels.map((l, i) => (i === 1 ? "Tab-1.1" : l)) } };
  const both = answerResultQuestion(twice, readResultQuestion("stress at element 1")!, null);
  assert.equal(both.kind, "refused");
  assert.match((both as { text: string }).text, /Strip-1\.1, Tab-1\.1/);
});

test("one value is said as a sentence with its ply, angle, element and unit; more than one is a table's", () => {
  const element = indexOf(125);
  const one = values(answerResultQuestion(fields, readResultQuestion("s11 in ply 2 at element 125")!, null));
  const value = (fields.element.ply.stress_12[element][1] as number[])[0];
  assert.equal(resultUnit(fields, "S11"), "MPa");
  assert.equal(resultUnit(fields, "E11"), "");
  assert.equal(resultSentence(one, resultUnit(fields, "S11"), printed), `σ₁ in ply 2 (0°) at element 125 is ${printed(value)} MPa.`);
  const strain = values(answerResultQuestion(fields, readResultQuestion("e22 in ply 2 at element 125")!, null));
  assert.equal(resultSentence(strain, resultUnit(fields, "E22"), printed), `ε₂ in ply 2 (0°) at element 125 is ${printed((fields.element.ply.strain_12[element][1] as number[])[1])}.`);
  assert.equal(resultSentence(values(answerResultQuestion(fields, readResultQuestion("stress in ply 2 at element 125")!, null)), "MPa", printed), null);
  for (const column of PROBE_COLUMNS) assert.deepEqual(bannedIn(`${RESULT_COLUMNS[column].symbol} ${RESULT_COLUMNS[column].words}`), [], column);
});
