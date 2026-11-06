import { test, expect } from "@playwright/test";

const API = /\/v1\/.*/;

/** The API answers the workspace needs to open: the coupon list only (the setup check and the jobs are the studio scenarios' business). */
async function quietApi(page: import("@playwright/test").Page) {
  await page.route(API, (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === "/v1/coupons") return route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not in this scenario" }) });
  });
}

test("the workspace opens on three tiles and the browser's projects, and a new project opens the three-column FEA workspace (ADR-0062)", async ({ page }) => {
  await quietApi(page);
  await page.goto("/workspace");
  const tiles = page.getByTestId("workspace-tiles");
  await expect(tiles.locator("[data-workspace]")).toHaveCount(3);
  await expect(tiles.locator("[data-workspace=cad]")).toHaveAttribute("data-status", "planned");
  await expect(page.getByTestId("workspace-projects")).toContainText("None yet in this browser");
  await page.getByRole("button", { name: /New coupon fea project/i }).click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  const shell = page.getByTestId("workspace-shell");
  await expect(shell).toHaveAttribute("data-assistant", "open");
  await expect(page.getByTestId("ws-rail").getByRole("button", { name: "Load example" })).toBeVisible();
  await expect(page.getByTestId("ws-stage").getByTestId("empty-scene")).toBeVisible();
  await expect(page.getByTestId("ws-assistant").getByTestId("chat-question")).toHaveAttribute("data-step", "test");
  await page.getByTestId("project-name").fill("OHT study");
  await page.getByTestId("assistant-toggle").click();
  await expect(shell).toHaveAttribute("data-assistant", "closed");
  await expect(page.getByTestId("ws-assistant")).toHaveCount(0);
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
  await page.getByLabel("Units", { exact: true }).selectOption("mm-MPa"); // on the panel: the assistant moves on
  await expect(page.getByTestId("ws-assistant").getByTestId("chat-question")).toHaveAttribute("data-step", "material");
  await page.getByRole("link", { name: "All projects" }).click();
  const rows = page.getByTestId("workspace-projects").locator("tbody tr");
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toHaveAttribute("data-kind", "laminate");
  await expect(rows.first()).toContainText("ABD check");
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
