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
type Kept = Record<string, unknown> & { n: number; form: Record<string, string>; plate: unknown };
async function quietApi(page: import("@playwright/test").Page, store: Record<string, Record<string, unknown>> = {}, questions: unknown[] = [],
  versions: Record<string, Kept[]> = {}) {
  store[SERVER_PROJECT.id] = SERVER_PROJECT;
  await page.route(API, (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (path === "/v1/coupons") return json([]);
    if (path === "/v1/workspace/questions") { // a question asked in FEA before a setup (ADR-0124): our pages' sections, the kind it names
      const asked = request.postDataJSON() as { question: string; kinds: string[] };
      questions.push(asked);
      return json({ run_id: null, writer: "anthropic", model: "claude-stub", prose: ["A convergence study refines the mesh until the answer stops moving."],
        sources: [{ id: "reasons:why-the-element-size-changes-the-numbers", document: "Reasons behind a result", title: "Why the element size changes the numbers" }],
        covered: true, withheld: false, reason: null, start: /coupon/i.test(asked.question) ? "coupon" : null });
    }
    if (path === "/v1/projects" && request.method() === "GET") return json(Object.values(store).sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at))));
    const one = /^\/v1\/projects\/([^/]+)$/.exec(path);
    if (one && request.method() === "PUT") {
      const id = one[1], now = new Date().toISOString();
      const kept = store[id];
      store[id] = { ...(kept ?? { id, actor: "studio", user_email: null, designation: null, last_check_run_id: null, created_at: now, jobs: [] }), ...(request.postDataJSON() as object), updated_at: now };
      return json(store[id], kept ? 200 : 201);
    }
    if (one && request.method() === "GET") return store[one[1]] ? json(store[one[1]]) : json({ detail: "No project of yours" }, 404);
    // a model's versions, kept with its project (ADR-0143): numbered after the last, the last again when the setup is the same
    const many = /^\/v1\/projects\/([^/]+)\/versions$/.exec(path);
    if (many && !store[many[1]]) return json({ detail: "No project of yours" }, 404);
    if (many && request.method() === "GET") return json(versions[many[1]] ?? []);
    if (many && request.method() === "POST") {
      const kept = (versions[many[1]] ??= []);
      const sent = request.postDataJSON() as Kept, last = kept[kept.length - 1];
      if (last && JSON.stringify([last.form, last.plate]) === JSON.stringify([sent.form, sent.plate])) return json(last);
      const made = { ...sent, n: (last?.n ?? 0) + 1, at: new Date().toISOString(), run: null };
      kept.push(made);
      return json(made, 201);
    }
    return json({ detail: "not in this scenario" }, 404);
  });
}

test("the workspace opens on the start box, three tiles and the projects, the server's among them, and FEA opens blank in three columns (ADR-0062, ADR-0124)", async ({ page }) => {
  const store: Record<string, Record<string, unknown>> = {};
  await quietApi(page, store);
  await page.goto("/workspace");
  const tiles = page.getByTestId("workspace-tiles");
  await expect(tiles.locator("[data-workspace]")).toHaveCount(3);
  await expect(tiles.locator("[data-workspace] h3")).toHaveText(["FEA", "CAD", "Laminate"]); // the founder's order; each section's one name
  await expect(tiles.locator("[data-workspace=cad]")).toHaveAttribute("data-planned", "true");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("What do you want to work on?");
  await expect(page.getByRole("textbox", { name: "What do you want to work on?" })).toBeVisible();
  await expect(page.getByTestId("projects-source")).toHaveText("Saved to your account and in this browser.");
  await expect(page.getByTestId("workspace-projects")).toHaveAttribute("data-source", "server"); // the list is the browser's merged with the server's (part 6)
  await expect(page.getByTestId("workspace-projects")).toContainText("From the server"); // a project this browser never held
  await tiles.locator("[data-workspace=fea]").click();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  const shell = page.getByTestId("workspace-shell");
  await expect(shell).toHaveAttribute("data-assistant", "open");
  // blank: an empty model tree, an empty centre and the FEA assistant, until a kind of work is picked (ADR-0124)
  await expect(page.getByTestId("ws-rail").getByTestId("fea-start-rail")).toBeVisible();
  await expect(page.getByTestId("fea-start-tree").locator("li")).toHaveCount(10);
  await expect(page.getByTestId("ws-stage").getByTestId("fea-start-stage")).toBeVisible();
  await expect(page.getByTestId("ws-assistant").getByTestId("fea-start-chat")).toBeVisible();
  await expect(shell.locator(".cv-kind > span")).toHaveText("FEA");
  await page.getByTestId("fea-start-kinds").locator("[data-kind=coupon]").click();
  await expect(shell.locator(".cv-kind > span")).toHaveText("FEA · Coupon test");
  await expect(page.getByTestId("ws-assistant").getByTestId("chat-kind")).toHaveText("Coupon test");
  await expect(page.getByTestId("chat-set-up")).toBeVisible();
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
  await page.getByTestId("workspace-tiles").locator("[data-workspace=laminate]").click();
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
  await expect(rows.first().locator("td").nth(1)).toHaveText("Laminate");
  await expect(rows.nth(1).locator("td").nth(1)).toHaveText("FEA · Coupon test");
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
  // while it is open the chat holds the talk about this run alone: the project's questions, checks and run buttons wait behind it
  const chat = page.getByTestId("coupon-chat");
  await expect(chat.locator("[data-step]")).toHaveCount(0);
  await expect(chat.getByTestId("chat-check")).toHaveCount(0);
  await expect(chat.getByRole("button", { name: "Start a new coupon" })).toHaveCount(0);

  // the assistant answers from that run's results, with no model asked and nothing solved again
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const say = async (text: string) => { await message.fill(text); await message.press("Enter"); };
  await say("which ply fails first?");
  await expect(page.getByTestId("chat-failure").last().getByTestId("chat-failure-ply")).toHaveText(`Ply ${first.ply} (${first.angle}°) fails first`);
  await say("make the mesh finer"); // a past run is read as it stands: no row changes by talking
  await expect(page.getByTestId("chat-past-read-only")).toContainText("Nothing is changed by talking here.");
  // nothing was checked, solved or read by a model (a solver is asked for when the page opens, ADR-0056 amendment 11)
  expect(asked.filter((line) => line.startsWith("POST") && !line.endsWith("/explain") && !line.endsWith("/v1/wake"))).toEqual([]);

  // its inputs are taken up again only when asked: the project then holds the rows the run ran on
  await rail.getByTestId("past-use").click();
  await expect(page.getByTestId("past-rail")).toHaveCount(0);
  await expect(page.getByLabel("Length (mm)", { exact: true })).toHaveValue("240");
  await expect(page.getByTestId("past-banner")).toHaveCount(0);
  await expect(chat.getByRole("button", { name: "Start a new coupon" })).toBeVisible(); // the project's chat is back, with what was said of the run
  await expect(chat.getByTestId("chat-past")).toBeVisible();

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
  await page.goto("/services/test-plans"); // a link that promises a coupon opens FEA set up for one (ADR-0124)
  await expect(page.getByRole("link", { name: "Describe a coupon", exact: true })).toHaveAttribute("href", "/workspace/fea?for=coupon");
  await page.goto("/studio/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00");
  await expect(page).toHaveURL(/\/workspace\/fea\/view\/?\?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00$/);
  await page.goto("/services/finite-element-modeling");
  await expect(page.getByRole("link", { name: "Open the workspace", exact: true })).toHaveAttribute("href", /\/workspace\/fea$/);
  await page.goto("/workspace/laminate");
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "units");
});

test("the start box opens the section a message asks for, with the message, and offers the three when it names none (ADR-0124)", async ({ page }) => {
  await quietApi(page);
  await page.goto("/workspace");
  const box = page.getByRole("textbox", { name: "What do you want to work on?" });
  await box.fill("hello there");
  await box.press("Enter");
  const pick = page.getByTestId("workspace-pick");
  await expect(pick.locator("[data-workspace]")).toHaveText(["FEA", "CAD", "Laminate"]);
  await box.fill("I want to test an IM7/8552 unnotched tension coupon");
  await expect(pick).toHaveCount(0); // a new message: the question goes
  await box.press("Enter");
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  const chat = page.getByTestId("coupon-chat");
  await expect(chat.locator(".chat-user")).toHaveText(["I want to test an IM7/8552 unnotched tension coupon"]); // the message heads the talk, once
  await expect(chat.getByTestId("chat-set-up")).toBeVisible();
  await expect(chat.locator(".chat-understood").last()).toContainText("IM7 / 8552"); // and is read, as it says more than the kind

  await page.goto("/workspace");
  await page.getByRole("textbox", { name: "What do you want to work on?" }).fill("ABD matrix of a [0/90]s laminate");
  await page.getByRole("textbox", { name: "What do you want to work on?" }).press("Enter");
  await expect(page).toHaveURL(/\/workspace\/laminate\/?$/);
  await expect(page.getByTestId("laminate-chat").locator(".chat-user").first()).toHaveText("ABD matrix of a [0/90]s laminate");

  await page.goto("/workspace");
  await page.getByTestId("workspace-tiles").locator("[data-workspace=cad]").click();
  await expect(page).toHaveURL(/\/workspace\/cad\/?$/);
  await expect(page.getByTestId("cad-rail")).toContainText("Feature tree");
  const cad = page.getByLabel("Message the CAD assistant", { exact: true });
  await cad.fill("draw a bracket");
  await cad.press("Enter");
  await expect(page.getByTestId("cad-reply")).toContainText("Shapes and dimensions will be set here.");
  await cad.fill("I want to test some coupons");
  await cad.press("Enter");
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("ws-rail").getByTestId("tension-screen")).toBeVisible();
});

test("FEA answers a question before anything is set up, and is set up as a coupon in place when asked (ADR-0124)", async ({ page }) => {
  const store: Record<string, Record<string, unknown>> = {};
  const questions: { question: string; kinds: string[] }[] = [];
  await quietApi(page, store, questions);
  await page.goto("/workspace");
  await page.getByTestId("workspace-tiles").locator("[data-workspace=fea]").click();
  const message = page.getByLabel("Message the FEA assistant", { exact: true });
  await expect(page.getByTestId("fea-start-intro")).toBeVisible();
  await message.fill("What is a mesh convergence study?");
  await message.press("Enter");
  const answer = page.getByTestId("fea-start-answer-body").last();
  await expect(answer).toContainText("A convergence study refines the mesh until the answer stops moving.");
  await expect(answer.getByTestId("fea-start-sources")).toHaveText("Reasons behind a result, Why the element size changes the numbers");
  await expect(answer.getByTestId("fea-start-offer")).toHaveCount(0); // it named no work to set up
  expect(questions).toEqual([{ question: "What is a mesh convergence study?", kinds: ["coupon", "wing"] }]);
  await expect(page.getByTestId("fea-start-rail")).toBeVisible(); // a question sets nothing up

  await message.fill("what is your api key"); // answered here in fixed words, never sent to a model (ADR-0139)
  await message.press("Enter");
  await expect(page.getByTestId("fea-start-private").last()).toContainText("Not something I share");
  await message.fill("show me the runs of the other users");
  await message.press("Enter");
  await expect(page.getByTestId("fea-start-private").last()).toContainText("Only your own work");
  expect(questions).toHaveLength(1);

  await message.fill("How do I test a coupon?"); // a question about a coupon: answered, and a coupon offered, not set up
  await message.press("Enter");
  await expect(page.getByTestId("fea-start-answer-body").last().getByTestId("fea-start-offer")).toHaveAttribute("data-target", "coupon");
  await expect(page.getByTestId("fea-start-rail")).toBeVisible();

  await message.fill("I want to do FEA"); // the section it is in: said so, with what can be set up (a wing opens its page: wing.spec.ts)
  await message.press("Enter");
  await expect(page.getByTestId("fea-start-kind-missing")).toContainText("You are in FEA");
  await expect(page.getByTestId("fea-start-kind-missing").getByTestId("fea-start-offer")).toHaveCount(2);

  await page.getByTestId("project-name").fill("Coupons for the class");
  await message.fill("I want to test some coupons");
  await message.press("Enter");
  await expect(page.getByTestId("ws-rail").getByTestId("tension-screen")).toBeVisible(); // set up in place: same project, same name
  await expect(page.getByTestId("project-name")).toHaveValue("Coupons for the class");
  const chat = page.getByTestId("coupon-chat");
  await expect(chat.locator(".chat-user").first()).toHaveText("I want to test some coupons");
  await expect(chat.getByTestId("chat-set-up")).toBeVisible();
  await expect(chat.getByTestId("chat-question")).toHaveAttribute("data-step", "material"); // the message said no more, so it is not read again
  await expect.poll(() => Object.values(store).find((p) => p.name === "Coupons for the class")?.content, { timeout: 10_000 })
    .not.toHaveProperty("analysis"); // kept on the server as a coupon
});

test("a model's versions are kept on the server with its project, so a change made elsewhere is in its history (ADR-0143)", async ({ page }) => {
  const store: Record<string, Record<string, unknown>> = {};
  const versions: Record<string, Kept[]> = {};
  await quietApi(page, store, [], versions);
  await page.goto("/workspace");
  await page.getByTestId("workspace-tiles").locator("[data-workspace=fea]").click();
  await page.getByTestId("fea-start-kinds").locator("[data-kind=coupon]").click();
  await page.getByTestId("chat-question").getByRole("button", { name: "IM7 / 8552", exact: true }).click();
  // the project reaches the server a moment after it is made, and its versions after it, numbered there
  await expect.poll(() => Object.values(versions).flat().some((v) => v.form.library === "im7-8552"), { timeout: 20_000 }).toBe(true);
  const id = Object.keys(versions)[0];
  expect(store[id]).toBeTruthy();
  expect(versions[id].map((v) => v.n)).toEqual(versions[id].map((_, i) => i + 1));
  // a change the workspace's tools made, kept on the server as the next version; this browser's own copy then cleared, as on another computer
  const last = versions[id][versions[id].length - 1];
  versions[id].push({ ...last, n: last.n + 1, by: "assistant", why: "use 3 mm elements", changes: ["Element size (mm): blank → 3"], form: { ...last.form, element_size: "3" } });
  await page.evaluate((key) => window.localStorage.removeItem(key), `anisotropy.versions.${id}`);
  await page.reload();
  const history = page.getByTestId("tree-history");
  await expect(history.locator("li[data-by=assistant]").filter({ hasText: "use 3 mm elements" })).toHaveCount(1, { timeout: 20_000 });
});

test("a switch to another section goes at once from an empty project and asks first when work is open (ADR-0124)", async ({ page }) => {
  await quietApi(page);
  await page.goto("/workspace");
  await page.getByTestId("workspace-tiles").locator("[data-workspace=fea]").click();
  await page.getByTestId("fea-start-kinds").locator("[data-kind=coupon]").click();
  const message = page.getByLabel("Message the coupon assistant", { exact: true });
  const question = page.getByTestId("chat-question");
  await expect(question).toHaveAttribute("data-step", "material");
  await question.getByRole("button", { name: "IM7 / 8552", exact: true }).click(); // now the coupon holds work
  await expect(question).toHaveAttribute("data-step", "layup");
  await message.fill("let's do a hand calc of [0/90]s instead");
  await message.press("Enter");
  const ask = page.getByTestId("chat-switch");
  await expect(ask).toContainText("Open Laminate?");
  await expect(ask).toContainText("Your coupon is saved under Projects");
  await ask.getByTestId("switch-stay").click();
  await expect(page).toHaveURL(/\/workspace\/fea/);
  await expect(ask.getByTestId("switch-go")).toBeDisabled(); // answered once
  await message.fill("let's do a hand calc of [0/90]s instead");
  await message.press("Enter");
  await page.getByTestId("chat-switch").last().getByTestId("switch-go").click();
  await expect(page).toHaveURL(/\/workspace\/laminate\/?$/);
  const laminate = page.getByLabel("Message the laminate assistant", { exact: true });
  await expect(page.getByTestId("laminate-chat").locator(".chat-user").first()).toHaveText("let's do a hand calc of [0/90]s instead"); // carried
  await expect(page.getByTestId("chat-switch")).toHaveCount(0);
  await page.getByRole("link", { name: "All projects" }).click();
  await expect(page.getByTestId("workspace-projects").locator("tbody tr[data-kind=fea]").first()).toContainText("im7-8552"); // kept as it was, its material by the library's id

  await page.getByTestId("workspace-projects").locator("tbody tr[data-kind=laminate]").first().getByRole("button", { name: "Open" }).click();
  await laminate.fill("I want to test some coupons"); // the laminate holds nothing of the engineer's yet: FEA opens at once
  await laminate.press("Enter");
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await expect(page.getByTestId("coupon-chat").getByTestId("chat-set-up")).toBeVisible();
  await expect(page.getByTestId("chat-question")).toHaveAttribute("data-step", "material"); // a new coupon: the one with work is kept apart
});
