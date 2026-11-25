import { test } from "node:test";
import assert from "node:assert/strict";
import { asksPlateEdit, canBecomePlate, plateFromCoupon, readPlateEdit } from "../lib/plate-edits";
import { blankForm, type StudioForm } from "../lib/studio-form";
import { emptyPlate, plateValues, PLATE_TEST, type PlateLists } from "../lib/studio-plate";

const plate: StudioForm = { ...blankForm(), test: PLATE_TEST, length: "200", width: "100" };
const read = (text: string, lists: PlateLists = emptyPlate(), form: StudioForm = plate, here: string[] = []) => readPlateEdit(text, form, lists, here);
const sent = (text: string, lists?: PlateLists, form?: StudioForm) => { const edit = read(text, lists, form); return edit ? plateValues(edit.lists) : null; };

test("a hold is read by the words an engineer uses, and means what it means everywhere on the plate (ADR-0101 amendment 4)", () => {
  const cases: [string, { region: string; dofs: number[] }[]][] = [
    ["fix the left edge", [{ region: "Edge-Left", dofs: [1, 2, 3] }]],
    ["hold the bottom edge", [{ region: "Edge-Bottom", dofs: [1, 2, 3] }]],
    ["clamp the top edge", [{ region: "Edge-Top", dofs: [1, 2, 3, 4, 5, 6] }]],
    ["fixed support on the left edge", [{ region: "Edge-Left", dofs: [1, 2, 3, 4, 5, 6] }]],
    ["encastre the right edge", [{ region: "Edge-Right", dofs: [1, 2, 3, 4, 5, 6] }]],
    ["pin the right side", [{ region: "Edge-Right", dofs: [1, 2, 3] }]],
    ["simply support all four edges", ["Edge-Left", "Edge-Right", "Edge-Bottom", "Edge-Top"].map((region) => ({ region, dofs: [3] }))],
    ["XSYMM on the left edge", [{ region: "Edge-Left", dofs: [1, 5, 6] }]],
    ["symmetry on the bottom edge", [{ region: "Edge-Bottom", dofs: [2, 4, 6] }]], // across the edge's own normal
    ["symmetry on the left edge", [{ region: "Edge-Left", dofs: [1, 5, 6] }]],
    ["frictionless support on the right edge", [{ region: "Edge-Right", dofs: [1] }]], // only the edge's normal is held
    ["frictionless support on the face", [{ region: "Face", dofs: [3] }]],
    ["hold the left edge in x and y", [{ region: "Edge-Left", dofs: [1, 2] }]],
    ["hold the top edge in z only", [{ region: "Edge-Top", dofs: [3] }]],
    ["fix U1 and UR3 on the bottom edge", [{ region: "Edge-Bottom", dofs: [1, 6] }]],
    ["fix the lefft edge", [{ region: "Edge-Left", dofs: [1, 2, 3] }]], // one slip of the keys
    ["Please fix the left edge.", [{ region: "Edge-Left", dofs: [1, 2, 3] }]],
  ];
  for (const [text, supports] of cases) assert.deepEqual(sent(text)?.supports, supports, text);
  assert.deepEqual(read("clamp the top edge")?.done, ["Edge-Top: fixed (encastre)"]);
  assert.deepEqual(read("fix the left edge")?.done, ["Edge-Left: held along x, y, z (pinned)"]);
  assert.equal(read("fix the left edge")?.tab, "conditions");
});

test("a load is read with its unit, its direction and its sense", () => {
  const cases: [string, unknown[]][] = [
    ["pull the right edge with 2 kN", [{ region: "Edge-Right", dof: 1, total: 2000 }]], // tension: along the outward normal
    ["10 kN tension on the top edge", [{ region: "Edge-Top", dof: 2, total: 10000 }]],
    ["pull the left edge with 500 N", [{ region: "Edge-Left", dof: 1, total: -500 }]],
    ["push the top edge with 1 kN", [{ region: "Edge-Top", dof: 2, total: -1000 }]],
    ["apply 300 N in -z on the right edge", [{ region: "Edge-Right", dof: 3, total: -300 }]],
    ["a force of 250 N along x on the top edge", [{ region: "Edge-Top", dof: 1, total: 250 }]],
    ["load the right edge with 100 N downward", [{ region: "Edge-Right", dof: 3, total: -100 }]],
    ["CF2 of 400 N on the top edge", [{ region: "Edge-Top", dof: 2, total: 400 }]],
    ["pressure of 0.1 MPa on the face", [{ region: "Face", pressure: 0.1 }]],
    ["apply 5 kPa pressure", [{ region: "Face", pressure: 0.005 }]], // a pressure with no region is the face's
    ["20 kPa suction on the face", [{ region: "Face", pressure: -0.02 }]],
    ["100 lbf tension on the right edge", [{ region: "Edge-Right", dof: 1, total: 444.822161526 }]], // into the plate's own units
  ];
  for (const [text, loads] of cases) assert.deepEqual(sent(text)?.loads, loads, text);
  assert.deepEqual(read("pull the right edge with 2 kN")?.done, ["Edge-Right: force of 2000 N along x (tension)"]);
  assert.equal(read("pull the right edge with 2 kN")?.tab, "loads");
  const inches: StudioForm = { ...plate, units: "in-psi" };
  assert.deepEqual(sent("pull the right edge with 100 lbf", emptyPlate(), inches)?.loads, [{ region: "Edge-Right", dof: 1, total: 100 }]);
  assert.deepEqual(sent("pressure of 2 psi on the face", emptyPlate(), inches)?.loads, [{ region: "Face", pressure: 2 }]);
});

test("an edge moved or turned by a set amount is a boundary condition with its value", () => {
  assert.deepEqual(sent("move the top edge 0.5 mm in y")?.supports, [{ region: "Edge-Top", dofs: [2], value: 0.5 }]);
  assert.deepEqual(sent("displace the right edge by 1 mm along x")?.supports, [{ region: "Edge-Right", dofs: [1], value: 1 }]);
  assert.deepEqual(sent("move the top edge 2 mm down")?.supports, [{ region: "Edge-Top", dofs: [3], value: -2 }]);
  assert.deepEqual(sent("rotate the right edge 0.01 rad about y")?.supports, [{ region: "Edge-Right", dofs: [5], value: 0.01 }]);
  // the moved direction leaves the edge's hold, which keeps the others; a new hold keeps the move
  const held = read("clamp the top edge")!.lists;
  assert.deepEqual(sent("move the top edge 0.5 mm in y", held)?.supports, [{ region: "Edge-Top", dofs: [1, 3, 4, 5, 6] }, { region: "Edge-Top", dofs: [2], value: 0.5 }]);
  const moved = read("move the top edge 0.5 mm in y")!.lists;
  assert.deepEqual(sent("hold the top edge in x and z", moved)?.supports, [{ region: "Edge-Top", dofs: [2], value: 0.5 }, { region: "Edge-Top", dofs: [1, 3] }]);
});

test("two regions in one clause are one change only when plainly joined", () => {
  assert.deepEqual(sent("clamp the left and right edges")?.supports, [{ region: "Edge-Left", dofs: [1, 2, 3, 4, 5, 6] }, { region: "Edge-Right", dofs: [1, 2, 3, 4, 5, 6] }]);
  assert.deepEqual(sent("fix the top, bottom and left edges")?.supports.map((s) => (s as { region: string }).region), ["Edge-Left", "Edge-Top", "Edge-Bottom"]);
  assert.deepEqual(sent("hold the bottom edge and pull the top edge with 10 kN in tension"), { supports: [{ region: "Edge-Bottom", dofs: [1, 2, 3] }],
    loads: [{ region: "Edge-Top", dof: 2, total: 10000 }], regions: [] });
});

test("one message changes several things, and a change replaces what was there", () => {
  const edit = read("fix the left edge and pull the right edge with 10 kN");
  assert.deepEqual(plateValues(edit!.lists), { supports: [{ region: "Edge-Left", dofs: [1, 2, 3] }], loads: [{ region: "Edge-Right", dof: 1, total: 10000 }], regions: [] });
  assert.equal(edit!.done.length, 2);
  // changing a boundary condition: the new hold takes the old one's place, the new force the old one's along that direction
  const again = read("clamp the left edge, then pull the right edge with 4 kN", edit!.lists);
  assert.deepEqual(plateValues(again!.lists), { supports: [{ region: "Edge-Left", dofs: [1, 2, 3, 4, 5, 6] }], loads: [{ region: "Edge-Right", dof: 1, total: 4000 }], regions: [] });
  const three = read("clamp the bottom edge; XSYMM on the left edge; 0.01 MPa on the face");
  assert.equal(three!.lists.supports.length, 2);
  assert.equal(three!.lists.loads.length, 1);
});

test("a hold or a load is taken away by name", () => {
  const lists = read("fix the left edge and pull the right edge with 10 kN")!.lists;
  assert.deepEqual(plateValues(read("remove the load on the right edge", lists)!.lists).loads, []);
  assert.deepEqual(plateValues(read("free the left edge", lists)!.lists).supports, []);
  assert.deepEqual(read("remove the boundary condition on the left edge", lists)!.done, ["Edge-Left: no longer held"]);
  assert.deepEqual(plateValues(read("remove all loads", lists)!.lists), { supports: [{ region: "Edge-Left", dofs: [1, 2, 3] }], loads: [], regions: [] });
  assert.deepEqual(plateValues(read("clear all boundary conditions", lists)!.lists).supports, []);
  assert.match(read("remove the load on the top edge", lists)!.notes[0], /Nothing to remove on Edge-Top/);
});

test("the place clicked is “here”, a hole and tabs are named when the plate has them", () => {
  assert.deepEqual(plateValues(read("fix this edge", emptyPlate(), plate, ["Face", "Edge-Top"])!.lists).supports, [{ region: "Edge-Top", dofs: [1, 2, 3] }]);
  assert.deepEqual(plateValues(read("0.02 MPa here", emptyPlate(), plate, ["Face"])!.lists).loads, [{ region: "Face", pressure: 0.02 }]);
  assert.equal(read("fix this edge", emptyPlate(), plate, ["Face"]), null); // nothing clicked that is an edge
  assert.equal(read("fix the hole")!.notes[0], "This plate has no hole.");
  const holed = { ...plate, hole_diameter: "10" };
  assert.deepEqual(sent("fix the hole", emptyPlate(), holed)?.supports, [{ region: "Hole", dofs: [1, 2, 3] }]);
  const tabbed = { ...plate, tab_length: "30" };
  assert.deepEqual(sent("clamp the bottom tab", emptyPlate(), tabbed)?.supports, [{ region: "Tab-Bottom", dofs: [1, 2, 3, 4, 5, 6] }]);
});

test("what is read and cannot be done is said, never guessed", () => {
  assert.match(read("pressure of 1 MPa on the left edge")!.notes[0], /acts on an area/);
  assert.match(read("roller on the left edge")!.notes[0], /roller holds one direction/);
  assert.match(read("apply a moment of 5 N·m about x on the top edge")!.notes[0], /moment is not offered yet/);
  assert.deepEqual(read("pressure of 1 MPa on the left edge")!.lists, emptyPlate());
});

test("a question, a row of the setup or a clause it cannot place is left to the next reader, whole", () => {
  for (const text of ["what holds the left edge?", "which edges are fixed", "is the left edge fixed?", "how do I fix the left edge", "don't fix the left edge",
    "make it 300 long", "finer mesh", "use AS4/8552", "[0/90]s", "run", "fix it", "fix the left edge and make it 300 long", "apply 5 kN", "pull the right edge",
    "pull the right edge with 2 kN and 3 kN", "make the top ply 45", "what's left to do", "press here, a hundredth of an MPa",
    "the bottom edge is bolted down and the top edge carries 10 kN in tension", "fix the left edge so the right edge can move"]) {
    assert.equal(read(text), null, text);
  }
});

test("on a tension coupon, a boundary condition of one's own is asked for by naming an edge or the face", () => {
  const coupon = { ...blankForm(), test: "unnotched tension", library: "im7-8552", ply_1: "0", symmetric: "yes" };
  for (const text of ["fix the left edge", "XSYMM on the left edge", "pressure of 0.1 MPa on the face", "pull the right edge with 2 kN", "clamp the bottom edge"]) {
    assert.ok(asksPlateEdit(text, coupon), text);
  }
  // the coupon's own pull, its rows and its questions stay the coupon's
  for (const text of ["pull it with 2 kN", "make it 30 wide", "what are the boundary conditions?", "add a boundary condition", "compression", "0.5 mm"]) {
    assert.ok(!asksPlateEdit(text, coupon), text);
  }
  assert.ok(canBecomePlate(coupon));
  assert.ok(!canBecomePlate({ ...coupon, test: "three-point bending" }));
  assert.ok(!canBecomePlate({ ...coupon, narrow_width: "13" }));
});

test("a tension coupon is carried over as a plate held and loaded as the test holds and loads it (ADR-0089 amendment 8)", () => {
  const coupon = { ...blankForm(), test: "unnotched tension", standard: "ASTM D3039/D3039M-17", library: "im7-8552", ply_1: "45", ply_2: "0", symmetric: "yes" };
  const built = { units: "mm-MPa",
    geometry: { length: 250, width: 25, tab_length: 56, hole_diameter: null, thickness: 1.46 },
    held: [{ set: "Grip-Bottom", through: null, dofs: [1, 2, 3, 4, 5, 6], directions: [], nodes: 377 }, { set: "Grip-Top", through: null, dofs: [1], directions: [], nodes: 377 },
      { set: "Grip-Top", through: null, dofs: [3, 4, 5, 6], directions: [], nodes: 377 }],
    loaded: { set: "Grip-Top", through: null, control: "displacement", dof: 2, direction: "+y", value: 1, unit: "mm", nodes: 377 } };
  const { form, lists, carried } = plateFromCoupon(coupon, built, { element_size: "2", length: "250" });
  assert.deepEqual([form.test, form.standard, form.length, form.width, form.tab_length, form.element_size, form.library], [PLATE_TEST, "none", "250", "25", "56", "2", "im7-8552"]);
  assert.deepEqual(plateValues(lists).supports, [{ region: "Tab-Bottom", dofs: [1, 2, 3, 4, 5, 6] }, { region: "Tab-Top", dofs: [1, 3, 4, 5, 6] },
    { region: "Tab-Top", dofs: [2], value: 1 }]); // as fea/tests/test_plate_kind.py states the coupon as a plate
  assert.deepEqual(carried, ["Tab-Bottom: fixed (encastre)", "Tab-Top: free to move along the coupon only", "Tab-Top: moved 1 mm along y"]);
  // under a force the top grip keeps its hold and the pull is a load
  const forced = plateFromCoupon(coupon, { ...built, loaded: { ...built.loaded, control: "force", value: 10000, unit: "N" } });
  assert.deepEqual(plateValues(forced.lists), { supports: [{ region: "Tab-Bottom", dofs: [1, 2, 3, 4, 5, 6] }, { region: "Tab-Top", dofs: [1, 3, 4, 5, 6] }],
    loads: [{ region: "Tab-Top", dof: 2, total: 10000 }], regions: [] });
  // with no model built yet: the test's own grips, the pull the rows state, and the size left for the engineer or the next check
  const bare = plateFromCoupon({ ...coupon, value: "0.5", control: "displacement" }, null);
  assert.deepEqual(plateValues(bare.lists).supports, [{ region: "Edge-Bottom", dofs: [1, 2, 3, 4, 5, 6] }, { region: "Edge-Top", dofs: [1, 3, 4, 5, 6] },
    { region: "Edge-Top", dofs: [2], value: 0.5 }]);
  assert.equal(bare.form.element_size, ""); // the package chooses it by the plate's size
  // a further sentence then changes it as it would any plate
  const edit = readPlateEdit("XSYMM on the left edge", form, lists);
  assert.equal(edit!.lists.supports.length, 4);
});
