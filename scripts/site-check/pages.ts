/** How the site check brings the live site to each page a bank asks its questions on (ADR-0138), as a customer would: by the page's own
 * buttons, with the public example's material and layup, IM7/8552 [45/0/-45/90]s (the deploy check's coupon, never a team's; ADR-0042).
 * Every setup starts in a fresh browser context, so nothing carries over from another page. A step that does not come in time throws with
 * what it waited for: the report names the page that could not be set up, and its questions are not asked. */
import { expect, type Page } from "@playwright/test";
import type { Page as BankPage } from "../../tests/assistant-questions/harness";
import { ask, BOX } from "./chat";

export const MATERIAL = "im7-8552";
export const LAYUP = "[45/0/-45/90]s";

type Setup = (page: Page) => Promise<void>;

async function fresh(page: Page, path: string, box: string): Promise<void> {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await expect(page.getByLabel(box, { exact: true }), `the ${box.toLowerCase()} box on ${path}`).toBeVisible({ timeout: 90_000 });
}

/** The coupon with the example's material and layup given, the rest left to the software, as a customer's tension screen takes it. */
async function couponGiven(page: Page): Promise<void> {
  await fresh(page, "/workspace/fea?for=coupon", "Message the coupon assistant");
  const screen = page.getByTestId("tension-screen");
  const example = page.getByRole("button", { name: "Load example" });
  await expect(screen.or(example), "the coupon's setup on the left").toBeVisible({ timeout: 60_000 });
  if (await screen.isVisible()) {
    await page.getByLabel("Material", { exact: true }).selectOption(MATERIAL);
    const layup = page.getByLabel("Layup, bottom ply first", { exact: true });
    await layup.fill(LAYUP);
    await layup.press("Enter");
    await expect(page.getByTestId("build-button"), "the Build button once the layup is read").toBeEnabled({ timeout: 60_000 });
  } else { // every test offered (a founder's or a local switch): the example form
    await example.click();
    await page.getByLabel("Run by", { exact: true }).fill("Site check");
  }
}

/** The coupon solved: the results on the page and the run done. */
async function couponSolved(page: Page): Promise<void> {
  await couponGiven(page);
  if (await page.getByTestId("tension-screen").isVisible()) {
    await page.getByTestId("build-button").click(); // the check, then the run once it is ready
  } else {
    await page.getByTestId("check-button").click();
    await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
    await page.getByTestId("solve-button").click();
  }
  await expect(page.getByTestId("results"), "the results of the run").toBeVisible({ timeout: 300_000 });
  await expect(page.getByTestId("job-progress"), "the run's progress at done").toHaveAttribute("data-state", "done", { timeout: 300_000 });
}

const SETUPS: Record<string, Setup> = {
  start: (page) => fresh(page, "/workspace/fea", "Message the FEA assistant"),
  blank: async (page) => {
    await fresh(page, "/workspace/fea?for=coupon", "Message the coupon assistant");
  },
  setup: couponGiven,
  ready: async (page) => { // checked and ready to run: the chat's own "check", as an engineer types it
    await couponGiven(page);
    const checked = await ask(page, "check", 120_000);
    if (checked.timedOut) throw new Error("the chat's check did not answer");
    await expect(page.locator("[data-testid=chat-check]").last(), "the check at ready").toHaveAttribute("data-state", "ready", { timeout: 60_000 });
  },
  results: couponSolved,
  past: async (page) => { // the newest of the check's own past analyses, opened read-only (it solved one on the results page)
    await page.goto("/workspace", { waitUntil: "domcontentloaded" });
    const listed = page.getByTestId("workspace-analyses");
    await expect(listed, "the list of past analyses").toHaveAttribute("data-state", "listed", { timeout: 90_000 });
    const open = listed.getByRole("button", { name: "Open" }).first();
    await expect(open, "a past analysis to open").toBeVisible({ timeout: 10_000 });
    await open.click();
    await expect(page.getByTestId("chat-past"), "the past run in the chat").toBeVisible({ timeout: 120_000 });
    await expect(page.getByLabel("Message the coupon assistant", { exact: true })).toBeVisible();
  },
  wing: async (page) => {
    await fresh(page, "/workspace/wing", "Message the wing assistant");
    await expect(page.getByTestId("wing-answer"), "the example wing worked").toBeVisible({ timeout: 90_000 });
  },
  "wing-caps": async (page) => {
    await SETUPS.wing(page);
    const caps = page.getByTestId("wing-spar_caps");
    if (!(await caps.getByTestId("wing-add-caps").isVisible())) await caps.locator("summary").first().click();
    await caps.getByTestId("wing-add-caps").click();
    await expect(page.getByTestId("wing-parts").or(page.getByTestId("wing-answer")), "the wing worked with its spar caps").toBeVisible({ timeout: 90_000 });
    await page.waitForTimeout(2_000); // the change is worked once the typing settles
  },
  repair: async (page) => {
    await fresh(page, "/workspace/repair", "Message the repair assistant");
    await expect(page.getByTestId("repair-headline"), "the example repair worked by hand").toBeVisible({ timeout: 90_000 });
  },
  "repair-solved": async (page) => {
    await SETUPS.repair(page);
    await page.getByTestId("repair-solve-here").click();
    await expect(page.getByTestId("repair-slice-short"), "the slice solved").toContainText("Solved slice:", { timeout: 240_000 });
  },
  "repair-bond": async (page) => { // the example repair solved, then its bond followed until it lets go, on its own button (ADR-0140)
    await SETUPS["repair-solved"](page);
    await page.getByTestId("repair-bond-here").click();
    await expect(page.getByTestId("repair-bond-short"), "the bond followed").toContainText("Bond followed:", { timeout: 240_000 });
  },
  "repair-external": async (page) => {
    await SETUPS.repair(page);
    const button = page.getByTestId("repair-example-external");
    if (!(await button.isVisible())) await page.locator("[data-testid=panel-repair] summary, #repair summary").first().click().catch(() => undefined);
    await button.click();
    await expect(page.getByTestId("repair-headline"), "the example bonded on top, worked by hand").toBeVisible({ timeout: 90_000 });
    await page.waitForTimeout(1_500);
  },
};

/** Brings the page to the state a bank's page names. */
export async function setUp(page: Page, which: BankPage): Promise<void> {
  const setup = SETUPS[which];
  if (!setup) throw new Error(`no setup for the page ${which}`);
  await setup(page);
  // What the page works out after a change lands a moment later (a setup's preview of first-ply failure): the questions wait for it, so
  // the same page is asked the same way every run. A page that keeps a connection open is given 15 s.
  await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(() => undefined);
}

/** Whether the page still shows what a bank's page names, after a question: its chat box, and for a solved page its results. */
export async function stillOn(page: Page, which: BankPage): Promise<boolean> {
  const path = new URL(page.url()).pathname.replace(/\/$/, "");
  const where: Record<string, string> = { start: "/workspace/fea", blank: "/workspace/fea", setup: "/workspace/fea", ready: "/workspace/fea", results: "/workspace/fea",
    past: "/workspace/fea/view", wing: "/workspace/wing", "wing-caps": "/workspace/wing", repair: "/workspace/repair", "repair-solved": "/workspace/repair", "repair-external": "/workspace/repair",
    "repair-bond": "/workspace/repair" };
  if (where[which] && path !== where[which]) return false;
  const box = page.locator(BOX).filter({ visible: true });
  if (!(await box.count())) return false;
  const label = await box.first().getAttribute("aria-label");
  if (which === "start") return label === "Message the FEA assistant";
  if (["blank", "setup", "ready", "results", "past"].includes(which) && label !== "Message the coupon assistant") return false;
  if (which === "results") return page.getByTestId("results").isVisible();
  if (which === "past") return page.getByTestId("chat-past").isVisible();
  if (which === "repair-solved") return (await page.getByTestId("repair-slice-short").textContent())?.includes("Solved slice:") ?? false;
  if (which === "repair-bond") return (await page.getByTestId("repair-bond-short").textContent({ timeout: 5_000 }).catch(() => null))?.includes("Bond followed:") ?? false;
  return true;
}
