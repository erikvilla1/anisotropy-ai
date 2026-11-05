import { test, expect, type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";

const fixture = (name: string, dir = "studio") => JSON.parse(readFileSync(`tests/fixtures/${dir}/${name}.json`, "utf8"));
const BENDING = "three-point bending";
const API = /https?:\/\/[^/]+\/v1\//;

/** The API, played from the public fixtures: the check, the solve, a job that runs then ends, its files, and the coupons. */
async function mockApi(page: Page, calls: { checks: unknown[]; solves: unknown[] }) {
  let polls = 0;
  let dir = "studio"; // the public tension coupon, or the public bending coupon once a check asks for it
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route(API, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === "/v1/coupons" && request.method() === "GET") return json(route, fixture("coupons"));
    if (path === "/v1/coupons/IM7-UNT-L1/values") return json(route, { name: "IM7-UNT-L1", values: fixture("values") });
    if (path === "/v1/coupon-jobs/check" && request.method() === "POST") {
      calls.checks.push(request.postDataJSON());
      const values = (request.postDataJSON() as { values: Record<string, unknown> }).values;
      dir = values.test === BENDING ? "studio-bending" : values.test === "plate" ? "studio-plate" : "studio";
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
      return json(route, polls < 2 ? fixture("job-running") : polls < 4 ? fixture("job-engine-done") : fixture("job-done"));
    }
    if (path.endsWith("/explain") && request.method() === "POST") {
      const explanation = fixture("explanation", dir);
      return json(route, { run_id: "run-2", job_id: path.split("/")[3], kind: (request.postDataJSON() as { kind: string }).kind, writer: "template", model: null,
        prose: explanation.sentences, withheld: false, reason: null, facts: explanation.facts });
    }
    if (path.endsWith("/files/fields")) return json(route, fixture("fields", dir));
    if (path.endsWith("/files/explanation")) return json(route, fixture("explanation", dir));
    if (path.endsWith("/files/package")) return route.fulfill({ status: 200, contentType: "application/zip", body: "PK" });
    return json(route, { detail: `no stand-in for ${request.method()} ${path}` }, 404);
  });
}

test("the studio checks a setup, solves it, shows the fields as soon as our engine has run, and lists the files", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/services/finite-element-modeling");
  await page.getByRole("link", { name: "Open the studio", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("From the coupon to its stresses.");
  await expect(page.getByTestId("empty-scene")).toBeVisible();
  await page.getByRole("tab", { name: "Full form" }).click();
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("250");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready");
  await expect(page.getByTestId("checklist").locator("li[data-state=pass]")).toHaveCount(12);
  expect(calls.checks).toHaveLength(1);
  const sent = (calls.checks[0] as { values: Record<string, unknown> }).values;
  expect(sent.length).toBe(250);
  expect(sent.ply_1).toBe(45);
  expect(sent.library).toBe("im7-8552");
  expect(sent.form_version).toBe(fixture("values").form_version);
  await expect(page.getByTestId("preview")).toBeVisible();
  await expect(page.getByTestId("preview")).toContainText("50 elements");
  await page.getByLabel("Run by", { exact: true }).fill("A. Engineer");
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("job-progress")).toBeVisible();
  expect((calls.solves[0] as { run_by: string }).run_by).toBe("A. Engineer");
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("legend")).toContainText("Failure index 1/R, worst ply");
  await expect(page.getByTestId("summary-reaction")).toContainText("N (in tension)");
  await expect(page.getByTestId("fpf-factor-tsai_hill")).toHaveText("1.013");
  await expect(page.getByTestId("explanation")).toContainText("does not exceed the Tsai-Hill criterion");
  await expect(page.getByTestId("explanation")).toHaveAttribute("data-writer", "template", { timeout: 15_000 }); // the API answered the explain call
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
  await expect(page.getByTestId("job-message")).toContainText("57 of 57 recorded values agree");
  await expect(page.getByTestId("job-progress").locator("li[data-state=done]")).toHaveCount(9); // every stage of a finished job, the last included
  await expect(page.getByTestId("downloads").locator("a[data-key=package]")).toHaveAttribute("href", /\/v1\/coupon-jobs\/0f3a2c9e[^/]*\/files\/package$/);
  await expect(page.getByTestId("downloads").locator("a[data-key=prepomax_results]")).toBeVisible();
  await expect(page.getByTestId("viewer-link")).toHaveAttribute("href", "/studio/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await page.getByLabel("Field", { exact: true }).selectOption("S22");
  await page.getByLabel("Ply", { exact: true }).selectOption("3");
  await expect(page.getByTestId("legend")).toContainText("Ply stress S22 (across the fibres) (ply 3, -45°)");
  await page.getByLabel("Shown as", { exact: true }).selectOption("element");
  await expect(page.getByTestId("legend")).toContainText("element values: the result");
  await page.getByTestId("fpf-table").locator("tr[data-criterion=tsai_hill] button").click();
  await expect(page.getByTestId("readout")).toContainText("the critical element");
  await expect(page.getByTestId("readout")).toContainText("tsai hill: ply");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-results.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a three-point bending coupon shows its supports, its deflection and the failing face (ADR-0053)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
  await page.getByRole("tab", { name: "Full form" }).click();
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByLabel("Test", { exact: true }).selectOption(BENDING);
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
  await expect(page.getByTestId("fpf-table")).toContainText("bottom face");
  await page.getByLabel("Field", { exact: true }).selectOption("u_z");
  await expect(page.getByTestId("legend")).toContainText("Deflection w (z)");
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
  await mockApi(page, calls);
  await page.goto("/studio");
  await page.getByRole("tab", { name: "Full form" }).click();
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByLabel("Test", { exact: true }).selectOption("plate");
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
  await expect(page.getByTestId("legend")).toContainText("Deflection w (z)");
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-plate.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("a blocked setup names its rows and the solve stays off", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
  await page.getByRole("tab", { name: "Full form" }).click();
  await page.getByRole("button", { name: "Load example" }).click();
  await page.getByLabel("Length (mm)", { exact: true }).fill("");
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "blocked");
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByTestId("checklist").locator("li[data-item=geometry]")).toHaveAttribute("data-state", "missing");
  await expect(page.getByTestId("solve-button")).toBeDisabled();
  expect(calls.solves).toHaveLength(0);
  await page.getByLabel("Length (mm)", { exact: true }).fill("250");
  await expect(page.getByTestId("solve-button")).toBeEnabled(); // inputs changed: the check must run again, and it will before a solve
});

test("a fresh form's choices start blank, not on their first word", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
  await page.getByRole("tab", { name: "Full form" }).click(); // the studio opens on the chat (ADR-0055); the rows are on the form tab
  for (const label of ["Test", "Symmetric", "Loading type"]) await expect(page.getByLabel(label, { exact: true })).toHaveValue("");
  await expect(page.getByLabel("Test", { exact: true }).locator("option:checked")).toHaveText("choose one");
  await page.getByLabel("Test", { exact: true }).selectOption("unnotched tension");
  await expect(page.getByLabel("Test", { exact: true })).toHaveValue("unnotched tension");
});

test("a coupon reopens into the form and the viewer window reads a job by its address", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
  await page.getByRole("tab", { name: "Full form" }).click();
  await page.getByLabel("Reopen a coupon", { exact: true }).selectOption("IM7-UNT-L1");
  await page.getByRole("button", { name: "Reopen", exact: true }).click();
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("250");
  await expect(page.getByLabel("Ply 3", { exact: true })).toHaveValue("-45");
  await expect(page.getByLabel("Material code", { exact: true })).toHaveValue("IM7");
  await page.goto("/studio/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("summary")).toContainText("Largest displacement");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
  await page.goto("/studio/view");
  await expect(page.getByText("No job in the address")).toBeVisible();
});

test("the guided chat asks one thing at a time, checks the setup itself, reads typed changes and runs (ADR-0055)", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", (error) => browserErrors.push(error.message));
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "test");
  await page.getByRole("button", { name: /^Unnotched tension/ }).click();
  await expect(question).toHaveAttribute("data-step", "material");
  await page.getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "shear");
  await page.getByRole("button", { name: /Use the tape estimate/ }).click();
  await expect(question).toHaveAttribute("data-step", "layup");
  await expect(question).toContainText("90° runs along the load");
  await page.getByRole("button", { name: /Quasi-isotropic/ }).click();
  await expect(question).toHaveAttribute("data-step", "geometry");
  await page.getByRole("button", { name: /250 × 25 mm, 56 mm tabs/ }).click();
  await expect(question).toHaveAttribute("data-step", "loading");
  await page.getByRole("button", { name: "Displacement 1 mm", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "name");
  await page.getByLabel("Filled in by", { exact: true }).fill("A. Engineer");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
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
  await expect(page.getByTestId("chat-result")).toBeVisible({ timeout: 15_000 });
  expect((calls.solves[0] as { run_by: string }).run_by).toBe("A. Engineer");
  await expect(page.getByTestId("chat-reaction")).toContainText("N");
  await expect(page.getByTestId("results")).toBeVisible();
  await expect(page.getByTestId("chat-result")).toContainText("57 of 57 recorded values agree", { timeout: 15_000 });
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.screenshot({ path: ".local/website/screenshots/studio-chat.png", fullPage: true });
  expect(browserErrors).toEqual([]);
});

test("one typed line fills the coupon and the chat asks only for what is missing (ADR-0055)", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
  await page.getByLabel("Message the coupon assistant", { exact: true }).fill("Open-hole tension, AS4/8552, [45/0/-45/90]s, 36 x 250 mm, 6 mm hole, 10 kN");
  await page.getByLabel("Message the coupon assistant", { exact: true }).press("Enter");
  await expect(page.getByText("Got it").last()).toBeVisible();
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "shear"); // the library lists no G13 or G23
  await expect(page.getByTestId("chat-spec")).toContainText("36 mm");
  await expect(page.getByTestId("chat-spec")).toContainText("Ø6 mm hole");
  await expect(page.getByTestId("chat-spec")).toContainText("10000 N force");
  await page.getByRole("tab", { name: "Full form" }).click();
  await expect(page.getByLabel("Hole diameter (mm)", { exact: true })).toHaveValue("6"); // the rows carry over to the full form
  await expect(page.getByLabel("Ply 2", { exact: true })).toHaveValue("0");
  expect(calls.checks).toHaveLength(0);
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
  await page.goto("/studio");
  await page.getByTestId("laminate-choice").click();
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
  await page.locator("#lam-Nx").fill("100");
  await page.getByLabel("lam-Nx unit", { exact: true }).selectOption("N/mm"); // the system's unit is N/m; the typed value keeps its own
  await page.getByRole("button", { name: "The rest are zero", exact: true }).click();
  await page.getByRole("button", { name: "Use these loads", exact: true }).click();
  await expect(question).toHaveAttribute("data-step", "review");
  await expect(page.getByTestId("laminate-spec")).toContainText("[0/45/-45/90]s, 8 plies, 0.125 mm plies");
  await expect(page.getByTestId("laminate-spec")).toContainText("Nx = 100 N/mm");
  await page.locator("#lam-f12").fill("-0.5");
  await page.getByTestId("laminate-solve").click();

  await expect(page.getByTestId("laminate-answer")).toBeVisible({ timeout: 15_000 });
  expect(problems).toHaveLength(1);
  const sent = problems[0] as { material: Record<string, unknown>; layup: number[]; ply_thickness: unknown; loads: Record<string, unknown>; f12_star: number; report_units: string };
  expect(sent.material.E1).toEqual({ value: 147, unit: "GPa" }); // as typed: the engine converts, the page never does
  expect(sent.material.E2).toEqual({ value: 10300, unit: "MPa" });
  expect(sent.material.F2t).toEqual({ value: 57, unit: "MPa" });
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
