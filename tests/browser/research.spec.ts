import { test, expect } from "@playwright/test";

test("homepage hands its message once to the coupon assistant (ADR-0055 amendment 1)", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Start chat", exact: true }),
  ).toBeDisabled();
  const input = page.getByRole("textbox", {
    name: "Describe your engineering question",
  });
  await input.fill("Open-hole tension, IM7/8552, [45/0/-45/90]s, 36 x 250 mm");
  await input.press("Shift+Enter");
  await expect(page).toHaveURL(/\/$/);
  await input.press("Enter");
  await expect(page).toHaveURL(/\/chat\/?$/);
  await expect(page.locator(".chat-user")).toHaveCount(1);
  await expect(page.getByTestId("chat-spec")).toContainText("open-hole tension");
  await expect(page.getByTestId("chat-spec")).toContainText("[45/0/-45/90]s, 8 plies");
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "shear");
  await page.reload();
  await expect(page.locator(".chat-user")).toHaveCount(0);
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "test");
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
  await expect(page.locator("details[open] .katex").first()).toBeVisible();
  await expect(page.locator("details[open] annotation").nth(1)).toContainText(String.raw`\frac{E_1}{\Delta}`);
  await page
    .locator("summary")
    .filter({ hasText: "Local strains & local stresses" })
    .click();
  await expect(page.locator("details[open]").last().locator("annotation")).toContainText(String.raw`\mathbf T_\varepsilon`);
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
  await page.getByRole("button", { name: /Thermal & moisture effects/ }).click();
  await expect(
    page.getByRole("textbox", { name: "Search this physics topic" }),
  ).toHaveValue("");
  await page
    .locator("summary")
    .filter({ hasText: "Expansion coefficient transformation" })
    .click();
  await expect(page.locator("details[open] annotation").nth(1)).toContainText(String.raw`2mn(\alpha_1-\alpha_2)`);
  await expect(page.locator("details[open]")).toContainText("Eq. 8.6, p. 210");
  await expect(page.getByRole("button", { name: /CAD, FEA & verification/ })).toHaveCount(0);
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
