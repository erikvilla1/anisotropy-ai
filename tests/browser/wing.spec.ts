import { readFileSync } from "node:fs";
import { test, expect, type Page, type Route } from "@playwright/test";
import { bannedIn } from "../../lib/studio-copy";

/** The wing workspace (ADR-0118), with the API played from the engine's own answer to the example wing
 * (tests/fixtures/wing/example-answer.json, written by scripts/wing-choices.py and checked against the API by
 * api/tests/test_wings_api.py). What the page sends is recorded, so each test can say what the engine was asked. */
const ANSWER = JSON.parse(readFileSync("tests/fixtures/wing/example-answer.json", "utf-8"));
const WINGS = /\/v1\/wings\/(analyze|shape)$/;
const SHAPE = { run_id: null, step: "ISO-10303-21;\nEND-ISO-10303-21;\n", parts: { wing: "Example straight wing", units: { thickness: "mm", area: "m^2", mass: "kg", step: "mm" },
  parts: [{ name: "Upper skin", layup: "skin", thickness: 7.463, area: 0.8652, mass: 2.249 }, { name: "Front spar", layup: "spar", thickness: 1.463, area: 0.09204, mass: 0.2128 }], mass: 2.462 } };

type Sent = { wing?: Record<string, unknown>; toml?: string };
const shapes: Sent[] = []; // what Download STEP sent, in the test that runs

async function playWings(page: Page, answer: (body: Sent) => { status: number; body: unknown } = () => ({ status: 200, body: ANSWER })) {
  const sent: Sent[] = [];
  shapes.length = 0;
  await page.route(/\/v1\/.*/, (route: Route) => {
    const request = route.request();
    if (!WINGS.test(new URL(request.url()).pathname)) return route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "not in this scenario" }) });
    const body = request.postDataJSON() as Sent;
    if (new URL(request.url()).pathname.endsWith("/shape")) {
      shapes.push(body);
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(SHAPE) });
    }
    sent.push(body);
    const reply = answer(body);
    return route.fulfill({ status: reply.status, contentType: "application/json", body: JSON.stringify(reply.body) });
  });
  return sent;
}

test("a new wing opens on the example and shows the engine's answer, drawings and every case (ADR-0118)", async ({ page }) => {
  const sent = await playWings(page);
  await page.goto("/workspace");
  const tiles = page.getByTestId("workspace-tiles");
  await expect(tiles.locator("[data-workspace]")).toHaveCount(3);
  await tiles.locator("[data-workspace=wing]").click();
  await expect(page).toHaveURL(/\/workspace\/wing\/?$/);
  const answer = page.getByTestId("wing-answer");
  await expect(answer.getByRole("heading", { level: 2 })).toHaveText("Passes the 34 cases run");
  await expect(answer).toContainText("Lowest margin +0.097: skin strength, upper skin, at the root, 0° ply, longitudinal compression");
  expect(sent[0].wing).toEqual(ANSWER.wing); // the description itself, as the wing file reads
  await expect(page.getByTestId("wing-planform")).toBeVisible();
  await expect(page.getByTestId("wing-section")).toBeVisible();
  await expect(page.getByTestId("wing-margin-chart")).toBeVisible();
  await expect(page.getByTestId("wing-cases").locator("tbody tr")).toHaveCount(34);
  await expect(page.getByTestId("wing-cases").locator("tr[data-governing=true]")).toHaveCount(1);
  await expect(page.getByTestId("wing-design")).toContainText("front web 57 %, rear web 34 %, curved skins the rest");
  await expect(page.getByTestId("wing-design")).toContainText("0.1858 m from the leading edge");
  await expect(page.getByTestId("wing-explain")).toContainText("Skin strength governs");
  await expect(page.getByTestId("wing-status")).toHaveText("Worked 34 cases in 0.050 s.");
  await expect(page.getByTestId("wing-not-run")).toHaveCount(0);
  // another case redraws the views from its own row of the answer
  await page.getByTestId("wing-case").selectOption({ label: "8 Negative high angle of attack, 0 m" });
  await expect(page.getByTestId("wing-views-note")).toContainText("Case 8, Negative high angle of attack");
});

test("a change is worked once the typing settles, a value that is not a number is not sent, and a refusal keeps the last answer", async ({ page }) => {
  const sent = await playWings(page, (body) => {
    const geometry = body.wing?.geometry as Record<string, unknown> | undefined;
    return geometry?.chord === 0.1 ? { status: 422, body: { detail: "The airfoil has no height at 0.25 of the chord" } } : { status: 200, body: ANSWER };
  });
  await page.goto("/workspace/wing");
  await expect(page.getByTestId("wing-answer")).toBeVisible();
  const before = sent.length;
  const span = page.getByLabel("Half span");
  await span.fill("2.");
  await span.fill("2.5");
  await expect.poll(() => sent.length).toBe(before + 1); // one request for the settled value, not one a keystroke
  expect((sent.at(-1)?.wing?.geometry as Record<string, unknown>).half_span).toBe(2.5);
  await span.fill("two");
  await expect(page.getByText("Not a number.")).toBeVisible();
  await page.waitForTimeout(600);
  expect(sent.length).toBe(before + 1);
  await page.getByLabel("Chord", { exact: true }).fill("0.1");
  await expect(page.getByTestId("wing-problem")).toContainText("The airfoil has no height at 0.25 of the chord");
  await expect(page.getByTestId("wing-answer")).toContainText("The results below are for the last wing that could be worked.");
  await expect(page.getByTestId("wing-stage")).toHaveAttribute("data-state", "stale");
  // the wing is kept in this browser: a reload shows the last values typed
  await page.reload();
  await expect(page.getByLabel("Half span")).toHaveValue("2.5");
});

test("the wing saves as a wing file and a wing file opens through the engine", async ({ page }) => {
  const sent = await playWings(page);
  await page.goto("/workspace/wing");
  await expect(page.getByTestId("wing-answer")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByTestId("wing-save").click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("example-straight-wing.toml");
  const text = readFileSync(await file.path(), "utf-8");
  expect(text).toContain('title = "Example straight wing"\n');
  expect(text).toContain("[geometry]\nhalf_span = 2\nchord = 0.45\nairfoil = \"naca-2412\"\n");
  expect(text).toContain("[envelope.speeds]\nstall_flaps = 20\n");
  expect(text).toContain("half_stack = [0, 45, -45, 0]");
  await page.getByTestId("wing-file").setInputFiles({ name: "mine.toml", mimeType: "text/plain", buffer: Buffer.from(text) });
  await expect(page.getByTestId("wing-file-note")).toHaveText("mine.toml opened.");
  expect(sent.at(-1)?.toml).toBe(text); // the file's text, read by the engine's own reader
});

test("missing speeds leave their cases out, listed with what they need, and the assistant says what governs", async ({ page }) => {
  const report = { ...ANSWER.report, cases: ANSWER.report.cases.slice(5, 6), not_run: [{ number: 3, label: "Cruise", altitude: 0, needs: "the cruise speed" }] };
  const views = { ...ANSWER.views, cases: ANSWER.views.cases.slice(5, 6) };
  await playWings(page, () => ({ status: 200, body: { ...ANSWER, report, views } }));
  await page.goto("/workspace/wing");
  await expect(page.getByTestId("wing-answer").getByRole("heading", { level: 2 })).toHaveText("Passes the 1 case run");
  await expect(page.getByTestId("wing-not-run")).toContainText("3 Cruise at 0 m: needs the cruise speed");
  await expect(page.getByTestId("wing-assistant")).toContainText("1 case wait for inputs");
});

test("Download STEP saves the shape the API built from the wing as it stands, and lists each part's thickness (ADR-0116, ADR-0118)", async ({ page }) => {
  await playWings(page);
  await page.goto("/workspace/wing");
  await expect(page.getByTestId("wing-answer")).toBeVisible();
  await page.getByTestId("panel-wing-shape").locator("summary").click();
  const download = page.waitForEvent("download");
  await page.getByTestId("wing-step").click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("example-straight-wing.step");
  expect(readFileSync(await file.path(), "utf-8")).toBe(SHAPE.step);
  expect(shapes.at(-1)?.wing).toEqual(ANSWER.wing);
  await expect(page.getByTestId("wing-step-note")).toHaveText("example-straight-wing.step saved: 2 parts, in millimetres.");
  await expect(page.getByTestId("wing-parts").locator("tbody tr")).toHaveCount(2);
  await expect(page.getByTestId("wing-parts")).toContainText("Front spar1.4630.213");
});

test("the wing workspace names no tool, no machinery and no record, with every panel open and the shape built (ADR-0091, ADR-0118)", async ({ page }) => {
  await playWings(page);
  await page.goto("/workspace/wing");
  await expect(page.getByTestId("wing-answer")).toBeVisible();
  const folded = page.locator("details.ws-panel:not([open]) > summary");
  while (await folded.count()) await folded.first().click(); // every folded panel opened, one at a time
  const download = page.waitForEvent("download");
  await page.getByTestId("wing-step").click();
  await download;
  await expect(page.getByTestId("wing-parts")).toBeVisible();
  const words = await page.evaluate(() => {
    const main = document.querySelector("main") ?? document.body;
    const attributes = [...main.querySelectorAll("[aria-label], [title], [placeholder]")]
      .flatMap((el) => ["aria-label", "title", "placeholder"].map((name) => el.getAttribute(name) ?? ""));
    const hrefs = [...main.querySelectorAll("a[href]")].map((a) => a.getAttribute("href") ?? "");
    return [document.title, main.textContent ?? "", ...attributes, ...hrefs].join("\n");
  });
  expect(bannedIn(words)).toEqual([]);
});
