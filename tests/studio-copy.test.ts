import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  bannedIn, checkText, customerText, downloadName, DOWNLOAD_LABELS, queueAhead, RUN_STEPS, runHeadline, runProblem, runSteps, shownSentence, verificationLine,
  withSymbols,
} from "../lib/studio-copy";

const fixture = (name: string, dir = "studio") => JSON.parse(readFileSync(`tests/fixtures/${dir}/${name}.json`, "utf8"));

test("the pipeline's stages fold into five steps, and a job's state says which is current (ADR-0091)", () => {
  assert.deepEqual(RUN_STEPS.map((s) => s.label), ["Queued", "Meshing", "Solving", "Post-processing", "Report ready"]);
  const states = (job: { state: string; stage: string | null; documents?: string | null }) =>
    runSteps(job as Parameters<typeof runSteps>[0]).map((s) => s.state).join(" ");
  assert.equal(states({ state: "queued", stage: null }), "current waiting waiting waiting waiting");
  assert.equal(states(fixture("job-running")), "done done current waiting waiting"); // "our engine": solving
  assert.equal(states({ state: "running", stage: "the CalculiX record" }), "done done done current waiting");
  assert.equal(states(fixture("job-result-in")), "done done done done current"); // "the package": the report is being written
  assert.equal(states(fixture("job-done")), "done done done done done");
  assert.equal(states({ state: "done", stage: "the outputs", documents: "the package not written (Tectonic stopped)" }), "done done done done stopped");
  assert.equal(states({ state: "stopped", stage: "CalculiX" }), "done done stopped waiting waiting");
  assert.equal(states({ state: "running", stage: "a stage added later" }), "done done current waiting waiting"); // unknown: solving
});

test("the run in a word, and a stopped run in plain language with what to do", () => {
  assert.equal(queueAhead("queued; 2 ahead"), 2);
  assert.equal(queueAhead("waiting for a free solver; 1 job(s) ahead of this one"), 1); // an API from before ADR-0091
  assert.equal(queueAhead("queued"), null);
  const job = (over: Record<string, unknown>) => ({ state: "running", stage: null, message: null, result: null, documents: null, ...over }) as Parameters<typeof runHeadline>[0];
  assert.equal(runHeadline(job({ state: "queued", message: "queued; 3 ahead" })), "Queued (3 ahead)");
  assert.equal(runHeadline(job({ state: "queued", message: "queued" })), "Queued");
  assert.equal(runHeadline(job({ stage: "our engine" })), "Solving");
  assert.equal(runHeadline(job({ stage: "the package" })), "Writing the report");
  assert.equal(runHeadline(job({ state: "done" })), "Done");
  const stopped = runProblem(job({ state: "stopped", stage: "CalculiX", message: "stopped at CalculiX: ccx_dynamic.exe exited with code 201: *ERROR in e_c3d" }))!;
  assert.equal(stopped, "The analysis stopped while solving. Run it again; if it stops again, contact us.");
  assert.deepEqual(bannedIn(stopped), []);
  assert.equal(runProblem(job({ state: "refused", message: "the layup is not symmetric" })), "The analysis did not start: the layup is not symmetric. Check the setup and run it again.");
  assert.equal(runProblem(job({ state: "refused", message: "run_coupon.py: CalculiX not found" })), "The analysis did not start. Check the setup and run it again.");
  assert.equal(runProblem(job({ state: "running" })), null);
});

test("the verification line comes from the summary when it is there, else from the result line", () => {
  assert.equal(verificationLine(null, { agree: "71 of 73", tolerance: 0.03 }), "Verified against reference solver: 71 of 73 values within 3 %");
  assert.equal(verificationLine("57 of 57 recorded values agree with CalculiX; our reaction +0.31 % from CalculiX's"),
    "Verified against reference solver: 57 of 57 values agree");
  assert.equal(verificationLine(null), null);
  assert.equal(verificationLine("the package not written"), null);
});

test("a downloaded file is named by the standard and the layup, never by an internal code", () => {
  const coupon = { standard: "ASTM D3039/D3039M-17", test: "unnotched tension", layup: "[0/90]2s" };
  assert.equal(downloadName("document", coupon), "D3039_[0-90]2s_report.pdf");
  assert.equal(downloadName("package", { ...coupon, layup: "[45/0/-45/90]s" }), "D3039_[45-0--45-90]s_package.zip");
  assert.equal(downloadName("abaqus_deck", { ...coupon, layup: "[±45]2s" }), "D3039_[+-45]2s_solver.inp");
  assert.equal(downloadName("prepomax_results", { standard: null, test: "unnotched tension", layup: "[0]8" }), "UnnotchedTension_[0]8_reference.frd");
  assert.equal(downloadName("prepomax_deck", {}), "Coupon_reference.inp");
  for (const [key] of DOWNLOAD_LABELS) assert.match(downloadName(key, coupon), /^[A-Za-z0-9_.,()[\]+-]+$/, key); // what the API accepts
  for (const [, label] of DOWNLOAD_LABELS) assert.deepEqual(bannedIn(label), [], label);
});

test("the guard keeps the product's words and drops tools, files, paths and exit codes", () => {
  for (const text of ["Anthropic", "written by claude-opus-5-5", "Our Abaqus deck", "PrePoMax opens it", "the CalculiX record", "tools/abaqus_beside.py",
    "IM7-UNT-L1-calculix.toml", "(the founder, 2026-11-08)", "The package for the team", "waiting for a free solver", "our engine's fields", "ADR-0066",
    "NEXT_PUBLIC_ANISOTROPY_API_URL"]) {
    assert.notDeepEqual(bannedIn(text), [], text);
    assert.equal(customerText(text), null, text);
  }
  assert.equal(customerText("C:\\Tools\\solver.exe was found"), null);
  assert.equal(customerText("the tool exited with code 1"), null);
  assert.equal(customerText("Length (mm): required"), "Length (mm): required");
  assert.equal(checkText({ state: "pass", message: "CalculiX 2.22 at C:\\Tools\\PrePoMax v2.6.0\\Solver\\ccx_dynamic.exe: the reference solver that checks our engine's result" }), "Ready.");
  assert.equal(checkText({ state: "fail", message: "CalculiX not found: set ANISOTROPY_CCX" }), "Not available right now. Try again later, or contact us.");
  assert.equal(checkText({ state: "pass", message: "version 2.22, ready" }), "version 2.22, ready");
});

test("an explanation sentence loses another viewer's aside, and the ASCII names become symbols", () => {
  const sentence = "In the gauge section, the largest tension along the fibres (sigma_1) is 1203 MPa in ply 2; these are element centroids in the ply's axes, not the global-axis values a viewer such as PrePoMax shows.";
  assert.equal(shownSentence(sentence), "In the gauge section, the largest tension along the fibres (σ₁) is 1203 MPa in ply 2.");
  assert.equal(shownSentence("Reference solver installed: CalculiX 2.22 at C:\\Tools\\ccx.exe."), null);
  assert.equal(withSymbols("eps_x = 1719 microstrain, gamma_xy = 0, nu_xy = 0.31, sigma2 reaches F2t, tau12 = 3"), "εx = 1719 microstrain, γxy = 0, νxy = 0.31, σ₂ reaches F2t, τ₁₂ = 3");
  for (const name of ["explanation"]) {
    for (const dir of ["studio", "studio-standards", "studio-bending", "studio-plate"]) {
      for (const s of fixture(name, dir).sentences as string[]) {
        const shown = shownSentence(s);
        if (shown !== null) assert.deepEqual(bannedIn(shown), [], shown);
      }
    }
  }
});
