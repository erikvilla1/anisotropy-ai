import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { emptyPlate, plateFromValues, plateValues, plateWords, regionOptions, regionsHere, namesPlateEdit, regionsOfElement, shapeWords, withLoad, withSupport, PLATE_TEST } from "../lib/studio-plate";
import { blankForm, buildValues, sectionsFor } from "../lib/studio-form";
import { plateLines, plateOffer, plateWith } from "../lib/proposals";
import { readPreview, readProposalAnswer } from "../lib/studio-api";

const values = JSON.parse(readFileSync("tests/fixtures/studio-plate/values.json", "utf8"));
const preview = readPreview(JSON.parse(readFileSync("tests/fixtures/studio-plate/preview.json", "utf8")));

test("a plate's form hides the grips and the loading rows and sends its lists (ADR-0054)", () => {
  const form = { ...blankForm(), test: PLATE_TEST, length: "100", width: "100" };
  const keys = sectionsFor(form).flatMap((s) => s.fields.map((f) => f.key));
  assert.ok(keys.includes("tab_length") && keys.includes("hole_diameter") && keys.includes("length"));
  for (const key of ["grips", "region", "control", "value", "span"]) assert.ok(!keys.includes(key), key);
  const lists = plateFromValues(values);
  assert.equal(lists.supports.length, 6);
  assert.deepEqual(lists.loads, [{ region: "Face", kind: "pressure", pressure: "-0.01" }]);
  assert.equal(lists.regions[1].name, "Corner-X");
  const built = buildValues(form, plateValues(lists));
  assert.deepEqual(built.loads, [{ region: "Face", pressure: -0.01 }]);
  assert.deepEqual((built.supports as Record<string, unknown>[])[4], { region: "Corner-Origin", dofs: [1, 2] });
  assert.deepEqual((built.regions as Record<string, unknown>[])[0], { name: "Corner-Origin", x0: 0, x1: 0.1, y0: 0, y1: 0.1 });
  assert.ok(!("supports" in buildValues({ ...form, test: "unnotched tension" }, plateValues(lists)))); // a coupon never sends the lists
  const blankValue = plateValues({ ...emptyPlate(), supports: [{ region: "Edge-Top", dofs: [2], value: " " }] });
  assert.deepEqual(blankValue.supports, [{ region: "Edge-Top", dofs: [2] }]); // a blank travel is left out so the check judges the row
});

test("the regions a plate offers follow the form, the boxes and the hole", () => {
  const form = { ...blankForm(), test: PLATE_TEST, tab_length: "20" };
  const names = regionOptions(form, { ...emptyPlate(), regions: [{ name: "Patch", x0: "1", x1: "2", y0: "1", y1: "2" }] }).map((o) => o.name);
  assert.deepEqual(names, ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Face", "Tab-Bottom", "Tab-Top", "Patch"]);
  const withHole = regionOptions({ ...form, tab_length: "", hole_diameter: "6" }, emptyPlate());
  assert.ok(withHole.some((o) => o.name === "Hole" && o.kind === "edge") && !withHole.some((o) => o.name === "Tab-Top"));
});

test("a click on an element names the regions it touches, and the buttons add rows", () => {
  const form = { ...blankForm(), test: PLATE_TEST, length: "100", width: "100" };
  const lists = plateFromValues(values);
  const options = regionOptions(form, lists);
  const corner = regionsOfElement(0, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, options).map((r) => r.name);
  assert.deepEqual(corner, ["Edge-Bottom", "Edge-Left", "Face", "Corner-Origin"]); // the first element sits at the origin
  const middle = regionsOfElement(136, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, options).map((r) => r.name);
  assert.deepEqual(middle, ["Face"]);
  const held = withSupport(emptyPlate(), "Edge-Left");
  assert.deepEqual(held.supports, [{ region: "Edge-Left", dofs: [1, 2, 3], value: "" }]);
  const loaded = withLoad(withLoad(held, "Face", "area"), "Edge-Top", "edge");
  assert.deepEqual(loaded.loads, [{ region: "Face", kind: "pressure", pressure: "" }, { region: "Edge-Top", kind: "force", dof: 3, total: "" }]);
  assert.equal(plateWords(loaded)[0], "Edge-Left holds x, y, z");
  assert.ok(plateWords(loaded)[1].includes("Face under a pressure of ? MPa"));
});

test("the plate preview lists every load with its region and the regions the plate offers", () => {
  assert.equal(preview.loads?.length, 1);
  assert.equal(preview.loads?.[0].control, "pressure");
  assert.equal(preview.loads?.[0].direction, "+z"); // a negative Abaqus pressure pushes along the normal
  assert.deepEqual(preview.regions, { edges: ["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right"], areas: ["Face", "Corner-Origin", "Corner-X"] });
  assert.equal(preview.held.filter((h) => h.set === "Edge-Left").length, 2); // dof 3 and dof 4, one boundary line each
});

// ------------------------------------------------------------------------------- a message and the place clicked (ADR-0101)

test("a plate offers a message its own regions and the ones clicked, never a box the engineer named (ADR-0101)", () => {
  const form = { ...blankForm(), test: PLATE_TEST, length: "100", width: "100" };
  const lists = plateFromValues(values); // holds two drawn boxes, Corner-Origin and Corner-X
  assert.deepEqual(regionsHere(0, preview.mesh, form).map((r) => r.name), ["Edge-Bottom", "Edge-Left", "Face"]); // the corner element, the box left out
  assert.deepEqual(regionsHere(136, preview.mesh, form).map((r) => r.name), ["Face"]);
  assert.deepEqual(regionsHere(null, preview.mesh, form), []);
  assert.deepEqual(regionsHere(0, null, form), []);
  assert.deepEqual(regionsHere(preview.mesh.quads.length, preview.mesh, form), []); // an element the mesh shown does not hold
  const offer = plateOffer(form, lists, ["Edge-Bottom", "Corner-Origin", "Face", "Face"]);
  assert.deepEqual(offer.regions.map((r) => `${r.name}:${r.kind}`), ["Edge-Bottom:edge", "Edge-Top:edge", "Edge-Left:edge", "Edge-Right:edge", "Face:area"]);
  assert.deepEqual(offer.here, ["Edge-Bottom", "Face"]);
  assert.deepEqual([offer.force_unit, offer.stress_unit], ["N", "MPa"]);
  assert.deepEqual(offer.loaded, ["Face"]);
  assert.ok(offer.held.length > 0 && offer.held.every((name) => offer.regions.some((r) => r.name === name)));
  assert.ok(!JSON.stringify(offer).includes("Corner") && !JSON.stringify(offer).includes("0.01")); // no named box, no value
  assert.deepEqual([plateOffer({ ...form, units: "in-psi" }, emptyPlate(), []).force_unit, plateOffer({ ...form, units: "in-psi" }, emptyPlate(), []).stress_unit], ["lbf", "psi"]);
});

test("the supports and loads kept from a message are shown in the plate's words and enter its lists only when ticked (ADR-0101)", () => {
  const answer = {
    supports: [{ region: "Edge-Bottom", dofs: [1, 2, 3], quote: "hold this edge" }],
    loads: [
      { region: "Edge-Top", kind: "force" as const, dof: 2, value: "10000", unit: "N", written_value: "10", written_unit: "kN", sense: "tension" as const, quote: "10 kN in tension on the top edge" },
      { region: "Face", kind: "pressure" as const, dof: null, value: "0.01", unit: "MPa", written_value: "0.01", written_unit: "MPa", sense: null, quote: "0.01 MPa on the face" },
      { region: "Edge-Left", kind: "force" as const, dof: 3, value: "-200", unit: "N", written_value: "200", written_unit: "N", sense: "as_signed" as const, quote: "200 N down on the left edge" },
    ],
  };
  assert.deepEqual(plateLines(answer), [
    { id: "support:0", label: "Hold Edge-Bottom", value: "x, y, z", unit: "", quote: "hold this edge" },
    { id: "load:0", label: "Force on Edge-Top", value: "10000", unit: "N along y", quote: "10 kN in tension on the top edge", note: "written 10 kN; tension: pulling outward from the edge" },
    { id: "load:1", label: "Pressure on Face", value: "0.01", unit: "MPa", quote: "0.01 MPa on the face", note: "positive presses down on the plate" },
    { id: "load:2", label: "Force on Edge-Left", value: "-200", unit: "N along z", quote: "200 N down on the left edge" },
  ]);
  const before = withSupport(emptyPlate(), "Edge-Right");
  const all = plateWith(before, answer, new Set(["support:0", "load:0", "load:1", "load:2"]));
  assert.deepEqual(all.supports, [{ region: "Edge-Right", dofs: [1, 2, 3], value: "" }, { region: "Edge-Bottom", dofs: [1, 2, 3], value: "" }]);
  assert.deepEqual(all.loads, [{ region: "Edge-Top", kind: "force", dof: 2, total: "10000" }, { region: "Face", kind: "pressure", pressure: "0.01" },
    { region: "Edge-Left", kind: "force", dof: 3, total: "-200" }]);
  assert.deepEqual(plateValues(all).loads, [{ region: "Edge-Top", dof: 2, total: 10000 }, { region: "Face", pressure: 0.01 }, { region: "Edge-Left", dof: 3, total: -200 }]);
  const some = plateWith(before, answer, new Set(["load:1"]));
  assert.deepEqual([some.supports.length, some.loads.length], [1, 1]);
  assert.deepEqual(plateWith(before, answer, new Set()), before); // nothing ticked, nothing entered
});

test("a plate's supports and loads in the proposals' answer are read only in the shape the API gives (ADR-0101)", () => {
  const base = { run_id: null, writer: "anthropic", model: "m", proposals: [], conditions: [], question: null, dropped: [], reason: null, unread: [] };
  const load = { region: "Edge-Top", kind: "force", dof: 2, value: "10000", unit: "N", written_value: "10", written_unit: "kN", sense: "tension", quote: "10 kN" };
  const good = { ...base, supports: [{ region: "Edge-Top", dofs: [1, 2, 3], quote: "hold this" }], loads: [load] };
  assert.deepEqual(readProposalAnswer(good), good);
  assert.deepEqual(readProposalAnswer(base), { ...base, supports: [], loads: [] }); // an API from before the plate's lists
  for (const bad of [
    { ...good, supports: [{ region: "Edge-Top", dofs: [], quote: "hold this" }] }, { ...good, supports: [{ region: "Edge-Top", dofs: [7], quote: "hold this" }] },
    { ...good, loads: [{ ...load, value: "ten thousand" }] }, { ...good, loads: [{ ...load, dof: null }] }, { ...good, loads: [{ ...load, dof: 4 }] },
    { ...good, loads: [{ ...load, kind: "pressure" }] }, { ...good, loads: [{ ...load, kind: "moment" }] }, { ...good, loads: [{ ...load, sense: "pull" }] },
    { ...good, loads: "none" },
  ]) assert.throws(() => readProposalAnswer(bad), /could not be read/);
});

test("a plate's shape is read with no load, its regions are clickable, and a model with no load is refused (ADR-0101 amendment 1)", () => {
  const raw = JSON.parse(readFileSync("tests/fixtures/studio-plate/preview.json", "utf8"));
  const bare = readPreview({ ...raw, held: [], loads: [], loaded: null, shape: ["supports", "loads"] });
  assert.equal(bare.loaded, null);
  assert.deepEqual(bare.shape, ["supports", "loads"]);
  // the element clicked on the shape is "here", exactly as on the checked model: the same mesh and sets
  const form = { ...blankForm(), test: PLATE_TEST };
  const edge = bare.mesh.node_sets["Edge-Bottom"];
  const onEdge = bare.mesh.quads.findIndex((quad) => quad.filter((node) => edge.includes(node)).length >= 2);
  assert.ok(onEdge >= 0);
  assert.deepEqual(regionsHere(onEdge, bare.mesh, form), regionsHere(onEdge, preview.mesh, form));
  assert.ok(regionsHere(onEdge, bare.mesh, form).some((region) => region.name === "Edge-Bottom" && region.kind === "edge"));
  // only a shape may come with no load, and a shape names a list that is missing
  for (const bad of [{ ...raw, loaded: null }, { ...raw, loaded: null, shape: [] }, { ...raw, loaded: null, shape: ["regions"] }, { ...raw, loaded: null, shape: "loads" }]) {
    assert.throws(() => readPreview(bad), /could not be read/);
  }
  assert.deepEqual(readPreview({ ...raw, loads: [], loaded: null, shape: ["loads"] }).held, raw.held); // held, not loaded yet: what is held is drawn
  assert.match(shapeWords(["supports", "loads"]), /^Nothing is held or loaded yet\./);
  assert.match(shapeWords(["supports"]), /^Nothing is held yet\./);
  assert.match(shapeWords(["loads"]), /^No load yet\./);
  for (const words of [shapeWords(["supports", "loads"]), shapeWords(["supports"]), shapeWords(["loads"])]) assert.match(words, /cannot be solved until/);
});

test("a plate edit is told from a person's name (ADR-0101 amendment 1)", () => {
  for (const edit of ["hold this edge", "Hold the bottom edge", "clamp it here", "press the face", "pin the hole", "fix that", "pull the top tab", "load here"]) {
    assert.equal(namesPlateEdit(edit), true, edit);
  }
  for (const name of ["Erik", "A. Engineer", "Maria Holden", "Thi Sanh", "Loadstone Lab", "Presley", "Fixler", "the test team"]) {
    assert.equal(namesPlateEdit(name), false, name);
  }
});
