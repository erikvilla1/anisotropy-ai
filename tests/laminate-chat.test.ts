import { test } from "node:test";
import assert from "node:assert/strict";
import {
  answerMatches, blankDraft, buildProblem, LIBRARY_MATERIALS, libraryChoice, libraryNameOf, libraryThicknessOf, loadChip, loadsWithZeros, missingIn, nextStep, plyLabel,
  problemLines, readConstants, readLayupLine, readLibraryMaterial, readLoads, readSystem, REPORT_SYSTEMS, ANGLE_CONVENTION,
  systemUnit, unitNamed, unitsOf, type LaminateDraft, type OwnConstants,
} from "../lib/laminate-chat";
import { libraryOptions } from "../lib/material-library-options";
import { bannedIn } from "../lib/studio-copy";
import library from "../engine/src/anisotropy_engine/data/material-library.json";
import usAnswer from "./fixtures/studio/laminate-answer-us.json";

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
  assert.deepEqual(understood.slice(0, 4), ["E₁ 147 GPa", "E₂ 10300 MPa", "G₁₂ 7.0 GPa", "ν₁₂ 0.27"]); // echoed with the symbols the fields use
  assert.deepEqual(refused, []);
  const us = readConstants("E1 = 21.3 Msi, E2 = 1.5, G12 0.9 Msi, v12 = 0.3, Xt 330 ksi, Xc 250, Yt 8.3, Yc 33, F6 11", "US");
  assert.deepEqual(us.constants.E2, { value: "1.5", unit: "Msi" });
  assert.deepEqual(us.constants.F1t, { value: "330", unit: "ksi" });
  assert.deepEqual(us.constants.F2c, { value: "33", unit: "ksi" });
  assert.equal(us.constants.nu12, "0.3");
  const wrong = readConstants("E1 147 mm", "SI");
  assert.equal(wrong.constants.E1, undefined);
  assert.deepEqual(wrong.refused, ["E₁: mm is not a modulus unit"]);
  assert.deepEqual(readConstants("G12 7.0 nu12 0.27", "SI").constants.G12, { value: "7.0", unit: "GPa" }); // the next name is not a unit
});

test("a library material, a layup with its ply thickness, and the loads are read with their units", () => {
  assert.equal(readLibraryMaterial("use IM7/8552"), "im7-8552::ncamp-im7-8552-2019-rtd-measured-v1"); // the material's first dataset, the primary one
  assert.equal(readLibraryMaterial("AS4/8552 please"), "as4-8552::ncamp-as4-8552-2011-rtd-measured-v2");
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
    ["Units", "SI"], ["Material", "AS4/3501-6, E₁ 147 GPa, E₂ 10300 MPa, G₁₂ 7.0 GPa"], ["Layup", "[0/45/-45/90]s, 8 plies, 0.125 mm plies"], ["Loads", "Nx = 100 N/mm"],
  ]);
  assert.deepEqual(problemLines(blankDraft()), [["Units", ""], ["Material", ""], ["Layup", ""], ["Loads", ""]]);
  assert.deepEqual(problemLines({ ...blankDraft(), material: { library: "im7-8552" }, layup: { notation: "[0/90]s", angles: [0, 90, 90, 0], symmetric: true } })[2],
    ["Layup", "[0/90]s, 4 plies, 0.1829 mm plies (library)"]);
});

// --- the temperature condition (ADR-0087) ---------------------------------------------------------------------------------------

test("a temperature change is read with its sign and unit, as engineers say it", async () => {
  const { readTemperature, temperatureUnit } = await import("../lib/laminate-chat");
  assert.deepEqual(readTemperature("the laminate is cooled by 150 °C after cure").delta_T, { value: "-150", unit: "degC" });
  assert.deepEqual(readTemperature("heated 80 C in service").delta_T, { value: "80", unit: "degC" });
  assert.deepEqual(readTemperature("ΔT = -270 °F").delta_T, { value: "-270", unit: "degF" });
  assert.deepEqual(readTemperature("a temperature change of −100 K").delta_T, { value: "-100", unit: "K" });
  assert.deepEqual(readTemperature("a drop of 120 deg C").delta_T, { value: "-120", unit: "degC" });
  assert.equal(readTemperature("cooled down a lot").delta_T, undefined, "no number, no value: the condition is offered instead");
  const alphas = readTemperature("alpha1 = -0.9e-6 /°C, α2 27 x10^-6 per °C");
  assert.deepEqual([alphas.alpha1, alphas.alpha2], [{ value: "-0.9e-6", unit: "1/degC" }, { value: "27", unit: "1e-6/degC" }]);
  assert.equal(temperatureUnit("°F"), "degF");
  assert.equal(temperatureUnit("MPa"), null);
});

test("the temperature step asks only once the condition is on, and the problem carries what it states", () => {
  const own: OwnConstants = { name: "typed", source: "", E1: { value: "147", unit: "GPa" }, E2: { value: "10.3", unit: "GPa" }, G12: { value: "7", unit: "GPa" },
    nu12: "0.27", F1t: { value: "", unit: "" }, F1c: { value: "", unit: "" }, F2t: { value: "", unit: "" }, F2c: { value: "", unit: "" }, F6: { value: "", unit: "" } };
  const draft: LaminateDraft = { ...blankDraft(), system: "SI", material: { own }, layup: { notation: "[0/90]s", angles: [0, 90, 90, 0], symmetric: true },
    thickness: { value: "0.25", unit: "mm" }, loads: loadsWithZeros({}, "SI") };
  assert.deepEqual(missingIn("temperature", draft), []);
  assert.equal(nextStep(draft), "review", "no condition, no temperature step");
  const on = { ...draft, conditions: ["temperature"] };
  assert.deepEqual(missingIn("temperature", on), ["temperature change", "alpha1 and alpha2"]);
  assert.equal(nextStep(on), "temperature");
  const stated: LaminateDraft = { ...on, delta_T: { value: "-150", unit: "degC" }, alphas: { alpha1: { value: "-1", unit: "1e-6/degC" }, alpha2: { value: "25", unit: "1e-6/degC" } } };
  assert.equal(nextStep(stated), "review");
  const built = buildProblem(stated);
  assert.ok(built.problem, JSON.stringify(built.errors));
  assert.deepEqual(built.problem!.delta_T, { value: -150, unit: "degC" });
  assert.ok("name" in built.problem!.material && built.problem!.material.alpha1?.unit === "1e-6/degC" && built.problem!.material.alpha2?.value === 25);
  assert.equal(buildProblem(draft).problem!.delta_T, undefined, "without the condition nothing thermal is sent");
  assert.deepEqual(problemLines(stated).at(-1), ["Temperature change", "-150 °C"]);
});

test("the words of a temperature change call the condition up", async () => {
  const { conditionsNamed } = await import("../lib/conditions");
  for (const text of ["there is a temperature change", "it is cooled after cure", "what are the residual stresses", "thermal loading too", "ΔT of 100"]) {
    assert.deepEqual(conditionsNamed(text, "laminate").map((c) => c.id), ["temperature"], text);
  }
  assert.deepEqual(conditionsNamed("Nx = 100 N/mm, the rest zero", "laminate"), []);
  assert.deepEqual(conditionsNamed("there is a temperature change", "fea"), [], "the coupon's temperature condition comes later (ADR-0087)");
});

// --- the one material list (D21), the answer's check (laminate-4), the words (laminate-2, 20, 21) --------------------------------

test("the workspace offers the calculator's list, one option per dataset, and sends the dataset picked (D21)", () => {
  assert.equal(LIBRARY_MATERIALS, libraryOptions); // one list, its labels as the library writes them
  const nasa = LIBRARY_MATERIALS.find((m) => m.datasetId === "nasa-tm-20230001560-im7-8552-rt-measured-v1")!;
  const draft: LaminateDraft = { ...blankDraft(), system: "SI", material: { library: nasa.value }, layup: { notation: "[0/90]s", angles: [0, 90, 90, 0], symmetric: true },
    loads: loadsWithZeros({ Nx: { value: "100", unit: "N/mm" } }, "SI") };
  assert.equal(libraryNameOf(nasa.value), nasa.label); // two IM7 / 8552 datasets: the chips and the card keep them apart
  const as4 = libraryChoice("as4-8552")!;
  assert.equal(libraryNameOf(as4.value), "AS4 / 8552"); // one dataset of the material: its name alone, without the dataset's words
  assert.equal(libraryNameOf("as4-8552"), "AS4 / 8552");
  assert.equal(problemLines({ ...blankDraft(), material: { library: as4.value } })[1][1], "AS4 / 8552");
  assert.equal(libraryThicknessOf(nasa.value), Number(nasa.thickness_mm));
  assert.deepEqual(buildProblem(draft).problem!.material, { library: "im7-8552", dataset: "nasa-tm-20230001560-im7-8552-rt-measured-v1" });
  // a project saved before the one list names the material alone: it reads as the first (primary) dataset and goes as it did
  assert.equal(libraryChoice("im7-8552")!.datasetId, "ncamp-im7-8552-2019-rtd-measured-v1");
  assert.deepEqual(buildProblem({ ...draft, material: { library: "im7-8552" } }).problem!.material, { library: "im7-8552" });
});

test("the list offers only the datasets the engine solves with: one value for each elastic input and for the ply thickness (ADR-0060 amendment 2)", () => {
  const ranged = (p: object | undefined) => p !== undefined && ("valueEnd" in p || "valueQualifier" in p);
  for (const d of library.datasets.filter((d) => d.elasticInputs)) {
    const props = new Map<string, object>(d.properties.map((p) => [p.key, p]));
    const keys = [...Object.values(d.elasticInputs as Record<string, string>), props.has("tply") ? "tply" : "tply-WT"];
    assert.equal(LIBRARY_MATERIALS.some((m) => m.datasetId === d.datasetId), !keys.some((k) => ranged(props.get(k))), d.datasetId);
  }
  // 7781 / E-765 records its ply thickness as 0.0091 to 0.0101 in, which the engine refuses; api/tests/test_laminate_problems.py solves the rest
  assert.equal(LIBRARY_MATERIALS.some((m) => m.datasetId === "agate-e765-2001-rtd-measured-v2"), false);
});

test("the assistant's one-click load is the same load in every system, in that system's units (laminate-26)", () => {
  assert.deepEqual(loadChip("SI"), { name: "Nx", quantity: { value: "100", unit: "N/mm" } });
  assert.deepEqual(loadChip("mm-MPa"), loadChip("SI"));
  assert.deepEqual(loadChip("US"), { name: "Nx", quantity: { value: "571", unit: "lb/in" } });
  assert.deepEqual(loadChip("psi"), loadChip("US"));
  // 571 lb/in is 100 N/mm as the engine itself reports it in US units, the same problem solved again in that system
  assert.match((usAnswer.prose as string[])[1], /^Under Nx = 571 lb\/in /);
  for (const system of ["SI", "mm-MPa", "US", "psi"] as const) assert.ok(unitsOf("N").includes(loadChip(system).quantity.unit), system);
});

test("an answer is shown only beside the problem it answers (laminate-4)", () => {
  const draft: LaminateDraft = { ...blankDraft(), system: "SI", material: { library: "im7-8552" }, layup: { notation: "[0/45/-45/90]s", angles: [0, 45, -45, 90, 90, -45, 45, 0], symmetric: true },
    thickness: { value: "0.125", unit: "mm" }, loads: loadsWithZeros({ Nx: { value: "100", unit: "N/mm" } }, "SI") };
  const problem = buildProblem(draft).problem!;
  const echoed = { report_units: "SI", case: { title: "[0/45/-45/90]s under Nx = 100 N/mm", laminate: { layup: [0, 45, -45, 90, 90, -45, 45, 0] } } };
  assert.equal(answerMatches(problem, echoed), true);
  assert.equal(answerMatches({ ...problem, title: "[0/45/-45/90]s under Nx = 100 N/m" }, echoed), false); // the same stack under another load
  assert.equal(answerMatches(problem, { ...echoed, report_units: "US" }), false);
  assert.equal(answerMatches(problem, { ...echoed, case: { ...echoed.case, laminate: { layup: [0, 90, 90, 0] } } }), false);
});

test("the laminate's words: one angle sentence, plain units, ply labels without a plus sign, nothing internal", () => {
  assert.equal(ANGLE_CONVENTION, "Bottom ply first. Angles run counterclockwise from x (the Nx direction) to the fibres.");
  assert.equal(plyLabel(4, 90), "Ply 4 · 90°");
  assert.equal(plyLabel(3, -45), "Ply 3 · −45°");
  assert.equal(REPORT_SYSTEMS.find((s) => s.id === "mm-MPa")!.detail, "MPa, mm, N/mm, N·mm/mm");
  for (const text of [ANGLE_CONVENTION, ...REPORT_SYSTEMS.flatMap((s) => [s.title, s.detail]), ...LIBRARY_MATERIALS.map((m) => m.label)]) assert.deepEqual(bannedIn(text), [], text);
});
