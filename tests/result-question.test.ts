import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import type { Fields } from "../lib/studio-api";
import { applyMessage } from "../lib/studio-chat";
import { printed } from "../lib/studio-colors";
import { bannedIn } from "../lib/studio-copy";
import { exampleForm } from "../lib/studio-form";
import { PROBE_COLUMNS, probeTable } from "../lib/studio-fields";
import { readResultReading } from "../lib/studio-api";
import { answerResultQuestion, extremeSentence, extremeWords, gaugeSection, questionFrom, readResultQuestion, resultOffer, RESULT_COLUMNS, resultSentence, resultUnit, type ResultExtremes, type ResultValues } from "../lib/result-question";

const fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8")) as Fields;
/** The mesh index of the element the fixture labels `Strip-1.<number>`. */
const indexOf = (number: number) => fields.mesh.element_labels.indexOf(`Strip-1.${number}`);
const values = (answer: ReturnType<typeof answerResultQuestion>): ResultValues => {
  assert.equal(answer.kind, "values");
  return answer as ResultValues;
};
const extremes = (answer: ReturnType<typeof answerResultQuestion>): ResultExtremes => {
  assert.equal(answer.kind, "extremes");
  return answer as ResultExtremes;
};

test("a question about a result names a quantity and a place; the reader holds the place and the columns, never a number of the result (ADR-0099)", () => {
  assert.deepEqual(readResultQuestion("What is the stress on ply 5 at element 1212?"), { kind: "values", element: 1212, plies: [5], columns: ["S11", "S22", "S12"] });
  assert.deepEqual(readResultQuestion("stress in ply 5"), { kind: "values", element: null, plies: [5], columns: ["S11", "S22", "S12"] });
  assert.deepEqual(readResultQuestion("longitudinal stress in ply 3 at element 125"), { kind: "values", element: 125, plies: [3], columns: ["S11"] });
  assert.deepEqual(readResultQuestion("transverse strain at el. 7"), { kind: "values", element: 7, plies: null, columns: ["E22"] });
  assert.deepEqual(readResultQuestion("shear stress and shear strain, layer 2, element #40"), { kind: "values", element: 40, plies: [2], columns: ["S12", "E12"] });
  assert.deepEqual(readResultQuestion("σ₁ and ε₂ here"), { kind: "values", element: "picked", plies: null, columns: ["S11", "E22"] });
  assert.deepEqual(readResultQuestion("S22 at this element"), { kind: "values", element: "picked", plies: null, columns: ["S22"] });
  assert.deepEqual(readResultQuestion("sigma 12 in ply 4 at element 9"), { kind: "values", element: 9, plies: [4], columns: ["S12"] });
  assert.deepEqual(readResultQuestion("von Mises stress here, ply 1"), { kind: "values", element: "picked", plies: [1], columns: ["Mises"] });
  assert.deepEqual(readResultQuestion("principal stresses at element 12"), { kind: "values", element: 12, plies: null, columns: ["Max. Principal", "Mid. Principal", "Min. Principal"] });
  assert.deepEqual(readResultQuestion("stress and strain at the selected element"),
    { kind: "values", element: "picked", plies: null, columns: ["S11", "S22", "S12", "E11", "E22", "E12"] });
  for (const question of ["stress in ply 2 at element 3", "E11 here", "tresca at element 4"]) {
    assert.ok(readResultQuestion(question)!.columns.every((c) => PROBE_COLUMNS.includes(c) && RESULT_COLUMNS[c]), question);
  }
});

test("a message that states the setup is not a question about a result, and the setup's own patterns still read it", () => {
  const setup = ["strain gauge length 50 mm", "make it [0/90]2s", "10 kN", "ply thickness 0.125", "250 x 25 mm, 56 mm tabs", "AS4/8552", "1 mm pull",
    "make ply 5 a 90", "apply a stress of 100 MPa at element 3", "what is the stress?", "run", "check", "max stress criterion", "use maximum strain and tsai-wu",
    "which ply carries the most load?", "strain gauge 25 mm max", "unnotched tension, ASTM D3039, IM7/8552, [45/0/-45/90]s, 1 mm pull"];
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

test("a quantity with an extreme word asks where it is largest: the end, the plies and the region are read, and an element named is a place to read instead (ADR-0100)", () => {
  assert.deepEqual(readResultQuestion("where is the shear stress highest?"), { kind: "extreme", sense: "largest", plies: null, region: "default", columns: ["S12"] });
  assert.deepEqual(readResultQuestion("minimum sigma 1 in ply 4"), { kind: "extreme", sense: "smallest", plies: [4], region: "default", columns: ["S11"] });
  assert.deepEqual(readResultQuestion("largest stress in the gauge section"), { kind: "extreme", sense: "magnitude", plies: null, region: "gauge", columns: ["S11", "S22", "S12"] });
  assert.deepEqual(readResultQuestion("peak transverse strain anywhere"), { kind: "extreme", sense: "magnitude", plies: null, region: "whole", columns: ["E22"] });
  assert.deepEqual(readResultQuestion("most compressive stress along the fibres"), { kind: "extreme", sense: "smallest", plies: null, region: "default", columns: ["S11"] });
  assert.deepEqual(readResultQuestion("highest stress at element 12"), { kind: "values", element: 12, plies: null, columns: ["S11", "S22", "S12"] });
});

test("the gauge section is the package's own: the page's extremes over it are the package's largest ply stresses, overall and ply by ply", () => {
  const written = fields.summary.ply_extremes!;
  assert.equal(written.basis, "gauge");
  assert.equal(gaugeSection(fields)!.length, 130, "the Gauge set's 140 elements less the row at each grip");
  const same = (a: number, b: number) => Math.abs(a - b) <= 1e-8 * Math.max(Math.abs(a), Math.abs(b));
  for (const [message, column, end] of [["max s11", "S11", "tension"], ["min s11", "S11", "compression"], ["max s22", "S22", "tension"], ["min s22", "S22", "compression"],
    ["largest shear stress", "S12", "largest"]] as const) {
    const answer = extremes(answerResultQuestion(fields, readResultQuestion(message)!, null));
    assert.equal(answer.region, "the gauge section", message);
    assert.equal(answer.elements, 130);
    assert.equal(answer.atGrip, false);
    const block = answer.blocks[0];
    assert.equal(block.column, column);
    const overall = (written.overall as Record<string, Record<string, { value: number; ply: number }>>)[column][end];
    assert.ok(same(block.rows[block.best].value, overall.value), `${message}: ${block.rows[block.best].value} against ${overall.value}`);
    assert.ok([block.rows[block.best].ply, ...block.tied].includes(overall.ply), `${message}: the package's ply is the page's or tied with it`);
    block.rows.forEach((row, i) => {
      const ply = (written.plies[i] as unknown as Record<string, Record<string, { value: number } | null>>)[column][end];
      // a ply with no tension (or no compression) has no such extreme in the package; a zero shear is noise on either side
      // and the largest shear is a magnitude, which two elements across the coupon's axis hold with opposite signs
      if (ply && Math.abs(ply.value) > 1e-6) assert.ok(end === "largest" ? same(Math.abs(row.value), Math.abs(ply.value)) : same(row.value, ply.value), `${message}, ply ${row.ply}`);
    });
    // every value is a cell of the fields: nothing derived
    const cells = fields.element.ply.stress_12.map((plies) => (plies[block.rows[block.best].ply - 1] as number[])[["S11", "S22", "S12"].indexOf(column)]);
    assert.equal(block.rows[block.best].value, cells[block.rows[block.best].element]);
  }
});

test("an extreme names its end, its region and the grip edge; an unsigned quantity is read by magnitude; a region or a ply the model does not hold is refused", () => {
  const shear = extremes(answerResultQuestion(fields, readResultQuestion("where is the shear stress highest?")!, null));
  assert.equal(shear.blocks[0].sense, "magnitude", "a shear stress has no sign to speak of");
  assert.equal(extremeWords("S12", shear.blocks[0].sense), "largest |τ₁₂|");
  assert.equal(extremeWords("S11", "largest"), "largest σ₁");
  assert.equal(extremeWords("S11", "smallest"), "smallest σ₁");
  assert.deepEqual(shear.blocks[0].rows.map((r) => r.ply), [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.ok(shear.blocks[0].tied.length, "the ±45° plies of a symmetric laminate tie");
  const whole = extremes(answerResultQuestion(fields, readResultQuestion("largest stress across the fibres anywhere")!, null));
  assert.equal(whole.region, "the whole model");
  assert.equal(whole.elements, fields.mesh.element_labels.length);
  assert.equal(whole.atGrip, true, "the whole model's peak is at a grip's clamped edge");
  const one = extremes(answerResultQuestion(fields, readResultQuestion("max s11 in ply 2")!, null));
  assert.deepEqual(one.blocks[0].rows.map((r) => r.ply), [2]);
  const set = extremes(answerResultQuestion(fields, { kind: "extreme", sense: "magnitude", plies: null, region: { set: "Tab-Top" }, columns: ["S11"] }, null));
  assert.equal(set.region, "the region Tab-Top");
  assert.ok(set.blocks[0].rows.every((r) => fields.mesh.element_sets["Tab-Top"].includes(r.element)));
  assert.equal(answerResultQuestion(fields, { kind: "extreme", sense: "largest", plies: null, region: { set: "Hole" }, columns: ["S11"] }, null).kind, "refused");
  assert.equal(answerResultQuestion(fields, readResultQuestion("max s11 in ply 9")!, null).kind, "refused");
  const plate: Fields = { ...fields, mesh: { ...fields.mesh, node_sets: {}, element_sets: {} } };
  assert.equal(gaugeSection(plate), null);
  assert.equal(extremes(answerResultQuestion(plate, readResultQuestion("max s11")!, null)).region, "the whole model");
  assert.equal(answerResultQuestion(plate, readResultQuestion("max s11 in the gauge section")!, null).kind, "refused");
});

test("several plies are read at one element, as a comparison asks", () => {
  const answer = values(answerResultQuestion(fields, { kind: "values", element: 125, plies: [7, 2, 4], columns: ["S11"] }, null));
  assert.deepEqual(answer.rows.map((r) => r.ply), [2, 4, 7]);
});

test("a model is offered what a question may name and never a value; its reading, as the guard kept it, becomes the page's typed question (ADR-0100)", () => {
  const offer = resultOffer(fields, "which ply carries the most load?", indexOf(40));
  assert.deepEqual(Object.keys(offer).sort(), ["gauge", "message", "picked", "plies", "quantities"]);
  assert.deepEqual(offer.quantities, PROBE_COLUMNS);
  assert.deepEqual(offer.plies, fields.mesh.angles.map((angle, i) => ({ ply: i + 1, angle })));
  assert.equal(offer.gauge, true);
  assert.equal(offer.picked, true);
  assert.equal(resultOffer(fields, "x", null).picked, false);
  const stressCells = new Set(fields.element.ply.stress_12.flat(2).filter((v) => Math.abs(v as number) > 1));
  assert.ok(!JSON.stringify(offer).match(/\d+\.\d{3,}/) && ![...stressCells].some((v) => JSON.stringify(offer).includes(String(v))), "no value of the results is offered");

  const most = questionFrom({ kind: "extreme", quantities: ["S11"], plies: [], element: null, here: false, sense: "magnitude", region: "default" });
  assert.deepEqual(most, { kind: "extreme", sense: "magnitude", plies: null, region: "default", columns: ["S11"] });
  const compare = questionFrom({ kind: "values", quantities: ["S12", "S11"], plies: [2, 4], element: null, here: true, sense: null, region: "default" });
  assert.deepEqual(compare, { kind: "values", element: "picked", plies: [2, 4], columns: ["S11", "S12"] });
  assert.deepEqual(questionFrom({ kind: "values", quantities: ["E22"], plies: [3], element: 40, here: false, sense: null, region: "default" }),
    { kind: "values", element: 40, plies: [3], columns: ["E22"] });
  assert.equal(questionFrom({ kind: "values", quantities: ["S33"], plies: [], element: 1, here: false, sense: null, region: "default" }), null, "a quantity the probe table does not hold");
  assert.equal(questionFrom({ kind: "extreme", quantities: ["S11"], plies: [], element: null, here: false, sense: null, region: "whole" }), null, "an extreme with no end");
  // the page judges the place again: a ply the laminate does not hold is refused, whoever read the question
  assert.equal(answerResultQuestion(fields, questionFrom({ kind: "extreme", quantities: ["S11"], plies: [12], element: null, here: false, sense: "largest", region: "gauge" })!, null).kind, "refused");

  const answer = extremes(answerResultQuestion(fields, most!, null));
  const block = answer.blocks[0], row = block.rows[block.best];
  const sentence = extremeSentence(block, answer.region, "MPa", printed);
  assert.equal(sentence, `The largest |σ₁| in the gauge section is ${printed(row.value)} MPa, in ply ${row.ply} (${row.angle}°) at element ${row.label}; ply ${block.tied[0]} ties.`);
  assert.deepEqual(bannedIn(`${sentence} ${answer.note}`), []);
});

test("an answer of the API that is not a reading is refused by the page", () => {
  const reading = { run_id: null, writer: "anthropic", model: "m", question: null, dropped: [], reason: null,
    request: { kind: "extreme", quantities: ["S11"], plies: [], element: null, here: false, sense: "largest", region: "gauge" } };
  assert.deepEqual(readResultReading(reading), reading);
  assert.equal(readResultReading({ ...reading, request: null }).request, null);
  for (const request of [{ ...reading.request, kind: "sum" }, { ...reading.request, plies: [1.5] }, { ...reading.request, region: "Tab-Top" }, { ...reading.request, element: "12" },
    { ...reading.request, sense: "average" }, { kind: "extreme" }]) {
    assert.throws(() => readResultReading({ ...reading, request }), /could not be read/);
  }
});
