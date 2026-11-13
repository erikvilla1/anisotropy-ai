import test from "node:test";
import { findLibraryOption, libraryOptions } from "../lib/material-library-options";
import assert from "node:assert/strict";
import example from "../api/examples/zero-degree-tension.json";
import {
  apiFieldErrors, buildAnalysisRequest, CalculationError, EXAMPLE_LIBRARY, exampleForm, readAnalysisResult, requestAnalysis, shownCitation, shownMatrices,
  type CalculatorForm,
} from "../lib/laminate-api";
import { ANALYSIS_UNAVAILABLE, bannedIn } from "../lib/studio-copy";

/** The example with its values typed by hand, as editing a value does on the page: the library choice is dropped. */
const manual = (): CalculatorForm => { const form = exampleForm(); form.material.library = ""; return form; };

test("the example is AS4 / 3501-6 from the material library under the API example's ply and load (laminate-1)", () => {
  const form = exampleForm();
  const option = findLibraryOption(EXAMPLE_LIBRARY)!;
  assert.equal(form.material.library, option.value);
  assert.equal(form.material.E1_GPa, "147");
  assert.equal(form.plies[0].thickness_mm, "0.25"); // the dataset records no ply thickness: the example's
  const request = buildAnalysisRequest(form).request!;
  assert.deepEqual(request.material, { library_id: "as4-3501", dataset_id: "daniel-ishai-2006-as4-3501-v2" }); // the dataset, not the rounded display
  assert.deepEqual([request.plies, request.loads, request.unit_system], [example.plies, example.loads, example.unit_system]);
  // the form shows the library's citation without its record ids, and never the API example's developer note
  assert.equal(form.material.source_reference, shownCitation(option.citation));
  assert.doesNotMatch(form.material.source_reference, /dataset|record|validation|\.toml|practice/);
  // it opens with the authors and year and cites the book's printed page, 377, as the provenance list after Solve does; 397 is the PDF's
  assert.equal(form.material.source_reference, "Daniel & Ishai (2006) · Engineering Mechanics of Composite Materials · Second edition · ISBN 978-0-19-515097-1; E₁ from p. 377");
  assert.doesNotMatch(form.material.source_reference, /397/);
  for (const value of [form.material.source_reference, ...Object.values(form.material), ...Object.values(form.loads)]) assert.deepEqual(bannedIn(value), [], value);
  // typed by hand, the values go as SI with their source
  assert.deepEqual(buildAnalysisRequest(manual()).request!.material,
    { E1_pa: 147e9, E2_pa: 10.3e9, G12_pa: 7e9, nu12: 0.27, source_reference: shownCitation(option.citation) });
});

test("signed scientific notation, explicit zeros and bottom-first ordering reach the API", () => {
  const form = exampleForm();
  form.loads.Nx = "-1.25e4";
  form.plies = [{ angle_deg: "-45", thickness_mm: "0.125" }, { angle_deg: "+30", thickness_mm: ".25" }];
  const parsed = buildAnalysisRequest(form);
  assert.ok(parsed.request);
  assert.equal(parsed.request.loads.Nx, -12500);
  assert.equal(parsed.request.loads.Mx, 0);
  assert.deepEqual(parsed.request.plies, [{ angle_deg: -45, thickness_m: 0.000125 }, { angle_deg: 30, thickness_m: 0.00025 }]);
});

test("missing loads, missing sources and empty stacks remain errors", () => {
  const form = manual();
  form.loads.Ny = " ";
  form.material.source_reference = "";
  form.plies = [];
  const parsed = buildAnalysisRequest(form);
  assert.equal(parsed.request, undefined);
  assert.deepEqual(Object.keys(parsed.errors!).sort(), ["loads.Ny", "material.source_reference", "plies"]);
});

test("malformed, non-finite and nonpositive input cannot become a calculation request", () => {
  for (const value of ["", "Infinity", "NaN", "0x20", "147 GPa", "1e309", "0", "-1"]) {
    const form = manual();
    form.material.E1_GPa = value;
    const parsed = buildAnalysisRequest(form);
    assert.ok(parsed.errors?.["material.E1_GPa"], value);
    assert.equal(parsed.request, undefined);
  }
  const form = exampleForm();
  form.plies[0].thickness_mm = "1e-323"; // Conversion to metres underflows to zero.
  assert.ok(buildAnalysisRequest(form).errors?.["plies.0.thickness_mm"]);
});

test("API field locations map to the displayed units", () => {
  assert.deepEqual(apiFieldErrors({ detail: [
    { loc: ["body", "material", "E1_pa"], msg: "Bad modulus" },
    { loc: ["body", "plies", 1, "thickness_m"], msg: "Bad thickness" },
    { loc: ["body", "material"], msg: "Invalid compliance" },
  ] }), { "material.E1_GPa": "Bad modulus", "plies.1.thickness_mm": "Bad thickness", material: "Invalid compliance" });
});

test("malformed matrices, non-finite results and mismatched echoed inputs are rejected", () => {
  const request = buildAnalysisRequest(exampleForm()).request!;
  // Synthetic protocol fixture, not claimed to be an engineering result.
  const result = {
    inputs: request, engine_version: "test", midplane_strain: [0, 0, 0], curvature_per_m: [0, 0, 0],
    A_N_per_m: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    B_N: [[0, 0, 0], [0, 0, 0], [0, 0, 0]],
    D_N_m: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  };
  assert.equal(readAnalysisResult(result, request), result);
  for (const invalid of [null, {}, { ...result, A_N_per_m: [[1, 2]] }, { ...result, midplane_strain: [Infinity, 0, 0] },
    { ...result, inputs: { ...request, loads: { ...request.loads, Nx: 42 } } }]) {
    assert.throws(() => readAnalysisResult(invalid, request), /unexpected result/);
  }
});

test("the stack's description and the failure check are optional, and whole when present (ADR-0059)", () => {
  const request = buildAnalysisRequest(exampleForm()).request!;
  const base = {
    inputs: request, engine_version: "test", midplane_strain: [0, 0, 0], curvature_per_m: [0, 0, 0],
    A_N_per_m: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], B_N: [[0, 0, 0], [0, 0, 0], [0, 0, 0]], D_N_m: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
  };
  const summary = {
    ply_count: 1, total_thickness_m: 0.00025, symmetric: true, antisymmetric: false, balanced: true, kind: "unidirectional",
    coupling: { extension_shear: false, extension_bending: false, bending_twisting: false }, relative_tolerance: 1e-9,
    areal_mass_kg_per_m2: null, areal_mass_missing: "plies [1] have no density",
  };
  const failure = {
    evaluated: true, reason: null,
    criteria: [{ criterion: "max_stress", strength_ratio: 2.5, ply: 1, angle_deg: 0, face: "bottom", z_m: -0.000125, mode: "fiber tension",
      failure_loads: { Nx: 62500, Ny: 0, Nxy: 0, Mx: 0, My: 0, Mxy: 0 } }],
    not_computed: [{ criterion: "tsai_wu", reason: "no f12_star" }],
  };
  assert.ok(readAnalysisResult({ ...base, summary: null, first_ply_failure: null }, request));
  assert.ok(readAnalysisResult({ ...base, summary, first_ply_failure: failure }, request));
  for (const invalid of [
    { ...base, summary: { ...summary, kind: "isotropic" } },
    { ...base, summary: { ...summary, coupling: {} } },
    { ...base, summary: { ...summary, total_thickness_m: "thick" } },
    { ...base, first_ply_failure: { ...failure, evaluated: "yes" } },
    { ...base, first_ply_failure: { ...failure, criteria: [{ ...failure.criteria[0], face: "middle" }] } },
    { ...base, first_ply_failure: { ...failure, criteria: [{ ...failure.criteria[0], failure_loads: { Nx: 1 } }] } },
  ]) {
    assert.throws(() => readAnalysisResult(invalid, request), /unexpected result/);
  }
});

test("a library selection sends the dataset reference, not the rounded display values", () => {
  const im7 = findLibraryOption("im7-8552::ncamp-im7-8552-2019-rtd-measured-v1")!;
  assert.equal(im7.E1_GPa, "162.096");
  assert.equal(im7.thickness_mm, "0.18288");
  assert.match(im7.citation, /CAM-RP-2009-015/);
  assert.match(im7.citation, /^Hexcel 8552 IM7 .*; E₁ from p\. 30$/); // the report names no authors; it records no printed page
  const nasa = findLibraryOption("im7-8552::nasa-tm-20230001560-im7-8552-rt-measured-v1")!;
  assert.match(nasa.citation, /^Maurya et al\. \(2023\) · Experimental Tests .*; E₁ from p\. 12$/); // five authors; printed p. 12, PDF p. 18
  assert.ok(libraryOptions.every(o => o.materialId && o.datasetId && Number(o.E1_GPa) > 0 && Number(o.nu12) >= 0));
  assert.ok(!libraryOptions.some(o => o.materialId === "t650-35-976")); // No elastic input set.
  const form = exampleForm();
  form.material = { ...form.material, library: im7.value, E1_GPa: im7.E1_GPa, source_reference: "" };
  const parsed = buildAnalysisRequest(form);
  assert.deepEqual(parsed.request!.material, { library_id: "im7-8552", dataset_id: "ncamp-im7-8552-2019-rtd-measured-v1" });
  form.material.library = "not-a-dataset";
  assert.ok(buildAnalysisRequest(form).errors!["material.library"]);
  assert.deepEqual(apiFieldErrors({ detail: [{ loc: ["body", "material", "library", "library_id"], msg: "unknown library material" }] }), { "material.library": "unknown library material" });
  assert.deepEqual(apiFieldErrors({ detail: [{ loc: ["body", "material", "explicit"], msg: "Invalid compliance" }, { loc: ["body", "material", "explicit", "E1_pa"], msg: "Bad" }] }), { material: "Invalid compliance", "material.E1_GPa": "Bad" });
});

test("A, B and D are shown without roundoff: B is zero without extension–bending coupling, A16 and A26 without extension–shear (laminate-5)", () => {
  const coupling = { extension_shear: false, extension_bending: false, bending_twisting: true };
  const summary = { ply_count: 8, total_thickness_m: 0.001, symmetric: true, antisymmetric: false, balanced: true, kind: "quasi-isotropic" as const,
    coupling, relative_tolerance: 1e-9, areal_mass_kg_per_m2: null, areal_mass_missing: null };
  // synthetic matrices with arithmetic noise where the stack has no coupling, not an engineering result
  const A = [[63.49e6, 18.36e6, 0], [18.36e6, 63.49e6, 1.86e-9], [0, 1.86e-9, 22.56e6]];
  const B = [[-9.09e-10, -1.14e-10, 0], [-1.14e-10, -1.14e-10, 0], [0, 0, 1.7e-10]];
  const D = [[8.754, 1.287, 0.5367], [1.287, 2.314, 0.5367], [0.5367, 0.5367, 1.637]];
  const shownAbd = shownMatrices({ A_N_per_m: A, B_N: B, D_N_m: D, summary });
  assert.deepEqual(shownAbd.B, [[0, 0, 0], [0, 0, 0], [0, 0, 0]]);
  assert.deepEqual(shownAbd.A, [[63.49e6, 18.36e6, 0], [18.36e6, 63.49e6, 0], [0, 0, 22.56e6]]);
  assert.deepEqual(shownAbd.D, D); // bending–twisting coupling is real: kept
  const coupled = shownMatrices({ A_N_per_m: A, B_N: [[1e3, 0, 0], [0, -1e3, 0], [0, 0, 1e-12]], D_N_m: D, summary: { ...summary, coupling: { ...coupling, extension_bending: true } } });
  assert.deepEqual(coupled.B, [[1e3, 0, 0], [0, -1e3, 0], [0, 0, 0]]); // a coupled B keeps its values, its noise settled
  assert.deepEqual(shownMatrices({ A_N_per_m: A, B_N: B, D_N_m: D }).B[0][0], B[0][0]); // an older answer with no summary: as it came
});

test("an outage says the analysis is unavailable and the inputs are kept; only a 422 asks to review the inputs (laminate-13)", async () => {
  const request = buildAnalysisRequest(exampleForm()).request!;
  const original = globalThis.fetch;
  const signal = new AbortController().signal;
  const answer = (body: string, status: number) => { globalThis.fetch = (async () => new Response(body, { status })) as typeof fetch; };
  try {
    globalThis.fetch = (async () => { throw new TypeError("fetch failed"); }) as typeof fetch;
    await assert.rejects(requestAnalysis("http://api.test", request, signal), (error: CalculationError) => error.message === ANALYSIS_UNAVAILABLE);
    answer("<html>Bad gateway</html>", 502);
    await assert.rejects(requestAnalysis("http://api.test", request, signal), (error: CalculationError) => error.message === ANALYSIS_UNAVAILABLE);
    answer(JSON.stringify({ detail: "the container did not answer" }), 503);
    await assert.rejects(requestAnalysis("http://api.test", request, signal), (error: CalculationError) => error.message === ANALYSIS_UNAVAILABLE);
    answer(JSON.stringify({ detail: "Elastic constants violate positive compliance" }), 422);
    await assert.rejects(requestAnalysis("http://api.test", request, signal), /positive compliance/);
    answer(JSON.stringify({ detail: "our engine refused it at engine/cases.py" }), 422); // a refusal whose words are not fit to show
    await assert.rejects(requestAnalysis("http://api.test", request, signal), /Review the highlighted inputs/);
    answer("not json", 200);
    await assert.rejects(requestAnalysis("http://api.test", request, signal), /unexpected result/);
    // a refusal that is not an outage nor the inputs' (signed out, a limit reached): not "unavailable", which says to wait
    answer("<html>Sign in</html>", 403);
    await assert.rejects(requestAnalysis("http://api.test", request, signal), (error: CalculationError) => error.message === "The analysis could not start. Try again; if it fails again, contact us.");
    answer(JSON.stringify({ detail: "Too many analyses at once; wait for one to finish." }), 429);
    await assert.rejects(requestAnalysis("http://api.test", request, signal), (error: CalculationError) => error.message === "Too many analyses at once; wait for one to finish.");
    answer(JSON.stringify({ detail: "the engine's queue at ANISOTROPY_LIVE_WORKERS is full" }), 429); // words not fit to show
    await assert.rejects(requestAnalysis("http://api.test", request, signal), (error: CalculationError) => error.message.startsWith("The analysis could not start."));
  } finally {
    globalThis.fetch = original;
  }
  assert.deepEqual(bannedIn(ANALYSIS_UNAVAILABLE), []);
});
