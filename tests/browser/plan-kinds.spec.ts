import { readFileSync } from "node:fs";
import { test, expect, type Locator, type Page, type Route } from "@playwright/test";
import { bannedIn } from "../../lib/studio-copy";
import { answerWords, feWords } from "../../lib/wing";

/** A wing's and a repair's plan on their pages (ADR-0144, step 5), with the API played from the planner's contract
 * (tests/fixtures/planner/, written by api/tests/test_planner_kinds.py from the API's own answers with a scripted model) and the
 * engine's and the solver's stored answers (tests/fixtures/wing, tests/fixtures/repair). What the page sends is recorded. */
const planner = (name: string) => JSON.parse(readFileSync(`tests/fixtures/planner/${name}.json`, "utf-8"));
const stored = (dir: string, name: string) => JSON.parse(readFileSync(`tests/fixtures/${dir}/${name}.json`, "utf-8"));
/** The engine's answer to the example wing with spar caps: the wing the page holds when it plans. */
const CAPS = stored("wing", "caps-answer");
/** The finite element check's report of the wing the plan leaves, as the fea package's tool wrote it at 40 mm: the check the plan
 * started answers with it. */
const CHECK = stored("wing", "plan-check");
const REPAIR_ANSWER = stored("repair", "example-answer");
/** Where the cards' pictures go: the scratch folder a reviewer names, or the website's local screenshots. */
const SHOTS = process.env.PLANNER_SHOTS ?? ".local/website/screenshots";

type Reported = { n: number; state: string; note: string | null };
/** A card's picture, without the chat's box that floats over the foot of the column. */
const shoot = (card: Locator, name: string) => card.screenshot({ path: `${SHOTS}/${name}.png`, style: ".chat-studio-composer { visibility: hidden !important; }" });
const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

/** The wing's page with a model reading and a kept wing project; `plan` is what planning answers. Returns what the page sent, and a
 * switch that lets the check end. */
async function playWingPlans(page: Page, plan: Record<string, unknown>) {
  const sent = { asked: [] as unknown[], approved: [] as unknown[], reported: [] as Reported[], saved: [] as string[], analyzed: 0 };
  const check = { done: false };
  const approval = planner("wing-approve-answered");
  const job = approval.plan.job as string;
  const checkAt = (state: string, more: Record<string, unknown> = {}) => ({ ...approval.runs[1].answer, state, ...more });
  await page.route(/\/v1\/.*/, (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/v1/workspace/assistant") return json(route, { proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path === "/v1/wake") return json(route, { waking: false }, 202);
    if (path === "/v1/wings/analyze") { sent.analyzed += 1; return json(route, CAPS); }
    const project = /^\/v1\/projects\/([^/]+)$/.exec(path);
    if (project) {
      if (request.method() === "PUT") sent.saved.push(project[1]);
      const body = request.method() === "PUT" ? request.postDataJSON() : { kind: "wing", name: "Wing", content: { wing: CAPS.wing } };
      return json(route, { ...body, id: project[1], form_version: null, units: null, designation: null, last_check_run_id: null, created_at: "2026-11-26T09:00:00+00:00",
        updated_at: "2026-11-26T09:00:00+00:00", jobs: [] });
    }
    const plans = /^\/v1\/projects\/([^/]+)\/plans(?:\/([^/]+))?(\/approve|\/steps\/(\d+))?$/.exec(path);
    if (plans) {
      const [, id, planId, tail, n] = plans;
      if (!planId) { sent.asked.push(request.postDataJSON()); return json(route, { ...plan, project: id }); }
      if (tail === "/approve") {
        sent.approved.push(request.postDataJSON());
        return json(route, { ...approval, plan: { ...approval.plan, project: id }, project: { ...approval.project, id } });
      }
      if (n) { sent.reported.push({ n: Number(n), ...(request.postDataJSON() as { state: string; note: string | null }) }); return json(route, { ...approval.plan, project: id }); }
      return json(route, { ...plan, project: id });
    }
    if (path === `/v1/wings/checks/${job}`) { // the check the approval started: under way until the test lets it end
      return json(route, check.done ? checkAt("done", { stage: null, stages: ["build", "solve", "modes"], stages_done: ["build", "solve", "modes"], report: CHECK })
        : checkAt("running", { stage: "solve", stages: ["build", "solve", "modes"], stages_done: ["build"] }));
    }
    return json(route, { detail: "not in this scenario" }, 404);
  });
  // a wing this browser kept: the wing project the page opens, kept and sent (ADR-0122)
  await page.addInitScript((wing) => {
    if (sessionStorage.getItem("seeded")) return;
    sessionStorage.setItem("seeded", "1");
    localStorage.setItem("anisotropy.wing.v1", JSON.stringify(wing));
  }, CAPS.wing);
  return { sent, check, approval };
}

/** The repair's page with a model reading; `plan` is what planning answers, and the approval waits until the test lets it answer. */
async function playRepairPlans(page: Page, plan: Record<string, unknown>) {
  const sent = { asked: [] as { ask: string; repair: Record<string, unknown> }[], approved: [] as { repair: Record<string, unknown>; base: string }[],
    reported: [] as Reported[], analyzed: [] as Record<string, unknown>[], swept: 0 };
  let release: () => void = () => undefined;
  const approving = new Promise<void>((resolve) => { release = resolve; });
  await page.route(/\/v1\/.*/, async (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/v1/workspace/assistant") return json(route, { proposes: true, provider: "anthropic", model: "claude-stand-in" });
    if (path === "/v1/repairs/analyze") { sent.analyzed.push((request.postDataJSON() as { repair: Record<string, unknown> }).repair); return json(route, REPAIR_ANSWER); }
    if (path === "/v1/repairs/sweeps") { sent.swept += 1; return json(route, { ...stored("repair", "example-sweep"), check: null }); }
    const plans = /^\/v1\/workspace\/repair-plans(?:\/([^/]+))?(\/approve|\/steps\/(\d+))?$/.exec(path);
    if (plans) {
      const [, planId, tail, n] = plans;
      if (!planId) { sent.asked.push(request.postDataJSON()); return json(route, plan); }
      if (tail === "/approve") { // the sweep, its pick, the solve and the bond run inside the request: seconds up to about two minutes
        sent.approved.push(request.postDataJSON());
        await approving;
        return json(route, planner("repair-approve-answered"));
      }
      if (n) { sent.reported.push({ n: Number(n), ...(request.postDataJSON() as { state: string; note: string | null }) }); return json(route, planner("repair-approve-answered").plan); }
      return json(route, plan);
    }
    return json(route, { detail: "not in this scenario" }, 404);
  });
  return { sent, release: () => release() };
}

test.describe("pictured", () => {
  test.use({ deviceScaleFactor: 2 }); // the cards' pictures are read at twice the pixels

  test("a wing's change, hand calculation, check and answer are planned, approved once, and tick off as the check is followed (ADR-0144, step 5)", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const proposed = planner("wing-plan-answered");
    const { sent, check, approval } = await playWingPlans(page, proposed);
    await page.goto("/workspace/wing");
    await expect(page.getByTestId("wing-answer")).toBeVisible();
    const chat = page.getByTestId("wing-chat");
    const box = chat.getByLabel("Message the wing assistant");
    await box.fill(proposed.ask);
    await box.press("Enter");

    // the sentence: the wing project saved, then planned; shown before anything changes
    const card = chat.getByTestId("plan-card").last();
    await expect(card).toHaveAttribute("data-state", "proposed", { timeout: 15_000 });
    expect(sent.asked).toEqual([{ ask: proposed.ask }]);
    expect(sent.saved.length).toBeGreaterThan(0);
    await expect(card.getByTestId("plan-heading")).toHaveText("Plan · 4 steps");
    await expect(card.locator(".plan-role")).toHaveText(["Setup", "Solver", "Solver", "Report"]);
    await expect(card.locator("[data-tool=add_plies]")).toContainText("Two 0° plies added to the spar caps along the whole span");
    await expect(card.getByTestId("plan-approve")).toHaveText("Approve and run");
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "wing-plan-proposed");

    // one approval: the wing the server changed becomes the page's, worked by hand as the plan worked it, and its check is followed
    const analyzedBefore = sent.analyzed;
    await card.getByTestId("plan-approve").click();
    await expect(card).toHaveAttribute("data-state", "approved", { timeout: 15_000 });
    expect(sent.approved).toEqual([{ base: proposed.base }]);
    await expect(card.locator("[data-tool=add_plies]")).toHaveAttribute("data-state", "done");
    await expect(card.locator("[data-tool=analyze]")).toHaveAttribute("data-state", "done");
    await expect(card.locator("[data-tool=check]")).toHaveAttribute("data-state", "running");
    await expect(card.locator("[data-tool=check] [data-testid=plan-step-note]")).toHaveText("Solving the flight loads (2 of 3)…");
    await expect(card.locator("[data-tool=answer]")).toHaveAttribute("data-state", "planned");
    await expect(card.getByTestId("plan-heading")).toHaveText("Plan running · 2 of 4 done");
    const verdict = answerWords(approval.runs[0].answer.report).verdict;
    await expect(page.getByTestId("wing-answer").getByRole("heading", { level: 2 })).toHaveText(verdict); // the plan's hand calculation, shown as the page's own
    await expect(card.getByTestId("plan-run-analyze")).toBeVisible();
    expect(sent.analyzed).toBe(analyzedBefore); // not worked again: the approval's own answer is the page's
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "wing-plan-running");

    // the check ends; its step is reported, then the answer is given as the wing's chat gives it, and reported
    check.done = true;
    await expect(card.locator("[data-tool=check]")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
    await expect(card.locator("[data-tool=check] [data-testid=plan-step-note]")).toHaveText(feWords(CHECK).headline);
    await expect(card.locator("[data-tool=answer]")).toHaveAttribute("data-state", "done");
    await expect(card.getByTestId("plan-answer-heading")).toHaveText(/first: [+−]\d\.\d{3}$/);
    await expect(card.getByTestId("plan-heading")).toHaveText("Plan done · 4 of 4 steps");
    await expect.poll(() => sent.reported.map((r) => `${r.n} ${r.state}`).sort()).toEqual(["3 done", "4 done"]); // the answer is read from the hand calculation at once: it ends without running
    expect(sent.reported.find((r) => r.n === 3)?.note).toBe(feWords(CHECK).headline);
    // the History holds a version by the assistant with the sentence as why, marked with the plan's check
    await page.getByTestId("panel-wing-history").locator("summary").click();
    const version = page.getByTestId("wing-history").locator("li[data-by=assistant]").filter({ hasText: proposed.ask });
    await expect(version).toHaveCount(1, { timeout: 10_000 });
    await expect(version.locator("[data-testid^=wing-version-check-]")).toContainText("Checked:");
    expect(bannedIn(await chat.innerText())).toEqual([]);
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "wing-plan-done");
    expect(errors).toEqual([]);
  });

  test("a wing's change the engine cannot make is refused with its reason, and nothing changes (ADR-0144, step 5)", async ({ page }) => {
    const refused = planner("wing-plan-refused");
    const { sent } = await playWingPlans(page, refused);
    await page.goto("/workspace/wing");
    await expect(page.getByTestId("wing-answer")).toBeVisible();
    const chat = page.getByTestId("wing-chat");
    await chat.getByLabel("Message the wing assistant").fill(refused.ask);
    await chat.getByLabel("Message the wing assistant").press("Enter");
    const card = chat.getByTestId("plan-card").last();
    await expect(card).toHaveAttribute("data-state", "refused", { timeout: 15_000 });
    await expect(card.getByRole("heading")).toHaveText("No plan for that");
    await expect(card.getByTestId("plan-reason")).toHaveText("[0/45/-45/0]s has 0 plies at 90°: 2 cannot be taken out.");
    await expect(card.getByTestId("plan-usual")).toBeVisible();
    expect(sent.approved).toEqual([]);
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "wing-plan-refused");
  });

  test("a repair's sweep, its pick, the solve, the bond and an answer are planned with the repair the page holds, waited for, and shown (ADR-0144, step 5)", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const proposed = planner("repair-plan-answered");
    const approval = planner("repair-approve-answered");
    const { sent, release } = await playRepairPlans(page, proposed);
    await page.goto("/workspace/repair");
    const box = page.getByLabel("Message the repair assistant");
    await expect(box).toBeVisible();
    await expect.poll(() => sent.analyzed.length).toBeGreaterThan(0);
    await box.fill(proposed.ask);
    await box.press("Enter");

    const chat = page.getByTestId("repair-chat");
    const card = chat.getByTestId("plan-card").last();
    await expect(card).toHaveAttribute("data-state", "proposed", { timeout: 15_000 });
    expect(sent.asked.map((a) => a.ask)).toEqual([proposed.ask]);
    expect(sent.asked[0].repair).toEqual(sent.analyzed.at(-1)); // the repair the page holds goes with the sentence
    await expect(card.getByTestId("plan-heading")).toHaveText("Plan · 5 steps");
    await expect(card.locator(".plan-role")).toHaveText(["Solver", "Geometry", "Solver", "Solver", "Report"]);
    await expect(card.locator("[data-tool=use_pick]")).toContainText("Use the sweep's pick: the step length goes from 12.5 mm to 4 mm.");
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "repair-plan-proposed");

    // the approval runs the solve and the bond inside the request: the card says so plainly while it waits
    await card.getByTestId("plan-approve").click();
    await expect(card).toHaveAttribute("data-state", "approving");
    const waiting = card.getByTestId("plan-waiting");
    await expect(waiting).toContainText("The sweep, the solve of the slice and the bond until it lets go run now: a few seconds, up to about two minutes.");
    await expect(card.getByTestId("plan-approve")).toBeDisabled();
    await expect(card.getByTestId("plan-waiting-time")).toHaveText(/^[1-9]\d* s$/, { timeout: 5_000 });
    expect(sent.approved).toEqual([{ repair: sent.asked[0].repair, base: proposed.base }]);
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "repair-plan-running");

    // the answer: the pick becomes the page's repair, the runs are shown as the page shows its own, and the answer is given and reported
    release();
    await expect(card).toHaveAttribute("data-state", "approved", { timeout: 15_000 });
    await expect(waiting).toHaveCount(0);
    await expect(card.getByTestId("plan-run-sweep").getByTestId("repair-sweep-heading")).toHaveText("Step length 4 mm: still elastic at 300 N/mm"); // by hand: the slice is the solve step's
    await expect(card.getByTestId("plan-run-sweep").locator("tr[data-pick=true]")).toHaveCount(1);
    await expect(card.getByTestId("repair-apply")).toHaveCount(0); // the plan took its pick: nothing to apply
    await expect(card.getByTestId("plan-run-check")).toHaveAttribute("data-holds", "false");
    await expect(card.getByTestId("plan-run-check")).toContainText("the slice does not hold the pick");
    await expect(card.getByTestId("plan-run-bond")).toContainText("lets go");
    await expect.poll(() => (sent.analyzed.at(-1)?.steps as { length?: number } | undefined)?.length).toBe(4); // the page's repair is the pick
    expect(sent.analyzed.at(-1)).toEqual(approval.repair);
    await expect(card.locator("[data-tool=answer]")).toHaveAttribute("data-state", "done", { timeout: 15_000 });
    await expect(card.getByTestId("plan-answer-heading")).toHaveText("The adhesive's elastic limit in shear, at 260.8 N/mm");
    await expect(card.getByTestId("plan-heading")).toHaveText("Plan done · 5 of 5 steps");
    await expect.poll(() => sent.reported.map((r) => `${r.n} ${r.state}`).sort()).toEqual(["5 done"]); // read from what the page holds at once: it ends without running
    const solve = JSON.parse(await page.evaluate(() => localStorage.getItem("anisotropy.repair-solve.v1") ?? "null"));
    expect([solve?.repair, solve?.cutFaces, solve?.solve.headline]).toEqual([approval.repair, "open", approval.runs[1].answer.headline]); // kept as the page keeps its own
    expect(bannedIn(await chat.innerText())).toEqual([]);
    await card.scrollIntoViewIfNeeded();
    await page.setViewportSize({ width: 1440, height: 2400 }); // the done card is taller than the window: the whole of it in one picture
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "repair-plan-done");
    expect(errors).toEqual([]);
  });

  test("a repair's plan whose sweep picks nothing is refused with the engine's reason, plainly (ADR-0144, step 5)", async ({ page }) => {
    const refused = planner("repair-plan-refused");
    const { sent } = await playRepairPlans(page, refused);
    await page.goto("/workspace/repair");
    const box = page.getByLabel("Message the repair assistant");
    await expect.poll(() => sent.analyzed.length).toBeGreaterThan(0);
    await box.fill(refused.ask);
    await box.press("Enter");
    const card = page.getByTestId("repair-chat").getByTestId("plan-card").last();
    await expect(card).toHaveAttribute("data-state", "refused", { timeout: 15_000 });
    await expect(card.getByRole("heading")).toHaveText("No plan for that");
    await expect(card.getByTestId("plan-reason")).toHaveText(
      /^The sweep picks nothing to use: None of these keeps the adhesive elastic at 300 N\/mm\. The most is [\d.]+ N\/mm, with a step length of [\d.]+ mm\.$/);
    expect(sent.approved).toEqual([]);
    await card.scrollIntoViewIfNeeded();
    await shoot(card, "repair-plan-refused");
    // read the usual way, the sentence is the chat's own sweep again
    await card.getByTestId("plan-usual").click();
    await expect(card.getByTestId("plan-usual")).toHaveCount(0);
    await expect(page.getByTestId("repair-chat-answer").last()).toHaveAttribute("data-kind", "sweep");
    await expect.poll(() => sent.swept).toBe(1);
  });
});
