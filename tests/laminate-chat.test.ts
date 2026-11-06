import { test } from "node:test";
import assert from "node:assert/strict";
import {
  blankDraft, buildProblem, loadsWithZeros, missingIn, nextStep, problemLines, readConstants, readLayupLine, readLibraryMaterial, readLoads, readSystem,
  systemUnit, unitNamed, unitsOf, type LaminateDraft, type OwnConstants,
} from "../lib/laminate-chat";

test("the unit names come from the engine's table and a typed unit is read to its canonical name", () => {
  assert.deepEqual(unitsOf("modulus"), ["Pa", "kPa", "MPa", "GPa", "psi", "ksi", "Msi"]);
  assert.deepEqual(unitsOf("N"), ["N/m", "N/mm", "kN/m", "kN/mm", "lb/in", "kip/in"]);
  assert.equal(unitNamed("pressure", "gpa"), "GPa");
  assert.equal(unitNamed("pressure", "MSI"), "Msi");
  assert.equal(unitNamed("force_per_length", "n/mm"), "N/mm");
  assert.equal(unitNamed("force_per_length", "lbf/in"), "lb/in");
  assert.equal(unitNamed("moment_per_length", "N·mm/mm"), "N*mm/mm");
  assert.equal(unitNamed("length", "inches"), "in");
  assert.equal(unitNamed("length", "GPa"), null);
  assert.equal(systemUnit("US", "stress"), "ksi");
  assert.equal(systemUnit("mm-MPa", "N"), "N/mm");
});

test("a message names the system the problem is stated in", () => {
  assert.equal(readSystem("SI"), "SI");
  assert.equal(readSystem("US customary"), "US");
  assert.equal(readSystem("it's in psi and inches"), "psi");
  assert.equal(readSystem("Msi and ksi"), "US");
  assert.equal(readSystem("mm, N and MPa"), "mm-MPa");
  assert.equal(readSystem("[0/90]s"), null);
});

test("typed constants keep the unit they were typed in and take the system's unit otherwise", () => {
  const { constants, understood, refused } = readConstants("E1 147 GPa, E2 10300 MPa, G12 7.0, nu12 0.27, F1t 2280, F1c 1725, F2t 57, F2c 228, F6 76 MPa", "SI");
  assert.deepEqual(constants.E1, { value: "147", unit: "GPa" });
  assert.deepEqual(constants.E2, { value: "10300", unit: "MPa" });
  assert.deepEqual(constants.G12, { value: "7.0", unit: "GPa" }); // no unit typed: the system's
  assert.equal(constants.nu12, "0.27");
  assert.deepEqual(constants.F1t, { value: "2280", unit: "MPa" });
  assert.deepEqual(constants.F6, { value: "76", unit: "MPa" });
  assert.equal(understood.length, 9);
  assert.deepEqual(refused, []);
  const us = readConstants("E1 = 21.3 Msi, E2 = 1.5, G12 0.9 Msi, v12 = 0.3, Xt 330 ksi, Xc 250, Yt 8.3, Yc 33, F6 11", "US");
  assert.deepEqual(us.constants.E2, { value: "1.5", unit: "Msi" });
  assert.deepEqual(us.constants.F1t, { value: "330", unit: "ksi" });
  assert.deepEqual(us.constants.F2c, { value: "33", unit: "ksi" });
  assert.equal(us.constants.nu12, "0.3");
  const wrong = readConstants("E1 147 mm", "SI");
  assert.equal(wrong.constants.E1, undefined);
  assert.deepEqual(wrong.refused, ["E1: mm is not a modulus unit"]);
  assert.deepEqual(readConstants("G12 7.0 nu12 0.27", "SI").constants.G12, { value: "7.0", unit: "GPa" }); // the next name is not a unit
});

test("a library material, a layup with its ply thickness, and the loads are read with their units", () => {
  assert.equal(readLibraryMaterial("use IM7/8552"), "im7-8552");
  assert.equal(readLibraryMaterial("AS4/8552 please"), "as4-8552");
  assert.equal(readLibraryMaterial("E1 147 GPa"), null);
  const line = readLayupLine("[0/45/-45/90]s, 0.125 mm plies", "SI");
  assert.deepEqual(line.layup, { notation: "[0/45/-45/90]s", angles: [0, 45, -45, 90, 90, -45, 45, 0], symmetric: true });
  assert.deepEqual(line.thickness, { value: "0.125", unit: "mm" });
  assert.deepEqual(readLayupLine("ply thickness 0.0049 in", "SI").thickness, { value: "0.0049", unit: "in" });
  assert.deepEqual(readLayupLine("[0/90]2s with plies of 0.005", "US").thickness, { value: "0.005", unit: "in" });
  assert.equal(readLayupLine("[0/90]s", "SI").thickness, null);
  const loads = readLoads("Nx = 100 N/mm, everything else zero", "SI");
  assert.deepEqual(loads.loads, { Nx: { value: "100", unit: "N/mm" } });
  assert.equal(loads.othersZero, true);
  const two = readLoads("Nx 571 lb/in and Nxy -20", "US");
  assert.deepEqual(two.loads, { Nx: { value: "571", unit: "lb/in" }, Nxy: { value: "-20", unit: "lb/in" } });
  assert.equal(two.othersZero, false);
  assert.deepEqual(readLoads("Mx = 2.5 kN·m/m only", "SI").loads, { Mx: { value: "2.5", unit: "kN*m/m" } });
  assert.deepEqual(readLoads("Nx 100 MPa", "SI").refused, ["Nx: MPa is not a force per width unit"]);
  assert.deepEqual(loadsWithZeros(loads.loads, "mm-MPa"), {
    Nx: { value: "100", unit: "N/mm" }, Ny: { value: "0", unit: "N/mm" }, Nxy: { value: "0", unit: "N/mm" },
    Mx: { value: "0", unit: "N*mm/mm" }, My: { value: "0", unit: "N*mm/mm" }, Mxy: { value: "0", unit: "N*mm/mm" },
  });
});

function homework(): LaminateDraft {
  return {
    system: "SI",
    material: { own: { name: "AS4/3501-6", source: "Table A.4", E1: { value: "147", unit: "GPa" }, E2: { value: "10300", unit: "MPa" }, G12: { value: "7.0", unit: "GPa" }, nu12: "0.27",
      F1t: { value: "2280", unit: "MPa" }, F1c: { value: "1725", unit: "MPa" }, F2t: { value: "57", unit: "MPa" }, F2c: { value: "228", unit: "MPa" }, F6: { value: "76", unit: "MPa" } } },
    layup: { notation: "[0/45/-45/90]s", angles: [0, 45, -45, 90, 90, -45, 45, 0], symmetric: true },
    thickness: { value: "0.125", unit: "mm" },
    loads: loadsWithZeros({ Nx: { value: "100", unit: "N/mm" } }, "SI"),
    f12_star: "-0.5",
    strain_limits: false,
  };
}

test("the steps ask for what is missing, in order", () => {
  const draft = blankDraft();
  assert.equal(nextStep(draft), "units");
  draft.system = "SI";
  assert.equal(nextStep(draft), "material");
  draft.material = { library: "im7-8552" };
  assert.equal(nextStep(draft), "layup");
  draft.layup = { notation: "[0/90]s", angles: [0, 90, 90, 0], symmetric: true };
  assert.equal(nextStep(draft), "loads"); // the library records the ply thickness
  draft.material = { library: "as4-3501" };
  assert.deepEqual(missingIn("layup", draft), ["ply thickness"]); // this dataset records none
  draft.thickness = { value: "0.125", unit: "mm" };
  assert.equal(nextStep(draft), "loads");
  draft.loads = loadsWithZeros({}, "SI");
  assert.equal(nextStep(draft), "review");
  const own = (homework().material as { own: OwnConstants }).own;
  draft.material = { own: { ...own, E2: { value: "", unit: "GPa" } } };
  assert.deepEqual(missingIn("material", draft), ["E2"]);
});

test("the problem goes to the API with every value as typed and its unit, and nothing filled in", () => {
  const { problem, errors } = buildProblem(homework());
  assert.equal(errors, undefined);
  assert.deepEqual(problem!.material, {
    name: "AS4/3501-6", source: "Table A.4", E1: { value: 147, unit: "GPa" }, E2: { value: 10300, unit: "MPa" }, G12: { value: 7, unit: "GPa" }, nu12: 0.27,
    F1t: { value: 2280, unit: "MPa" }, F1c: { value: 1725, unit: "MPa" }, F2t: { value: 57, unit: "MPa" }, F2c: { value: 228, unit: "MPa" }, F6: { value: 76, unit: "MPa" },
  });
  assert.deepEqual(problem!.layup, [0, 45, -45, 90, 90, -45, 45, 0]);
  assert.equal(problem!.layup_notation, "[0/45/-45/90]s");
  assert.deepEqual(problem!.ply_thickness, { value: 0.125, unit: "mm" });
  assert.deepEqual(problem!.loads.Nx, { value: 100, unit: "N/mm" });
  assert.deepEqual(problem!.loads.Mxy, { value: 0, unit: "N*m/m" });
  assert.equal(problem!.f12_star, -0.5);
  assert.equal(problem!.report_units, "SI");
  assert.equal(problem!.title, "[0/45/-45/90]s under Nx = 100 N/mm");
  assert.equal(buildProblem(homework(), "US").problem!.report_units, "US");
  const four = homework();
  (four.material as { own: Record<string, unknown> }).own.F6 = { value: "", unit: "MPa" };
  assert.deepEqual(buildProblem(four).errors, ["strengths: give all five (F1t, F1c, F2t, F2c, F6) or none; F1t, F1c, F2t, F2c given"]);
  const blank = homework();
  blank.loads!.Ny = { value: "", unit: "N/m" };
  blank.f12_star = "abc";
  assert.deepEqual(buildProblem(blank).errors, ["Ny: required", 'f12*: "abc" is not a number']);
  const library = { ...homework(), material: { library: "im7-8552" }, thickness: null, f12_star: "" };
  const sent = buildProblem(library).problem!;
  assert.deepEqual(sent.material, { library: "im7-8552" });
  assert.equal(sent.ply_thickness, undefined);
  assert.equal(sent.f12_star, undefined);
  assert.equal("strain_limits" in sent.material, false); // not ticked: nothing is sent, nothing is assumed
});

test("maximum strain is a stated choice: ticked, it goes with the material; without five strengths it is refused", () => {
  const ticked = { ...homework(), strain_limits: true };
  assert.equal(buildProblem(ticked).problem!.material.strain_limits, "from-strengths");
  const library = { ...homework(), material: { library: "im7-8552" }, thickness: null, strain_limits: true };
  assert.deepEqual(buildProblem(library).problem!.material, { library: "im7-8552", strain_limits: "from-strengths" });
  const own = (homework().material as { own: OwnConstants }).own;
  const bare = { ...homework(), material: { own: { ...own, F1t: "", F1c: "", F2t: "", F2c: "", F6: "" } }, strain_limits: true };
  assert.deepEqual(buildProblem(bare).errors, ["strain limits: maximum strain needs all five strengths to derive its limits from"]);
});

test("the card beside the chat states only what is given", () => {
  assert.deepEqual(problemLines(homework()), [
    ["Units", "SI"], ["Material", "AS4/3501-6, E1 147 GPa, E2 10300 MPa, G12 7.0 GPa"], ["Layup", "[0/45/-45/90]s, 8 plies, 0.125 mm plies"], ["Loads", "Nx = 100 N/mm"],
  ]);
  assert.deepEqual(problemLines(blankDraft()), [["Units", ""], ["Material", ""], ["Layup", ""], ["Loads", ""]]);
  assert.deepEqual(problemLines({ ...blankDraft(), material: { library: "im7-8552" }, layup: { notation: "[0/90]s", angles: [0, 90, 90, 0], symmetric: true } })[2],
    ["Layup", "[0/90]s, 4 plies, 0.1829 mm plies (library)"]);
});
