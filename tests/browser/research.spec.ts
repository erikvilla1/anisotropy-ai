import { test, expect } from "@playwright/test";

test("homepage submits the initial message once to its own chat page", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Start chat", exact: true }),
  ).toBeDisabled();
  const input = page.getByRole("textbox", {
    name: "Describe your engineering question",
  });
  await input.fill("D5766 coupon 250 x 36 mm at 20 kN");
  await input.press("Shift+Enter");
  await expect(page).toHaveURL(/\/$/);
  await page.getByLabel("Response format").selectOption("json");
  await input.press("Enter");
  await expect(page).toHaveURL(/\/chat\/?$/);
  await expect(page.locator(".conversation-turn")).toHaveCount(1);
  await expect(page.locator(".conversation-turn pre")).toContainText(
    '"width_mm": 36',
  );
  await expect(page.getByLabel("Response format")).toHaveValue("json");
  await expect(
    page.getByRole("tab", { name: "AI scope assistant" }),
  ).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".conversation-turn")).toHaveCount(0);
  await page.goto("/");
  await input.fill("Compare D3039 and D5766");
  await page.getByRole("button", { name: "Start chat", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Two tests. Different questions." }),
  ).toBeVisible();
});

test("materials retain source units, missing values, review notes and export provenance", async ({
  page,
  request,
}) => {
  await page.goto("/library");
  await expect(page.getByText("22 source records")).toBeVisible();
  await page.getByRole("textbox", { name: "Search materials" }).fill("CF0302");
  await expect(
    page.getByRole("heading", { name: "CF0302 / MTM49LT" }),
  ).toBeVisible();
  const row = page
    .getByRole("row")
    .filter({ has: page.getByRole("cell", { name: "F1C", exact: true }) });
  await expect(row).toContainText("-87300");
  await expect(row).toContainText("ksi");
  await expect(row).toContainText("Confirm with the source owner");
  const event = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export source record" }).click();
  const stream = await (await event).createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream!) chunks.push(Buffer.from(chunk));
  const record = JSON.parse(Buffer.concat(chunks).toString());
  expect(record.page).toBe(4);
  expect(
    record.properties.find((p: { symbol: string }) => p.symbol === "F1C").value,
  ).toBe("-87300");
  await page
    .getByRole("textbox", { name: "Search materials" })
    .fill("Glass UD · nominal");
  await expect(
    page
      .getByRole("row")
      .filter({ has: page.getByRole("cell", { name: "ρ", exact: true }) }),
  ).toContainText("0.700");
  await page
    .getByRole("textbox", { name: "Search materials" })
    .fill("E-glass plain weave · VaRTM");
  await expect(
    page
      .getByRole("row")
      .filter({ has: page.getByRole("cell", { name: "F1C", exact: true }) }),
  ).toContainText("Not provided");
  const source = await request.get("/assets/documents/material-properties-2026-v2.pdf");
  expect(source.ok()).toBeTruthy();
  expect((await source.body()).subarray(0, 5).toString()).toBe("%PDF-");
});

test("physics topics group transformations, local recovery and failure functions", async ({
  page,
}) => {
  await page.goto("/library");
  await page.getByRole("tab", { name: "Physics & references" }).click();
  await page
    .locator("summary")
    .filter({ hasText: "Reduced stiffness Q" })
    .click();
  await expect(page.locator("details[open]")).toContainText("Q₁₁ = E₁/Δ");
  await page
    .locator("summary")
    .filter({ hasText: "Local strains & local stresses" })
    .click();
  await expect(page.locator("details[open]").last()).toContainText(
    "Tε εxy,mech",
  );
  await page.getByRole("button", { name: /Ply failure criteria/ }).click();
  await expect(
    page.locator("summary").filter({ hasText: "Reduced stiffness" }),
  ).toHaveCount(0);
  await page
    .getByRole("textbox", { name: "Search this physics topic" })
    .fill("Tsai");
  await expect(page.locator(".method-entry")).toHaveCount(4);
  await expect(
    page.locator("details[open]").filter({ hasText: "Tsai–Wu coefficients" }),
  ).toContainText("experimental evidence");
  await page.getByRole("button", { name: /CAD, FEA & verification/ }).click();
  await expect(
    page.getByRole("textbox", { name: "Search this physics topic" }),
  ).toHaveValue("");
  await page
    .locator("summary")
    .filter({ hasText: "Verification gate" })
    .click();
  await expect(page.locator("details[open]")).toContainText("MS ≥ 0");
});

test("research positioning is explicit without an AI implementation pitch on About", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".research-foundation")).toContainText(
    "open-source datasets",
  );
  await expect(page.locator(".research-foundation")).toContainText(
    "published research studies",
  );
  await page.goto("/about");
  await expect(page.locator("main")).not.toContainText(
    /machine learning|scikit-learn|PyTorch|surrogate|FastAPI/i,
  );
  await page.goto("/industries");
  await expect(page.locator(".priority-grid .industry-card")).toHaveCount(2);
  await expect(page.locator(".potential-grid article")).toHaveCount(4);
});
