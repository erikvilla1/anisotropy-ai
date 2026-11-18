import { test } from "node:test";
import assert from "node:assert/strict";
import { applyMessage, COARSER, FINER, readMesh } from "../lib/studio-chat";
import { exampleForm } from "../lib/studio-form";

const form = { ...exampleForm("2026-11-16"), element_size: "2" };

test("an element size written in a message is read into its row (ADR-0088 amendment 2)", () => {
  for (const [message, size] of [["use 2.5 mm elements", "2.5"], ["element size 1.5 mm", "1.5"], ["mesh size 1", "1"], ["set the mesh to 3 mm", "3"],
    ["a 0.5 mm mesh please", "0.5"], ["refine to 0.5 mm elements", "0.5"], ["element size of .75", "0.75"]] as const) {
    assert.deepEqual(readMesh(message, form), { rows: { element_size: size }, understood: [`element size ${size} mm`], note: null }, message);
  }
  const inches = { ...form, units: "in-psi", element_size: "0.08" };
  assert.deepEqual(readMesh("0.05 in elements", inches)?.understood, ["element size 0.05 in"]);
  assert.equal(readMesh("element size 0", form), null);
});

test("Abaqus's seed words state the same element size (ADR-0110)", () => {
  for (const [message, size] of [["seed 2 mm", "2"], ["global seed of 1.5", "1.5"], ["approximate global size 3", "3"], ["seed the part at 2.5 mm", "2.5"],
    ["Global seeds: 1", "1"], ["seeding to 0.5", "0.5"]] as const) {
    assert.deepEqual(readMesh(message, form)?.rows, { element_size: size }, message);
  }
  assert.equal(readMesh("what is a seed?", form), null);
  assert.deepEqual(applyMessage(form, "seed 1.5 mm").understood, ["element size 1.5 mm"]);
});

test("finer is half the element size the form holds and coarser is twice it, each said with the size before (ADR-0088 amendment 2)", () => {
  assert.equal(FINER, 0.5);
  assert.equal(COARSER, 2);
  for (const message of ["finer mesh", "make the mesh finer", "refine it", "twice as fine", "halve the element size", "can you make it finer?", "smaller elements"]) {
    assert.deepEqual(readMesh(message, form), { rows: { element_size: "1" }, understood: ["element size 1 mm (half of 2 mm)"], note: null }, message);
  }
  for (const message of ["coarser mesh", "coarsen the mesh", "double the element size", "fewer elements", "twice as coarse"]) {
    assert.deepEqual(readMesh(message, form), { rows: { element_size: "4" }, understood: ["element size 4 mm (twice 2 mm)"], note: null }, message);
  }
  assert.deepEqual(readMesh("finer mesh", { ...form, element_size: "6.25" })?.rows, { element_size: "3.125" });
  assert.deepEqual(readMesh("finer", { ...form, element_size: "1.25" })?.rows, { element_size: "0.625" });
  assert.deepEqual(readMesh("coarser", { ...form, element_size: "0.3" })?.rows, { element_size: "0.6" }); // no long tail of digits
  // with no size to start from nothing is guessed: the page says what to state
  const blank = readMesh("finer mesh", { ...form, element_size: "" });
  assert.deepEqual(blank?.rows, {});
  assert.match(blank?.note ?? "", /^No element size is stated yet, so there is nothing to make finer\. State one, for example “2 mm elements”\.$/);
});

test("a message that says nothing of the mesh, says both ways, or asks about it changes nothing (ADR-0088 amendment 2)", () => {
  for (const message of ["stress at element 120", "change the length to 300 mm", "make it [0/90]2s", "250 x 25 mm", "mesh quality", "finer and coarser",
    "would a finer mesh change the stress?", "is the mesh fine enough?", "why is the mesh coarser at the grips", "what element size is this?"]) {
    assert.equal(readMesh(message, form), null, message);
  }
});

test("the mesh is read with the other rows of a message (ADR-0088 amendment 2)", () => {
  const both = applyMessage(form, "250 x 25 mm with a finer mesh");
  assert.deepEqual(both.rows, { length: "250", width: "25", element_size: "1" });
  assert.deepEqual(both.understood, ["length 250 mm", "width 25 mm", "element size 1 mm (half of 2 mm)"]);
  assert.deepEqual(applyMessage(form, "make it [0/90]2s").understood.filter((u) => u.startsWith("element")), []);
});
