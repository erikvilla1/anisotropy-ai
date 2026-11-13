import { test, expect } from "@playwright/test";

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

test("the workspace opens on three tiles and the projects, the server's among them, and a new project opens the three-column FEA workspace (ADR-0062)", async ({ page }) => {
  const store: Record<string, Record<string, unknown>> = {};
  await quietApi(page, store);
  await page.goto("/workspace");
  const tiles = page.getByTestId("workspace-tiles");
  await expect(tiles.locator("[data-workspace]")).toHaveCount(3);
  await expect(tiles.locator("[data-workspace=cad]")).toHaveAttribute("data-status", "planned");
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
  await expect(rows.nth(2)).toContainText("Open-hole tension: not available yet"); // kept and listed, not offered (ADR-0089)
  await expect.poll(() => Object.values(store).some((p) => p.name === "ABD check" && p.kind === "laminate"), { timeout: 10_000 }).toBe(true);
  await rows.nth(1).getByRole("button", { name: "Open" }).click(); // the coupon project, untouched
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("project-name")).toHaveValue("OHT study");
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
  await page.goto("/workspace/cad");
  await expect(page.getByTestId("cad-placeholder")).toContainText("What is planned");
});
