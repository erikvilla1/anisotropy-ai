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
      dir = values.test === BENDING ? "studio-bending" : "studio";
      if (dir === "studio-bending") {
        return json(route, { run_id: "run-3", state: "ready", designation: "IM7-3PB-L1", checklist: fixture("checklist", dir), preview: fixture("preview", dir) });
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
  await page.goto("/");
  await page.getByRole("link", { name: "Studio", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("From the coupon to its stresses.");
  await expect(page.getByTestId("empty-scene")).toBeVisible();
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

test("a blocked setup names its rows and the solve stays off", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
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

test("a coupon reopens into the form and the viewer window reads a job by its address", async ({ page }) => {
  const calls = { checks: [] as unknown[], solves: [] as unknown[] };
  await mockApi(page, calls);
  await page.goto("/studio");
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
