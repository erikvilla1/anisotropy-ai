import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";
import { printed } from "../../lib/studio-colors";

const API = /\/v1\/.*/;
const SERVER_PROJECT = {
  id: "7c1a2b3c-4d5e-4f60-8a7b-9c0d1e2f3a4b", kind: "fea", name: "From the server", actor: "studio", user_email: null, form_version: "0.6", units: "mm-MPa",
  content: { form: { test: "open-hole tension", length: "250", width: "36" }, plate: { supports: [], loads: [], regions: [] } },
  designation: null, last_check_run_id: null, created_at: "2026-11-01T10:00:00+00:00", updated_at: "2026-11-01T10:00:00+00:00", jobs: [],
};

/** The API answers the workspace needs to open: the coupon list, and the project store with one project kept on the server (part 6); the
 * setup check and the jobs are the studio scenarios' business. `store` holds what the page PUT. */
async function quietApi(page: import("@playwright/test").Page, store: Record<string, Record<string, unknown>> = {}) {
  store[SERVER_PROJECT.id] = SERVER_PROJECT;
  await page.route(API, (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/coupons") return json([]);
    if (path === "/v1/projects" && request.method() === "GET") return json(Object.values(store).sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))));
    const one = /^\/v1\/projects\/([^/]+)$/.exec(path);
    if (one && request.method() === "PUT") {
      const id = one[1], now = new Date().toISOString();
      const kept = store[id];
      store[id] = { ...(kept ?? { id, actor: "studio", user_email: null, designation: null, last_check_run_id: null, created_at: now, jobs: [] }), ...(request.postDataJSON() as object), updated_at: now };
      return json(store[id], kept ? 200 : 201);
    }
    if (one && request.method() === "GET") return store[one[1]] ? json(store[one[1]]) : json({ detail: "No project of yours" }, 404);
    return json({ detail: "not in this scenario" }, 404);
  });
}

test("the workspace opens on two tiles and the projects, the server's among them, and a new project opens the three-column FEA workspace (ADR-0062)", async ({ page }) => {
  const store: Record<string, Record<string, unknown>> = {};
  await quietApi(page, store);
  await page.goto("/workspace");
  const tiles = page.getByTestId("workspace-tiles");
  await expect(tiles.locator("[data-workspace]")).toHaveCount(2); // the CAD tile is gone (decision D5)
  await expect(tiles.locator("[data-workspace=cad]")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Start a project");
  await expect(tiles.locator("[data-workspace=fea] h3")).toHaveText("New Coupon FEA project"); // the workspace's one name, as written
  await expect(page.getByTestId("projects-source")).toHaveText("Saved to your account and in this browser.");
  await expect(page.getByTestId("workspace-projects")).toHaveAttribute("data-source", "server"); // the list is the browser's merged with the server's (part 6)
  await expect(page.getByTestId("workspace-projects")).toContainText("From the server"); // a project this browser never held
  await page.getByRole("button", { name: /New coupon fea project/i }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  const shell = page.getByTestId("workspace-shell");
  await expect(shell).toHaveAttribute("data-assistant", "open");
  await expect(page.getByTestId("ws-rail").getByTestId("tension-screen")).toBeVisible(); // the product's view: the material and the layup (ADR-0090)
  await expect(page.getByTestId("ws-stage").getByTestId("empty-scene")).toBeVisible();
  await expect(page.getByTestId("ws-assistant").getByTestId("chat-question")).toHaveAttribute("data-step", "material");
  await page.getByTestId("project-name").fill("OHT study");
  await expect.poll(() => Object.values(store).some((p) => p.name === "OHT study" && p.kind === "fea"), { timeout: 10_000 }).toBe(true); // PUT to the server a moment after the change
  await expect(page.getByTestId("assistant-toggle")).toHaveAttribute("aria-expanded", "true"); // a disclosure: expanded, not "pressed" (WCAG 4.1.2)
  await expect(page.getByTestId("assistant-toggle")).toHaveAttribute("aria-controls", "ws-assistant");
  await page.getByTestId("assistant-toggle").click();
  await expect(shell).toHaveAttribute("data-assistant", "closed");
  await expect(page.getByTestId("ws-assistant")).toHaveCount(0);
  await expect(page.getByTestId("assistant-toggle")).toHaveAttribute("aria-expanded", "false");
  await page.getByTestId("assistant-toggle").click();
  await expect(page.getByTestId("ws-assistant")).toBeVisible();

  await page.getByRole("link", { name: "All projects" }).click(); // the project is kept in this browser, under its name
  await expect(page).toHaveURL(/\/workspace\/?$/);
  await expect(page.getByTestId("workspace-projects")).toContainText("OHT study");
  await page.getByTestId("workspace-projects").getByRole("button", { name: "Open" }).first().click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("project-name")).toHaveValue("OHT study");

  await page.getByRole("link", { name: "All projects" }).click(); // a laminate project is kept beside it and opens its own workspace (part 5)
  await page.getByRole("button", { name: /New laminate response project/i }).click();
  await expect(page).toHaveURL(/\/workspace\/laminate\/?$/);
  await expect(page.getByTestId("laminate-rail").getByTestId("panel-units")).toBeVisible();
  await expect(page.getByTestId("ws-stage").getByTestId("empty-stack")).toBeVisible();
  await expect(page.getByTestId("ws-assistant").getByTestId("chat-question")).toHaveAttribute("data-step", "units");
  await page.getByTestId("project-name").fill("ABD check");
  await page.getByLabel("Stated in", { exact: true }).selectOption("mm-MPa"); // on the panel, named by its visible label (WCAG 2.5.3): the assistant moves on
  await expect(page.getByTestId("ws-assistant").getByTestId("chat-question")).toHaveAttribute("data-step", "material");
  await page.getByRole("link", { name: "All projects" }).click();
  const rows = page.getByTestId("workspace-projects").locator("tbody tr");
  await expect(rows).toHaveCount(3); // the laminate, the coupon, and the server's
  await expect(rows.first()).toHaveAttribute("data-kind", "laminate");
  await expect(rows.first()).toContainText("ABD check");
  await expect(rows.nth(2)).toContainText("From the server");
  await expect(rows.nth(2)).toContainText("Open-hole tension: not offered yet"); // kept and listed, not offered (ADR-0089)
  await expect(rows.first()).toContainText("Laminate response");
  await expect(rows.nth(1)).toContainText("Coupon FEA");
  await expect.poll(() => Object.values(store).some((p) => p.name === "ABD check" && p.kind === "laminate"), { timeout: 10_000 }).toBe(true);
  await rows.nth(1).getByRole("button", { name: "Open" }).click(); // the coupon project, untouched
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("project-name")).toHaveValue("OHT study");
});

test("your analyses lists the finished runs with their answers, and one opens again as it was solved (ADR-0109)", async ({ page }) => {
  const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}.json`, "utf8"));
  const fields = fixture("fields");
  const verdict = fields.summary.verdict, first = fields.summary.fpf_gauge[verdict.earliest];
  // the answer as the run's tool picks it from the summary (fea `fields.run_answer`), and the run's own rows kept by key
  const done = { ...fixture("job-done"), outputs: { ...fixture("job-done").outputs, values: "a/IM7-UNT-L1-values.json" },
    answer: { basis: verdict.basis, criterion: verdict.earliest, fails: verdict.fails, factor: verdict.factor, ply: first.ply, angle: first.angle, face: first.face } };
  const older = { ...fixture("job-done"), job_id: "1f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00", coupon: "IM7-UNT-L2", finished_at: "2026-10-20T09:00:00+00:00" }; // before answers were kept
  const stopped = { ...fixture("job-running"), job_id: "2f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00", state: "stopped", outputs: {} };
  const asked: string[] = [];
  await page.route(API, (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    asked.push(`${request.method()} ${path}`);
    if (path === "/v1/coupon-tests") return json({ all: true });
    if (path === "/v1/coupons") return json([]);
    if (path === "/v1/coupon-jobs" && request.method() === "GET") return json([done, stopped, older]);
    if (path === `/v1/coupon-jobs/${done.job_id}`) return json(done);
    if (path === `/v1/coupon-jobs/${done.job_id}/files/fields`) return json(fields);
    if (path === `/v1/coupon-jobs/${done.job_id}/files/explanation`) return json(fixture("explanation"));
    if (path === `/v1/coupon-jobs/${done.job_id}/files/values`) return json({ ...fixture("values"), length: 240 }); // the rows this run ran on
    if (path === `/v1/coupon-jobs/${done.job_id}/explain`) { // the result's words, asked for as any result's view asks (ADR-0052)
      const explanation = fixture("explanation");
      return json({ run_id: "run-2", job_id: done.job_id, kind: "result", writer: "template", model: null, prose: explanation.sentences, withheld: false, reason: null,
        facts: explanation.facts });
    }
    if (path === "/v1/coupon-jobs/live") return; // the project behind it is not this scenario's business
    return json({ detail: "not in this scenario" }, 404);
  });
  await page.goto("/workspace");
  const list = page.getByTestId("workspace-analyses");
  await expect(list).toHaveAttribute("data-state", "listed");
  const rows = list.locator("tbody tr");
  await expect(rows).toHaveCount(2); // the two finished runs, newest first; the stopped one has nothing to open
  await expect(rows.first()).toContainText("IM7-UNT-L1");
  await expect(rows.first().getByTestId("analysis-answer")).toHaveText(`Holds at ${printed(verdict.factor)} × the applied load`);
  await expect(rows.first()).toContainText(`ply ${first.ply} (${first.angle}°) · Tsai-Hill · gauge section`);
  await expect(rows.nth(1)).toContainText("IM7-UNT-L2");
  await expect(rows.nth(1).getByTestId("analysis-answer")).toHaveText("–"); // a run from before the answer was kept says none, never a guess

  await rows.first().getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/); // no id in the address: the run to open passes through this tab's storage
  await expect(page.getByTestId("past-banner")).toContainText("Past run of IM7-UNT-L1");
  await expect(page.getByTestId("past-banner")).toContainText("Shown as it was solved.");
  const rail = page.getByTestId("ws-rail").getByTestId("past-rail");
  await expect(rail.getByTestId("past-answer")).toHaveText(`Holds at ${printed(verdict.factor)} × the applied load`);
  await expect(rail.getByTestId("past-files").locator("a[data-key=document]")).toHaveAttribute("href", new RegExp(`/v1/coupon-jobs/${done.job_id}/files/document`));
  await expect(page.getByTestId("ws-stage").getByTestId("results")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("chat-past")).toContainText("IM7-UNT-L1");

  // the assistant answers from that run's results, with no model asked and nothing solved again
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await say("which ply fails first?");
  await expect(page.getByTestId("chat-failure").last().getByTestId("chat-failure-ply")).toHaveText(`Ply ${first.ply} (${first.angle}°) fails first`);
  await say("make the mesh finer"); // a past run is read as it stands: no row changes by talking
  await expect(page.getByTestId("chat-past-read-only")).toContainText("Nothing is changed by talking here.");
  expect(asked.filter((line) => line.startsWith("POST") && !line.endsWith("/explain"))).toEqual([]); // nothing was checked, solved or read by a model

  // its inputs are taken up again only when asked: the project then holds the rows the run ran on
  await rail.getByTestId("past-use").click();
  await expect(page.getByTestId("past-rail")).toHaveCount(0);
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("240");
  await expect(page.getByTestId("past-banner")).toHaveCount(0);

  // a reload opens the project, not the past run again: the id was taken once
  await page.reload();
  await expect(page.getByTestId("studio-form")).toBeVisible();
  await expect(page.getByTestId("past-rail")).toHaveCount(0);
});

test("the old addresses go to the workspace with their query, and the service pages point at it (ADR-0058 amendment 1)", async ({ page }) => {
  await quietApi(page);
  await page.goto("/chat?material=im7-8552");
  await expect(page).toHaveURL(/\/workspace\/fea\/?(\?material=im7-8552)?$/);
  await expect(page.getByTestId("ws-assistant")).toContainText("IM7 / 8552");
  await page.goto("/chat/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page).toHaveURL(/\/workspace\/fea\/view\/?\?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00$/);
  await page.goto("/studio");
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await page.goto("/studio/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page).toHaveURL(/\/workspace\/fea\/view\/?\?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00$/);
  await page.goto("/services/finite-element-modeling");
  await expect(page.getByRole("link", { name: "Open the workspace", exact: true })).toHaveAttribute("href", /\/workspace\/fea$/);
  await page.goto("/workspace/laminate");
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "units");
  await page.goto("/workspace/cad"); // no CAD page in the workspace (decision D5)
  await expect(page.getByTestId("cad-placeholder")).toHaveCount(0);
});
