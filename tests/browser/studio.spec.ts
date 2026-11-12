import { test, expect, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";
import { printed } from "../../lib/studio-colors";
import { bannedIn } from "../../lib/studio-copy";

const fixture = (name: string, dir = "studio") => JSON.parse(readFileSync(`tests/fixtures/${dir}/${name}.json`, "utf8"));
const BENDING = "three-point bending";
const API = /https?:\/\/[^/]+\/v1\//;
/** The first step's answers (ADR-0062 amendment 1): a test, then a standard, each a choice on the Test and standard panel. */
const pickTest = (page: Page, test: string) => page.getByTestId("question-test").locator(`input[value="${test}"]`).check();
const pickStandard = (page: Page, designation: string) => page.getByTestId("question-standard").locator(`input[value="${designation}"]`).check();
const standardChoice = (page: Page, designation: string) => page.getByTestId("question-standard").locator(`input[value="${designation}"]`);

// THROTTLE=4 npm run test:studio slows the browser's CPU fourfold, to find on this machine the timing a slower CI runner meets
test.beforeEach(async ({ page }) => {
  if (!process.env.THROTTLE) return;
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: Number(process.env.THROTTLE) });
});

/** What the package chooses for IM7/8552 [45/0/-45/90]s on the tension screen (anisotropy_fea.tension_input), as the check lists it. */
const TENSION_BUILT = [
  { row: "width", value: 25, reason: "ASTM D3039/D3039M-17, Table 2, balanced and symmetric" },
  { row: "length", value: 250, reason: "ASTM D3039/D3039M-17, Table 2, balanced and symmetric" },
  { row: "tab_length", value: 56, reason: "ASTM D3039/D3039M-17, Table 2, balanced and symmetric grips through emery cloth and sets no grip length: 56 mm by default" },
  { row: "strain_length", value: 25, reason: "25 mm, within ASTM D3039/D3039M-17 §7.3.2's 10 to 50 mm, centred on the coupon" },
  { row: "value", value: 1, reason: "1 mm: the model is linear, so the answer, the loading at first-ply failure, does not depend on it" },
];

/** The API, played from the public fixtures: the check, the solve, a job that runs then ends, its files, and the coupons. */
async function mockApi(page: Page, calls: { checks: unknown[]; solves: unknown[]; fieldsReads?: number; tows?: unknown[]; lives?: unknown[] },
  options: { missFirstFieldsRead?: boolean; live?: boolean; allTests?: boolean; writer?: "template" | "model"; jobs?: (poll: number) => unknown } = {}) {
  let polls = 0;
  calls.fieldsReads = 0;
  let dir = "studio"; // the public tension coupon, or the public bending coupon once a check asks for it
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route(API, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    // one workflow first (ADR-0089): the API says whether every test is offered. The scenarios below test the full panels, development's
    // view, so the switch is on unless a scenario turns it off for the tension screen (ADR-0090), the product's view
    if (path === "/v1/coupon-tests" && request.method() === "GET") return json(route, { all: options.allTests ?? true });
    if (path === "/v1/workspace/assistant" && options.writer === "model") return json(route, { proposes: false, provider: "anthropic", model: "claude-opus-5-5" });
    if (path === "/v1/coupons" && request.method() === "GET") return json(route, fixture("coupons"));
    if (path.startsWith("/v1/projects")) return json(route, { detail: "Run records are switched off (ANISOTROPY_RUN_RECORDS=off); there is nothing to read" }, 503); // no project store: the browser keeps the project alone
    if (path === "/v1/coupons/IM7-UNT-L1/values") return json(route, { name: "IM7-UNT-L1", values: fixture("values") });
    if (path === "/v1/tow-tests" && request.method() === "POST") { // a fibre tow record, answered by the package from the public fixture (ADR-0074)
      (calls.tows ??= []).push(request.postDataJSON());
      const answer = fixture("tow", "studio-tow");
      return json(route, { run_id: "run-6", state: answer.checklist.state, checklist: answer.checklist, result: answer.result });
    }
    if (path === "/v1/coupon-jobs/live" && request.method() === "POST") { // our kernel's live answer (ADR-0086), played from the same fixtures
      (calls.lives ??= []).push(request.postDataJSON());
      const values = (request.postDataJSON() as { values: Record<string, unknown> }).values;
      const d = values.test === BENDING ? "studio-bending" : values.test === "plate" ? "studio-plate" : "studio";
      const answer = { run_id: "run-live", state: "ready", designation: fixture("checklist", d).designation, solver: "kernel", warm: true, seconds: 0.6,
        timings: { check: 0.18, solve: 0.01 }, checklist: fixture("checklist", d), preview: fixture("preview", d) };
      // by default it never answers, as a kernel slower than the scenario: the scenarios below keep to the check and the run they test, at
      // any speed (on CI a live answer used to land mid-scenario and take the stage); `live` plays the kernel's answer
      if (!options.live) return;
      return json(route, { ...answer, fields: fixture("fields", d), explanation: fixture("explanation", d) });
    }
    if (path === "/v1/coupon-jobs/check" && request.method() === "POST") {
      calls.checks.push(request.postDataJSON());
      const values = (request.postDataJSON() as { values: Record<string, unknown> }).values;
      if (values.input === "tension") { // the tension screen (ADR-0090): the package chooses the rest and lists its choices, played here
        dir = "studio-standards";
        return json(route, { run_id: "run-7", state: "ready", designation: "IM78552-UNT-L1", checklist: { ...fixture("checklist", "studio-standards"), built: TENSION_BUILT },
          preview: fixture("preview", "studio-standards") });
      }
      dir = values.test === BENDING ? "studio-bending" : values.test === "plate" ? "studio-plate" : "studio";
      if (values.standard === "ASTM D3039/D3039M-17") { // the public coupon under D3039, judged by the package (ADR-0072)
        dir = "studio-standards";
        return json(route, { run_id: "run-5", state: "ready", designation: "IM7-UNT-L1", checklist: fixture("checklist", "studio-standards"),
          preview: fixture("preview", "studio-standards") });
      }
      if (dir === "studio-bending") {
        return json(route, { run_id: "run-3", state: "ready", designation: "IM7-3PB-L1", checklist: fixture("checklist", dir), preview: fixture("preview", dir) });
      }
      if (dir === "studio-plate") {
        return json(route, { run_id: "run-4", state: "ready", designation: "NOM-PLT-L1", checklist: fixture("checklist", dir), preview: fixture("preview", dir) });
      }
      if (!("length" in values)) {
        const checklist = fixture("checklist");
        checklist.state = "blocked";
        checklist.items = checklist.items.map((item: { id: string }) => item.id === "geometry"
          ? { ...item, state: "missing", message: "Length (mm): required", rows: ["Length (mm)"] } : item);
        return json(route, { run_id: null, state: "blocked", designation: null, checklist, preview: null });
      }
      return json(route, { run_id: "run-1", state: "ready", designation: "IM7-UNT-L1", checklist: fixture("checklist"), preview: fixture("preview") });
    }
    if (path === "/v1/coupon-jobs" && request.method() === "POST") {
      calls.solves.push(request.postDataJSON());
      return json(route, fixture("job-running"), 202);
    }
    if (/^\/v1\/coupon-jobs\/[^/]+$/.test(path)) {
      polls += 1;
      if (options.jobs) return json(route, options.jobs(polls));
      return json(route, polls < 2 ? fixture("job-running") : polls < 4 ? fixture("job-engine-done") : polls < 8 ? fixture("job-result-in") : fixture("job-done"));
    }
    if (path.endsWith("/explain") && request.method() === "POST") {
      const explanation = fixture("explanation", dir);
      const model = options.writer === "model"; // a model's rewording, kept by the number guard (ADR-0052): the page never says who wrote it (ADR-0091)
      return json(route, { run_id: "run-2", job_id: path.split("/")[3], kind: (request.postDataJSON() as { kind: string }).kind, writer: model ? "anthropic" : "template",
        model: model ? "claude-opus-5-5" : null,
        prose: explanation.sentences, withheld: false, reason: null, facts: explanation.facts });
    }
    if (path.endsWith("/files/fields")) {
      calls.fieldsReads = (calls.fieldsReads ?? 0) + 1;
      if (options.missFirstFieldsRead && calls.fieldsReads === 1) return json(route, { detail: "the container did not answer" }, 503); // the first read misses, as the hosted Worker did live on 2026-11-07; the page tries again
      return json(route, fixture("fields", dir));
    }
    if (path.endsWith("/files/explanation")) return json(route, fixture("explanation", dir));
    if (path.endsWith("/files/package")) return route.fulfill({ status: 200, contentType: "application/zip", body: "PK" });
    return json(route, { detail: `no stand-in for ${request.method()} ${path}` }, 404);
  });
}

test("the studio checks a setup, solves it, shows the fields as soon as our engine has run, and lists the files", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error" && /THREE|WebGL|shader/i.test(message.text())) browserErrors.push(message.text()); }); // a shader that fails to compile is logged, not thrown
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { missFirstFieldsRead: true }); // the hosted Worker missed one read live on 2026-11-07
  await page.goto("/services/finite-element-modeling");
  await page.getByRole("link", { name: "Open the workspace", exact: true }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("workspace-shell")).toHaveAttribute("data-assistant", "open"); // three columns, the assistant beside the model (ADR-0062)
  await expect(page.getByTestId("empty-scene")).toBeVisible();
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("250");
  await expect(page.getByTestId("sketch")).toContainText("25 × 250 mm, 56 mm tabs"); // the typed rows drawn before any check (ADR-0062)
  await expect(page.getByTestId("panel-geometry")).toHaveAttribute("data-state", "none");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("panel-geometry")).toHaveAttribute("data-state", "pass");
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready");
  await expect(page.getByTestId("checklist").locator("li[data-state=pass]")).toHaveCount(13);
  expect(calls.checks).toHaveLength(1);
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect(sent.length).toBe(250);
  expect(sent.ply_1).toBe(45);
  expect(sent.library).toBe("im7-8552");
  expect(sent.form_version).toBe(fixture("values").form_version);
  await expect(page.getByTestId("preview")).toBeVisible();
  await expect(page.getByTestId("preview")).toContainText("50 elements");
  await expect(page.getByTestId("studio-scene")).toHaveAttribute("data-mode", "presentation"); // the model lit, the results unlit (ADR-0063)
  await page.getByLabel("Run by", { exact: true }).fill("A. Engineer");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("job-progress")).toBeVisible();
  expect((calls.solves[0] as { run_by: string }).run_by).toBe("A. Engineer");
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 30_000 }) // the first results render compiles the shaders, slow on CI's software GL, and the missed read adds a poll interval;
  expect((calls as { fieldsReads?: number }).fieldsReads).toBeGreaterThanOrEqual(2); // the first read of the fields failed and the page read them again
  await expect(page.getByTestId("legend")).toContainText("Failure index 1/R, worst ply");
  await expect(page.getByTestId("studio-scene")).toHaveAttribute("data-mode", "results"); // coloured on the graphics card, unlit (ADR-0063)
  await expect(page.getByTestId("studio-scene")).toHaveAttribute("data-bands", "8");
  await expect(page.getByTestId("legend")).toHaveAttribute("data-source", "package"); // the legend's ends are the package's
  const written = fixture("fields").ranges.failure_index.tsai_hill.nodal as [number, number];
  await expect(page.getByTestId("legend")).toContainText(`${printed(written[0])} to ${printed(written[1])} · 8 bands`);
  await page.getByTestId("studio-scene").locator("canvas").evaluate((canvas) => { canvas.dataset.kept = "yes"; });
  await expect(page.getByTestId("summary-reaction")).toContainText("N (in tension)");
  // the validation table (ADR-0066): laminate theory beside Anisotropy, one row per ply in the fibre axes; the peaks apart, per ply, collapsed
  await expect(page.getByTestId("validation-table")).toContainText("Laminate theory");
  await expect(page.getByTestId("validation-table").locator("tr[data-ply='2']")).toContainText("Ply 2 · 0°");
  await expect(page.getByTestId("peaks")).toContainText("Peak stresses at the grips (not converged)");
  await expect(page.getByTestId("peaks-table").locator("tr[data-ply='2']")).toContainText("at element 178"); // the 0° ply's largest σ₁, named by its element
  // the mesh convergence study (ADR-0068): the kernel at 1x, 2x and 4x; the reaction settles, the 0° ply's clamped-edge peak keeps growing
  await expect(page.getByTestId("convergence")).toContainText("Mesh convergence");
  await expect(page.getByTestId("convergence-table")).toContainText("4,000 elements");
  await expect(page.getByTestId("convergence-table").locator("tr[data-row='reaction']")).toContainText("−0.024 %, settled");
  await expect(page.getByTestId("convergence-table").locator("tr[data-row='peak'][data-ply='2']")).toContainText("+11.4 %, still moving");
  await expect(page.getByTestId("convergence-words")).toContainText("The reaction, the gauge strain and the gauge ply stresses changed by less than 1 %");
  await expect(page.getByTestId("convergence-words")).toContainText("The grip peaks, the whole-model R and the gauge-section R keep changing");
  await expect(page.getByTestId("fpf-factor-tsai_hill")).toHaveText("1.013");
  await expect(page.getByTestId("fpf-gauge-factor-tsai_hill")).toHaveText("1.032");  // the gauge section's own first-ply failure, away from the clamped edge
  await expect(page.getByTestId("explanation")).toContainText("By the Tsai-Hill criterion the laminate holds at the applied loading, in the gauge section");
  await expect(page.getByTestId("explanation")).toContainText("Outside the gauge section, Tsai-Hill is reached earlier, at 1.013 times the applied loading"); // the clamped edge apart (ADR-0085)
  // the answer card (ADR-0085): fails or holds per criterion in the gauge section, the loading at first-ply failure, the clamped edge apart
  const answer = page.getByTestId("answer");
  await expect(answer).toHaveAttribute("data-basis", "gauge");
  await expect(answer).toHaveAttribute("data-fails", "false");
  await expect(page.getByTestId("answer-headline")).toContainText("Holds at the applied loading (Tsai-Hill).");
  await expect(page.getByTestId("answer-headline")).toContainText("The first ply would fail at 1.032 × the applied loading (1.032 mm,");
  await expect(page.getByTestId("answer-verdict-tsai_hill")).toHaveText("holds");
  await expect(page.getByTestId("answer-factor-tsai_hill")).toHaveText("1.032");
  await expect(page.getByTestId("answer-loading-tsai_hill")).toContainText("1.032 mm");
  await expect(page.getByTestId("answer-outside")).toContainText("At a grip edge, Tsai-Hill is reached earlier, at 1.013 × the applied loading");
  await expect(page.getByTestId("answer-extremes").locator("tbody tr")).toHaveCount(5);
  await expect(page.getByTestId("fpf-details")).not.toHaveAttribute("open", ""); // the per-criterion tables of the whole model fold away under the answer
  await expect(page.getByTestId("explanation")).toHaveAttribute("data-writer", "template", { timeout: 15_000 }); // the API answered the explain call
  // the result before the documents (ADR-0064): the agreement line while the job still draws and builds the package
  await expect(page.getByTestId("job-progress")).toContainText("Results are ready. The report follows.", { timeout: 15_000 });
  await expect(page.getByTestId("job-message")).toContainText("Verified against reference solver: 57 of 57 values agree");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
  await expect(page.getByTestId("job-message")).toContainText("Verified against reference solver: 57 of 57 values agree");
  await expect(page.getByTestId("job-progress").locator("li[data-state=done]")).toHaveCount(5); // the five steps of a finished job (ADR-0091)
  const outputs = page.getByTestId("panel-outputs"); // the files in the left column, named by the standard and the layup (ADR-0091)
  await expect(outputs.locator("a[data-key=package]")).toHaveAttribute("href", /\/v1\/coupon-jobs\/0f3a2c9e[^/]*\/files\/package\?name=UnnotchedTension_%5B45-0--45-90%5Ds_package\.zip$/);
  await expect(outputs.locator("a[data-key=package]")).toHaveAttribute("download", "UnnotchedTension_[45-0--45-90]s_package.zip");
  await expect(outputs.locator("a[data-key=prepomax_results]")).toHaveText("Reference solver results (.frd)");
  await expect(page.getByTestId("downloads")).toHaveCount(0); // not twice: the centre leaves the files to the left column
  await expect(page.getByTestId("viewer-link")).toHaveAttribute("href", "/workspace/fea/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await page.getByLabel("Field", { exact: true }).selectOption("S22");
  await page.getByLabel("Ply", { exact: true }).selectOption("3");
  await expect(page.getByTestId("legend")).toContainText("Ply stress σ₂ (ply 3, -45°)");
  await page.getByLabel("Shown as", { exact: true }).selectOption("element");
  await expect(page.getByTestId("legend")).toContainText("element values");
  await expect(page.getByTestId("studio-scene").locator("canvas")).toHaveAttribute("data-kept", "yes"); // the field switch uploads values; the mesh and the canvas stay
  const perPly = fixture("fields").ranges.S22.element[2] as [number, number];
  await expect(page.getByTestId("legend")).toContainText(`${printed(perPly[0])} to ${printed(perPly[1])} MPa`);
  await page.getByLabel("Contours", { exact: true }).selectOption("0");
  await expect(page.getByTestId("legend")).toHaveAttribute("data-bands", "0");
  await expect(page.getByTestId("studio-scene")).toHaveAttribute("data-bands", "0");
  await page.getByLabel("Contours", { exact: true }).selectOption("8");
  await page.getByTestId("answer-table").locator("tr[data-criterion=tsai_hill] button").click(); // the answer's own row, in the gauge section (ADR-0085)
  await expect(page.getByTestId("readout")).toContainText("critical");
  await expect(page.getByTestId("readout")).toContainText("Tsai-Hill: ply");
  // every ply of the picked element (ADR-0066 amendment 2): its number, each ply's stresses and invariants
  const probe = page.getByTestId("probe");
  await expect(probe).toContainText("Ply results at element");
  await expect(probe.getByTestId("probe-table").locator("tbody tr")).toHaveCount(8);
  await expect(probe.getByTestId("probe-table").locator("thead")).toContainText("Tresca");
  await expect(probe).toContainText("S13 and S23 are not modelled (membrane state)");
  await expect(probe.getByTestId("probe-csv")).toHaveAttribute("download", /^probe-element-\d+\.csv$/);
  await page.getByLabel("Field", { exact: true }).selectOption("tresca");
  await expect(page.getByLabel("Shown as", { exact: true })).toHaveCount(0); // element values only: no display averages for an invariant
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-results.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a three-point bending coupon shows its supports, its deflection and the failing face (ADR-0053)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  await pickTest(page, BENDING);
  await expect(page.getByLabel("Support span (mm)", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Tab length (mm)", { exact: true })).toHaveCount(0); // a bending coupon rests on supports
  await expect(page.getByLabel("Grip kind", { exact: true })).toHaveCount(0);
  await page.getByLabel("Length (mm)", { exact: true }).fill("60");
  await page.getByLabel("Width (mm)", { exact: true }).fill("13");
  await page.getByLabel("Support span (mm)", { exact: true }).fill("48");
  await page.getByLabel("Overhang (mm)", { exact: true }).fill("6");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready");
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect(sent.test).toBe(BENDING);
  expect(sent.span).toBe(48);
  expect(sent.tab_length).toBeUndefined(); // the hidden rows are not sent
  expect(sent.grips).toBeUndefined();
  await expect(page.getByTestId("preview")).toContainText("Support-Left");
  await page.getByLabel("Run by", { exact: true }).fill("A. Engineer");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("summary-reaction")).toContainText("pressing the coupon down");
  await expect(page.getByTestId("summary")).toContainText("the deflection w");
  await expect(page.getByTestId("convergence-not-studied")).toContainText("three point bending is a later step");  // ADR-0068: a bending coupon says so
  await expect(page.getByTestId("fpf-table")).toContainText("bottom face");
  await expect(page.getByTestId("answer")).toHaveAttribute("data-basis", "whole"); // no gauge section: the whole model answers (ADR-0085)
  await expect(page.getByTestId("answer-table")).toContainText("bottom face");
  await page.getByLabel("Field", { exact: true }).selectOption("u_z");
  await expect(page.getByTestId("legend")).toContainText("Deflection w (mm)");
  await page.getByLabel("Field", { exact: true }).selectOption("S11");
  await page.getByLabel("Face", { exact: true }).selectOption("1");
  await expect(page.getByTestId("legend")).toContainText("top face");
  await expect(page.getByTestId("explanation")).toContainText("under the loading nose", { timeout: 15_000 });
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-bending.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a plate is stated by its regions: hold an edge, press the face, check and solve (ADR-0054)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  await pickTest(page, "plate");
  await expect(page.getByTestId("plate-panel")).toBeVisible();
  await expect(page.getByLabel("Grip kind", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Loading type", { exact: true })).toHaveCount(0);
  await page.getByLabel("Length (mm)", { exact: true }).fill("100");
  await page.getByLabel("Width (mm)", { exact: true }).fill("100");
  await page.getByLabel("Tab length (mm)", { exact: true }).fill("");
  await page.getByTestId("add-support").click();
  await page.getByLabel("Support 1 region", { exact: true }).selectOption("Edge-Left");
  await page.getByTestId("add-load").click();
  await page.getByLabel("Load 1 pressure", { exact: true }).fill("-0.01");
  await expect(page.getByTestId("plate-words")).toContainText("Edge-Left holds x, y, z");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready");
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect(sent.test).toBe("plate");
  expect(sent.supports).toEqual([{ region: "Edge-Left", dofs: [1, 2, 3] }]);
  expect(sent.loads).toEqual([{ region: "Face", pressure: -0.01 }]);
  expect(sent.control).toBeUndefined();
  expect(sent.grips).toBeUndefined();
  await expect(page.getByTestId("preview")).toContainText("pressure");
  await expect(page.getByTestId("preview")).toContainText("Click an element to hold or load");
  await page.getByLabel("Run by", { exact: true }).fill("A. Engineer");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("summary-reaction")).toContainText("holding the plate down");
  await page.getByLabel("Field", { exact: true }).selectOption("u_z");
  await expect(page.getByTestId("legend")).toContainText("Deflection w (mm)");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-plate.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a blocked setup names its rows and the solve stays off", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByLabel("Length (mm)", { exact: true }).fill("");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "blocked");
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByTestId("checklist").locator("li[data-item=geometry]")).toHaveAttribute("data-state", "missing");
  await expect(page.getByTestId("panel-geometry")).toHaveAttribute("data-state", "missing");
  await expect(page.getByTestId("solve-button")).toBeDisabled();
  expect(calls.solves).toHaveLength(0);
  await page.getByLabel("Length (mm)", { exact: true }).fill("250");
  await expect(page.getByTestId("solve-button")).toBeEnabled(); // inputs changed: the check must run again, and it will before a solve
});

test("a standard is offered by its test, fills its size, and the check judges the specimen clause by clause (ADR-0072)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  const titles = page.getByTestId("question-standard").locator(".ws-choice-title");
  await expect(titles).toHaveText(["ASTM D3039/D3039M-17", "ASTM D638-22", "No standard"]); // C1869 is open-hole tension: not offered here
  await expect(standardChoice(page, "none")).toBeChecked();
  await expect(page.getByTestId("setup-line")).toContainText("Setting up unnotched tension to your own size, under no standard");
  await expect(page.getByTestId("standard-card")).toContainText("No standard picked");
  await pickStandard(page, "ASTM D3039/D3039M-17");
  await expect(page.getByTestId("setup-line")).toContainText("Setting up unnotched tension under ASTM D3039/D3039M-17");
  await expect(page.getByTestId("standard-card")).toContainText("Tensile properties of polymer matrix composites");
  await expect(page.getByTestId("step-standard-geometry")).toContainText("What ASTM D3039/D3039M-17 asks of the geometry");
  await page.getByRole("button", { name: "Use 0° unidirectional" }).click();
  await expect(page.getByLabel("Width (mm)", { exact: true })).toHaveValue("15");
  await expect(page.getByLabel("Tab bevel angle (deg)", { exact: true })).toHaveValue("7");
  await page.getByRole("button", { name: "Use balanced and symmetric" }).click();
  await expect(page.getByLabel("Width (mm)", { exact: true })).toHaveValue("25");
  await expect(page.getByLabel("Tab bevel angle (deg)", { exact: true })).toHaveValue(""); // Table 2 grips this class through emery cloth
  await expect(page.getByLabel("Tab length (mm)", { exact: true })).toHaveValue("56"); // it gives no grip length, so the typed one stays
  await page.getByLabel("Strain measurement", { exact: true }).selectOption("extensometer");
  await page.getByLabel("Strain measurement length (mm)", { exact: true }).fill("25");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist").locator("li[data-item=standard]")).toHaveAttribute("data-state", "pass");
  await expect(page.getByTestId("standard-summary")).toContainText("5 of 5 requirements a model can meet are met");
  await expect(page.getByTestId("standard-card").locator("[data-requirement=t2-thickness]")).toHaveAttribute("data-state", "advisory");
  await expect(page.getByTestId("standard-card").locator("[data-requirement=min-length]")).toContainText("at least 187 mm");
  await expect(page.getByTestId("step-standard-geometry").locator("[data-requirement=min-length]")).toHaveAttribute("data-state", "met"); // judged on its step too
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect([sent.standard, sent.strain_device, sent.strain_length, sent.width]).toEqual(["ASTM D3039/D3039M-17", "extensometer", 25, 25]);
  await pickTest(page, "open-hole tension"); // another test clears a standard that does not cover it
  await expect(standardChoice(page, "none")).toBeChecked();
  await expect(page.getByTestId("status")).toContainText("the Standard row is back to none");
  await expect(titles).toHaveText(["ASTM C1869-18(2023)", "No standard"]);
  await pickStandard(page, "ASTM C1869-18(2023)");
  await expect(page.getByLabel("Specimen", { exact: true }).locator("option")).toHaveText(["(blank)", "A", "B", "other"]);
  await page.getByRole("button", { name: /Use Specimen B/ }).click();
  await expect(page.getByLabel("Specimen", { exact: true })).toHaveValue("B");
  await expect(page.getByLabel("Hole diameter (mm)", { exact: true })).toHaveValue("3");
  await expect(page.getByTestId("sketch")).toContainText("10 × 60 mm, 15 mm tabs, a 3 mm hole");
  await expect(page.getByTestId("sketch")).toContainText("Sized for ASTM C1869-18(2023), Specimen B");
});

test("a plastic dog-bone is sized by D638's Type I and stated by its thickness, E and nu in place of the plies (ADR-0075)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  await pickStandard(page, "ASTM D638-22");
  await expect(page.getByTestId("setup-line")).toContainText("Setting up unnotched tension under ASTM D638-22");
  await page.getByRole("button", { name: /Use Type I: 13 mm wide/ }).click();
  await expect(page.getByLabel("Narrow width (mm)", { exact: true })).toHaveValue("13");
  await expect(page.getByLabel("Fillet radius (mm)", { exact: true })).toHaveValue("76");
  await expect(page.getByLabel("Outer radius (mm)", { exact: true })).toHaveValue(""); // Type I has none
  await expect(page.getByLabel("Width (mm)", { exact: true })).toHaveValue("19");
  await expect(page.getByLabel("Strain measurement", { exact: true })).toHaveValue("extensometer"); // the gage length is an extensometer's
  await expect(page.getByLabel("Specimen", { exact: true })).toHaveValue("I");
  await expect(page.getByTestId("layup-editor")).toBeVisible(); // plies until the material kind says otherwise
  await page.getByLabel("Material kind", { exact: true }).selectOption("isotropic");
  await expect(page.getByTestId("layup-editor")).toHaveCount(0);
  await expect(page.getByTestId("isotropic-hint")).toBeVisible();
  await page.getByLabel("Thickness (mm)", { exact: true }).fill("3.2");
  await page.getByLabel("Own material: E (MPa)", { exact: true }).fill("3000");
  await page.getByLabel("Own material: nu", { exact: true }).fill("0.35");
  await expect(page.getByLabel("G13 (MPa)", { exact: true })).toHaveCount(0); // no ply material for a plastic
  await expect(page.getByTestId("sketch")).toContainText("a dog-bone narrowing to 13 by 57 mm through 76 mm fillets");
  await expect(page.getByTestId("sketch")).toContainText("3.2 mm thick");
  await page.getByTestId("check-button").click();
  await expect.poll(() => calls.checks.length).toBeGreaterThan(0);
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect([sent.standard, sent.specimen, sent.material_kind, sent.thickness, sent.own_E, sent.own_nu, sent.narrow_width, sent.radius])
    .toEqual(["ASTM D638-22", "I", "isotropic", 3.2, 3000, 0.35, 13, 76]);
  expect([sent.ply_1, sent.library, sent.G13, sent.criteria]).toEqual([undefined, undefined, undefined, undefined]); // hidden rows are not sent
});

test("the tension screen takes the material and the layup, builds the model, says how it chose the rest, and lists the files (ADR-0089, ADR-0090)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: false }); // the switch off, as on the hosted tier: the product's view
  await page.goto("/workspace/fea");
  const screen = page.getByTestId("tension-screen");
  await expect(screen).toBeVisible();
  await expect(page.getByTestId("question-test")).toHaveCount(0); // one test: no test to pick, no other standard than D3039 or none
  await expect(screen.locator("input[name=tension-standard]")).toHaveCount(2);
  await expect(page.getByRole("button", { name: "Load example" })).toHaveCount(0);
  await expect(page.getByText(/Abaqus name|Your Abaqus mesh/)).toHaveCount(0); // no Abaqus row on the page
  await expect(page.getByTestId("build-button")).toBeDisabled();
  await expect(page.getByTestId("tension-missing")).toContainText("the material, the layup");

  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("Open-hole tension, 6 mm hole");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByTestId("chat-not-available").last()).toContainText("Open-hole tension is not available yet");

  await page.getByLabel("Material", { exact: true }).selectOption("as4-8552"); // its library record gives no ply thickness: the screen asks
  await expect(page.getByTestId("library-ply-thickness")).toBeVisible();
  await expect(page.getByTestId("tension-missing")).toContainText("Ply thickness (mm)");
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await expect(page.getByTestId("library-ply-thickness")).toHaveCount(0); // IM7/8552's record gives one
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await expect(page.getByTestId("tension-missing")).toHaveCount(0);
  await page.getByTestId("build-button").click();
  await expect.poll(() => calls.solves.length).toBe(1); // ready, so Build goes on to the full analysis
  const sent = (calls.checks.at(-1) as { values: Record<string, unknown> }).values;
  expect(sent.input).toBe("tension");
  expect(sent.library).toBe("im7-8552");
  expect([sent.ply_1, sent.ply_2, sent.ply_3, sent.ply_4, sent.symmetric]).toEqual([45, 0, -45, 90, "yes"]);
  for (const key of ["length", "width", "tab_length", "grips", "element_size", "G13", "G23", "test", "units"]) expect(sent[key], key).toBeUndefined(); // the package chooses them
  const built = page.getByTestId("tension-built");
  await expect(built.locator("tr[data-row=width]")).toContainText("ASTM D3039/D3039M-17, Table 2, balanced and symmetric");
  await expect(built.locator("tr[data-row=tab_length]")).toContainText("56 mm by default");
  await expect(page.getByTestId("tension-files")).toContainText("Solver input (.inp)", { timeout: 20_000 });
  await expect(page.getByTestId("tension-files")).toContainText("Report (PDF)");
  await expect(page.getByTestId("tension-files").locator("a[data-key=document]")).toHaveAttribute("download", "D3039_[45-0--45-90]s_report.pdf");
});

test("a coupon solved under a test standard shows the quantities the standard reduces a test to (ADR-0072)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  await pickStandard(page, "ASTM D3039/D3039M-17");
  await page.getByLabel("Strain measurement", { exact: true }).selectOption("extensometer");
  await page.getByLabel("Strain measurement length (mm)", { exact: true }).fill("25");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready");
  await page.getByLabel("Run by", { exact: true }).fill("A. Engineer");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 30_000 });
  const tm = fixture("fields", "studio-standards").summary.test_method;
  const card = page.getByTestId("test-method");
  await expect(card).toContainText("ASTM D3039/D3039M-17 test quantities");
  await expect(card).toContainText(`${Number(tm.strain.chord.modulus.toPrecision(3))} GPa`); // the package's chord modulus, at three figures
  await expect(card).toContainText(`laminate theory ${Number(tm.laminate_theory.modulus.toPrecision(3))} GPa`);
  await expect(card).toContainText("not ultimate strength");
  await expect(page.getByTestId("explanation")).toContainText("chord modulus between 1000 and 3000 microstrain");
});

test("a fresh form's choices start blank, not on their first word", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await expect(page.getByTestId("question-test").locator("input:checked")).toHaveCount(0); // the first step asks; nothing is picked for the engineer
  await expect(page.getByTestId("setup-line")).toContainText("Start with step 1");
  await expect(page.getByTestId("waiting-geometry")).toBeVisible(); // the steps that depend on the test wait for it
  await expect(page.getByTestId("question-standard")).toHaveCount(0);
  await pickTest(page, "unnotched tension");
  await expect(page.getByTestId("waiting-geometry")).toHaveCount(0);
  for (const label of ["Symmetric", "Loading type"]) await expect(page.getByLabel(label, { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Loading type", { exact: true }).locator("option:checked")).toHaveText("choose one");
  await expect(standardChoice(page, "none")).toBeChecked();
  await pickTest(page, "in-plane shear");
  await expect(page.getByTestId("no-standard-offered")).toContainText("Our list holds no test standard for in-plane shear yet");
});

test("a coupon reopens into the form and the viewer window reads a job by its address", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  await page.getByLabel("Reopen a coupon", { exact: true }).selectOption("IM7-UNT-L1");
  await page.getByRole("button", { name: "Reopen", exact: true }).click();
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("250");
  await expect(page.getByLabel("Ply 3", { exact: true })).toHaveValue("-45");
  await expect(page.getByLabel("Material code", { exact: true })).toHaveValue("IM7");
  await page.goto("/workspace/fea/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("summary")).toContainText("Largest displacement");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
  await page.goto("/workspace/fea/view");
  await expect(page.getByText("No results to show")).toBeVisible();
});

test("the studio's old addresses go to the chat with their query (ADR-0055 amendment 3)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio?material=im7-8552");
  // The chat reads the material from the query once and then clears the query from the address (readHandoff), so the address
  // is /chat with or without it by the time it is read; that the chat got the material is the next line.
  await expect(page).toHaveURL(/\/workspace\/fea\/?(\?material=im7-8552)?$/);
  await expect(page.getByTestId("chat-spec")).toContainText("IM7 / 8552");
  await expect(page.getByTestId("coupon-tool")).toContainText("Coupon test"); // the first question lists the tools
  await page.goto("/studio/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page).toHaveURL(/\/workspace\/fea\/view\/?\?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00$/);
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
});

test("the guided chat asks one thing at a time, checks the setup itself, reads typed changes and runs (ADR-0055)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "test");
  await page.getByRole("button", { name: /^Unnotched tension/ }).click();
  await expect(question).toHaveAttribute("data-step", "material");
  await page.getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "shear");
  await page.getByRole("button", { name: /Use the tape estimate/ }).click();
  await expect(question).toHaveAttribute("data-step", "layup");
  await expect(question).toContainText("0° runs along the load");
  await page.getByRole("button", { name: /Quasi-isotropic/ }).click();
  await expect(question).toHaveAttribute("data-step", "geometry");
  await page.getByRole("button", { name: /250 × 25 mm, 56 mm tabs/ }).click();
  await expect(question).toHaveAttribute("data-step", "loading");
  await page.getByRole("button", { name: "Displacement 1 mm", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "name");
  await expect(question.locator("[data-panel=run]")).toBeVisible(); // the suggestion opens the Run panel; the name can also be typed here
  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("A. Engineer");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  expect(calls.checks).toHaveLength(1);
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect([sent.test, sent.library, sent.length, sent.tab_length, sent.ply_4, sent.symmetric, sent.value, sent.filled_by])
    .toEqual(["unnotched tension", "im7-8552", 250, 56, 90, "yes", 1, "A. Engineer"]);
  expect([sent.G13, sent.G23]).toEqual([4688, 2988]);
  expect(String(sent.notes)).toContain("tape estimate");
  await expect(page.getByTestId("chat-spec")).toContainText("[45/0/-45/90]s, 8 plies");
  await expect(page.getByTestId("preview")).toContainText("50 elements");

  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("make it [0/90]2s");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByTestId("chat-check")).toHaveCount(2);
  const changed = (calls.checks[1] as { values: Record<string, unknown> }).values;
  expect([changed.ply_1, changed.ply_2, changed.ply_3, changed.ply_4, changed.ply_5]).toEqual([0, 90, 0, 90, undefined]);
  await expect(page.getByTestId("chat-spec")).toContainText("[0/90/0/90]s, 8 plies");

  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 }) // the first results render compiles the shaders, slow on CI's software GL, and the missed read adds a poll interval;
  expect((calls.solves[0] as { run_by: string }).run_by).toBe("A. Engineer");
  await expect(page.getByTestId("chat-reaction")).toContainText("N");
  await expect(page.getByTestId("results")).toBeVisible();
  await expect(page.getByTestId("chat-result")).toContainText("Verified against reference solver: 57 of 57 values agree", { timeout: 15_000 });
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-chat.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a thing to fix takes its rows in the chat, and applying them checks again (ADR-0062 amendment 2)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await message.fill("A. Engineer");
  await message.press("Enter");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  await expect(page.getByTestId("chat-fix")).toHaveCount(0); // nothing to fix, nothing to type
  await page.getByLabel("Length (mm)", { exact: true }).fill(""); // emptied on its panel
  await message.fill("check");
  await message.press("Enter");
  const card = page.getByTestId("chat-check").last();
  await expect(card).toHaveAttribute("data-state", "blocked");
  const fix = card.getByTestId("chat-fix");
  const length = fix.locator("li[data-item=geometry]").getByLabel("Length (mm)");
  await expect(length).toHaveValue("");
  await expect(fix.getByTestId("chat-fix-apply")).toBeDisabled(); // nothing typed yet
  await length.fill("250");
  await fix.getByTestId("chat-fix-apply").click();
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  expect((calls.checks.at(-1) as { values: Record<string, unknown> }).values.length).toBe(250);
  await expect(page.locator(".chat-user").last()).toHaveText("Length (mm): 250");
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("250"); // the panel shows the row the chat filled
  await expect(page.getByTestId("chat-check").nth(1).getByTestId("chat-fix")).toHaveCount(0); // the earlier card keeps its words and drops its inputs
});

test("a word that names no value sends the engineer to the panel that asks for the next thing, and a row typed there moves the conversation on (ADR-0062)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await message.fill("coupon");
  await message.press("Enter");
  const redirect = page.getByTestId("chat-redirect").last();
  await expect(redirect).toHaveAttribute("data-panel", "test"); // the test is the next thing to state, the first step
  await expect(redirect).toContainText("This workspace sets up and solves test coupons");
  await expect(redirect).toContainText("Next: what are we analysing (Test and standard)");
  await page.getByTestId("ws-rail").getByTestId("question-test").locator('input[value="unnotched tension"]').check(); // picked on the panel, not in the chat
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "material");
  await page.getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "shear");
  await page.getByTestId("ws-rail").getByLabel("G13 (MPa)", { exact: true }).fill("4688");
  await page.getByTestId("ws-rail").getByLabel("G23 (MPa)", { exact: true }).fill("2988");
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "layup");
  await message.fill("help");
  await message.press("Enter");
  await expect(page.getByTestId("chat-redirect").last()).toHaveAttribute("data-panel", "layup");
  await page.getByTestId("chat-redirect").last().locator("[data-panel=layup]").click();
  await expect(page.getByTestId("panel-layup")).toHaveAttribute("open", "");
  expect(calls.checks).toHaveLength(0);
});

test("one typed line fills the coupon and the chat asks only for what is missing (ADR-0055)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("Open-hole tension, AS4/8552, [45/0/-45/90]s, 36 x 250 mm, 6 mm hole, 10 kN");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByText("Got it").last()).toBeVisible();
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "shear"); // the library lists no G13 or G23
  await expect(page.getByTestId("chat-spec")).toContainText("36 mm");
  await expect(page.getByTestId("chat-spec")).toContainText("Ø6 mm hole");
  await expect(page.getByTestId("chat-spec")).toContainText("10000 N force");
  await expect(page.getByLabel("Hole diameter (mm)", { exact: true })).toHaveValue("6"); // the rows carry over to the full form
  await expect(page.getByLabel("Ply 2", { exact: true })).toHaveValue("0");
  expect(calls.checks).toHaveLength(0);
});

test("with a model on, a message is read into a card the engineer ticks: what is ticked goes in, an unticked value does not (ADR-0088)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const asked: Record<string, unknown>[] = [];
  await mockApi(page, calls, { allTests: true });
  await page.route(API, async (route) => { // a model behind the API: its reading, as the source guard would keep it
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    asked.push(request.postDataJSON() as Record<string, unknown>);
    const take = (key: string, label: string, value: string, unit: string | null, quote: string, written = value, writtenUnit = unit) =>
      ({ key, label, value, unit, written_value: written, written_unit: writtenUnit, quote });
    return json({ run_id: "run-p", writer: "anthropic", model: "claude-stand-in", conditions: [], question: null, reason: null,
      proposals: [take("test", "Test", "open-hole tension", null, "open hole tension"), take("library", "Library material", "as4-8552", null, "AS4/8552"),
        take("layup", "Layup", "[45/0/-45/90]s", null, "[45/0/-45/90]s"), take("width", "Width (mm)", "36", "mm", "36 mm wide"),
        take("length", "Length (mm)", "250", "mm", "250 mm long"), take("hole_diameter", "Hole diameter (mm)", "6", "mm", "a 6 mm hole"),
        take("force", "Force applied (N)", "10000", "N", "pulled to 10 kN", "10", "kN")],
      dropped: [{ key: "tab_length", reason: "2.2 is not a number the quoted words write" }] });
  });
  await page.goto("/workspace/fea");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await message.fill("an open hole tension coupon in AS4/8552, [45/0/-45/90]s, 36 mm wide and 250 mm long with a 6 mm hole, pulled to 10 kN");
  await message.press("Enter");
  const card = page.getByTestId("proposal-card");
  await expect(card).toBeVisible();
  await expect(card).not.toContainText("claude-stand-in"); // the card says what was read, never who read it (ADR-0091)
  await expect(card).toContainText("Read from your message");
  await expect(card.locator("li[data-key='force']")).toContainText("10000 N");
  await expect(card.locator("li[data-key='force']")).toContainText("written 10 kN");
  await expect(card.locator("li[data-key='force']")).toContainText("pulled to 10 kN");
  await expect(card.getByTestId("proposal-dropped")).toContainText("Tab length: 2.2 is not a number"); // by its label, not its key (ADR-0091)
  // nothing has gone in before the tick
  await expect(page.getByTestId("chat-spec")).not.toContainText("open-hole tension");
  await expect(page.getByTestId("chat-spec")).not.toContainText("10000 N");
  await card.locator("li[data-key='width'] input").uncheck(); // a value the engineer does not take
  await card.getByTestId("proposal-apply").click();
  await expect(card.getByTestId("proposal-done")).toContainText("Applied 6 of 7");
  await expect(page.getByLabel("Hole diameter (mm)", { exact: true })).toHaveValue("6");
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("250");
  await expect(page.getByLabel("Width (mm)", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Ply 2", { exact: true })).toHaveValue("0");
  await expect(page.getByTestId("chat-spec")).toContainText("10000 N force");
  // the model was offered the rows in the coupon's units, and saw no name
  const sent = asked[0] as { product: string; rows: { key: string; unit?: string }[]; form: Record<string, string> };
  expect(sent.product).toBe("coupon");
  expect(sent.rows.find((r) => r.key === "length")?.unit).toBe("mm");
  expect(sent.rows.find((r) => r.key === "force")?.unit).toBe("N");
  expect(sent.form.filled_by).toBeUndefined();
  expect(calls.checks).toHaveLength(0);
});

test("a model that does not answer leaves the message to the page's patterns, and is not asked again that session (ADR-0088)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  let asked = 0;
  await mockApi(page, calls, { allTests: true });
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    asked += 1;
    return json({ run_id: "run-p", writer: "template", model: null, proposals: [], conditions: [], question: null, dropped: [],
      reason: "the model could not be reached" });
  });
  await page.goto("/workspace/fea");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await message.fill("Open-hole tension, AS4/8552, [45/0/-45/90]s, 36 x 250 mm, 6 mm hole, 10 kN");
  await message.press("Enter");
  await expect(page.getByText("Reading simple phrases only")).toBeVisible();
  await expect(page.getByText("Got it").last()).toBeVisible();
  await expect(page.getByTestId("chat-spec")).toContainText("10000 N force");
  await message.fill("make it [0/90]2s");
  await message.press("Enter");
  await expect(page.getByLabel("Ply 2", { exact: true })).toHaveValue("90");
  expect(asked).toBe(1);
  await expect(page.getByTestId("proposal-card")).toHaveCount(0);
});

test("a coupon stated in inches and psi is read, labelled and sent in those units (ADR-0061)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  await page.getByTestId("chat-units").selectOption("in-psi");
  await expect(page.getByTestId("chat-spec")).toContainText("in, psi and lbf");
  await page.getByRole("button", { name: /^Unnotched tension/ }).click();
  await page.getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "shear");
  await expect(page.getByRole("button", { name: /Use the tape estimate/ })).toContainText("G13 = 680000, G23 = 433300 psi"); // the engine's psi figures
  await page.getByRole("button", { name: /Use the tape estimate/ }).click();
  await expect(question).toHaveAttribute("data-step", "layup");
  await expect(question).toContainText("Ply thickness 0.0072 in (library)");
  await page.getByRole("button", { name: /Quasi-isotropic/ }).click();
  await expect(question).toHaveAttribute("data-step", "geometry");
  await expect(question.locator("[data-panel=geometry]")).toBeVisible(); // the size is typed under Geometry, labelled in inches
  await expect(page.getByTestId("studio-form").getByLabel("Length (in)", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /10 × 1 in, 2.2 in tabs/ }).click();
  await expect(question).toHaveAttribute("data-step", "loading");
  await page.getByRole("button", { name: "Force 2000 lbf", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "name");
  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("A. Engineer");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  expect(calls.checks).toHaveLength(1);
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect([sent.units, sent.length, sent.width, sent.tab_length, sent.control, sent.value, sent.G13, sent.G23]).toEqual(["in-psi", 10, 1, 2.2, "force", 2000, 680000, 433300]);
  expect(Math.abs(Number(sent.element_size) - 2 / 25.4)).toBeLessThan(1e-9); // the engine's 2 mm default, stated in inches by the engine
  await expect(page.getByTestId("chat-spec")).toContainText("10 × 1 in, 2.2 in tabs");
  await expect(page.getByTestId("chat-spec")).toContainText("2000 lbf force");
  // a value in another system is refused, not read as inches
  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("pull it 1 mm, in millimetres");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByText("Another unit system").last()).toBeVisible();
  expect(calls.checks).toHaveLength(1);
  // the full form carries the same rows, labelled in inches
  const form = page.getByTestId("studio-form");
  await expect(form.getByLabel("Units", { exact: true })).toHaveValue("in-psi");
  await expect(form.getByLabel("Length (in)", { exact: true })).toHaveValue("10");
  await expect(form.getByLabel("G13 (psi)", { exact: true })).toHaveValue("680000");
  await expect(form.getByLabel("Length (mm)", { exact: true })).toHaveCount(0);
});

test("the chat solves a laminate problem with each value in its own unit, and shows the answer in the units picked (ADR-0060)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const problems: Record<string, unknown>[] = [];
  await mockApi(page, calls);
  await page.route(API, async (route) => { // in front of the coupon stand-ins: the laminate solve, answered from the captured fixtures
    const request = route.request();
    if (new URL(request.url()).pathname !== "/v1/laminates/solve" || request.method() !== "POST") return route.fallback();
    const problem = request.postDataJSON() as Record<string, unknown>;
    problems.push(problem);
    const body = fixture(problem.report_units === "US" ? "laminate-answer-us" : "laminate-answer");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/workspace/fea");
  await page.getByTestId("laminate-choice").click();
  await expect(page).toHaveURL(/\/workspace\/laminate\/?$/);
  await expect(page.getByTestId("laminate-rail").getByTestId("panel-units")).toBeVisible();
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "units");
  await page.locator("button[data-system='SI']").click();
  await expect(question).toHaveAttribute("data-step", "material");

  const message = page.getByLabel("Message the laminate assistant", { exact: true });
  await message.fill("E1 147 GPa, E2 10300 MPa, G12 7, nu12 0.27, F1t 2280 MPa, F1c 1725 MPa, F2t 57 MPa, F2c 228 MPa, F6 76 MPa");
  await message.press("Enter");
  await expect(page.getByText("Got it").last()).toBeVisible();
  await expect(question).toHaveAttribute("data-step", "layup");
  await expect(question).toContainText("0° runs along x");
  await message.fill("[0/45/-45/90]s, 0.125 mm plies");
  await message.press("Enter");
  await expect(question).toHaveAttribute("data-step", "loads");
  await expect(page.getByTestId("laminate-stack")).toContainText("8 plies"); // the stack is drawn as soon as the layup is given
  await page.locator("#lam-Nx").fill("100"); // on the Loads panel
  await page.getByLabel("lam-Nx unit", { exact: true }).selectOption("N/mm"); // the system's unit is N/m; the typed value keeps its own
  await page.getByRole("button", { name: "The rest are zero", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "review"); // the rows typed on the panel moved the conversation on
  await expect(page.getByTestId("laminate-spec")).toContainText("[0/45/-45/90]s, 8 plies, 0.125 mm plies");
  await expect(page.getByTestId("laminate-spec")).toContainText("Nx = 100 N/mm");
  await page.locator("#lam-f12").fill("-0.5"); // on the Solve panel
  await page.getByTestId("lam-strain-limits").check(); // maximum strain with limits derived from the strengths: a stated choice, sent with the material
  await page.getByTestId("laminate-solve").click();

  await expect(page.getByTestId("laminate-answer")).toBeVisible({ timeout: 15_000 });
  expect(problems).toHaveLength(1);
  const sent = problems[0] as { material: Record<string, unknown>; layup: number[]; ply_thickness: unknown; loads: Record<string, unknown>; f12_star: number; report_units: string };
  expect(sent.material.E1).toEqual({ value: 147, unit: "GPa" }); // as typed: the engine converts, the page never does
  expect(sent.material.E2).toEqual({ value: 10300, unit: "MPa" });
  expect(sent.material.F2t).toEqual({ value: 57, unit: "MPa" });
  expect(sent.material.strain_limits).toBe("from-strengths");
  expect(sent.layup).toEqual([0, 45, -45, 90, 90, -45, 45, 0]);
  expect(sent.ply_thickness).toEqual({ value: 0.125, unit: "mm" });
  expect(sent.loads.Nx).toEqual({ value: 100, unit: "N/mm" });
  expect(sent.loads.My).toEqual({ value: 0, unit: "N*m/m" });
  expect([sent.f12_star, sent.report_units]).toEqual([-0.5, "SI"]);
  expect(calls.checks).toHaveLength(0); // no coupon check: this is not a coupon

  const results = page.getByTestId("laminate-results");
  await expect(results).toHaveAttribute("data-units", "SI");
  await expect(page.getByTestId("lam-eps-x")).toHaveText("1719");
  await expect(page.getByTestId("lam-fpf")).toContainText("R = 3.207");
  await expect(page.getByTestId("lam-ratio-tsai_wu")).toHaveText("3.207");
  await expect(page.getByTestId("lam-ratio-max_strain")).toHaveText("3.22"); // the fourth criterion, from the limits the engine derived
  await expect(page.getByTestId("lam-no-max-strain")).toHaveCount(0);
  await expect(page.getByTestId("lam-fpf-table").locator("tr.studio-earliest")).toHaveAttribute("data-criterion", "tsai_wu");
  await expect(page.getByTestId("lam-ply-table").locator("tr.studio-earliest")).toHaveAttribute("data-ply", "4");
  await expect(page.getByTestId("matrix-A")).toContainText("N/m");
  await expect(page.getByTestId("lam-explanation")).toHaveAttribute("data-writer", "template");
  await expect(page.getByTestId("lam-explanation")).toContainText("By Tsai-Wu, ply 4 (90 degrees) fails first");

  await page.getByRole("button", { name: "US customary", exact: true }).click(); // solved again by the engine in the other system
  await expect(results).toHaveAttribute("data-units", "US", { timeout: 15_000 });
  expect(problems).toHaveLength(2);
  expect((problems[1] as { report_units: string; loads: { Nx: unknown } }).report_units).toBe("US");
  expect((problems[1] as { loads: { Nx: unknown } }).loads.Nx).toEqual({ value: 100, unit: "N/mm" }); // the problem itself is unchanged
  await expect(page.getByTestId("matrix-A")).toContainText("lb/in");
  await expect(page.getByTestId("lam-ratio-tsai_wu")).toHaveText("3.207"); // a ratio has no unit
  await expect(page.getByTestId("lam-explanation")).toContainText("Nx = 571 lb/in");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-laminate.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("the model is lit for presentation before a run: the sketch and the package's preview, never the results (ADR-0063)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("console", (message) => { if (message.type() === "error" && /THREE|WebGL|shader/i.test(message.text())) browserErrors.push(message.text()); });
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.getByTestId("sketch-scene")).toHaveAttribute("data-mode", "presentation");
  await page.getByTestId("sketch-scene").screenshot({ path: ".local/website/screenshots/studio-sketch-lit.png" });
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("preview")).toBeVisible();
  await expect(page.getByTestId("studio-scene")).toHaveAttribute("data-mode", "presentation");
  await expect(page.getByTestId("studio-scene")).toHaveAttribute("data-bands", "");
  await page.getByTestId("studio-scene").screenshot({ path: ".local/website/screenshots/studio-preview-lit.png" });
  expect(browserErrors).toEqual([]);
});

test("the fibre tow test swaps the panels for the tow's, and Calculate shows each specimen and the statistics (ADR-0074)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[], tows: [] as unknown[] };
  await mockApi(page, calls, { allTests: true });
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  const rail = page.getByTestId("ws-rail");
  await rail.getByTestId("question-test").locator('input[value="fibre tow tension"]').check(); // the first step's card, as for a coupon
  await expect(page.getByTestId("tow-form")).toBeVisible();
  await expect(rail.getByTestId("panel-tow-standard")).toContainText("Test and standard"); // the same first step, still there
  await expect(rail.getByTestId("question-test").locator("input:checked")).toHaveValue("fibre tow tension");
  await expect(page.getByTestId("panel-geometry")).toHaveCount(0); // a tow has no coupon geometry, layup or mesh
  await expect(page.getByTestId("tow-sketch")).toBeVisible();
  const standard = rail.getByTestId("question-standard");
  await expect(standard.locator("input")).toHaveCount(2);
  expect(await standard.locator("input").evaluateAll((inputs) => inputs.map((i) => (i as HTMLInputElement).value))).toEqual(["ASTM D4018-23", "none"]);
  await standard.locator('input[value="ASTM D4018-23"]').check();
  await expect(page.getByTestId("setup-line")).toContainText("fibre tow tension under ASTM D4018-23");
  await expect(page.getByTestId("standard-card")).toContainText("What Calculate will judge");
  await expect(page.getByLabel("Bundles per specimen", { exact: true })).toHaveValue("1");
  const values = fixture("values", "studio-tow");
  await page.getByLabel("Filled in by", { exact: true }).fill(values.filled_by);
  for (const [label, key] of [["Fibre", "fibre"], ["Filaments per bundle", "filaments"], ["Mass per unit length (g/m)", "mul"], ["Measured density (g/cm³)", "fibre_density"],
    ["Resin strain to failure (microstrain)", "resin_strain"], ["Impregnated mass per unit length (g/m)", "mul_impregnated"], ["Gauge length (mm)", "tow_gauge_length"],
    ["Machine speed (mm/min)", "speed"], ["Typical strain at failure (microstrain)", "failure_strain"], ["Datasheet strength (MPa)", "datasheet_strength"],
    ["Datasheet modulus (GPa)", "datasheet_modulus"]] as const) {
    await page.getByLabel(label, { exact: true }).fill(String(values[key]));
  }
  await page.getByLabel("Fibre type", { exact: true }).selectOption("carbon");
  await page.getByLabel("Density measured on", { exact: true }).selectOption("desized");
  await page.getByLabel("Tabs", { exact: true }).selectOption("paper or card");
  await expect(page.getByTestId("strand-sketch")).toHaveAttribute("aria-label", /150 mm between the tabs, paper or card tabs/);
  const pasted = (values.specimens as Record<string, unknown>[]).map((s) => ["id", "max_force", "force_lower", "force_upper", "failure_code", "status", "note"]
    .map((k) => (s[k] ?? "")).join("\t")).join("\n");
  await page.getByText("Paste specimens from a spreadsheet").click();
  await page.getByLabel("Specimens to paste").fill(pasted);
  await page.getByRole("button", { name: "Replace the list" }).click();
  await expect(page.getByTestId("tow-specimens").locator("fieldset")).toHaveCount(5);
  await expect(page.getByTestId("tow-specimens").locator("[data-specimen='4']")).toContainText("grip or tab, at the grip or tab, top");
  await page.getByTestId("tow-calculate").click();
  await expect(page.getByTestId("tow-results")).toBeVisible();
  const sent = (calls.tows[0] as { values: Record<string, unknown> }).values;
  expect([sent.test, sent.standard, sent.mul, sent.tow_gauge_length, sent.bundles, (sent.specimens as unknown[]).length]).toEqual(["fibre tow tension", "ASTM D4018-23", 0.8, 150, 1, 5]);
  expect((sent.specimens as Record<string, unknown>[])[0]).toEqual(values.specimens[0]);
  const result = fixture("tow", "studio-tow").result;
  await expect(page.getByTestId("tow-strength")).toContainText(`${Number(result.strength.mean.toPrecision(4))} MPa`); // the engine's mean, printed
  await expect(page.getByTestId("tow-modulus")).toContainText(`${Number(result.modulus.mean.toPrecision(4))} GPa`);
  await expect(page.getByTestId("tow-specimen-table").locator("tbody tr")).toHaveCount(5);
  await expect(page.getByTestId("tow-specimen-table").locator("tr[data-status=rejected]")).toContainText("slipped in the top grip");
  await expect(page.getByTestId("tow-conformance")).toContainText("test record checked against ASTM D4018-23: 7 of 7 requirements the record shows are met");
  await expect(page.getByTestId("standard-card").locator("[data-requirement=grip-failures]")).toHaveAttribute("data-state", "note");
  await expect(page.getByTestId("tow-report").locator("li[data-shown=no]").first()).toContainText("not in this record");
  await rail.getByTestId("question-test").locator('input[value="unnotched tension"]').check(); // back to a coupon: its panels, the tow's standard cleared
  await expect(page.getByTestId("tow-form")).toHaveCount(0);
  await expect(rail.getByTestId("question-standard").locator("input:checked")).toHaveValue("none");
});

test("every settled edit is answered by our kernel live, labelled a preview, and a full run replaces it (ADR-0086)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[], lives: [] as unknown[] };
  await mockApi(page, calls, { live: true });
  await page.goto("/workspace/fea");
  await page.getByRole("button", { name: "Load example" }).click();
  // no Run pressed: the complete example is answered by the live solve, with the answer card and the banner
  await expect(page.getByTestId("results")).toHaveAttribute("data-source", "live", { timeout: 10_000 });
  await expect(page.getByTestId("live-banner")).toContainText("Preview (0.6 s). Run the analysis to verify it and write the report.");
  await expect(page.getByTestId("answer-headline")).toContainText("Holds at the applied loading");
  await expect(page.getByTestId("solve-button")).toHaveText("Run full analysis");
  expect(calls.lives.length).toBe(1);
  expect(calls.solves.length).toBe(0);
  // a settled edit is one live solve, with the rows as they stand (a value filled at once: typing key by key on a slow machine can pause past
  // the debounce, which is the debounce working, not a second edit)
  const value = page.getByLabel("Value (mm or N)", { exact: true });
  await value.fill("0.75");
  await expect.poll(() => calls.lives.length, { timeout: 10_000 }).toBe(2);
  await page.waitForTimeout(1500);
  expect(calls.lives.length).toBe(2);
  expect((calls.lives[1] as { values: Record<string, unknown> }).values.value).toBe(0.75);
  // the full run: CalculiX, the mesh study and the package; its fields replace the preview and the banner goes
  await page.getByLabel("Run by", { exact: true }).fill("A. Tester");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toHaveAttribute("data-source", "run", { timeout: 20_000 });
  await expect(page.getByTestId("live-banner")).toHaveCount(0);
  expect(calls.solves.length).toBe(1);
});

test("a temperature change named in the laminate chat brings up its condition, its panel and its values, and goes with the problem (ADR-0087)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const problems: Record<string, unknown>[] = [];
  await mockApi(page, calls);
  await page.route(API, async (route) => { // the laminate solve, answered from the captured fixture
    const request = route.request();
    if (new URL(request.url()).pathname !== "/v1/laminates/solve" || request.method() !== "POST") return route.fallback();
    problems.push(request.postDataJSON() as Record<string, unknown>);
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixture("laminate-answer")) });
  });
  await page.goto("/workspace/laminate");
  await page.locator("button[data-system='SI']").click();
  const message = page.getByLabel("Message the laminate assistant", { exact: true });
  const rail = page.getByTestId("laminate-rail");
  await expect(rail.getByTestId("panel-temperature")).toHaveCount(0); // never shown before it is asked for
  await expect(rail.getByTestId("add-condition")).toContainText("+ Temperature change");
  // words that name the condition without a value: it is offered, nothing opens unasked
  await message.fill("there are residual stresses from the cure");
  await message.press("Enter");
  await expect(page.locator("button[data-condition='temperature']")).toBeVisible();
  await expect(rail.getByTestId("panel-temperature")).toHaveCount(0);
  // a value states it: the condition comes on with it, read with its sign and unit
  await message.fill("E1 147 GPa, E2 10.3 GPa, G12 7 GPa, nu12 0.27, F1t 2280 MPa, F1c 1725 MPa, F2t 57 MPa, F2c 228 MPa, F6 76 MPa");
  await message.press("Enter");
  await message.fill("[0/90]s, 0.25 mm plies, Nx = 0 N/m, the rest zero");
  await message.press("Enter");
  await message.fill("it is cooled by 150 °C after cure, alpha1 = -1e-6 /°C, alpha2 = 25e-6 /°C");
  await message.press("Enter");
  await expect(page.getByText("temperature change -150 °C")).toBeVisible();
  await expect(rail.getByTestId("panel-temperature")).toBeVisible();
  await expect(page.locator("#lam-delta-t")).toHaveValue("-150");
  await expect(page.locator("#lam-alpha2")).toHaveValue("25e-6");
  await expect(rail.getByTestId("add-condition")).toHaveCount(0); // the only condition is on
  await expect(page.getByTestId("laminate-spec")).toContainText("-150 °C");
  await page.getByTestId("laminate-solve").click();
  await expect(page.getByTestId("laminate-answer")).toBeVisible({ timeout: 15_000 });
  const sent = problems[0] as { delta_T: unknown; material: Record<string, unknown> };
  expect(sent.delta_T).toEqual({ value: -150, unit: "degC" });
  expect([sent.material.alpha1, sent.material.alpha2]).toEqual([{ value: -1e-6, unit: "1/degC" }, { value: 25e-6, unit: "1/degC" }]);
  // removed, it sends nothing thermal and the menu offers it again
  await rail.getByTestId("remove-temperature").click();
  await expect(rail.getByTestId("panel-temperature")).toHaveCount(0);
  await expect(rail.getByTestId("add-condition")).toContainText("+ Temperature change");
});

test("with a model on, the laminate chat's card proposes a temperature change and its condition, and the panel opens once applied (ADR-0088)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    return json({ run_id: "run-p", writer: "anthropic", model: "claude-stand-in", question: null, reason: null, dropped: [],
      proposals: [{ key: "delta_T", label: "Temperature change, uniform (a cooling is negative)", value: "-150", unit: "degC", written_value: "-150",
        written_unit: "°C", quote: "cooled by 150 °C" }],
      conditions: [{ id: "temperature", title: "Temperature change", quote: "cooled by 150 °C after cure" }] });
  });
  await page.goto("/workspace/laminate");
  await page.locator("button[data-system='SI']").click();
  const rail = page.getByTestId("laminate-rail");
  const message = page.getByLabel("Message the laminate assistant", { exact: true });
  await message.fill("the laminate is cooled by 150 °C after cure");
  await message.press("Enter");
  const card = page.getByTestId("proposal-card");
  await expect(card.locator("li[data-key='delta_T']")).toContainText("-150 °C");
  await expect(card.locator("li[data-key='condition:temperature']")).toContainText("Add a temperature change");
  await expect(rail.getByTestId("panel-temperature")).toHaveCount(0); // nothing opens before the tick
  await card.getByTestId("proposal-apply").click();
  await expect(rail.getByTestId("panel-temperature")).toBeVisible();
  await expect(page.locator("#lam-delta-t")).toHaveValue("-150");
});

/** Every word a customer can read in the workspace (ADR-0091): the shell's text, folded details included, and the words a screen reader,
 * a tooltip, a placeholder or a saved file's name carries. */
async function shownText(page: Page): Promise<string> {
  return page.getByTestId("workspace-shell").evaluate((shell) => {
    const attributes = [...shell.querySelectorAll("[aria-label], [title], [placeholder], a[download]")]
      .flatMap((el) => ["aria-label", "title", "placeholder", "download"].map((name) => el.getAttribute(name) ?? ""));
    return [shell.textContent ?? "", ...attributes].join("\n");
  });
}
const expectNoBannedTerms = async (page: Page, where: string) => expect(bannedIn(await shownText(page)), where).toEqual([]);

test("the customer's workspace never names a tool, a vendor, a model, a script, a record or a person (ADR-0091)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const queued = { ...fixture("job-running"), state: "queued", stage: null, stages_done: [], outputs: {}, log_tail: [], message: "queued; 1 ahead" };
  // the oldest words the pipeline still writes come through: stage names, "agree with CalculiX", the record's .toml, the console
  await mockApi(page, calls, { allTests: false, writer: "model",
    jobs: (poll) => (poll < 3 ? queued : poll < 5 ? fixture("job-running") : poll < 7 ? fixture("job-result-in") : fixture("job-done")) });
  await page.goto("/workspace/fea");
  await expect(page.getByTestId("tension-screen")).toBeVisible();
  await expectNoBannedTerms(page, "a fresh start");
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await page.getByTestId("build-button").click();
  await expect(page.getByTestId("job-progress").first()).toHaveAttribute("data-state", "queued");
  await expect(page.getByTestId("job-state").first()).toHaveText("Queued (1 ahead)");
  await expectNoBannedTerms(page, "queued");
  await expect(page.getByTestId("job-progress").first()).toHaveAttribute("data-state", "running", { timeout: 15_000 });
  await expectNoBannedTerms(page, "running");
  await expect(page.getByTestId("job-progress").first()).toHaveAttribute("data-state", "done", { timeout: 30_000 });
  await expect(page.getByTestId("explanation")).toHaveAttribute("data-writer", "anthropic", { timeout: 15_000 }); // a model wrote it; the page does not say so
  await page.getByTestId("answer-table").getByRole("button", { name: "Show" }).first().click();
  await expect(page.getByTestId("probe")).toBeVisible();
  await expect(page.getByTestId("tension-files").locator("a[data-key=prepomax_results]")).toHaveText("Reference solver results (.frd)");
  await expectNoBannedTerms(page, "done, with the probe table and the files");
});

test("a stopped run says what happened and what to do, in plain words (ADR-0091)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const stopped = { ...fixture("job-running"), state: "stopped", stage: "CalculiX", finished_at: "2026-10-28T20:01:00+00:00",
    message: "stopped at CalculiX: ccx_dynamic.exe exited with code 201: *ERROR in e_c3d: nonpositive jacobian determinant in element 812",
    log_tail: ["== CalculiX", " *ERROR in e_c3d", "run_coupon: stopped at CalculiX"] };
  await mockApi(page, calls, { allTests: false, jobs: () => stopped });
  await page.goto("/workspace/fea");
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await page.getByTestId("build-button").click();
  const run = page.getByTestId("job-progress").first();
  await expect(run).toHaveAttribute("data-state", "stopped", { timeout: 15_000 });
  await expect(run.getByTestId("job-problem")).toHaveText("The analysis stopped while solving. Run it again; if it stops again, contact us.");
  await expect(run.locator("li[data-step=solving]")).toHaveAttribute("data-state", "stopped");
  await expect(run).not.toContainText("exited with code");
  await expectNoBannedTerms(page, "stopped");
});
