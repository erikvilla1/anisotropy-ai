import test from "node:test";
import { findLibraryOption, libraryOptions } from "../lib/material-library-options";
import assert from "node:assert/strict";
import example from "../api/examples/zero-degree-tension.json";
import { apiFieldErrors, buildAnalysisRequest, exampleForm, readAnalysisResult } from "../lib/laminate-api";

test("display units round-trip the shared cited API example", () => {
  const form = exampleForm();
  assert.equal(form.material.E1_GPa, "147");
  assert.equal(form.plies[0].thickness_mm, "0.25");
  assert.deepEqual(buildAnalysisRequest(form).request, example);
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
  const form = exampleForm();
  form.loads.Ny = " ";
  form.material.source_reference = "";
  form.plies = [];
  const parsed = buildAnalysisRequest(form);
  assert.equal(parsed.request, undefined);
  assert.deepEqual(Object.keys(parsed.errors!).sort(), ["loads.Ny", "material.source_reference", "plies"]);
});

test("malformed, non-finite and nonpositive input cannot become a calculation request", () => {
  for (const value of ["", "Infinity", "NaN", "0x20", "147 GPa", "1e309", "0", "-1"]) {
    const form = exampleForm();
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

test("a library selection sends the dataset reference, not the rounded display values", () => {
  const im7 = findLibraryOption("im7-8552::ncamp-im7-8552-2019-rtd-measured-v1")!;
  assert.equal(im7.E1_GPa, "162.096");
  assert.equal(im7.thickness_mm, "0.18288");
  assert.match(im7.citation, /CAM-RP-2009-015/);
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
