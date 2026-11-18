import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  bannedIn, checkText, CUSTOMER_DOWNLOADS, customerText, downloadable, downloadName, DOWNLOAD_LABELS, downloadsFor, FILE_URL_KEY, heldWords, loadWords, queueAhead, rowProblems,
  RUN_STEPS, runDetail, runHeadline, runProblem, runStatus, runSteps, runTook, secondsText, setWords, shownSentence, stepSeconds, verificationOf, withSymbols,
} from "../lib/studio-copy";

const fixture = (name: string, dir = "studio") => JSON.parse(readFileSync(`tests/fixtures/${dir}/${name}.json`, "utf8"));

test("the pipeline's stages fold into five steps, and a job's state says which is current (ADR-0091)", () => {
  assert.deepEqual(RUN_STEPS.map((s) => s.label), ["Queued", "Meshing", "Solving", "Post-processing", "Report ready"]);
  const states = (job: { state: string; stage: string | null; documents?: string | null }) =>
    runSteps(job as Parameters<typeof runSteps>[0]).map((s) => s.state).join(" ");
  assert.equal(states({ state: "queued", stage: null }), "current waiting waiting waiting waiting");
  assert.equal(states(fixture("job-running")), "done done current waiting waiting"); // "our engine": solving
  assert.equal(states({ state: "running", stage: "the CalculiX record" }), "done done done current waiting");
  assert.equal(states({ state: "running", stage: "the drawings" }), "done done done done current"); // after the result: the report's (ADR-0064 am. 1)
  assert.equal(states(fixture("job-result-in")), "done done done done current"); // "the package": the report is being written
  assert.equal(states(fixture("job-done")), "done done done done done");
  assert.equal(states({ state: "done", stage: "the outputs", documents: "the package not written (Tectonic stopped)" }), "done done done done stopped");
  assert.equal(states({ state: "stopped", stage: "CalculiX" }), "done done stopped waiting waiting");
  assert.equal(states({ state: "running", stage: "a stage added later" }), "done done current waiting waiting"); // unknown: solving
  assert.equal(states({ state: "stopped", stage: null }), "stopped waiting waiting waiting waiting"); // never taken up: it ended in the queue
  const stored = (outputs: Record<string, string>) => runSteps({ state: "done", stage: "the outputs", documents: null, outputs }).map((s) => s.state).join(" ");
  assert.equal(stored({ fields: "f" }), "done done done done stopped"); // read back from its row with no package stored: no report
  assert.equal(stored({ fields: "f", package: "p" }), "done done done done stopped"); // a package without its PDF is no report (ADR-0064 am. 2)
  assert.equal(stored({ fields: "f", package: "p", document: "d" }), "done done done done done");
  const missing = { state: "done", stage: "the outputs", documents: "the package was written without its document", outputs: { package: "p" } };
  assert.equal(runSteps(missing as Parameters<typeof runSteps>[0]).map((s) => s.state).join(" "), "done done done done stopped"); // the hosted row's word
});

test("each step shows the seconds it took, and a done run how long it took in all (ADR-0064 amendment 1)", () => {
  // the hosted run of 2026-11-14 (job dfbb2082): its row's timings and times
  const job = {
    state: "done" as const, started_at: "2026-11-14T17:36:48.133+00:00", claimed_at: "2026-11-14T17:36:58.333+00:00", finished_at: "2026-11-14T17:38:33.706+00:00",
    timings: { gate_s: 2.5, CalculiX: 5.6, upload_s: 9.7, restore_s: 14.1, "the decks": 0.5, "the input": 2.3, "our engine": 3.4, "the result": 0.3,
      lock_wait_s: 0.3, "the attempt": 0, "the outputs": 0.2, "the package": 35.2, "the drawings": 6, "the setup check": 1.1, "the CalculiX record": 4.7,
      "the convergence study": 7.2 },
  };
  const seconds = stepSeconds(job);
  const near = (a: number | undefined, b: number) => assert.ok(a !== undefined && Math.abs(a - b) < 1e-9, `${a} is not ${b}`);
  near(seconds.queued, 10.2); // filed to taken up
  near(seconds.meshing, 14.1 + 1.1 + 2.3 + 0.5 + 0); // the coupons fetched, then the tool's first stages; the lock and gate waits are inside them
  near(seconds.solving, 3.4 + 7.2 + 5.6);
  near(seconds.post, 4.7 + 0.3);
  near(seconds.report, 6 + 35.2 + 0.2 + 9.7); // the drawings, the package, the outputs and the upload
  assert.deepEqual(Object.keys(stepSeconds({ started_at: job.started_at, claimed_at: null, timings: { "our engine": 1.2, some_phase_s: 3 } })), ["solving"]); // local: no queue
  assert.deepEqual(stepSeconds({ started_at: job.started_at, claimed_at: null }), {});
  assert.equal(secondsText(4.23), "4.2 s");
  assert.equal(secondsText(0.04), "0 s");
  assert.equal(secondsText(16.24), "16 s");
  assert.equal(secondsText(105.4), "105 s");
  assert.equal(runTook(job), "Finished in 106 s."); // 105.6 s from the click to the last file
  assert.equal(runTook({ ...job, state: "running", finished_at: null }), null);
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
  assert.equal(runProblem(job({ state: "stopped", stage: null, message: "the solver could not run the job: gone" })),
    "The analysis stopped before it started. Run it again; if it stops again, contact us.");
  assert.equal(runHeadline({ ...job({ state: "done" }), outputs: { fields: "f" } }), "Done, report not written");
  assert.equal(runStatus(job({ state: "done", documents: "written" }), "Files"), "Done. Download the report and files under Files."); // no position words (fea-run-50)
  assert.equal(runDetail(job({ state: "queued", message: "queued; 1 ahead" })), "Waiting for the run ahead."); // not "when a solver is free" (fea-run-14)
  assert.equal(runDetail(job({ state: "queued", message: "queued; 3 ahead" })), "Waiting for the 3 runs ahead.");
  assert.equal(runDetail(job({ state: "queued", message: "queued" })), "The analysis starts in a moment.");
  assert.equal(runStatus(job({ state: "queued", message: "queued; 2 ahead" }), "Files"), "Queued (2 ahead).");
  assert.equal(runStatus(job({ stage: "our engine" }), "Outputs"), "Solving…");
});

test("the verification line says verified only when every value agrees, from the summary when it is there, else the result line", () => {
  assert.deepEqual(verificationOf(null, { agree: "73 of 73", tolerance: 0.03 }), { line: "Verified against reference solver: 73 of 73 values within 3 %", verified: true });
  assert.deepEqual(verificationOf("57 of 57 recorded values agree with CalculiX; our reaction +0.31 % from CalculiX's"),
    { line: "Verified against reference solver: 57 of 57 values agree", verified: true });
  // some values outside the tolerance: the line says how many, and is not a pass
  assert.deepEqual(verificationOf(null, { agree: "71 of 73", tolerance: 0.03 }), { line: "Reference solver check: 71 of 73 values within 3 %", verified: false });
  assert.deepEqual(verificationOf("52 of 57 recorded values agree with CalculiX"), { line: "Reference solver check: 52 of 57 values agree", verified: false });
  assert.equal(verificationOf(null), null);
  // the product's view: whether a second solver agrees, without the counts a customer is not asked to judge (ADR-0111 amendment 2)
  assert.deepEqual(verificationOf(null, { agree: "73 of 73", tolerance: 0.03 }, true), { line: "Checked by a second solver", verified: true });
  assert.deepEqual(verificationOf("52 of 57 recorded values agree with CalculiX", null, true),
    { line: "A second solver differs on some values: treat this result with care", verified: false });
  assert.equal(verificationOf("the package not written"), null);
});

test("files are offered once the run has ended, never while they are still being written (ADR-0064 amendment 2)", () => {
  const outputs = { document: "d", abaqus_deck: "a", prepomax_deck: "p", package: "z" };
  assert.deepEqual(downloadable({ state: "running", outputs }, true), []);
  assert.deepEqual(downloadable({ state: "queued", outputs }, false), []);
  assert.deepEqual(downloadable({ state: "done", outputs }, false).map(([key]) => key), ["document", "abaqus_deck"]);
  assert.deepEqual(downloadable({ state: "stopped", outputs: { prepomax_deck: "p" } }, true).map(([key]) => key), ["prepomax_deck"]); // a stopped run's deck
  assert.deepEqual(downloadable(null, true), []);
});

test("a downloaded file is named by the standard and the layup, never by an internal code", () => {
  const coupon = { standard: "ASTM D3039/D3039M-17", test: "unnotched tension", layup: "[0/90]2s" };
  assert.equal(downloadName("document", coupon), "D3039_[0,90]2s_report.pdf");
  assert.equal(downloadName("package", { ...coupon, layup: "[45/0/-45/90]s" }), "D3039_[45,0,-45,90]s_package.zip"); // commas: no double hyphen (fea-run-39)
  assert.equal(downloadName("abaqus_deck", { ...coupon, layup: "[±45]2s" }), "D3039_[+-45]2s_solver.inp");
  assert.equal(downloadName("prepomax_results", { standard: null, test: "unnotched tension", layup: "[0]8" }), "UnnotchedTension_[0]8_reference.frd");
  assert.equal(downloadName("prepomax_deck", {}), "Coupon_reference.inp");
  for (const [key] of DOWNLOAD_LABELS) assert.match(downloadName(key, coupon), /^[A-Za-z0-9_.,()[\]+-]+$/, key); // what the API accepts
  for (const [, label] of DOWNLOAD_LABELS) assert.deepEqual(bannedIn(label), [], label);
  // decision D4: a customer gets the report and the solver input, asked for by neutral names; the team's files with the switch on
  assert.deepEqual(downloadsFor(false).map(([key]) => key), ["document", "abaqus_deck"]);
  assert.deepEqual(CUSTOMER_DOWNLOADS, ["document", "abaqus_deck"]);
  assert.deepEqual(downloadsFor(true), DOWNLOAD_LABELS);
  for (const key of Object.values(FILE_URL_KEY)) assert.deepEqual(bannedIn(key.replace(/_/g, " ")), [], key);
  assert.deepEqual(FILE_URL_KEY, { abaqus_deck: "solver_input", prepomax_deck: "reference_input", prepomax_results: "reference_results" });
});

test("the guard keeps the product's words and drops tools, files, paths and exit codes", () => {
  for (const text of ["Anthropic", "written by claude-opus-5-5", "Our Abaqus deck", "PrePoMax opens it", "the CalculiX record", "tools/abaqus_beside.py",
    "IM7-UNT-L1-calculix.toml", "(the founder, 2026-11-08)", "The package for the team", "waiting for a free solver", "our engine's fields", "ADR-0066",
    "NEXT_PUBLIC_ANISOTROPY_API_URL", "The analysis starts when a solver is free.", "every job that ended has its receipt in GET /v1/runs",
    "not in this API process", "the Worker has no queue", "not in the jobs table", "run records are off", "The run records database did not answer",
    "held: Grip-Bottom", "Every one of our decks"]) {
    assert.notDeepEqual(bannedIn(text), [], text);
    assert.equal(customerText(text), null, text);
  }
  assert.equal(customerText("C:\\Tools\\solver.exe was found"), null);
  assert.equal(customerText("the tool exited with code 1"), null);
  assert.equal(customerText("Length (mm): required"), "Length (mm): required");
  assert.equal(checkText({ state: "pass", message: "CalculiX 2.22 at C:\\Tools\\PrePoMax v2.6.0\\Solver\\ccx_dynamic.exe: the reference solver that checks our engine's result" }), "Ready.");
  assert.equal(checkText({ state: "fail", message: "CalculiX not found: set ANISOTROPY_CCX" }), "Not available right now. Try again later, or contact us.");
  assert.equal(checkText({ state: "pass", message: "version 2.22, ready" }), "version 2.22, ready");
  // an item the engineer can act on keeps saying so when its own words cannot be shown, and names its inputs (audit repository-2)
  assert.equal(checkText({ state: "missing", message: "Your Abaqus mesh: give all three rows", rows: ["Element size (mm)"] }), "Inputs to fill in: Element size (mm).");
  assert.equal(checkText({ state: "fail", message: "the CalculiX twin cannot be written", rows: ["Element size (mm)", "Element size (mm)"] }), "Inputs to change: Element size (mm).");
  assert.equal(checkText({ state: "fail", message: "the CalculiX twin cannot be written", rows: ["Your Abaqus mesh: rows per segment"] }), "Change the inputs listed.");
  // a folder path is a path too; a layup and a material are not (audit fea-run-7)
  assert.equal(customerText("the checks of fea/checks/unnotched-im7-8552/ pass"), null);
  assert.equal(customerText("8 plies [45/0/-45/90]s, 1.463 mm thick"), "8 plies [45/0/-45/90]s, 1.463 mm thick");
  assert.equal(customerText("IM7/8552 and AS4/3501-6"), "IM7/8552 and AS4/3501-6");
  assert.equal(checkText({ state: "pending", message: "CalculiX runs after the check" }), "Not checked yet.");
  assert.deepEqual(bannedIn("its SPOOLES solver stopped"), ["SPOOLES"]);
  // the laminate's machinery words (audit, laminate-2): the engine, the decks, the case runner; an engineer is not an engine
  for (const text of ["the engine converts, never this page", "the units the coupon decks use", "the engine's case runner lists both", "Engine 0.1.0"]) {
    assert.notDeepEqual(bannedIn(text), [], text);
  }
  assert.deepEqual(bannedIn("Run by A. Engineer, engineering shear strain"), []);
});

test("an explanation sentence loses another viewer's aside, and the ASCII names become symbols", () => {
  const sentence = "In the gauge section, the largest tension along the fibres (sigma_1) is 1203 MPa in ply 2; these are element centroids in the ply's axes, not the global-axis values a viewer such as PrePoMax shows.";
  assert.equal(shownSentence(sentence), "In the gauge section, the largest tension along the fibres (σ₁) is 1203 MPa in ply 2.");
  assert.equal(shownSentence("Reference solver installed: CalculiX 2.22 at C:\\Tools\\ccx.exe."), null);
  assert.equal(withSymbols("eps_x = 1719 microstrain, gamma_xy = 0, nu_xy = 0.31, sigma2 reaches F2t, tau12 = 3"), "εx = 1719 microstrain, γxy = 0, νxy = 0.31, σ₂ reaches F2t, τ₁₂ = 3");
  assert.equal(withSymbols("E1 147 GPa, E2 10300 MPa, G12 7 GPa, nu12 0.27, F1t 2280 MPa"), "E₁ 147 GPa, E₂ 10300 MPa, G₁₂ 7 GPa, ν₁₂ 0.27, F1t 2280 MPa");
  // the numbers read as the page prints them (ADR-0091 amendment 1): plain below a million, the minus sign, the layup as written
  assert.equal(shownSentence("Under Nx = 1e+05 N/m the mid-plane strain is eps_x = 1719 microstrain, eps_y = -497 microstrain."),
    "Under Nx = 100000 N/m the mid-plane strain is εx = 1719 microstrain, εy = −497 microstrain.");
  // a coupon job solved before the rule: its sentence quotes the grip's force as the Summary beside it prints it
  const grip = (fixture("explanation").sentences as string[]).find((s) => s.includes("grip carries"))!;
  assert.match(grip, /1\.622e\+04 N/);
  assert.match(shownSentence(grip)!, /grip carries 16220 N/);
  assert.equal(shownSentence("The stack [0/45/-45/90/90/-45/45/0] of 8 plies is 1 mm thick."), "The stack [0/45/-45/90/90/-45/45/0] of 8 plies is 1 mm thick.");
  // an older job's sentence opens on the coupon's record name: the page drops it and opens on the test (audit fea-run-8)
  assert.match(shownSentence(grip)!, /^Unnotched tension, under a displacement of 1 mm along the coupon: the top grip carries 16220 N/);
  assert.equal(shownSentence("X840PW-OHT-L12, open-hole tension, under a force."), "Open-hole tension, under a force.");
  for (const name of ["explanation"]) {
    for (const dir of ["studio", "studio-standards", "studio-bending", "studio-plate"]) {
      for (const s of fixture(name, dir).sentences as string[]) {
        const shown = shownSentence(s);
        if (shown !== null) assert.deepEqual(bannedIn(shown), [], shown);
      }
    }
  }
});

test("every sentence of a laminate answer is shown, with no machinery word and no e-notation (laminate-2, laminate-6)", () => {
  for (const name of ["laminate-answer", "laminate-answer-us"]) {
    for (const s of fixture(name).prose as string[]) {
      const shown = shownSentence(s);
      assert.notEqual(shown, null, s);
      assert.deepEqual(bannedIn(shown!), [], shown!);
      assert.doesNotMatch(shown!, /\de[-+]\d/, shown!);
    }
  }
});

test("each field shows its own problem, in words fit to show (audit fea-run-49)", () => {
  const item = { message: "Length (mm): required; Width (mm): 'wide' is not a number; Element size: must be above 0 (here: 0); Your Abaqus mesh: give all three rows",
    rows: ["Length (mm)", "Width (mm)", "Element size (mm)", "Tab length (mm)"] };
  assert.deepEqual(rowProblems(item), {
    "Length (mm)": "Required.", "Width (mm)": "'wide' is not a number.", "Element size (mm)": "Must be above 0 (here: 0).", "Tab length (mm)": "Check this value.",
  });
  const listed = { message: "Narrow width (mm), Fillet radius (mm): required for a dog-bone", rows: ["Narrow width (mm)", "Fillet radius (mm)"] };
  assert.deepEqual(rowProblems(listed), { "Narrow width (mm)": "Required for a dog-bone.", "Fillet radius (mm)": "Required for a dog-bone." });
  const continued = { message: "Test: required; one of unnotched tension, plate", rows: ["Test"] };
  assert.deepEqual(rowProblems(continued), { Test: "Required; one of unnotched tension, plate." });
  assert.deepEqual(rowProblems({ message: "Element size (mm): the CalculiX twin cannot be written", rows: ["Element size (mm)"] }), { "Element size (mm)": "Check this value." });
  // a group's refusal is every one of its rows' problem; one field's problem is not another field's
  const strengths = { message: "Own material strengths: enter all five, or none; F1t, F1c, F2t, F2c given",
    rows: ["Own material strengths", "Own material: F1t (MPa)", "Own material: F6 (MPa)"] };
  assert.equal(rowProblems(strengths, (label) => label.startsWith("Own material: "))["Own material: F6 (MPa)"], "Enter all five, or none; F1t, F1c, F2t, F2c given.");
  assert.equal(rowProblems({ message: "Length (mm): required", rows: ["Length (mm)", "Width (mm)"] })["Width (mm)"], "Check this value.");
});

test("what is held and loaded reads in words, one line per set (audit fea-run-16)", () => {
  const preview = fixture("preview");
  assert.equal(setWords("Grip-Bottom"), "bottom grip");
  assert.equal(setWords("Pin-Left"), "left pin");
  assert.deepEqual(bannedIn("Abaqus input file (.inp)"), []); // the one phrase that may name it (D18)
  assert.deepEqual(bannedIn("Open it in Abaqus"), ["Abaqus"]);
  assert.equal(setWords("the top grip"), "the top grip");
  assert.equal(setWords("Edge-Left"), "Edge-Left"); // a plate's own region, as named
  const top = preview.held.filter((h: { set: string }) => h.set === "Grip-Top");
  assert.equal(heldWords("Grip-Bottom", [1, 2, 3, 4, 5, 6], []), "Bottom grip: fixed (encastre)");
  // Abaqus's names for a set of held directions, beside the directions (ADR-0110)
  assert.equal(heldWords("Edge-Left", [1, 2, 3], ["x", "y", "z"]), "Edge-Left: held along x, y, z (pinned)");
  assert.equal(heldWords("Edge-Left", [1, 5, 6], ["x", "tilt about y", "rotation about z"]), "Edge-Left: held along x, tilt about y, rotation about z (XSYMM)");
  assert.equal(heldWords("Edge-Bottom", [2, 4, 6], ["y", "tilt about x", "rotation about z"]), "Edge-Bottom: held along y, tilt about x, rotation about z (YSYMM)");
  assert.equal(heldWords("Grip-Top", top.flatMap((h: { dofs: number[] }) => h.dofs), top.flatMap((h: { directions: string[] }) => h.directions)),
    "Top grip: free to move along the coupon only");
  assert.equal(heldWords("Support-Left", [3], ["z"]), "Left support: held along z");
  assert.equal(loadWords(preview.loaded), "Top grip: pulled 1 mm along the coupon");
  assert.equal(loadWords({ ...preview.loaded, control: "force", value: 10000, unit: "N" }), "Top grip: pulled by 10000 N along the coupon");
  for (const words of [heldWords("Grip-Top", [1], ["x"]), loadWords(preview.loaded)]) assert.deepEqual(bannedIn(words), [], words);
});
