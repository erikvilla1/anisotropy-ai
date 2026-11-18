import { test, expect } from "@playwright/test";

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
  // Five cards since 2026-10-10 (ADR-0019): the combined-load card states the Tsai-Wu quadratic.
  await expect(page.locator(".method-entry")).toHaveCount(5);
  await expect(page.locator(".method-entry summary strong")).toHaveText([
    "Tsai-Hill",
    "Tsai-Wu coefficients",
    "Tsai-Wu failure index",
    "Strength ratio & safety margin",
    "Strength ratio with fixed & variable loads",
  ]);
  await expect(
    page.locator("details[open]").filter({ hasText: "Tsai-Wu coefficients" }),
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
  // The home page's Impact section, which stated the research foundation, left it (ADR-0077 amendment 14).
  await page.goto("/");
  await expect(page.locator(".research-foundation")).toHaveCount(0);
  await page.goto("/about");
  await expect(page.locator("main")).not.toContainText(
    /machine learning|scikit-learn|PyTorch|surrogate|FastAPI/i,
  );
  await page.goto("/industries");
  await expect(page.locator(".industry-priorities .industry-priority")).toHaveCount(2);
  await expect(page.locator(".industry-potentials .industry-potential")).toHaveCount(4);
});

// The Resources pages (the library, a source's page, the test data page) and the calculator stand on white under the black
// header (ADR-0077 amendment 69): their <main> carries the section kit's light values, and no rule of theirs is left with
// a colour written for the dark ground.
test("the library, a source's page, the test data page and the calculator are white under the black header, and every text on them reads (ADR-0077 amendment 69)", async ({ page }) => {
  const pages = [
    { address: "/library", ready: ".material-detail h2" },
    { address: "/library?tab=physics", ready: ".topic-content h2" },
    { address: "/sources?source=daniel-ishai-2006&page=377&dataset=daniel-ishai-2006-as4-3501-v2", ready: ".source-heading h1" },
    { address: "/data", ready: ".dropzone" },
    { address: "/calculator", ready: ".calc-form" },
  ];
  for (const { address, ready } of pages) {
    await page.goto(address);
    await expect(page.locator(ready).first(), address).toBeVisible();
    const main = page.locator("main");
    await expect(main, address).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await expect(main, address).toHaveCSS("color", "rgb(17, 17, 17)");
    // White from one edge of the window to the other, between a black header and the black footer.
    expect(await main.evaluate((element) => { const box = element.getBoundingClientRect(); return [Math.round(box.left), Math.round(document.documentElement.clientWidth - box.right)]; }), address).toEqual([0, 0]);
    await expect(page.locator(".site-header"), address).toHaveCSS("background-color", "rgb(0, 0, 0)");
    await expect(page.locator(".site-footer"), address).toHaveCSS("background-color", "rgb(0, 0, 0)");
    // Every text in it against what lies under it, and every surface: nothing below 4.5 to 1, and nothing dark but the
    // filled button and the pressed filter, which are the accent.
    const found = await main.evaluate((root) => {
      type Colour = { r: number; g: number; b: number; a: number };
      const parse = (value: string): Colour | null => {
        const match = /rgba?\(([^)]+)\)/.exec(value);
        if (!match) return null;
        const [r, g, b, a = 1] = match[1].split(/[,/ ]+/).filter(Boolean).map(Number);
        return { r, g, b, a };
      };
      const linear = (value: number) => { const share = value / 255; return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4; };
      const light = (colour: Colour) => 0.2126 * linear(colour.r) + 0.7152 * linear(colour.g) + 0.0722 * linear(colour.b);
      const over = (top: Colour, under: Colour): Colour => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1 });
      const ground = (element: Element): Colour => {
        const layers: Colour[] = [];
        for (let at: Element | null = element; at; at = at.parentElement) {
          const colour = parse(getComputedStyle(at).backgroundColor);
          if (colour && colour.a > 0) { layers.push(colour); if (colour.a === 1) break; }
        }
        return layers.reverse().reduce((under, layer) => over(layer, under), { r: 255, g: 255, b: 255, a: 1 });
      };
      const name = (element: Element) => `${element.tagName.toLowerCase()}${typeof element.className === "string" && element.className ? "." + element.className.trim().split(/\s+/).join(".") : ""}`;
      const low: string[] = [];
      const dark: string[] = [];
      for (const element of root.querySelectorAll<HTMLElement>("*")) {
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        if (!box.width || !box.height || style.visibility === "hidden" || element.closest(".sr-only, [disabled]")) continue;
        const under = ground(element);
        const words = [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) || element.matches("input, textarea, select");
        const colour = parse(style.color);
        if (words && colour) {
          const [high, lower] = [light(over(colour, under)), light(under)].sort((a, b) => b - a);
          const ratio = (high + 0.05) / (lower + 0.05);
          if (ratio < 4.5) low.push(`${name(element)} ${ratio.toFixed(2)}`);
        }
        const fill = parse(style.backgroundColor);
        if (fill && fill.a > 0.5 && light(fill) < 0.25 && !element.matches(".button.primary, .property-filters button[aria-pressed='true']")) dark.push(name(element));
      }
      return { low: [...new Set(low)], dark: [...new Set(dark)] };
    });
    expect(found, address).toEqual({ low: [], dark: [] });
  }
});
