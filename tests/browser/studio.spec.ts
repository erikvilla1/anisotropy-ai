import { test, expect, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";
import { printed } from "../../lib/studio-colors";
import { probeTable } from "../../lib/studio-fields";
import { ANALYSIS_UNAVAILABLE, bannedIn, bannedInAbaqusCard } from "../../lib/studio-copy";
import { exchangeState, LIMITS, mockExchange, uploadOf } from "./abaqus-api";
import { hydrated } from "./hydrated";

// Each scenario opens its own page and plays the API on it, so the scenarios may run in any order and on any worker, and CI splits
// them into parts by scenario rather than by file (ADR-0114 amendment 2).
test.describe.configure({ mode: "parallel" });

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
  { row: "tab_length", value: 56, reason: "ASTM D3039/D3039M-17, Table 2, balanced and symmetric: gripped through emery cloth, with no tab length given; 56 mm is the software's choice" },
  { row: "strain_length", value: 25, reason: "25 mm, within ASTM D3039/D3039M-17 §7.3.2's 10 to 50 mm, centred on the coupon" },
  { row: "grips", value: "nodal", reason: "every node of each tab is held; the top tab moves" },
  { row: "control", value: "displacement", reason: "the top grip moves; the bottom one is held" },
  { row: "value", value: 1, reason: "the model is linear, so R, the loading at first-ply failure, does not depend on it" },
];

/** The API, played from the public fixtures: the check, the solve, a job that runs then ends, its files, and the coupons. */
async function mockApi(page: Page, calls: { checks: unknown[]; solves: unknown[]; fieldsReads?: number; tows?: unknown[]; lives?: unknown[]; wakes?: number;
    reports?: number; reportReads?: string[] },
  options: { missFirstFieldsRead?: boolean; live?: boolean; allTests?: boolean; plates?: boolean; writer?: "template" | "model"; jobs?: (poll: number) => unknown;
    report?: () => { status: number; body: unknown } } = {}) {
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
    if (path === "/v1/coupon-tests" && request.method() === "GET") return json(route, { all: options.allTests ?? true, plates: options.plates ?? false });
    if (path === "/v1/workspace/assistant" && options.writer === "model") return json(route, { proposes: false, provider: "anthropic", model: "claude-opus-5-5" });
    if (path === "/v1/coupons" && request.method() === "GET") return json(route, fixture("coupons"));
    if (path.startsWith("/v1/projects")) { // no project store, and the API says so: the browser keeps the project alone (ADR-0091 amendment 2)
      // the page and the API are on two origins in CI, so the header must be exposed to be read, as the API's CORS layer does (main.py)
      return route.fulfill({ status: 503, contentType: "application/json", headers: { "X-Anisotropy-Records": "off", "Access-Control-Expose-Headers": "X-Anisotropy-Records" },
        body: JSON.stringify({ detail: "Records are switched off on this server, so there is nothing to read" }) });
    }
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
    if (path === "/v1/wake" && request.method() === "POST") { // the page says a run may follow (ADR-0056 amendment 11); nothing to wake here
      calls.wakes = (calls.wakes ?? 0) + 1;
      return json(route, { waking: false }, 202);
    }
    if (/^\/v1\/coupon-jobs\/[^/]+\/document$/.test(path) && request.method() === "POST") { // a report asked for (ADR-0064 amendment 3)
      calls.reports = (calls.reports ?? 0) + 1;
      const answer = options.report?.() ?? { status: 409, body: { detail: "This analysis kept no report to write. Run the analysis again to get one." } };
      return json(route, answer.body, answer.status);
    }
    if (path.endsWith("/files/document")) {
      (calls.reportReads ??= []).push(url.search);
      return route.fulfill({ status: 200, contentType: "application/pdf", headers: { "Content-Disposition": 'attachment; filename="report.pdf"' }, body: "%PDF-1.5" });
    }
    if (path === "/v1/coupon-jobs" && request.method() === "POST") {
      calls.solves.push(request.postDataJSON());
      return json(route, options.jobs ? options.jobs(0) : fixture("job-running"), 202); // a scenario's own jobs start as it says, queued among them
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
  await page.getByTestId("fea-start-kinds").locator("[data-kind=coupon]").click(); // FEA opens blank; a coupon is picked (ADR-0124)
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
  // where the gauge section is read (ADR-0108), as the package wrote it: the same distance from the tab lines on every mesh
  await expect(page.getByTestId("answer-gauge-reading")).toHaveText("The gauge section is read at least 6.25 mm from each tab line, a quarter of the width, the same distance on every mesh.");
  await expect(page.getByTestId("answer-extremes").locator("tbody tr")).toHaveCount(5);
  await expect(page.getByTestId("fpf-details")).not.toHaveAttribute("open", ""); // the per-criterion tables of the whole model fold away under the answer
  await expect(page.getByTestId("explanation")).toHaveAttribute("data-writer", "template", { timeout: 15_000 }); // the API answered the explain call
  // the result before the documents (ADR-0064): the agreement line while the job still draws and builds the package
  await expect(page.getByTestId("job-progress")).toContainText("Results are ready. The report follows.", { timeout: 15_000 });
  await expect(page.getByTestId("job-message")).toContainText("Verified against reference solver: 57 of 57 values agree");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
  await expect(page.getByTestId("job-message")).toContainText("Verified against reference solver: 57 of 57 values agree");
  await expect(page.getByTestId("job-progress").locator("li[data-state=done]")).toHaveCount(5); // the five steps of a finished job (ADR-0091)
  await expect(page.getByTestId("job-took")).toHaveText("Finished in 80 s."); // from the click to the last file, the job's own times (ADR-0064 amendment 1)
  const outputs = page.getByTestId("panel-outputs"); // the files in the left column, named by the standard and the layup (ADR-0091)
  await expect(outputs.locator("a[data-key=package]")).toHaveAttribute("href", /\/v1\/coupon-jobs\/0f3a2c9e[^/]*\/files\/package\?name=UnnotchedTension_%5B45%2C0%2C-45%2C90%5Ds_package\.zip$/);
  await expect(outputs.locator("a[data-key=package]")).toHaveAttribute("download", "UnnotchedTension_[45,0,-45,90]s_package.zip"); // commas (fea-run-39)
  await expect(outputs.locator("a[data-key=prepomax_results]")).toHaveText("Reference solver results (.frd)"); // the development view lists every file (D4)
  await expect(outputs.locator("a[data-key=prepomax_results]")).toHaveAttribute("href", /\/files\/reference_results\?name=/); // by a neutral name
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
  await page.goto("/workspace/fea?for=coupon");
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
  await expect(page.getByTestId("preview")).toContainText("Left support: held along z"); // the sets in words (audit fea-run-16)
  await expect(page.getByTestId("preview")).toContainText("Left pin: held along x, y");
  await expect(page.getByTestId("preview")).not.toContainText("Pin-Left");
  await page.getByLabel("Run by", { exact: true }).fill("A. Engineer");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 30_000 }); // 15 s was passed twice on CI runners that ran every test of this file at half speed
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
  await page.goto("/workspace/fea?for=coupon");
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
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 30_000 }); // 15 s was passed on a CI runner that ran every test of this file at half speed (10.2 min for the suite), as for the bending coupon above
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
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
  await expect(page.getByTestId("chat-not-available").last()).toContainText(
    "Open-hole tension is not offered yet. This workspace runs the unnotched tension coupon, under ASTM D3039 or no standard."); // no tool, no open validation
  // a layup that bends as it is pulled is refused on the page, before Run analysis, in the setup check's words (audit repository-2)
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await expect(page.getByTestId("tension-screen").getByRole("alert")).toHaveText("This layup is not symmetric. Use a layup that reads the same from both faces, such as [0/45/-45/90]s.");

  await page.getByLabel("Material", { exact: true }).selectOption("as4-8552"); // its library record gives no ply thickness: the screen asks
  await expect(page.getByTestId("library-ply-thickness")).toBeVisible();
  await expect(page.getByTestId("tension-missing")).toContainText("Ply thickness (mm)");
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await expect(page.getByTestId("library-ply-thickness")).toHaveCount(0); // IM7/8552's record gives one
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await expect(page.getByTestId("tension-missing")).toHaveCount(0);
  // a layup refused after a good one never reaches the form, which keeps the good one: Run analysis waits until it is fixed (review R2-3)
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await expect(page.getByTestId("tension-screen").getByRole("alert")).toContainText("This layup is not symmetric.");
  await expect(page.getByTestId("build-button")).toBeDisabled();
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await expect(page.getByTestId("build-button")).toBeEnabled();
  await page.getByTestId("build-button").click();
  await expect.poll(() => calls.solves.length).toBe(1); // ready, so Build goes on to the full analysis
  const sent = (calls.checks.at(-1) as { values: Record<string, unknown> }).values;
  expect(sent.input).toBe("tension");
  expect(sent.library).toBe("im7-8552");
  expect([sent.ply_1, sent.ply_2, sent.ply_3, sent.ply_4, sent.symmetric]).toEqual([45, 0, -45, 90, "yes"]);
  for (const key of ["length", "width", "tab_length", "grips", "element_size", "G13", "G23", "test", "units"]) expect(sent[key], key).toBeUndefined(); // the package chooses them
  // what the software chose is said in the tab it belongs to (ADR-0111): the size under Geometry, the loading under Loads
  const built = page.getByTestId("defaults-geometry");
  await expect(built.locator("tr[data-row=width]")).toContainText("ASTM D3039/D3039M-17, Table 2, balanced and symmetric");
  await expect(built.locator("tr[data-row=tab_length]")).toContainText("56 mm is the software's choice");
  await expect(page.getByTestId("panel-geometry").locator(".ws-panel-note")).toHaveText("250 × 25 mm, 56 mm tabs");
  // a blank field of the tree shows the value in use, not nothing (ADR-0090 amendment 1)
  await expect(page.locator("#studio-width")).toHaveAttribute("placeholder", "25");
  await expect(page.locator("#studio-length")).toHaveAttribute("placeholder", "250");
  await expect(page.locator("#studio-tab_length")).toHaveAttribute("placeholder", "56");
  await expect(page.locator("#studio-width")).toHaveValue("");
  const loading = page.getByTestId("defaults-loads");
  await expect(loading.locator("tr[data-row=value] th")).toHaveText("Applied displacement (mm)"); // the label alone in the row header (uiux-fea-run-29)
  await expect(loading.locator("tr[data-row=value] td").last()).toHaveText("The model is linear, so R, the loading at first-ply failure, does not depend on it.");
  await expect(page.getByTestId("tension-files")).toContainText("Abaqus input file (.inp)", { timeout: 45_000 }); // the job ends at the eighth poll, slower on CI
  await expect(page.getByTestId("tension-files")).toContainText("Report (PDF)");
  await expect(page.getByTestId("tension-files").locator("a[data-key=document]")).toHaveAttribute("download", "D3039_[45,0,-45,90]s_report.pdf");
  // a customer gets the report and the solver input, asked for by what it is; the team's package and reference files stay out (D4)
  await expect(page.getByTestId("tension-files").locator("a[data-key=abaqus_deck]")).toHaveAttribute("href", /\/files\/solver_input\?name=D3039_%5B45%2C0%2C-45%2C90%5Ds_solver\.inp$/);
  await expect(page.getByTestId("tension-files").locator("a[data-key=package], a[data-key=prepomax_deck], a[data-key=prepomax_results]")).toHaveCount(0);
  await expect(page.getByTestId("status")).toHaveText("Done. Download the report and files under Results.");
});

test.describe("the model tree", () => {
  test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 }); // its pictures are looked at by people

  /** Keeps, in the page, the id of every tab the assistant marks as changed from now on. The mark lasts 1.8 s, which a slow runner can
   * spend before an assertion first looks (PR #252's studio-browser run), so the test asks whether it was put on, not whether it is on. */
  const watchMarks = (page: Page) =>
    page.evaluate(() => {
      const marked: string[] = [];
      (window as unknown as { marked: string[] }).marked = marked;
      new MutationObserver((records) => {
        for (const record of records) {
          const element = record.target as HTMLElement;
          if (element.classList.contains("ws-panel-changed")) marked.push(element.id);
        }
      }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["class"] });
    });
  const marked = (page: Page) => page.evaluate(() => (window as unknown as { marked: string[] }).marked);

  test("the setup is a model tree in the words of any finite element program; a tab lights its part of the model and a change in the chat opens its tab (ADR-0111)", async ({ page }) => {
    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    const calls = { checks: [] as unknown[], solves: [] as unknown[] };
    await mockApi(page, calls, { allTests: false }); // the product's view
    await page.goto("/workspace/fea?for=coupon");
    const screen = page.getByTestId("tension-screen");
    await expect(screen.locator(".ws-panel-title")).toHaveText(["Test", "Geometry", "Material", "Layup", "Analysis step", "Boundary conditions", "Loads",
      "Mesh", "Solve", "Results", "History"]);
    const said = (await screen.innerText()).toLowerCase();
    for (const word of ["abaqus", "ansys", "calculix", "change settings", "model settings"]) expect(said).not.toContain(word);
    await expect(page.getByTestId("panel-step")).toContainText("Static, linear");
    await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
    await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
    await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
    await expect(page.getByTestId("panel-layup").locator(".ws-panel-note")).toHaveText("[45/0/-45/90]s, 8 plies");
    // a change made by talking opens the tab it changed and marks it, so the engineer sees where it went
    const mesh = page.getByTestId("panel-mesh");
    await expect(mesh).not.toHaveAttribute("open", "");
    const message = page.getByLabel("Message the coupon assistant", { exact: true });
    await watchMarks(page);
    await message.fill("use 4 mm elements");
    await message.press("Enter");
    await expect(mesh).toHaveAttribute("open", "");
    await expect.poll(() => marked(page)).toContain("panel-mesh");
    await expect(page.locator("#studio-element_size")).toHaveValue("4");
    await expect(mesh.locator(".ws-panel-note")).toContainText("4 mm elements"); // and the count once the preview has meshed it
    await page.screenshot({ path: ".local/website/screenshots/model-tree-chat-change.png" });
    // the change is kept as a version, said to come from the assistant and the message (ADR-0113)
    const history = page.getByTestId("panel-history");
    await history.locator("summary").click();
    const byChat = history.locator("li[data-by=assistant]").filter({ hasText: "use 4 mm elements" });
    await expect(byChat).toContainText("→ 4");

    await page.getByTestId("build-button").click();
    await expect.poll(() => calls.solves.length).toBe(1);
    expect((calls.checks.at(-1) as { values: Record<string, unknown> }).values.element_size).toBe(4);
    // a tab of the model lights its part on the model while it is open, and lists it in the words under the model
    const scene = page.getByTestId("studio-scene");
    const conditions = page.getByTestId("panel-conditions");
    await conditions.locator("summary").click();
    await expect(scene).toHaveAttribute("data-emphasis", "conditions");
    await expect(page.getByTestId("tree-conditions")).toContainText("Bottom grip: fixed (encastre)");
    await expect(page.getByTestId("tree-conditions")).toContainText("Top grip: free to move along the coupon only");
    await expect(page.getByTestId("defaults-conditions").locator("tr[data-row=grips]")).toContainText("Clamped");
    await page.screenshot({ path: ".local/website/screenshots/model-tree-boundary-conditions.png" });
    await conditions.locator("summary").click();
    await expect(scene).toHaveAttribute("data-emphasis", "");
    await page.getByTestId("panel-loads").locator("summary").click();
    await expect(scene).toHaveAttribute("data-emphasis", "loads");
    await expect(page.getByTestId("tree-loads")).toContainText("Top grip: pulled 1 mm along the coupon");
    await expect(page.locator("#studio-control option[value='']")).toHaveText("displacement, chosen for you"); // a blank row says what stands for it
    await expect(page.getByTestId("tension-files")).toContainText("Report (PDF)", { timeout: 45_000 });
    await expect(page.getByTestId("panel-outputs")).toHaveAttribute("open", "");
    await expect(page.getByTestId("chat-result-line")).toHaveText("Checked by a second solver"); // no counts for the customer to judge
    // the Results tab says the answer in three lines and colours the model by a field and a ply, both ways with the viewer
    const answer = page.getByTestId("tree-results-answer");
    await expect(answer).toContainText("Reaction");
    await expect(answer).toContainText("Largest displacement");
    await expect(answer).toContainText("First-ply failure");
    const tree = page.getByTestId("tree-results");
    const viewer = page.getByTestId("field-controls");
    await tree.locator("button[data-field=S11]").click();
    await expect(viewer.getByLabel("Field", { exact: true })).toHaveValue("S11");
    await expect(tree.locator("button[data-field=S11]")).toHaveAttribute("aria-pressed", "true");
    await page.getByLabel("Ply shown", { exact: true }).selectOption("2");
    await expect(viewer.getByLabel("Ply", { exact: true })).toHaveValue("2");
    await viewer.getByLabel("Field", { exact: true }).selectOption("u_mag");
    await expect(tree.locator("button[data-field=u_mag]")).toHaveAttribute("aria-pressed", "true");
    await expect(tree.locator("button[data-field=S11]")).toHaveAttribute("aria-pressed", "false");
    await tree.locator("button[data-field=S11]").click();
    await page.screenshot({ path: ".local/website/screenshots/model-tree-after-run.png" });
    // the model's own view buttons: a layer hidden and shown, straight above and back (ADR-0111 amendment 2)
    await expect(scene).toHaveAttribute("data-shown", "mesh conditions loads");
    await page.getByTestId("show-conditions").click();
    await expect(scene).toHaveAttribute("data-shown", "mesh loads");
    await expect(page.getByTestId("show-conditions")).toHaveAttribute("aria-pressed", "false");
    await page.getByTestId("show-conditions").click();
    await page.getByTestId("view-top").click();
    await expect(scene).toHaveAttribute("data-view", "top");
    await page.getByTestId("view-fit").click();
    await expect(scene).toHaveAttribute("data-view", "home");
    // the run's answer is kept on the version it was made from; two versions compare; going back is a new version (ADR-0113)
    await expect(history).toHaveAttribute("open", ""); // still open from the chat's change
    await expect(byChat.locator("[data-testid^=version-run-]")).toContainText("Run: Holds, R =");
    const ticks = history.locator("input[type=checkbox]");
    await ticks.nth(0).check();
    await ticks.nth(1).check();
    await expect(page.getByTestId("history-compare")).toContainText("First-ply failure");
    await page.screenshot({ path: ".local/website/screenshots/model-tree-history.png" });
    await page.getByTestId("history-undo").click();
    await expect(page.locator("#studio-element_size")).toHaveValue("2"); // the blank form's own, before the message
    await expect(history.locator("ol.ws-history > li").first()).toContainText("Back to version", { timeout: 5_000 });
    expect(browserErrors).toEqual([]);
  });

  test("a founder sets up a plate on the tree: held and loaded by the chat, by a click on the model and on its tabs (ADR-0089 amendment 7, ADR-0111)", async ({ page }) => {
    const browserErrors: string[] = [];
    page.on("pageerror", (error) => browserErrors.push(error.message));
    const calls = { checks: [] as unknown[], solves: [] as unknown[] };
    await mockApi(page, calls, { allTests: false, plates: true }); // the product's view, as a founder's sign-in is offered it
    await page.route(API, async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname;
      const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
      if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
      if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
      // what the API's guard keeps of a model's reading (api/tests/test_plate_proposals.py): "fix" holds all six, "pull" is a force outward
      return json({ run_id: "run-p", writer: "anthropic", model: "claude-stand-in", proposals: [], conditions: [], question: null, dropped: [], reason: null, unread: [],
        supports: [{ region: "Edge-Left", dofs: [1, 2, 3, 4, 5, 6], quote: "fix the left edge" }],
        loads: [{ region: "Edge-Right", kind: "force", dof: 1, value: "10000", unit: "N", written_value: "10", written_unit: "kN", sense: "tension",
          quote: "pull the right edge with 10 kN" }] });
    });
    await page.goto("/workspace/fea?for=coupon");
    const screen = page.getByTestId("tension-screen");
    await page.getByTestId("panel-test").locator("summary").click();
    await screen.getByRole("radio", { name: "Plate", exact: true }).check();
    await expect(page.getByTestId("panel-test").locator(".ws-panel-note")).toHaveText("Plate, held and loaded where you say");
    await expect(page.getByTestId("tension-standard")).toHaveCount(0); // a plate follows no test standard
    await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
    await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
    await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
    await page.locator("#studio-length").fill("100");
    await page.locator("#studio-width").fill("100");
    await expect(page.getByTestId("tension-missing")).toHaveText("Still needed: a boundary condition, a load.");
    await expect(page.getByTestId("panel-conditions")).toHaveAttribute("data-state", "missing");
    // said in the chat: read into the plate's lists, applied, and the tab that holds them opened and marked
    const message = page.getByLabel("Message the coupon assistant", { exact: true });
    await expect(message).toHaveAttribute("placeholder", /hold this edge/);
    await message.fill("fix the left edge and pull the right edge with 10 kN");
    await message.press("Enter");
    const card = page.getByTestId("proposal-card").last();
    await expect(card.locator("[data-key='support:0']")).toContainText("Edge-Left");
    await watchMarks(page);
    await card.getByTestId("proposal-apply").click();
    const conditions = page.getByTestId("panel-conditions");
    await expect(conditions).toHaveAttribute("open", "");
    await expect.poll(() => marked(page)).toContain("panel-conditions");
    await expect(page.getByTestId("plate-words-supports")).toContainText("Edge-Left holds x, y, z, tilt about x, tilt about y, rotation about z");
    await expect(page.getByTestId("plate-supports")).toContainText("θx"); // the directions in no program's notation on the tree
    await expect(page.getByTestId("plate-supports")).not.toContainText("UR1");
    await expect(page.getByTestId("panel-loads").locator(".ws-panel-note")).toHaveText("1 on Edge-Right");
    await expect(page.getByTestId("tension-missing")).toHaveCount(0);
    await expect.poll(() => calls.checks.length).toBe(1); // applied, the setup is checked with the lists and the model appears
    const first = (calls.checks[0] as { values: Record<string, unknown> }).values;
    expect([first.test, first.supports, first.loads]).toEqual(["plate", [{ region: "Edge-Left", dofs: [1, 2, 3, 4, 5, 6] }], [{ region: "Edge-Right", dof: 1, total: 10000 }]]);
    // a warning is said in the tab it is about, naming what is missing, and the chat's warning opens that tab (ADR-0111 amendment 2)
    await expect(page.getByTestId("warnings-material")).toContainText("it needs F1t, F1c, F2t, F2c and F6");
    // folded first, by the page's own property: a click on its summary was lost once in Firefox on CI, and folding is not what
    // this checks (ADR-0114)
    await page.getByTestId("panel-material").evaluate((panel) => { (panel as HTMLDetailsElement).open = false; });
    await expect(page.getByTestId("panel-material")).not.toHaveAttribute("open", "");
    await page.getByTestId("chat-check").last().getByRole("button", { name: "Open Material" }).click();
    await expect(page.getByTestId("panel-material")).toHaveAttribute("open", "");
    // clicked on the model: the face is loaded from the click, and the Loads tab opens with its row to fill in
    await expect(page.getByTestId("preview")).toBeVisible();
    await expect(async () => { // the scene takes a click once it has drawn the new model
      const box = (await page.getByTestId("studio-scene").locator("canvas").boundingBox())!;
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await expect(page.getByTestId("picked-regions")).toContainText("Face", { timeout: 1_500 });
    }).toPass({ timeout: 20_000 });
    await page.screenshot({ path: ".local/website/screenshots/model-tree-plate-click.png" });
    await page.getByTestId("picked-regions").getByRole("button", { name: "load" }).last().click();
    const loads = page.getByTestId("panel-loads");
    await expect(loads).toHaveAttribute("open", "");
    await expect(page.getByTestId("plate-words-loads")).toContainText("Face under a pressure of ? MPa");
    await page.getByLabel("Load 2 pressure", { exact: true }).fill("0.01");
    await expect(page.getByTestId("plate-words-loads")).toContainText("Face under a pressure of 0.01 MPa");
    await page.screenshot({ path: ".local/website/screenshots/model-tree-plate.png" });
    await page.getByTestId("build-button").click();
    await expect.poll(() => calls.solves.length).toBe(1);
    const sent = (calls.checks.at(-1) as { values: Record<string, unknown> }).values;
    expect(sent.loads).toEqual([{ region: "Edge-Right", dof: 1, total: 10000 }, { region: "Face", pressure: 0.01 }]);
    expect(sent.input).toBeUndefined(); // every row is sent for a plate, not the tension screen's own
    const said = (await page.getByTestId("coupon-chat").innerText()).toLowerCase();
    for (const word of ["claude", "anthropic", "model", "abaqus"]) expect(said).not.toContain(word);
    expect(browserErrors).toEqual([]);
  });

  test("a customer's tree offers no plate (ADR-0089 amendment 7)", async ({ page }) => {
    const calls = { checks: [] as unknown[], solves: [] as unknown[] };
    await mockApi(page, calls, { allTests: false });
    await page.goto("/workspace/fea?for=coupon");
    await expect(page.getByTestId("tension-screen")).toBeVisible();
    await expect(page.getByTestId("tree-kind")).toHaveCount(0);
    await expect(page.getByTestId("chat-spec")).toHaveCount(0); // the tree says the setup: no summary strip above the model (ADR-0111)
  });
});

test("a run ends without its PDF; Report (PDF) writes it when asked, says so, and downloads it when it is ready (ADR-0064 amendment 3)", async ({ page, browserName }) => {
  const calls: Parameters<typeof mockApi>[1] = { checks: [], solves: [] };
  // the run as the hosted tier now ends it: no PDF among its files, and what the report is typeset from kept in its place
  const { document: _pdf, ...kept } = fixture("job-done").outputs as Record<string, string>;
  const done = { ...fixture("job-done"), outputs: { ...kept, document_source: ".local/fea/IM7-UNT-L1/ours/runs/attempt-02_2026-10-28/run/IM7-UNT-L1-report-source.zip" } };
  let asked = 0, pollsSince = 0, fails = true;
  await mockApi(page, calls, {
    allTests: false,
    jobs: (poll) => {
      if (poll === 0) return fixture("job-running");
      if (poll < 3) return fixture("job-result-in");
      if (!asked) return done;
      pollsSince += 1;
      if (pollsSince < 3) return { ...done, report: "writing" };
      return fails ? { ...done, report: "failed" } : { ...done, outputs: { ...done.outputs, document: ".local/fea/IM7-UNT-L1/documents/2026-10-28_IM7-UNT-L1/IM7-UNT-L1.pdf" } };
    },
    report: () => { asked += 1; pollsSince = 0; return { status: 202, body: { ...done, report: "writing" } }; },
  });
  await page.goto("/workspace/fea?for=coupon");
  await expect.poll(() => calls.wakes ?? 0).toBe(1); // the page opened: a solver is asked for before any run (ADR-0056 amendment 11)
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await page.getByTestId("build-button").click();
  await expect.poll(() => calls.solves.length).toBe(1);
  expect((calls.solves[0] as { pdf: boolean }).pdf).toBe(false); // the run is asked for no PDF
  expect(calls.wakes).toBe(1); // the check that passed asks again only after ten minutes

  const files = page.getByTestId("tension-files");
  const ask = files.locator("button[data-key=document]");
  await expect(ask).toHaveText("Report (PDF)", { timeout: 45_000 });
  await expect(ask).toHaveAttribute("data-state", "idle");
  await expect(files.getByTestId("report-note")).toHaveText("Written when you ask for it, in about half a minute.");
  await expect(files.locator("a[data-key=document]")).toHaveCount(0);
  await expect(page.getByTestId("job-state")).toHaveText("Done"); // the report can be had: the run's last step is ticked
  await expect(page.getByTestId("job-progress").locator("li[data-step=report]")).toHaveAttribute("data-state", "done");
  expect(calls.reports ?? 0).toBe(0); // nothing is written before someone asks

  await ask.click(); // the first try fails at the service: the page says so and offers it again
  await expect(ask).toBeDisabled();
  await expect(files.getByTestId("report-note")).toHaveText("Writing the report. It downloads when it is ready, in about half a minute.");
  await expect(files.getByTestId("report-note")).toHaveText("The report could not be written. Try again; if it keeps failing, contact us.", { timeout: 20_000 });
  await expect(ask).toBeEnabled();
  expect(calls.reports).toBe(1);
  expect(calls.reportReads ?? []).toEqual([]);

  fails = false;
  // Playwright's WebKit gives no download event for a file its route handler answers, so there the read of the file below stands for it (ADR-0114)
  const download = browserName === "webkit" ? null : page.waitForEvent("download");
  await ask.click();
  await expect(files.locator("a[data-key=document]")).toHaveText("Report (PDF)", { timeout: 20_000 }); // written: a file like the others
  await expect(files.locator("a[data-key=document]")).toHaveAttribute("download", "D3039_[45,0,-45,90]s_report.pdf");
  await expect(files.locator("button[data-key=document]")).toHaveCount(0);
  await expect(files.getByTestId("report-note")).toHaveCount(0);
  await download; // and it came down by itself, under the page's name for it
  expect(calls.reports).toBe(2);
  await expect.poll(() => calls.reportReads).toEqual(["?name=D3039_%5B45%2C0%2C-45%2C90%5Ds_report.pdf"]);
  expect(bannedIn(await files.innerText())).toEqual([]);
});

test("a coupon solved under a test standard shows the quantities the standard reduces a test to (ADR-0072)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
  await expect(page.getByTestId("coupon-tool")).toContainText("Coupon FEA"); // the first question lists the tools, by the workspace's one name
  await page.goto("/studio/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page).toHaveURL(/\/workspace\/fea\/view\/?\?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00$/);
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
});

test("the guided chat asks one thing at a time, checks the setup itself, reads typed changes and runs (ADR-0055)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
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
  // the chat's card leads with the answer the page leads with (ADR-0085), the gauge section's, and says the grip edge's apart
  await expect(page.getByTestId("chat-result-answer")).toHaveText("First-ply failureHoldsR = 1.032, Tsai-Hill, ply 4 · 90°, the gauge section");
  await expect(page.getByTestId("chat-result-outside")).toHaveText("At a grip edge R = 1.013, reported apart: stress there grows with a finer mesh.");
  await expect(page.getByTestId("answer-headline")).toContainText("Holds at the applied loading");
  await expect(page.getByTestId("chat-result")).toContainText("Verified against reference solver: 57 of 57 values agree", { timeout: 15_000 });
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-chat.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("the assistant answers a question about a ply's stress from the results on the page, reads “here” as the clicked element and frames the place (ADR-0099)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  await say("what is the stress on ply 5 at element 125?"); // asked before anything is solved: no number, and the setup is not touched
  await expect(page.getByTestId("chat-value-none")).toContainText("then ask again");
  expect(calls.checks).toHaveLength(1);
  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("chat-ask-hint")).toContainText("at element");

  const fields = fixture("fields");
  const element = fields.mesh.element_labels.indexOf("Strip-1.125");
  await say("what is the stress on ply 5 at element 125?");
  const card = page.getByTestId("chat-values").last();
  await expect(card).toHaveAttribute("data-element", "125");
  await expect(card).toHaveAttribute("data-source", "run");
  const cells = card.getByTestId("chat-values-table").locator("tr[data-ply='5'] td");
  await expect(cells).toHaveText((fields.element.ply.stress_12[element][4] as number[]).map((v) => printed(v))); // the fields' own numbers, printed as the probe table prints them
  await expect(card.getByTestId("chat-values-note")).toBeHidden(); // how the values are taken is folded under Details
  await card.getByText("Details", { exact: true }).click();
  await expect(card.getByTestId("chat-values-note")).toContainText("Element centroid, no averaging, fibre axes");
  // the viewer frames the place: the element is read out with every ply, and the model shows σ₁ of ply 5
  await expect(page.getByTestId("probe")).toContainText("Ply results at element 125");
  await expect(page.getByLabel("Field", { exact: true })).toHaveValue("S11");
  await expect(page.getByLabel("Ply", { exact: true })).toHaveValue("5");
  expect(calls.checks).toHaveLength(1); // a question changes no row and asks the service nothing

  await say("s11 in ply 2 at element 125");
  await expect(page.getByTestId("chat-value").last()).toHaveText(`σ₁ = ${printed(fields.element.ply.stress_12[element][1][0])} MPa`); // the value is the heading
  await expect(page.getByTestId("chat-value-facts").last()).toContainText("ply 2 (0°) · element 125");

  // “here” is the element picked on the model: the answer card's Show picks the governing element
  await page.getByTestId("answer-table").locator("tr[data-criterion=tsai_hill] button").click();
  const title = await page.getByTestId("probe").locator("summary").innerText();
  const here = title.replace("Ply results at element ", "").trim();
  await say("shear strain here, ply 3");
  const picked = fields.mesh.element_labels.indexOf(`Strip-1.${here}`);
  await expect(page.getByTestId("chat-value").last()).toHaveText(`γ₁₂ = ${printed(fields.element.ply.strain_12[picked][2][2])}`);
  await expect(page.getByTestId("chat-value-facts").last()).toContainText(`ply 3 (-45°) · element ${here}`);

  await say("stress on ply 5 at element 1212");
  await expect(page.getByTestId("chat-value-refused").last()).toHaveText("This model has no element 1212. Its elements are numbered 1 to 250.");
  await say("stress on ply 9 at element 12");
  await expect(page.getByTestId("chat-value-refused").last()).toContainText("there is no ply 9");
  // a question the patterns do not read is told so; it is never read as a row of the setup ("compression" is a test's name).
  // A question of why is answered in words (ADR-0102)
  await say("which is worse here, tension or compression?");
  await expect(page.getByTestId("chat-value-unread")).toContainText("where is the shear stress highest?");
  expect(calls.checks).toHaveLength(1);
  await expect(page.getByTestId("chat-spec")).toContainText("unnotched tension");
  // an earlier answer shows its place again
  await page.getByTestId("chat-values").first().getByTestId("chat-values-show").click();
  await expect(page.getByTestId("probe")).toContainText("Ply results at element 125");
  expect(bannedIn(await page.getByTestId("coupon-chat").innerText()), "the assistant's answers about a result").toEqual([]); // the product's own words (ADR-0091)
  expect(browserErrors).toEqual([]);
});

test("the assistant keeps the thread: a missing place is the gauge centre, a fragment follows the question before it, an element is explained, and a statement back gets a yes (ADR-0099 amendment 3)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });

  const fields = fixture("fields");
  const centre = fields.summary.gauge_centre;
  const number = centre.label.split(".").pop();
  // no element named and none clicked: the gauge centre, said in one line, never "Which element?"
  await say("what is the stress at ply 7");
  const first = page.getByTestId("chat-values").last();
  await expect(first).toHaveAttribute("data-place", "gauge centre");
  await expect(first).toHaveAttribute("data-element", number);
  await expect(first.getByTestId("chat-values-table").locator("tr[data-ply='7'] td")).toHaveText((fields.element.ply.stress_12[centre.element][6] as number[]).map((v) => printed(v)));
  await expect(first.getByTestId("chat-value-facts")).toHaveText("gauge centre");
  await expect(first.getByTestId("chat-value-default")).toContainText("No element was named, so this is the gauge centre.");
  await expect(page.getByTestId("probe")).toContainText(`Ply results at element ${number}`);

  // a fragment keeps the place and the quantity of the question before it, then the ply
  await say("now in ply 5");
  const second = page.getByTestId("chat-values").last();
  await expect(second).toHaveAttribute("data-element", number);
  await expect(second.getByTestId("chat-values-table").locator("tr[data-ply='5'] td")).toHaveText((fields.element.ply.stress_12[centre.element][4] as number[]).map((v) => printed(v)));
  await say("sigma 1");
  await expect(page.getByTestId("chat-value").last()).toHaveText(`σ₁ = ${printed(fields.element.ply.stress_12[centre.element][4][0])} MPa`);
  await expect(page.getByTestId("chat-value-facts").last()).toContainText(`ply 5 (90°) · element ${number}`); // the place shown on the model stays the place
  // a comparison measure typed loosely is read, for the same ply and place, and says what it is not
  await say("von misses");
  await expect(page.getByTestId("chat-value").last()).toHaveText(`Mises = ${printed(probeTable(fields, centre.element).rows[4].values[3])} MPa`);
  await expect(page.getByTestId("chat-value-facts").last()).toContainText(`ply 5 (90°) · element ${number}`);
  await expect(page.getByTestId("chat-value-caution").last()).toContainText("not composite failure criteria");
  await say("and at element 125");
  await expect(page.getByTestId("chat-values").last()).toHaveAttribute("data-element", "125");
  await expect(page.getByTestId("chat-values").last()).toHaveAttribute("data-place", "named");
  await expect(page.getByTestId("chat-value-facts").last()).toContainText("ply 5 (90°) · element 125");

  // what an element is: the thing and where it sits, never a question about quantities; "it" is the element spoken of
  await say("what does element 183 represent");
  const what = page.getByTestId("chat-element").last();
  await expect(what).toHaveAttribute("data-element", "183");
  await expect(what).toHaveAttribute("data-where", "gauge");
  await expect(what.locator("h4")).toHaveText("Element 183");
  await expect(what.getByTestId("chat-element-what")).toContainText("One of the 250 small four-sided pieces the model is divided into");
  await expect(what.getByTestId("chat-element-where")).toContainText("in the gauge section, where the answer is read");
  await expect(page.getByTestId("probe")).toContainText("Ply results at element 183");
  await say("what does it represent");
  await expect(page.getByTestId("chat-element")).toHaveCount(2);
  await expect(page.getByTestId("chat-element").last()).toHaveAttribute("data-element", "183");
  await page.getByTestId("chat-element").last().getByTestId("chat-element-stress").click();
  await expect(page.getByTestId("chat-values").last()).toHaveAttribute("data-element", "183");
  await say("what is an element?");
  await expect(page.getByTestId("chat-element").last().locator("h4")).toHaveText("An element");
  await say("what does element 1212 represent");
  await expect(page.getByTestId("chat-value-refused").last()).toHaveText("This model has no element 1212. Its elements are numbered 1 to 250.");

  // the failure card shows the applied state beside the failure state; the same answer stated back, with the page's numbers, gets a yes
  const s = fields.summary;
  const row = s.fpf_gauge[s.verdict.earliest];
  const now = `${printed(s.applied.value)} mm, ${printed(s.reaction.value)} N`;
  const failing = `${printed(row.at_failure.applied)} mm, ${printed(row.at_failure.reaction)} N`;
  await say("which ply fails first?");
  const card = page.getByTestId("chat-failure").last();
  await expect(card.getByTestId("chat-failure-ply")).toHaveText("Ply 4 (90°) fails first");
  await expect(card.getByTestId("chat-failure-applied")).toHaveText(`Applied: ${now}.`);
  await say(`does it mean that once it reaches ${printed(s.applied.value)} mm it got ${printed(s.reaction.value)} N, but for the first ply failure its ${printed(row.at_failure.reaction)} N`);
  const yes = page.getByTestId("chat-failure").last();
  await expect(yes.getByTestId("chat-failure-yes")).toHaveText("Yes");
  await expect(yes.getByTestId("chat-failure-loading")).toHaveText(`At the applied ${now} no ply has failed. Ply 4 (90°) fails first at ${printed(row.factor)} × that: ${failing}.`);
  // a statement with a number the page does not print is told no, with both states as the page prints them (ADR-0099 amendment 4)
  await say("does it mean that it fails at 20000 N");
  const no = page.getByTestId("chat-failure").last();
  await expect(no.getByTestId("chat-failure-yes")).toHaveCount(0);
  await expect(no.getByTestId("chat-failure-no")).toHaveText("No");
  await expect(no.getByTestId("chat-failure-loading")).toHaveText(`At the applied ${now} no ply has failed. Ply 4 (90°) fails first at ${printed(row.factor)} × that: ${failing}.`);

  expect(calls.checks).toHaveLength(1); // a question changes no row and asks the service nothing
  await expect(page.getByTestId("chat-spec")).toContainText("unnotched tension");
  expect(bannedIn(await page.getByTestId("coupon-chat").innerText()), "the assistant's answers about a result").toEqual([]);
  await page.getByTestId("coupon-chat").screenshot({ path: ".local/website/screenshots/studio-chat-thread.png" });
  expect(browserErrors).toEqual([]);
});

test("with a model on, a loose question about the results is read into a fixed request and answered with the solver's values; the model is sent no result (ADR-0100)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const offers: Record<string, unknown>[] = [];
  let proposalsAsked = 0;
  // a model behind the API: its readings, as the guard would keep them
  const readings: Record<string, unknown> = {
    "where's the shearing worst?": { kind: "extreme", quantities: ["S12"], plies: [], element: null, here: false, sense: "magnitude", region: "default" },
    "which ply carries the most load?": { kind: "extreme", quantities: ["S11"], plies: [], element: null, here: false, sense: "magnitude", region: "default" },
    "compare the 0° and 90° plies here": { kind: "values", quantities: ["S11", "S22", "S12"], plies: [2, 4, 5, 7], element: null, here: true, sense: null, region: "default" },
    "worst transverse loading anywhere, grips included?": { kind: "extreme", quantities: ["S22"], plies: [], element: null, here: false, sense: "magnitude", region: "whole" },
    "whats the weakest layer": { kind: "failure", quantities: [], plies: [], element: null, here: false, sense: null, region: "default" },
  };
  await mockApi(page, calls);
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path === "/v1/workspace/proposals" && request.method() === "POST") {
      proposalsAsked += 1;
      return json({ run_id: "run-p", writer: "anthropic", model: "claude-stand-in", proposals: [], conditions: [], question: null, dropped: [], reason: null });
    }
    if (path !== "/v1/workspace/result-questions" || request.method() !== "POST") return route.fallback();
    const offer = request.postDataJSON() as Record<string, unknown>;
    offers.push(offer);
    const read = readings[offer.message as string] ?? null;
    return json({ run_id: "run-q", writer: "anthropic", model: "claude-stand-in", request: read, question: null, dropped: [], reason: null });
  });
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });
  const fields = fixture("fields");

  // the page's own patterns read a plain question: no model is asked
  await say("where is the shear stress highest?");
  const plain = page.getByTestId("chat-extremes").first();
  await expect(plain).toHaveAttribute("data-reader", "patterns");
  await expect(plain).toHaveAttribute("data-region", "the gauge section");
  expect(offers).toHaveLength(0);

  // and one with its words misspelt (ADR-0121 amendment 2)
  await say("wher is teh shear highest?");
  await expect(page.getByTestId("chat-extremes")).toHaveCount(2);
  await expect(page.getByTestId("chat-extremes").last()).toHaveAttribute("data-reader", "patterns");
  expect(offers).toHaveLength(0);

  // a loose one goes to the model, which answers with a request; the page looks the values up
  await say("where's the shearing worst?");
  const loose = page.getByTestId("chat-extremes").last();
  await expect(loose).toHaveAttribute("data-reader", "model");
  await expect(loose.getByTestId("chat-extreme")).toHaveText(await plain.getByTestId("chat-extreme").innerText()); // the same answer, whoever read the question
  const written = fields.summary.ply_extremes.overall.S12.largest;
  await expect(loose.getByTestId("chat-extreme")).toContainText(`${printed(-Math.abs(written.value))} MPa`); // the package's own largest shear, on the element first in the mesh
  await expect(loose.getByTestId("chat-extreme-facts")).toContainText("gauge section");
  await expect(loose.getByTestId("chat-extremes-table")).toBeHidden(); // each ply's own extreme is folded under Details
  await loose.getByText("Details", { exact: true }).click();
  await expect(loose.getByTestId("chat-extremes-table").locator("tbody tr")).toHaveCount(8);
  await expect(loose.getByTestId("chat-extremes-note")).toContainText("130 elements read");
  await expect(page.getByLabel("Field", { exact: true })).toHaveValue("S12");
  expect(offers).toHaveLength(1);
  expect(Object.keys(offers[0]).sort()).toEqual(["gauge", "message", "picked", "plies", "quantities"]); // the offer: no value of the results
  expect(offers[0].plies).toEqual(fields.mesh.angles.map((angle: number, i: number) => ({ ply: i + 1, angle })));
  expect(offers[0].picked).toBe(true); // the first answer's place is the element read out on the model

  await say("which ply carries the most load?");
  const load = page.getByTestId("chat-extremes").last();
  await expect(load.getByTestId("chat-extreme")).toHaveText(`Largest |σ₁|: ${printed(fields.summary.ply_extremes.overall.S11.tension.value)} MPa`);
  await expect(load.getByTestId("chat-extreme-facts")).toContainText("ply 2 (0°)");
  await expect(load.getByTestId("chat-extreme-facts")).toContainText("gauge section · tied with ply 7");

  await say("compare the 0° and 90° plies here");
  const compared = page.getByTestId("chat-values").last();
  await expect(compared.locator("h4")).toContainText("plies 2, 4, 5, 7");
  await expect(compared.getByTestId("chat-values-table").locator("tbody tr")).toHaveCount(4);

  await say("worst transverse loading anywhere, grips included?");
  const whole = page.getByTestId("chat-extremes").last();
  await expect(whole).toHaveAttribute("data-region", "the whole model");
  await expect(whole.getByTestId("chat-extremes-grip")).toHaveText("At a grip edge, so it grows with a finer mesh. Ask for the gauge section.");

  // which ply fails is the package's own answer, never a table of the largest stresses (ADR-0099 amendment 1): the page's patterns
  // read it with no model asked, and a loose wording the model reads as the kind failure gets the same answer
  const asked = offers.length;
  await say("what is the the ply that fails");
  const failing = page.getByTestId("chat-failure").last();
  const governs = fields.summary.fpf_gauge[fields.summary.verdict.earliest];
  await expect(failing).toHaveAttribute("data-reader", "patterns");
  await expect(failing).toHaveAttribute("data-criterion", fields.summary.verdict.earliest);
  await expect(failing.getByTestId("chat-failure-ply")).toHaveText(`Ply ${governs.ply} (${governs.angle}°) fails first`);
  await expect(failing.getByTestId("chat-failure-loading")).toContainText(`At ${printed(governs.factor)} × the applied load`);
  await expect(failing.getByTestId("chat-failure-loading")).toContainText("The coupon holds.");
  await expect(failing.getByTestId("chat-failure-facts")).toContainText("Tsai-Hill · combined stresses · element 183 · gauge section");
  await expect(failing.getByTestId("chat-failure-table")).toBeHidden(); // the rest is folded away until asked for
  await failing.getByText("Details", { exact: true }).click();
  await expect(failing.getByTestId("chat-failure-table").locator("tbody tr")).toHaveCount(Object.keys(fields.summary.fpf_gauge).length);
  await expect(failing.getByTestId("chat-failure-note")).toContainText("from each tab line");
  await expect(page.getByLabel("Field", { exact: true })).toHaveValue("failure_index_ply"); // shown on the model: that ply's failure index
  expect(offers).toHaveLength(asked);
  await say("whats the weakest layer");
  const weakest = page.getByTestId("chat-failure").last();
  await expect(weakest).toHaveAttribute("data-reader", "model");
  await expect(weakest.getByTestId("chat-failure-ply")).toHaveText(await failing.getByTestId("chat-failure-ply").innerText());
  expect(offers).toHaveLength(asked + 1);

  // a message the model reads as nothing of the results goes on to the setup's reading, and a setup line never asks about results
  expect(proposalsAsked).toBe(0);
  await say("which is worse here, tension or compression?"); // a question, though the setup's patterns know "compression": the model is asked first,
  await expect(page.getByTestId("chat-value-unread")).toBeVisible(); // and with nothing read, it is told so and no row changes (a question of why is ADR-0102's)
  expect(offers).toHaveLength(6);
  expect((offers[5] as { message: string }).message).toBe("which is worse here, tension or compression?");
  await expect(page.getByTestId("chat-spec")).toContainText("unnotched tension");
  await say("thanks, looks good");
  await expect(page.getByTestId("chat-redirect").last()).toBeVisible();
  expect(offers).toHaveLength(7);
  expect(proposalsAsked).toBe(2);
  expect(bannedIn(await page.getByTestId("coupon-chat").innerText()), "the assistant's answers about a result").toEqual([]);
  expect(browserErrors).toEqual([]);
});

test("a question of why is answered in words from the results and our theory pages, the section named, and no row changes (ADR-0102)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const asked: { question: string; facts: Record<string, unknown> }[] = [];
  let readings = 0;
  const FAILURE = { id: "engine:5-failure", document: "Laminate theory", title: "5. Failure" };
  const PLIES = { id: "fea:6-ply-stresses-in-material-axes", document: "Finite element theory", title: "6. Ply stresses in material axes" };
  const written = { run_id: "run-w", writer: "anthropic", model: "claude-stand-in", withheld: false, reason: null };
  // a model behind the API: its answers, as the number guard would keep them, or none
  const answers: Record<string, unknown> = {
    "why does ply 4 fail first?": { ...written, covered: true, sources: [FAILURE],
      prose: ["Ply 4 (90 degrees) fails first, across its fibres.", "Its sigma_2 is 60.6 MPa there.", "By Tsai-Hill that is at 1.032 times the applied loading."] },
    "why is ply 4 in compression?": { ...written, covered: false, sources: [],
      prose: ["The results show ply 4 (90 degrees) at -364.8 MPa along its fibres.", "The theory pages do not explain this yet."] },
    "what does the failure index mean?": { ...written, writer: "template", model: null, covered: false, withheld: true, reason: "numbers", prose: [], sources: [FAILURE, PLIES] },
  };
  await mockApi(page, calls);
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if ((path === "/v1/workspace/proposals" || path === "/v1/workspace/result-questions") && request.method() === "POST") {
      readings += 1;
      return json({ run_id: "run-p", writer: "template", model: null, proposals: [], conditions: [], request: null, question: null, dropped: [], reason: null });
    }
    if (path !== "/v1/workspace/result-answers" || request.method() !== "POST") return route.fallback();
    const body = request.postDataJSON() as { question: string; facts: Record<string, unknown> };
    asked.push(body);
    return body.question in answers ? json(answers[body.question]) : json({ detail: "the service is busy" }, 503);
  });
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");

  // before a result there is nothing to answer from: the page says so, nothing is sent, and no row changes
  const before = readings;
  await say("why is ply 4 in compression?");
  await expect(page.getByTestId("chat-why-none")).toHaveText("A question of why is answered from a solved model. Say “run”, then ask again.");
  expect(asked).toHaveLength(0);
  await expect(page.getByTestId("chat-spec")).toContainText("unnotched tension"); // "compression" in a question is not the test

  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });

  // answered in words: the fact sheet of the result on the page goes with the question; the first sentence is the heading, and the section
  // is named under Details (ADR-0102 amendment 1)
  await say("why does ply 4 fail first?");
  const why = page.getByTestId("chat-why").last();
  await expect(why).toHaveAttribute("data-answered", "yes");
  await expect(why).toHaveAttribute("data-covered", "yes");
  await expect(why).toHaveAttribute("data-source", "run");
  await expect(why.getByTestId("chat-why-answer")).toHaveText("Ply 4 (90 degrees) fails first, across its fibres.");
  await expect(why.getByTestId("chat-why-sentence")).toHaveText(["Its σ₂ is 60.6 MPa there.", "By Tsai-Hill that is at 1.032 times the applied loading."]);
  await expect(why.getByTestId("chat-why-note")).toHaveText("Read in the gauge section. From the results and our theory pages.");
  await expect(why.getByTestId("chat-why-sources")).not.toHaveAttribute("open");
  await why.getByTestId("chat-why-sources").getByText("Details", { exact: true }).click();
  await expect(why.getByTestId("chat-why-sources")).toContainText("Our theory pages: Laminate theory, 5. Failure.");
  await expect(why.getByTestId("chat-why-working")).toHaveText("Show the working"); // the formulas with the numbers put in are one click away (ADR-0103)
  expect(asked).toHaveLength(1);
  expect(Object.keys(asked[0]).sort()).toEqual(["facts", "question"]);
  expect(asked[0].facts).toEqual(fixture("explanation").facts); // the engine's fact sheet, as the job wrote it

  // a reason the pages do not hold is said to be missing, and nothing is cited; the setup's patterns do not read "compression"
  await say("why is ply 4 in compression?");
  const uncovered = page.getByTestId("chat-why").last();
  await expect(uncovered).toHaveAttribute("data-covered", "no");
  // a first sentence too long for a heading (68 characters) stands whole under a fixed one (ADR-0121 amendment 7)
  await expect(uncovered.getByTestId("chat-why-answer")).toHaveText("Answered in words from the results");
  await expect(uncovered.getByTestId("chat-why-sentence").first()).toHaveText(`The results show ply 4 (90 degrees) at ${printed(-364.8)} MPa along its fibres.`);
  await expect(uncovered.getByTestId("chat-why-note")).toHaveText("Read in the gauge section. From the results only.");
  await expect(uncovered.getByTestId("chat-why-sources")).toHaveCount(0);
  await expect(page.getByTestId("chat-spec")).toContainText("unnotched tension");

  // an answer the guard set aside is not shown; the sections the question found are named
  await say("what does the failure index mean?");
  const withheld = page.getByTestId("chat-why").last();
  await expect(withheld).toHaveAttribute("data-answered", "no");
  await expect(withheld.getByTestId("chat-why-answer")).toHaveText("No answer in words");
  await expect(withheld.getByTestId("chat-why-sentence")).toHaveCount(0);
  await expect(withheld.getByTestId("chat-why-note")).toHaveText("The answer held a number the results do not, so it is not shown. See: Laminate theory, 5. Failure; Finite element theory, 6. Ply stresses in material axes.");

  await page.getByTestId("chat-why").first().scrollIntoViewIfNeeded();
  await page.getByTestId("coupon-chat").screenshot({ path: ".local/website/screenshots/studio-why.png" });

  // a service that does not answer is said plainly
  await say("explain the shear in ply 1");
  await expect(page.getByTestId("chat-why-failed")).toBeVisible();
  expect(asked).toHaveLength(4);

  // a question about a value is still the lookup's, and none of the questions of why was read as a row or a value
  await say("where is the shear stress highest?");
  await expect(page.getByTestId("chat-extremes").last()).toHaveAttribute("data-reader", "patterns");
  expect(asked).toHaveLength(4);
  expect(readings).toBe(before);
  expect(calls.checks).toHaveLength(1);
  expect(bannedIn(await page.getByTestId("coupon-chat").innerText()), "the assistant's answers of why").toEqual([]);
  expect(browserErrors).toEqual([]);
});

test("the working behind an answer is shown when asked: each formula with the solver's numbers put in, and no model is asked (ADR-0103)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  let asked = 0; // any call that would have a model read or write
  await mockApi(page, calls);
  await page.route(API, async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/v1/workspace/assistant") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ proposes: true, provider: "anthropic", model: "claude-stand-in" }) });
    if (/^\/v1\/workspace\/(proposals|result-questions|result-answers)$/.test(path)) { asked += 1; return route.fulfill({ status: 503, contentType: "application/json", body: "{}" }); }
    return route.fallback();
  });
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");

  // before a result there is no working: the page says so and changes no row
  await say("show me the formula");
  await expect(page.getByTestId("chat-working-none")).toHaveText("The working is written with a solved model. Say “run”, then ask again.");
  await expect(page.getByTestId("chat-working")).toHaveCount(0);

  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });
  const working = fixture("fields").summary.working;

  // one click under the results: the earliest criterion's chain, four steps, each formula typeset
  await page.getByTestId("chat-result-working").click();
  const first = page.getByTestId("chat-working").nth(0);
  await expect(first).toHaveAttribute("data-criterion", "tsai_hill");
  await expect(first).toHaveAttribute("data-source", "run");
  const hill = working.criteria.tsai_hill;
  await expect(first.getByTestId("chat-working-where")).toHaveText(`The first ply to fail in the gauge section: ply 4 (90°), element ${hill.element}, at ${printed(hill.factor)} times the applied loading.`);
  await expect(first.getByTestId("chat-working-step")).toHaveCount(4);
  await expect(first.getByTestId("chat-working-step").nth(0)).toHaveAttribute("data-step", "strain");
  await expect(first.getByTestId("chat-working-step").nth(3)).toHaveAttribute("data-step", "loading");
  const equations = hill.steps.reduce((n: number, step: { equations: unknown[] }) => n + step.equations.length, 0);
  await expect(first.getByTestId("chat-working-equation")).toHaveCount(equations);
  await expect(first.locator(".chat-working-equation .katex").first()).toBeVisible(); // typeset, not shown as source
  await expect(first.locator(".katex-error")).toHaveCount(0);
  // the values put in are the package's own, to six figures
  const criterion = first.locator('[data-step="criterion"]');
  await expect(criterion.getByTestId("chat-working-value").nth(1)).toHaveText("64.0523 MPa");
  await expect(criterion.locator("annotation").last()).toHaveText(hill.steps[2].equations[2].substituted.replaceAll("\\frac", "\\dfrac")); // R = 1/sqrt(FI), as the package wrote it
  await expect(criterion.getByTestId("chat-working-source")).toHaveText("From: Laminate theory, 5. Failure.");
  await expect(first.getByTestId("chat-working-note")).toContainText("Inputs are shown to 6 figures, results to 4.");

  // asked in words, with the criterion named: the engineer's own phrases
  await say("send me the formula for max stress");
  const second = page.getByTestId("chat-working").nth(1);
  await expect(second).toHaveAttribute("data-criterion", "max_stress");
  await expect(second.locator('[data-step="criterion"]').getByTestId("chat-working-text")).toContainText("σ₂ reaching F2t"); // the page's symbols, not sigma_2
  await expect(second.locator('[data-step="criterion"]').getByTestId("chat-working-equation").nth(1).locator("annotation").last()).toHaveText(working.criteria.max_stress.steps[2].equations[1].substituted.replaceAll("\\frac", "\\dfrac"));
  await say("the proof of it being solved");
  await expect(page.getByTestId("chat-working")).toHaveCount(3);
  await expect(page.getByTestId("chat-working").last()).toHaveAttribute("data-criterion", "tsai_hill");

  // a criterion with no working written is said, with the ones that have one
  await say("show the working for Tsai-Wu");
  await expect(page.getByTestId("chat-working-none").last()).toHaveText("The working of Tsai-Wu is not written yet. Ask for Maximum stress or Tsai-Hill.");

  // a quantity asked by name gets its one step, headed by it, with the whole working one click away (ADR-0103 amendment 1); the founder's
  // "equation for stress" was shown all four steps of Tsai-Hill (2026-11-20)
  await say("equation for stress");
  const stress = page.getByTestId("chat-working").last();
  await expect(stress).toHaveAttribute("data-step", "stress");
  await expect(stress.locator("h4")).toHaveText("The ply's stress from its strain");
  await expect(stress.getByTestId("chat-working-where")).toHaveText(`The first ply to fail in the gauge section: ply 4 (90°), element ${hill.element}, at ${printed(hill.factor)} times the applied loading, by Tsai-Hill.`);
  await expect(stress.getByTestId("chat-working-step")).toHaveCount(1);
  await expect(page.getByTestId("chat-working-stale")).toHaveCount(0); // the same result read again is not a changed setup (sameResults)
  await expect(stress.getByTestId("chat-working-equation")).toHaveCount(hill.steps[1].equations.length);
  await page.waitForTimeout(600); // the list has settled at its newest message
  await stress.evaluate((answer) => answer.scrollIntoView({ block: "start" }));
  await page.getByTestId("coupon-chat").screenshot({ path: ".local/website/screenshots/studio-working-step.png" });
  await stress.getByTestId("chat-working-all").click();
  await expect(page.getByTestId("chat-working").last()).toHaveAttribute("data-step", "all");
  await expect(page.getByTestId("chat-working").last().getByTestId("chat-working-step")).toHaveCount(4);

  await page.waitForTimeout(600); // the list has settled at its newest message
  await first.locator('[data-step="stress"]').evaluate((step) => step.scrollIntoView({ block: "start" }));
  await page.getByTestId("coupon-chat").screenshot({ path: ".local/website/screenshots/studio-working.png" });
  await first.locator('[data-step="criterion"]').evaluate((step) => step.scrollIntoView({ block: "start" }));
  await page.getByTestId("coupon-chat").screenshot({ path: ".local/website/screenshots/studio-working-criterion.png" });

  // nothing was sent to a model, nothing was checked or solved again, and no row changed
  expect(asked).toBe(0);
  expect(calls.checks).toHaveLength(1);
  expect(calls.solves).toHaveLength(1);
  await expect(page.getByTestId("chat-spec")).toContainText("unnotched tension");
  expect(bannedIn(await page.getByTestId("coupon-chat").innerText()), "the working").toEqual([]);
  expect(browserErrors).toEqual([]);
});

test("a thing to fix takes its rows in the chat, and applying them checks again (ADR-0062 amendment 2)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await hydrated(message);
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
  await page.goto("/workspace/fea?for=coupon");
  await hydrated(page.getByLabel("Message the coupon assistant", { exact: true }));
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
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await hydrated(message);
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
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await hydrated(message);
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

test("the assistant says which words it could not use and why, in place of “Not sure what to change” (ADR-0088 amendment 1)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const reading = { run_id: "run-p", writer: "anthropic", model: "claude-stand-in", conditions: [], question: null, dropped: [], reason: null };
  await mockApi(page, calls, { allTests: false }); // the product's view, as on the hosted tier: the unnotched tension coupon only
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    const said = (request.postDataJSON() as { message: string }).message;
    if (said.includes("16 plys")) {
      return json({ ...reading, proposals: [], unread: [{ quote: "same thing", reason: "refers_back" }, { quote: "compresion", reason: "not_offered" },
        { quote: "16 plys", reason: "no_value" }] });
    }
    if (said.includes("300")) {
      return json({ ...reading, unread: [{ quote: "like before", reason: "refers_back" }], proposals: [{ key: "length", label: "Length (mm)", value: "300",
        unit: "mm", written_value: "300", written_unit: "mm", quote: "300 mm long" }] });
    }
    return json({ ...reading, proposals: [], unread: [{ quote: "compression", reason: "not_offered" }] });
  });
  await page.goto("/workspace/fea?for=coupon");
  const chat = page.getByTestId("coupon-chat");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await hydrated(message);
  // the founder's message of 2026-11-16 on the live site: nothing in it can become a row, and the page now says why, part by part
  await message.fill("same thing but make it compresion and 16 plys");
  await message.press("Enter");
  const notUsed = page.getByTestId("chat-not-used");
  await expect(notUsed).toHaveCount(1);
  await expect(notUsed.locator("li")).toHaveText([
    /same thing.*each message is read on its own, so say the whole change/,
    /compresion.*not something you can set here yet/,
    /16 plys.*names no value to enter; state the value itself, for example a layup as \[0\/90\]2s/,
  ]);
  await expect(page.getByText("Not sure what to change")).toHaveCount(0);
  await expect(page.getByTestId("proposal-card")).toHaveCount(0);
  // a test the page knows by name keeps the page's own, fuller answer: the patterns read first
  await message.fill("make it compression");
  await message.press("Enter");
  await expect(page.getByTestId("chat-not-available")).toContainText("not offered yet");
  await expect(notUsed).toHaveCount(1);
  // beside values that were read, the card lists the words that were not
  await message.fill("300 mm long like before");
  await message.press("Enter");
  const card = page.getByTestId("proposal-card");
  await expect(card.locator("[data-key=length]")).toContainText("300 mm");
  await expect(card.getByTestId("proposal-unread")).toContainText("like before");
  await expect(card.getByTestId("proposal-unread")).toContainText("each message is read on its own");
  const said = (await chat.innerText()).toLowerCase();
  for (const word of ["claude", "anthropic", "model", "abaqus"]) expect(said).not.toContain(word);
});

/** The stand-in for the mesh scenarios: with `model`, the assistant has a model that answers a size that is not written as a model does,
 * with nothing to enter and the words it could not use (api/tests/test_proposals.py); every message it is sent is kept in `asked`. */
async function meshScenario(page: Page, model: boolean) {
  const calls = { checks: [] as unknown[], solves: [] as unknown[], lives: [] as unknown[] };
  const asked: string[] = [];
  await mockApi(page, calls, { allTests: true });
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant" && model) return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    asked.push((request.postDataJSON() as { message: string }).message);
    return json({ run_id: "run-p", writer: "anthropic", model: "claude-stand-in", proposals: [], conditions: [], question: null, dropped: [], reason: null,
      supports: [], loads: [], unread: [{ quote: "coarser", reason: "no_value" }] });
  });
  await page.goto("/workspace/fea?for=coupon");
  await page.getByRole("button", { name: "Load example" }).click();
  // the rows the page last asked a preview for: the new size goes to the package, which meshes it (the page computes no mesh)
  const sizeSent = () => (calls.lives.at(-1) as { values: Record<string, unknown> } | undefined)?.values.element_size;
  return { calls, asked, sizeSent, chat: page.getByTestId("coupon-chat"), message: page.getByLabel("Message the coupon assistant", { exact: true }) };
}

test("the mesh is changed by talking: a written element size, and finer as half the size held (ADR-0088 amendment 2)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const { calls, sizeSent, chat, message } = await meshScenario(page, false);
  // no model on: the page's own patterns read it, say the size before and after, and the preview is asked for with the new size.
  // “Who is running it?” is open, and “finer mesh” is not taken as the name
  await message.fill("finer mesh");
  await message.press("Enter");
  await expect(chat.locator(".chat-understood").last()).toContainText("element size 1 mm (half of 2 mm)");
  await expect.poll(sizeSent).toBe(1);
  await message.fill("use 4 mm elements");
  await message.press("Enter");
  await expect(chat.locator(".chat-understood").last()).toContainText("element size 4 mm");
  await expect.poll(sizeSent).toBe(4);
  // a question about the mesh changes nothing, and is not taken as the name either
  const livesBefore = calls.lives.length;
  await message.fill("would a finer mesh change the answer?");
  await message.press("Enter");
  await expect(page.getByTestId("chat-value-unread").last()).toContainText("is it ready to run?"); // a question is said so (ADR-0121 amendment 2)
  await page.waitForTimeout(1_200); // longer than the preview's wait after an edit
  expect(calls.lives.length).toBe(livesBefore);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-mesh-talk.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("with a model on, a mesh step the model cannot turn into a value is still read by the page (ADR-0088 amendment 2)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const { asked, sizeSent, chat, message } = await meshScenario(page, true);
  await message.fill("make the mesh coarser");
  await message.press("Enter");
  await expect(chat.locator(".chat-understood").last()).toContainText("element size 4 mm (twice 2 mm)");
  expect(asked).toEqual(["make the mesh coarser"]); // the model was asked first
  await expect(page.getByTestId("chat-not-used")).toHaveCount(0);
  await expect.poll(sizeSent).toBe(4);
  expect(browserErrors).toEqual([]);
});

test("a plate is held and loaded by talking: regions named in words, and “here” as the element clicked (ADR-0101)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const asked: { message: string; plate?: { regions: { name: string }[]; here: string[]; held: string[]; loaded: string[]; force_unit: string; stress_unit: string } }[] = [];
  const reading = { run_id: "run-p", writer: "anthropic", model: "claude-stand-in", proposals: [], conditions: [], question: null, dropped: [], reason: null, unread: [] };
  await mockApi(page, calls, { allTests: true });
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    const body = request.postDataJSON() as (typeof asked)[number];
    asked.push(body);
    if (body.message.includes("bottom edge")) { // what the API's guard keeps of a model's reading (api/tests/test_plate_proposals.py)
      return json({ ...reading, supports: [{ region: "Edge-Bottom", dofs: [1, 2, 3], quote: "hold the bottom edge" }],
        loads: [{ region: "Edge-Top", kind: "force", dof: 2, value: "10000", unit: "N", written_value: "10", written_unit: "kN", sense: "tension",
          quote: "pull the top edge with 10 kN in tension" }] });
    }
    return json({ ...reading, loads: [{ region: "Face", kind: "pressure", dof: null, value: "0.01", unit: "MPa", written_value: "0.01", written_unit: "MPa",
      sense: null, quote: "press here with 0.01 MPa" }],
      dropped: [{ key: "load on Edge-Left", reason: "the quoted words do not name Edge-Left, and it is not where you clicked" }] });
  });
  await page.goto("/workspace/fea?for=coupon");
  await page.getByRole("button", { name: "Load example" }).click();
  await pickTest(page, "plate");
  await page.getByLabel("Length (mm)", { exact: true }).fill("100");
  await page.getByLabel("Width (mm)", { exact: true }).fill("100");
  await page.getByLabel("Tab length (mm)", { exact: true }).fill("");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await expect(message).toHaveAttribute("placeholder", /hold this edge/);
  // with no model on the page yet, the regions are named in words
  await message.fill("hold the bottom edge and pull the top edge with 10 kN in tension");
  await message.press("Enter");
  const card = page.getByTestId("proposal-card").last();
  await expect(card.locator("[data-key='support:0']")).toContainText("Hold Edge-Bottom x, y, z");
  await expect(card.locator("[data-key='load:0']")).toContainText("Force on Edge-Top 10000 N along y");
  await expect(card.locator("[data-key='load:0']")).toContainText("written 10 kN; tension: pulling outward from the edge");
  expect(asked[0].plate?.regions.map((r) => r.name)).toEqual(["Edge-Bottom", "Edge-Top", "Edge-Left", "Edge-Right", "Face"]);
  expect(asked[0].plate).toMatchObject({ here: [], held: [], loaded: [], force_unit: "N", stress_unit: "MPa" });
  expect(calls.checks).toHaveLength(0); // nothing has entered the plate
  await expect(page.getByTestId("plate-words")).toHaveCount(0);
  await card.getByTestId("proposal-apply").click();
  await expect(page.getByTestId("plate-words")).toContainText("Edge-Bottom holds x, y, z");
  await expect(page.getByTestId("plate-words")).toContainText("Edge-Top loaded by 10000 N along y");
  // applied, the setup is checked with the lists, and the model appears with what is held and loaded
  await expect(page.getByTestId("preview")).toBeVisible();
  const first = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect(first.supports).toEqual([{ region: "Edge-Bottom", dofs: [1, 2, 3] }]);
  expect(first.loads).toEqual([{ region: "Edge-Top", dof: 2, total: 10000 }]);
  // an element clicked on the model is “here”: the page says which regions that is, and sends them with the next message
  await expect(page.getByTestId("chat-here")).toHaveCount(0);
  await expect(async () => { // the scene takes a click once it has drawn the new model: on a slow machine the first one can come too early
    const box = (await page.getByTestId("studio-scene").locator("canvas").boundingBox())!;
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
    await expect(page.getByTestId("picked-regions")).toContainText("Face", { timeout: 1_500 });
  }).toPass({ timeout: 20_000 });
  await expect(page.getByTestId("chat-here")).toContainText("Face");
  await message.fill("press here with 0.01 MPa");
  await message.press("Enter");
  const second = page.getByTestId("proposal-card").last();
  await expect(second.locator("[data-key='load:0']")).toContainText("Pressure on Face 0.01 MPa");
  await expect(second.getByTestId("proposal-dropped")).toContainText("it is not where you clicked");
  // proposed and not applied: drawn dashed on the model and listed apart from what is applied (ADR-0110)
  await expect(page.getByTestId("applied-proposed")).toContainText("Face: pressure 0.01 MPa");
  await expect(page.getByTestId("applied-conditions")).toContainText("Edge-Bottom: held along z, rotation about y"); // the checked preview's own (the stand-in package's)
  expect(asked[1].plate?.here).toContain("Face");
  expect(asked[1].plate).toMatchObject({ held: ["Edge-Bottom"], loaded: ["Edge-Top"] });
  await second.getByTestId("proposal-apply").click();
  await expect(page.getByTestId("plate-words")).toContainText("Face under a pressure of 0.01 MPa");
  await expect(page.getByTestId("applied-proposed")).toHaveCount(0);
  await expect.poll(() => calls.checks.length).toBe(2);
  expect((calls.checks[1] as { values: Record<string, unknown> }).values.loads).toEqual([{ region: "Edge-Top", dof: 2, total: 10000 }, { region: "Face", pressure: 0.01 }]);
  const said = (await page.getByTestId("coupon-chat").innerText()).toLowerCase();
  for (const word of ["claude", "anthropic", "model", "abaqus"]) expect(said).not.toContain(word);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-plate-talk.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a plate with nothing held shows its shape, and the first hold is the edge clicked (ADR-0101 amendment 1)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const lives: { values: { supports?: unknown[]; loads?: unknown[] } }[] = [];
  const asked: { message: string; plate?: { here: string[]; held: string[] } }[] = [];
  const full = fixture("preview", "studio-plate");
  await mockApi(page, calls, { allTests: true });
  await page.route(API, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/workspace/assistant") return json({ proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path === "/v1/coupon-jobs/live" && request.method() === "POST") { // the package's answer for a plate that states no support yet: blocked, with its shape
      const body = request.postDataJSON() as (typeof lives)[number];
      lives.push(body);
      if (body.values.supports?.length) return; // held: the scenario goes on with the check the apply sends
      const checklist = fixture("checklist", "studio-plate");
      checklist.state = "blocked";
      checklist.items = checklist.items.map((item: { id: string }) => item.id === "constraints"
        ? { ...item, state: "missing", message: "Supports: required for a plate (at least one)", rows: [] } : { ...item, state: "pending", message: "" });
      return json({ run_id: "run-live", state: "blocked", designation: null, solver: "kernel", warm: true, seconds: 0.2, timings: { check: 0.1 }, checklist,
        preview: { ...full, held: [], loads: [], loaded: null, shape: ["supports", "loads"] }, fields: null, explanation: null });
    }
    if (path !== "/v1/workspace/proposals" || request.method() !== "POST") return route.fallback();
    const body = request.postDataJSON() as (typeof asked)[number];
    asked.push(body);
    const edge = body.plate?.here.find((name) => name.startsWith("Edge-")) ?? "Edge-Bottom"; // as the API's guard keeps it: the edge clicked
    return json({ run_id: "run-p", writer: "anthropic", model: "claude-stand-in", proposals: [], conditions: [], question: null, dropped: [], reason: null, unread: [],
      supports: [{ region: edge, dofs: [1, 2, 3], quote: "hold this edge" }], loads: [] });
  });
  await page.goto("/workspace/fea?for=coupon");
  await page.getByRole("button", { name: "Load example" }).click();
  await pickTest(page, "plate");
  await page.getByLabel("Length (mm)", { exact: true }).fill("100");
  await page.getByLabel("Width (mm)", { exact: true }).fill("100");
  await page.getByLabel("Tab length (mm)", { exact: true }).fill("");
  // nothing is held or loaded, and the plate is on the page to be clicked: its mesh, no support and no load drawn
  await expect(page.getByTestId("preview")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("preview-shape")).toContainText("Nothing is held or loaded yet");
  expect(lives.at(-1)!.values.supports ?? []).toEqual([]);
  await expect(page.getByTestId("plate-words")).toHaveCount(0);
  // an element on an edge is clicked: the canvas is walked up from its centre, towards the plate's far edges, until the page names an edge
  const canvas = page.getByTestId("studio-scene").locator("canvas");
  let clicked = "";
  for (let step = 0; step < 60 && !clicked; step += 1) {
    const box = (await canvas.boundingBox())!; // read at every click: the line under the model moves the page
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2 - step * box.height / 130);
    await page.waitForTimeout(60);
    const picked = page.getByTestId("picked-regions");
    clicked = ((await picked.count()) ? await picked.innerText() : "").match(/Edge-(Bottom|Top|Left|Right)/)?.[0] ?? "";
  }
  expect(clicked).toMatch(/^Edge-/);
  await expect(page.getByTestId("chat-here")).toContainText(clicked);
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await message.fill("hold this edge");
  await message.press("Enter");
  const card = page.getByTestId("proposal-card").last();
  await expect(card.locator("[data-key='support:0']")).toContainText(`Hold ${clicked} x, y, z`);
  expect(asked[0].plate?.here).toContain(clicked);
  expect(asked[0].plate?.held).toEqual([]);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-plate-shape.png", fullPage: true });
  await card.getByTestId("proposal-apply").click();
  await expect(page.getByTestId("plate-words")).toContainText(`${clicked} holds x, y, z`);
  await expect.poll(() => calls.checks.length).toBe(1);
  expect((calls.checks[0] as { values: Record<string, unknown> }).values.supports).toEqual([{ region: clicked, dofs: [1, 2, 3] }]);
  const said = (await page.getByTestId("coupon-chat").innerText()).toLowerCase();
  for (const word of ["claude", "anthropic", "model", "abaqus"]) expect(said).not.toContain(word);
  expect(browserErrors).toEqual([]);
});

test("what is applied is drawn and listed under the model before and after a run, and Abaqus's words are answered from the glossary (ADR-0110)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  // a word's meaning is answered before anything is solved: no result and no model is needed
  await say("what is a BC?");
  await expect(page.getByTestId("chat-term").last()).toHaveAttribute("data-term", "boundary-condition");
  await expect(page.getByTestId("chat-term").last()).toContainText("Holds part of the model still");
  // under the model: each boundary condition with what it holds, the load, and the model they act on
  const applied = page.getByTestId("applied");
  await expect(applied.getByTestId("applied-conditions")).toContainText("Bottom grip: fixed (encastre)");
  await expect(applied.getByTestId("applied-conditions")).toContainText("Top grip: free to move along the coupon only");
  await expect(applied.getByTestId("applied-loads")).toContainText("Top grip: pulled 1 mm along the coupon");
  await expect(applied.getByTestId("applied-about")).toContainText("[45/0/-45/90]s, 8 plies");
  await expect(applied).toBeInViewport({ ratio: 0.5 }); // not hidden by the canvas's clipped box
  const bottom = applied.getByRole("button", { name: "Bottom grip: fixed (encastre)" });
  await bottom.click();
  await expect(bottom).toHaveAttribute("aria-pressed", "true"); // its set is framed on the model
  await bottom.click();
  await expect(bottom).toHaveAttribute("aria-pressed", "false");
  // this model's own, in the same words; a request to add one where the test sets them; a name with one meaning
  await say("what are the boundary conditions?");
  await expect(page.getByTestId("chat-applied").last()).toContainText("Bottom grip: fixed (encastre)");
  await say("add a boundary condition on the left edge");
  await expect(page.getByTestId("chat-applied").last()).toContainText("set by its test");
  await expect(page.getByTestId("chat-applied").last()).toContainText("Top grip: pulled 1 mm along the coupon");
  await say("what does XSYMM mean?");
  await expect(page.getByTestId("chat-term").last()).toHaveAttribute("data-term", "symmetry");
  await expect(page.getByTestId("chat-term").last()).toContainText("XSYMM holds a face as a mirror across x");
  expect(calls.checks).toHaveLength(1); // nothing asked changed the setup
  // after the run the model draws and lists the same, not the first load only
  await page.getByTestId("chat-run").click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("applied-conditions")).toContainText("Bottom grip: fixed (encastre)");
  await expect(page.getByTestId("applied-loads")).toContainText("Top grip: pulled 1 mm along the coupon");
  expect(browserErrors).toEqual([]);
});

test("a question is answered and changes nothing: the units, inches, who it is, a test's name, ready to run, the working, the reaction, yes or no (ADR-0121 amendment 2, ADR-0099 amendment 4)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  const meanings: unknown[] = []; // a question of what something means, sent to the theory pages' reader (ADR-0121 amendment 5)
  await page.route(API, (route) => {
    const request = route.request();
    if (new URL(request.url()).pathname !== "/v1/workspace/questions") return route.fallback();
    meanings.push(request.postDataJSON());
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ run_id: null, writer: "anthropic", model: "claude-stand-in",
      prose: ["It ties a laminate's loads to its strains.", "Its parts hold the in-plane, coupling and bending stiffness."],
      sources: [{ id: "engine:3-laminate-stiffness", document: "Laminate theory", title: "3. Laminate stiffness" }], covered: true, withheld: false, reason: null, start: null }) });
  });
  await page.goto("/workspace/fea?for=coupon");
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  await hydrated(message);
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  const heading = () => page.getByTestId("coupon-chat").locator("h4").last();
  await page.getByRole("button", { name: "Start from the IM7/8552 example" }).click();
  await say("A. Engineer");
  await expect(page.getByTestId("chat-check").last()).toHaveAttribute("data-state", "ready");
  // the first real-model run of the question banks (2026-11-20) found each of these answered “Not sure what to change”, or read as a change
  await say("can I use inches?"); // asked, not told: the units stay, and the switch is one click away
  await expect(page.getByTestId("chat-about").last()).toHaveAttribute("data-topic", "units-other");
  await expect(heading()).toHaveText("Yes: in, psi and lbf");
  await expect(page.getByTestId("chat-about").last().getByRole("button", { name: "Switch to in, psi and lbf" })).toBeVisible();
  await say("what units are you using?");
  await expect(heading()).toHaveText("mm, MPa and N");
  await say("who made you");
  await expect(heading()).toHaveText("Anisotropy's assistant");
  await say("what is a tension coupon"); // a test's name, asked: what it is, and no test set
  await expect(page.getByTestId("chat-term").last()).toHaveAttribute("data-term", "tension-coupon");
  await say("what is the width?"); // a value of the setup, read from its own row (ADR-0121 amendment 3)
  await expect(page.getByTestId("chat-about").last()).toHaveAttribute("data-topic", "setup-value");
  await expect(heading()).toHaveText("Width: 25 mm");
  await say("what is the ABD matrix?"); // what something means, with no result yet: answered in words, the first sentence the heading
  await expect(heading()).toHaveText("It ties a laminate's loads to its strains.");
  await expect(page.getByTestId("chat-general").last()).toContainText("From our theory pages.");
  expect(meanings).toEqual([{ question: "what is the ABD matrix?", kinds: [] }]);
  expect(calls.checks).toHaveLength(1); // nothing asked changed the setup
  await say("is my setup ok?"); // checked, and the answer opens with Yes or No
  await expect(page.getByTestId("chat-check").last().locator("h4")).toHaveText("Yes, ready to run");
  await page.getByTestId("chat-run").last().click();
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 30_000 });
  await say("how did you get 16740 N"); // a number of the answer, asked about: the working, never a new load of 16740 N
  await expect(page.getByTestId("chat-working-none").or(page.getByTestId("chat-working")).last()).toBeVisible();
  await expect(page.getByTestId("coupon-chat")).not.toContainText("16740 N force");
  // questions of the result the page answers itself, each opening with the answer (ADR-0099 amendment 4)
  await say("what is the reaction force");
  await expect(heading()).toHaveText(`Reaction: ${printed(16222.038876522856)} N`);
  await expect(page.getByTestId("chat-summary").last()).toContainText("the top grip, in tension");
  await say("does it fail?");
  await expect(page.getByTestId("chat-failure-verdict").last()).toHaveText("No, the coupon holds");
  await say("what is the margin of safety");
  await expect(page.getByTestId("chat-failure-margin").last()).toContainText("No margin of safety is worked out here");
  await say("is ply 2 above 1000 MPa in σ₁ at element 125?");
  await expect(page.getByTestId("chat-value-verdict").last()).toHaveText(/^Yes, \d+ MPa is above 1000 MPa$/);
  expect(calls.solves).toHaveLength(1);
  const said = (await page.getByTestId("coupon-chat").innerText()).toLowerCase();
  for (const word of ["claude", "anthropic", "chatgpt", "abaqus"]) expect(said).not.toContain(word);
  expect(browserErrors).toEqual([]);
});

test("a coupon stated in inches and psi is read, labelled and sent in those units (ADR-0061)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/workspace/fea?for=coupon");
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
    const body = echoed(problem.report_units === "US" ? "laminate-answer-us" : "laminate-answer", problem);
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/workspace/fea?for=coupon");
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
  await expect(question).toContainText("Angles run counterclockwise from x (the Nx direction) to the fibres.");
  await message.fill("[0/45/-45/90]s, 0.125 mm plies");
  await message.press("Enter");
  await expect(question).toHaveAttribute("data-step", "loads");
  await expect(page.getByTestId("laminate-stack")).toContainText("8 plies"); // the stack is drawn as soon as the layup is given
  await page.locator("#lam-Nx").fill("100"); // on the Loads panel
  await page.getByLabel("Nx unit", { exact: true }).selectOption("N/mm"); // the system's unit is N/m; the typed value keeps its own
  await page.getByRole("button", { name: "Set the rest to zero", exact: true }).click();
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
  await expect(page.getByTestId("lam-ratio-max_strain")).toHaveText("3.220"); // the fourth criterion, from the limits the engine derived; four figures in a column
  await expect(page.getByTestId("lam-no-max-strain")).toHaveCount(0);
  await expect(page.getByTestId("lam-fpf-table").locator("tr.studio-earliest")).toHaveAttribute("data-criterion", "tsai_wu");
  await expect(page.getByTestId("lam-ply-table").locator("tr.studio-earliest")).toHaveAttribute("data-ply", "4");
  await expect(page.getByTestId("matrix-A")).toContainText("N/m");
  await expect(page.getByTestId("lam-explanation")).toHaveAttribute("data-writer", "template");
  await expect(page.getByTestId("lam-explanation")).toContainText("By Tsai-Wu, ply 4 (90°) fails first");
  await expect(page.getByTestId("lam-explanation")).toContainText("Nx = 100000 N/m"); // the one number rule: plain below a million
  await expect(page.getByTestId("lam-fpf-table").locator("tr.studio-earliest th")).toContainText("Tsai-Wu (governs)"); // marked in words, not by tint alone
  await expect(page.getByTestId("lam-ply-table").locator("tr[data-ply='4'] th")).toContainText("Ply 4 · 90°");
  await expect(page.getByTestId("matrix-B").locator("tbody td")).toHaveText(Array(9).fill("0")); // no extension–bending coupling: B is zero, not roundoff
  await expect(page.getByTestId("laminate-rail").getByTestId("status")).toHaveText("Solved. Results are under the stack."); // solved from the chat, said in the rail
  await expect(page.getByTestId("panel-solve").locator(".studio-badge")).toHaveText("solved");
  await expect(page.getByTestId("panel-units").locator(".studio-badge")).toHaveText("complete");

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
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
  await page.goto("/workspace/fea?for=coupon");
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
    const problem = request.postDataJSON() as Record<string, unknown>;
    problems.push(problem);
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(echoed("laminate-answer", problem)) });
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
  await message.fill("[0/45/-45/90]s, 0.25 mm plies, Nx = 0 N/m, the rest zero"); // the captured answer's plies, so its echo is whole
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

/** A laminate answer from a captured fixture, echoing the problem it was sent (the page shows an answer only beside the problem it answers,
 * audit finding laminate-4): the title, the layup and the system come from the request. */
function echoed(name: string, problem: Record<string, unknown>) {
  const body = fixture(name);
  return { ...body, report_units: problem.report_units, case: { ...body.case, title: problem.title, laminate: { ...body.case.laminate, layup: problem.layup } } };
}

/** Every word a customer can read in the workspace (ADR-0091): the shell's text, folded details included, and the words a screen reader,
 * a tooltip, a placeholder or a saved file's name carries. `part` reads the card of the user's own Abaqus alone, or everything but it:
 * that card may name Abaqus and the connector's file (ADR-0094 part 7), and is judged by its own list. */
async function shownText(page: Page, part: "outside the Abaqus card" | "the Abaqus card" = "outside the Abaqus card"): Promise<string> {
  return page.getByTestId("workspace-shell").evaluate((shell, inside) => {
    const root = shell.cloneNode(true) as HTMLElement;
    const cards = [...root.querySelectorAll("[data-names-abaqus]")];
    if (!inside) cards.forEach((card) => card.remove());
    const read = (el: Element) => [el.textContent ?? "", ...[...el.querySelectorAll("[aria-label], [title], [placeholder], a[download]")]
      .flatMap((x) => ["aria-label", "title", "placeholder", "download"].map((name) => x.getAttribute(name) ?? ""))].join("\n");
    return (inside ? cards : [root]).map(read).join("\n");
  }, part === "the Abaqus card");
}
const expectNoBannedTerms = async (page: Page, where: string) => expect(bannedIn(await shownText(page)), where).toEqual([]);

test("the customer's workspace never names a tool, a vendor, a model, a script, a record or a person (ADR-0091)", async ({ page }) => {
  test.setTimeout(180_000);
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const queued = { ...fixture("job-running"), state: "queued", stage: null, stages_done: [], outputs: {}, log_tail: [], message: "queued; 1 ahead" };
  // the job moves on only when the scenario says, so a slow runner cannot skip a state; the oldest words the pipeline still writes come
  // through: stage names, "agree with CalculiX", the record's .toml, the console
  let phase: "queued" | "running" | "result" | "done" = "queued";
  const jobs = { queued, running: fixture("job-running"), result: fixture("job-result-in"), done: fixture("job-done") };
  await mockApi(page, calls, { allTests: false, writer: "model", jobs: () => jobs[phase] });
  await mockExchange(page, exchangeState({ exchange: { uploads: true, connector_route: true, ...LIMITS }, uploads: [uploadOf("differs")] }));
  await page.goto("/workspace/fea?for=coupon");
  await expect(page.getByTestId("tension-screen")).toBeVisible();
  await expectNoBannedTerms(page, "a fresh start");
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await page.getByTestId("build-button").click();
  const run = page.getByTestId("job-progress").first();
  await expect(run).toHaveAttribute("data-state", "queued", { timeout: 15_000 });
  await expect(page.getByTestId("job-state").first()).toHaveText("Queued (1 ahead)");
  await expectNoBannedTerms(page, "queued");
  phase = "running";
  await expect(run).toHaveAttribute("data-state", "running", { timeout: 30_000 });
  await expectNoBannedTerms(page, "running");
  phase = "result"; // solved and checked against the reference solver, the report still being written
  // the customer is told the second solver agrees, not asked to judge its counts (the founder, 2026-11-17; ADR-0111 amendment 2)
  await expect(run.getByTestId("job-message")).toHaveText("Checked by a second solver", { timeout: 30_000 });
  await expectNoBannedTerms(page, "the result in, the report being written");
  phase = "done";
  await expect(run).toHaveAttribute("data-state", "done", { timeout: 30_000 });
  await expect(page.getByTestId("explanation")).toHaveAttribute("data-writer", "anthropic", { timeout: 15_000 }); // a model wrote it; the page does not say so
  await page.getByTestId("answer-table").getByRole("button", { name: "Show" }).first().click();
  await expect(page.getByTestId("probe")).toBeVisible();
  await expect(page.getByTestId("tension-files").locator("a[data-key=abaqus_deck]")).toHaveText("Abaqus input file (.inp)");
  await expect(page.getByTestId("tension-files").locator("a[data-key=prepomax_results]")).toHaveCount(0); // the team's file, not the customer's (D4)
  await expectNoBannedTerms(page, "done, with the probe table and the files");
  // the card of the user's own Abaqus (ADR-0094 part 7), with a model that differs, an upload key just made and every fold open: it names
  // Abaqus and the connector's file and nothing else of the list; the rest of the page still names neither
  const card = page.getByTestId("abaqus-card");
  await expect(card.getByTestId("abaqus-verdict")).toHaveText("Differs in 2 places");
  await card.getByTestId("abaqus-keys").locator("summary").click();
  await card.getByTestId("abaqus-key-create").click();
  await expect(card.getByTestId("abaqus-key-value")).toBeVisible();
  const onCard = await shownText(page, "the Abaqus card");
  expect(bannedIn(onCard)).toEqual(["Abaqus", ".py"]);
  expect(bannedInAbaqusCard(onCard)).toEqual([]);
  await expectNoBannedTerms(page, "done, beside the Abaqus card");
  await expect(page.getByTestId("tension-files")).not.toContainText(/build/i); // the build script is offered on the card alone
});

test("a stopped run says what happened and what to do, in plain words (ADR-0091)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  const stopped = { ...fixture("job-running"), state: "stopped", stage: "CalculiX", finished_at: "2026-10-28T20:01:00+00:00",
    message: "stopped at CalculiX: ccx_dynamic.exe exited with code 201: *ERROR in e_c3d: nonpositive jacobian determinant in element 812",
    log_tail: ["== CalculiX", " *ERROR in e_c3d", "run_coupon: stopped at CalculiX"] };
  await mockApi(page, calls, { allTests: false, jobs: () => stopped });
  await page.goto("/workspace/fea?for=coupon");
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

test("the laminate workspace never names its machinery, unsolved or solved, and a mismatched answer is not shown (laminate-2, laminate-4)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  let echo = true;
  await mockApi(page, calls);
  await page.route(API, async (route) => {
    const request = route.request();
    if (new URL(request.url()).pathname !== "/v1/laminates/solve" || request.method() !== "POST") return route.fallback();
    const problem = request.postDataJSON() as Record<string, unknown>;
    const body = echo ? echoed("laminate-answer", problem) : fixture("laminate-answer"); // the captured answer is for Nx = 100 N/mm
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/workspace/laminate");
  await expectNoBannedTerms(page, "laminate, a fresh start");
  await page.locator("button[data-system='SI']").click();
  await expectNoBannedTerms(page, "laminate, the units picked");
  const message = page.getByLabel("Message the laminate assistant", { exact: true });
  await message.fill("E1 147 GPa, E2 10300 MPa, G12 7, nu12 0.27, F1t 2280 MPa, F1c 1725 MPa, F2t 57 MPa, F2c 228 MPa, F6 76 MPa");
  await message.press("Enter");
  await message.fill("[0/45/-45/90]s, 0.125 mm plies");
  await message.press("Enter");
  await message.fill("Nx = 100 N/m, everything else zero"); // a thousand times smaller than the captured answer's load
  await message.press("Enter");
  const rail = page.getByTestId("laminate-rail");
  echo = false;
  await page.getByTestId("laminate-solve").click(); // from the assistant
  await expect(rail.getByRole("alert")).toHaveText("The result did not match the problem; solve again.");
  await expect(page.getByTestId("laminate-results")).toHaveCount(0);
  // the analysis ran and its answer was for another problem: the assistant asks for a new solve, not that the analysis did not run
  await expect(page.getByTestId("ws-assistant").locator(".chat-problem h4").last()).toHaveText("Solve again");
  await page.getByTestId("solve-button").click(); // from the rail: refused the same way, said once
  await expect(rail.getByRole("alert")).toHaveText("The result did not match the problem; solve again.");
  await expect(page.getByTestId("laminate-results")).toHaveCount(0);
  echo = true;
  await message.fill("solve"); // from the assistant after the rail's refusal: the rail shows one state, the answer's
  await message.press("Enter");
  await expect(page.getByTestId("laminate-results")).toBeVisible({ timeout: 15_000 });
  await expect(rail.getByRole("alert")).toHaveCount(0);
  await expect(rail.getByTestId("status")).toHaveText("Solved. Results are under the stack.");
  await expectNoBannedTerms(page, "laminate, solved");
  expect(await shownText(page)).not.toMatch(/\de[+-]\d/); // no programmer's exponent anywhere on the page
  await page.getByTestId("assistant-toggle").click();
  await expect(page.getByTestId("assistant-toggle")).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByTestId("assistant-toggle")).not.toHaveAttribute("aria-pressed", /.*/);
});

/** Every word a workspace page carries for a reader, a screen reader or a search engine (audit fea-screens-19): the title, the meta
 * description, the main text, the attributes and the links' addresses, the service's own address part left aside. `part` reads the card
 * of the user's own Abaqus alone, or everything but it: that card may name Abaqus and the connector's file (ADR-0094 part 7), its build
 * script's link among them, and is judged by its own list. */
async function pageWords(page: Page, part: "outside the Abaqus card" | "the Abaqus card" = "outside the Abaqus card"): Promise<string> {
  return page.evaluate((inside) => {
    const main = (document.querySelector("main") ?? document.body).cloneNode(true) as HTMLElement;
    const cards = [...main.querySelectorAll("[data-names-abaqus]")];
    if (!inside) cards.forEach((card) => card.remove());
    const read = (root: Element) => {
      const attributes = [...root.querySelectorAll("[aria-label], [title], [placeholder], a[download]")]
        .flatMap((el) => ["aria-label", "title", "placeholder", "download"].map((name) => el.getAttribute(name) ?? ""));
      const hrefs = [...root.querySelectorAll("a[href]")].map((a) => (a.getAttribute("href") ?? "").replace("/v1/", "/"));
      return [root.textContent ?? "", ...attributes, ...hrefs].join("\n");
    };
    if (inside) return cards.map(read).join("\n");
    const description = document.querySelector('meta[name="description"]')?.getAttribute("content") ?? "";
    return [document.title, description, read(main)].join("\n");
  }, part === "the Abaqus card");
}
const expectNoBannedWords = async (page: Page, where: string) => {
  expect(bannedIn(await pageWords(page)), where).toEqual([]);
  expect(bannedInAbaqusCard(await pageWords(page, "the Abaqus card")), `${where}: the Abaqus card`).toEqual([]);
};

test("no workspace page names a tool, its machinery or a record, in its head, its text or its links, the service up or down (audit fea-screens-19)", async ({ page }) => {
  test.setTimeout(120_000);
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls, { allTests: false });
  await page.goto("/workspace");
  await expect(page.getByTestId("workspace-projects")).toHaveAttribute("data-source", "browser"); // the stand-in keeps no projects, and says so
  await expect(page.getByTestId("projects-source")).toHaveText("Projects are saved in this browser only; clearing its site data removes them.");
  await expect(page.getByTestId("workspace-tiles").locator("[data-workspace]")).toHaveCount(3); // FEA, CAD and Laminate (ADR-0124)
  await expectNoBannedWords(page, "the chooser");
  await page.getByTestId("workspace-tiles").locator("[data-workspace=fea]").click();
  await expect(page.getByTestId("fea-start-chat")).toBeVisible();
  await expectNoBannedWords(page, "an FEA project not set up yet");
  await page.goto("/workspace/cad");
  await expect(page.getByTestId("cad-chat")).toBeVisible();
  await expectNoBannedWords(page, "the CAD section");
  await page.goto("/workspace/fea?for=coupon");
  await expect(page.getByTestId("tension-screen")).toBeVisible();
  await expect(page.getByTestId("panel-loads").locator(".ws-panel-note")).toHaveText("1 mm pull"); // the load the package will apply, before any check, on its tab
  await hydrated(page.getByLabel("Message the coupon assistant", { exact: true }));
  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("Open-hole tension, 6 mm hole");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByTestId("chat-not-available").last()).toContainText("not offered yet");
  await expectNoBannedWords(page, "the coupon workspace, a hidden test named");
  await page.goto("/workspace/laminate");
  await expectNoBannedWords(page, "the laminate workspace");
  await page.goto("/workspace/wing");
  await expectNoBannedWords(page, "the wing workspace");
  await page.goto("/workspace/fea/view");
  await expectNoBannedWords(page, "the viewer with no job");
  await page.goto("/workspace/fea/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 30_000 });
  await expectNoBannedWords(page, "the viewer with a job");
  // an old link to a job the service no longer has, answered in an older API's words: the page says it plainly
  await page.route(API, (route) => (/^\/v1\/coupon-jobs\/[^/]+$/.test(new URL(route.request().url()).pathname)
    ? route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No coupon job x: not in this API process, and not in the jobs "
      + "table (which exists when run records are on); every job that ended has its receipt in GET /v1/runs?endpoint=/v1/coupon-jobs" }) })
    : route.fallback()));
  await page.goto("/workspace/fea/view?job=00000000-0000-0000-0000-000000000000");
  // scoped: the route announcer of the App Router has role=alert too
  await expect(page.locator(".studio-viewer").getByRole("alert")).toHaveText("These results are no longer available. Run the analysis again from your project.");
  await expect(page.locator(".studio-viewer").getByRole("status")).toHaveCount(0); // no "Loading results…" under it
  await expectNoBannedWords(page, "the viewer, the job gone");
  // the service down: every call answers 503, with no word that it keeps no records
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await page.route(API, (route) => route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "the container did not answer" }) }));
  await page.goto("/workspace");
  await expect(page.getByTestId("workspace-projects")).toHaveAttribute("data-source", "down");
  await expect(page.getByTestId("projects-source")).toHaveText("Saved projects could not be loaded. Showing the ones in this browser. Reload to try again.");
  await expectNoBannedWords(page, "the chooser, the service down");
  await page.goto("/workspace/fea?for=coupon");
  await expect(page.getByTestId("tension-screen")).toBeVisible();
  await page.getByLabel("Material", { exact: true }).selectOption("im7-8552");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).fill("[45/0/-45/90]s");
  await page.getByLabel("Layup, bottom ply first", { exact: true }).press("Enter");
  await page.getByTestId("build-button").click();
  await expect(page.getByTestId("tension-screen").getByRole("alert")).toHaveText(ANALYSIS_UNAVAILABLE);
  await expect(page.getByText(ANALYSIS_UNAVAILABLE, { exact: true })).toHaveCount(1); // said once, in the rail, not again in the assistant (fea-run-48)
  await expectNoBannedWords(page, "the coupon workspace, the service down");
});
