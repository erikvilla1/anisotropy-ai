import { readFileSync } from "node:fs";
import { test, expect, type Page, type Route } from "@playwright/test";
import { bannedIn } from "../../lib/studio-copy";

/** The repair's page and its report (ADR-0135), with the API played from the engine's and the solver's own answers to the two examples
 * (tests/fixtures/repair, written by scripts/repair-choices.py and checked against the API by api/tests/test_repairs_api.py). What the
 * page sends is recorded, so each test can say what was asked. */
const read = (name: string) => JSON.parse(readFileSync(`tests/fixtures/repair/${name}.json`, "utf-8"));
const ANSWER = read("example-answer"), EXTERNAL = read("external-answer"), SOLVE = read("example-solve");
// the chat's (ADR-0136): the engine's previews of two changes, its sweep of the step length to a load, and what the solved slice of
// that sweep's pick says of it, as the API puts the two together
const STEP_CHANGE = read("example-step-change"), LENGTH_CHANGE = read("example-change"), SWEEP = { ...read("example-sweep"), check: read("example-sweep-check") };
/** One section of our page "Bonded repairs", cut from the page itself as the API's search cuts it. */
function section(title: string) {
  const page = readFileSync("engine/docs/references/bonded-repairs.md", "utf-8");
  const text = page.split(/^## /m).find((part) => part.startsWith(`${title}\n`))!.slice(title.length).replace(/<!--[\s\S]*?-->/g, "").trim();
  return { id: `repairs:${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`, document: "Bonded repairs", title, text };
}
const SHAPE = { run_id: null, step: "ISO-10303-21;\nEND-ISO-10303-21;\n", parts: { title: "Example stepped patch repair", units: { length: "mm", volume: "mm^3" },
  parts: [{ name: "Laminate ply 1 (45°)", kind: "parent", angle: 45, volume: 10972.8 }, { name: "Patch ply 1 (90°)", kind: "patch", angle: 90, volume: 89.77 },
    { name: "Adhesive on the floor", kind: "adhesive", angle: null, volume: 49.09 }], volumes: { parent: 85089, patch: 2678.8, cover: 2244.3, adhesive: 1241.5 } } };

type Sent = { repair?: Record<string, Record<string, unknown> & unknown>; toml?: string; cut_faces?: string };
type Reply = { status: number; body: unknown };
const solves: Sent[] = []; // what "Solve the slice" sent, in the test that runs
const shapes: Sent[] = []; // what Download STEP sent
type Asked = Sent & { change?: Record<string, unknown>; sweep?: Record<string, unknown>; question?: string; about?: string };
const changes: Asked[] = []; // what the chat sent for a preview
const sweeps: Asked[] = []; // what the chat sent for a sweep
const searched: Asked[] = []; // what the chat asked of the reference pages
/** What the chat's three addresses answer in a test: by default the engine's preview of the change read, the sweep with its pick held,
 * and the section on where the shear stress peaks. */
const chat: { change(body: Asked): Reply; sweep(body: Asked): Reply; sections: unknown[] } = { change: () => ({ status: 404, body: {} }), sweep: () => ({ status: 404, body: {} }), sections: [] };

/** Plays the three addresses of a repair. `answer` says what the hand calculation answers to a body; by default the engine's answer to
 * whichever example's kind the body states. */
async function playRepairs(page: Page, answer: (body: Sent) => Reply = (body) => ({ status: 200, body: (body.repair as Record<string, unknown> | undefined)?.kind === "external" ? EXTERNAL : ANSWER }),
  solve: (body: Sent) => Reply = () => ({ status: 200, body: SOLVE })) {
  const sent: Sent[] = [];
  solves.length = 0;
  shapes.length = 0;
  changes.length = 0;
  sweeps.length = 0;
  searched.length = 0;
  chat.change = (body) => ({ status: 200, body: body.change?.action === "add_steps" ? STEP_CHANGE : LENGTH_CHANGE });
  chat.sweep = () => ({ status: 200, body: SWEEP });
  chat.sections = [section("Why the shear stress peaks at the ends of a step"), section("Why more steps lower the peak")];
  await page.route(/\/v1\/.*/, (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = (request.method() === "POST" ? request.postDataJSON() : {}) as Sent;
    const reply = (r: Reply) => route.fulfill({ status: r.status, contentType: "application/json", body: JSON.stringify(r.body) });
    if (path.endsWith("/v1/repairs/analyze")) { sent.push(body); return reply(answer(body)); }
    if (path.endsWith("/v1/repairs/solve")) { solves.push(body); return reply(solve(body)); }
    if (path.endsWith("/v1/repairs/shape")) { shapes.push(body); return reply({ status: 200, body: SHAPE }); }
    if (path.endsWith("/v1/repairs/changes")) { changes.push(body); return reply(chat.change(body)); }
    if (path.endsWith("/v1/repairs/sweeps")) { sweeps.push(body); return reply(chat.sweep(body)); }
    if (path.endsWith("/v1/workspace/theory-sections")) { searched.push(body); return reply({ status: 200, body: { run_id: null, sections: chat.sections } }); }
    return reply({ status: 404, body: { detail: "not in this scenario" } });
  });
  return sent;
}

test("a patch repair is picked at the FEA start, opens on the example and shows the bondline worked by hand (ADR-0135)", async ({ page }) => {
  const sent = await playRepairs(page);
  await page.goto("/workspace");
  await page.getByTestId("workspace-tiles").locator("[data-workspace=fea]").click();
  await page.getByTestId("fea-start-kinds").locator("[data-kind=repair]").click();
  await expect(page).toHaveURL(/\/workspace\/repair\/?$/);
  await expect(page.locator(".cv-kind > span")).toHaveText("FEA · Patch repair");
  await expect(page.getByTestId("project-name")).toHaveValue("Example stepped patch repair");
  await expect(page.getByTestId("repair-headline")).toHaveText("Largest bondline shear 12.58 MPa under 100 N/mm");
  await expect(page.getByTestId("repair-detail")).toHaveText("By hand, at the inner end of the ledge of step 1. The adhesive reaches its elastic limit in shear at 238.5 N/mm. Not the repair's strength: the adhesive yields before it fails.");
  expect(sent[0].repair).toEqual(ANSWER.repair); // the description itself, as the repair file reads
  await expect(page.getByTestId("project-status")).toHaveText("Worked by hand on every change. Kept in this browser.");
  // the slice as the engine cut it: every rectangle drawn, the laminate's, the patch's and the adhesive's
  const slice = page.getByTestId("repair-slice");
  await expect(slice).toBeVisible();
  await expect(slice.locator("rect[data-kind=parent]")).toHaveCount(ANSWER.report.regions.filter((g: { kind: string; r0: number }) => g.kind === "parent" && g.r0 < 78.125).length);
  expect(await slice.locator("rect[data-kind=adhesive]").count()).toBeGreaterThan(4);
  await expect(page.getByTestId("repair-slice-legend")).toContainText("patch and cover plies");
  await expect(page.getByTestId("repair-slice-caption")).toContainText("The thickness is drawn about 9 times larger than the length.");
  // the chart under it: the hand calculation alone until the slice is solved
  const chart = page.getByTestId("repair-bond-chart");
  await expect(chart.locator("polyline[data-series=hand]")).toHaveCount(1);
  await expect(chart.locator("polyline[data-series=shear]")).toHaveCount(0);
  await expect(page.getByTestId("repair-bond-chart-key")).toContainText("Shear by hand");
  await expect(page.getByTestId("repair-slice-short")).toHaveText("The slice is not solved yet: it adds the peel stress and each ply's stresses.");
  // the assistant's column says what the numbers are, and holds the chat under it (ADR-0136)
  await expect(page.getByTestId("repair-explain")).toContainText("12.58 MPa by hand, at the inner end of the ledge of step 1.");
  await expect(page.getByTestId("repair-not-strength")).toContainText("Neither answer is a failure load.");
  await expect(page.getByTestId("repair-no-chat")).toHaveCount(0);
  await expect(page.getByLabel("Message the repair assistant")).toBeVisible();
  await expect(page.getByTestId("repair-chat")).toContainText("Nothing changes until you tap Apply");
  // the details hold the hand calculation's table, the peak's row marked, and what the analysis is not
  await page.getByTestId("details-toggle").click();
  await expect(page.getByTestId("repair-lap").locator("tbody tr")).toHaveCount(5);
  await expect(page.getByTestId("repair-lap").locator("tr[data-peak=true] th")).toHaveText("Ledge of step 1");
  await expect(page.getByTestId("repair-lap")).not.toContainText("× 10"); // a zero of the arithmetic prints as 0
  await expect(page.getByTestId("repair-sizes")).toContainText("Plies removed, plies left");
  await expect(page.getByTestId("repair-limits").locator("li")).toHaveCount(5);
});

test("the words for a patch repair open its page from the FEA start, and a question about one offers it", async ({ page }) => {
  await playRepairs(page);
  await page.goto("/workspace/fea");
  const box = page.getByLabel("Message the FEA assistant");
  await box.fill("what is a scarf repair?");
  await box.press("Enter");
  // the question is answered in words (here the service has no answer for it), and the repair's page is offered under it, not opened
  await expect(page.getByTestId("fea-start-answer").last()).toBeVisible();
  await expect(page).toHaveURL(/\/workspace\/fea\/?$/);
  await box.fill("a bonded repair over an open hole");
  await box.press("Enter");
  await expect(page).toHaveURL(/\/workspace\/repair\/?$/); // a repair, though an open hole is a coupon's word too
  await expect(page.getByTestId("repair-headline")).toBeVisible();
});

test("a change is worked once the typing settles, a refusal keeps the last answer in the engine's words, and the repair is kept over a reload", async ({ page }) => {
  const sent = await playRepairs(page, (body) => {
    const steps = (body.repair?.steps ?? {}) as Record<string, unknown>;
    return steps.count === 9 ? { status: 422, body: { detail: "9 steps of 1 plies remove 9 plies, and the laminate has 8" } } : { status: 200, body: ANSWER };
  });
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  const before = sent.length;
  const load = page.getByTestId("repair-applied-load");
  await load.fill("12");
  await load.fill("120");
  await expect.poll(() => sent.length).toBe(before + 1); // one request for the settled value, not one a keystroke
  expect((sent.at(-1)?.repair?.applied as Record<string, unknown>).load).toBe(120);
  await load.fill("heavy");
  await expect(page.getByText("Not a number.")).toBeVisible();
  await page.waitForTimeout(600);
  expect(sent.length).toBe(before + 1); // what does not read is not sent
  await load.fill("120");
  await page.getByTestId("repair-steps-count").fill("9");
  await expect(page.getByTestId("repair-problem")).toHaveText("The repair calculation: 9 steps of 1 plies remove 9 plies, and the laminate has 8");
  await expect(page.getByTestId("repair-answer")).toContainText("The results shown are for the last repair that could be worked.");
  await expect(page.getByTestId("repair-headline")).toHaveText("Largest bondline shear 12.58 MPa under 100 N/mm");
  await expect(page.getByTestId("repair-solve-button")).toBeDisabled(); // a repair the engine refuses is not solved
  await page.getByTestId("repair-steps-count").fill("4");
  await expect(page.getByTestId("repair-problem")).toHaveCount(0);
  await page.getByTestId("project-name").fill("Skin repair at frame 12");
  await expect.poll(() => sent.at(-1)?.repair?.title).toBe("Skin repair at frame 12");
  await page.reload();
  await expect(page.getByTestId("project-name")).toHaveValue("Skin repair at frame 12"); // kept in this browser
  await expect(page.getByTestId("repair-applied-load")).toHaveValue("120");
  await page.getByTestId("repair-example").click();
  await expect(page.getByTestId("project-name")).toHaveValue("Example stepped patch repair");
});

test("the slice is solved on request: its stresses join the chart, its tables the details, and a change says the solve is of the repair as it was", async ({ page }) => {
  await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  await expect(page.getByTestId("repair-needs")).toHaveCount(0);
  await page.getByTestId("repair-solve-here").click();
  await expect(page.getByTestId("repair-slice-short")).toHaveText("Solved slice: Under 100 N/mm: largest bondline shear 11.5 MPa (hand calculation 12.58), largest peel 4.112 MPa; first, the adhesive reaches its elastic limit in shear at 260.8 N/mm.");
  expect(solves).toHaveLength(1);
  expect(solves[0].repair).toEqual(ANSWER.repair);
  expect(solves[0].cut_faces).toBe("open");
  await expect(page.getByTestId("project-status")).toHaveText("Worked by hand and as a solved slice. Kept in this browser.");
  const chart = page.getByTestId("repair-bond-chart");
  expect(await chart.locator("polyline[data-series=shear]").count()).toBeGreaterThan(0);
  expect(await chart.locator("polyline[data-series=peel]").count()).toBeGreaterThan(0);
  await expect(page.getByTestId("repair-bond-chart-key")).toContainText("Peel, solved slice");
  await expect(page.getByTestId("repair-solve-status")).toContainText("largest peel 4.112 MPa");
  await page.getByTestId("details-toggle").click();
  await expect(page.getByTestId("repair-slice-model")).toContainText("Solved as 6,344 eight-node plane elements held flat, 38,838 equations");
  const lines = page.getByTestId("repair-slice-lines");
  await expect(lines).toContainText("Largest shear 11.5 MPa, 37.29 mm from the middle (the adhesive on the ledge of step 2); by hand 12.58 MPa.");
  await expect(lines).toContainText("The adhesive reaches its elastic limit in shear at 260.8 N/mm; by hand 238.5 N/mm. Not the repair's strength: the adhesive yields before it fails.");
  await expect(lines).toContainText("First ply by maximum stress: laminate ply 6 (−45°), transverse tension, at 466.1 N/mm");
  await expect(page.getByTestId("repair-boundaries").locator("tbody tr")).toHaveCount(SOLVE.report.boundaries.length);
  await expect(page.getByTestId("repair-plies").locator("tbody tr")).toHaveCount(6);
  await expect(page.getByTestId("repair-force-chart").locator("polyline[data-series=laminate]")).toHaveCount(1);
  await page.getByTestId("details-toggle").click();
  // the cut faces' choice belongs to the solve: changing it, or the repair, makes the solve one of the repair as it was
  await page.getByTestId("repair-cut-faces").selectOption("bonded");
  await expect(page.getByTestId("repair-slice-short")).toHaveText("The slice was solved for the repair as it was. Solve it again for this one.");
  await expect(chart.locator("polyline[data-series=shear]")).toHaveCount(0); // its lines would stand under a slice they do not belong to
  await page.getByTestId("repair-solve-button").click();
  await expect.poll(() => solves.length).toBe(2);
  expect(solves[1].cut_faces).toBe("bonded");
  await expect(page.getByTestId("repair-slice-short")).toContainText("Solved slice:");
  await page.reload();
  await expect(page.getByTestId("repair-slice-short")).toContainText("Solved slice:"); // the solve is kept with the repair
  await expect(page.getByTestId("repair-cut-faces")).toHaveValue("bonded");
});

test("a solve that cannot be made says so and keeps the page as it was, and a repair that lacks what the solve needs says what", async ({ page }) => {
  await playRepairs(page, (body) => {
    const adhesive = (body.repair?.adhesive ?? {}) as Record<string, unknown>;
    return { status: 200, body: adhesive.poisson === undefined ? { ...ANSWER, repair: body.repair, needs: [{ path: "adhesive.poisson", words: "the adhesive's Poisson's ratio" }] } : ANSWER };
  }, () => ({ status: 503, body: { detail: "The slice cannot be solved right now. Try again in a minute." } }));
  await page.goto("/workspace/repair");
  await page.getByTestId("repair-solve-here").click();
  await expect(page.getByTestId("repair-solve-problem")).toHaveText("Analysis is unavailable right now. Your inputs are kept; try again in a minute, and contact us if it continues.");
  await expect(page.getByTestId("repair-slice-short")).toHaveText("The slice is not solved yet: it adds the peel stress and each ply's stresses.");
  await page.locator("#panel-repair-adhesive > summary").click();
  await page.getByTestId("repair-adhesive-poisson").fill("");
  await expect(page.getByTestId("repair-needs")).toHaveText("The solve of the slice still needs the adhesive's Poisson's ratio.");
  await expect(page.getByTestId("repair-solve-button")).toBeDisabled();
  await expect(page.getByTestId("repair-solve-here")).toHaveCount(0);
  await expect(page.getByTestId("repair-slice-short")).toHaveText("The solve of the slice still needs the adhesive's Poisson's ratio.");
});

test("the other kind of repair, a patch bonded on top, has its own steps and its own answer", async ({ page }) => {
  const sent = await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("panel-repair-cover")).toBeVisible();
  await page.getByTestId("repair-example-external").click();
  await expect(page.getByTestId("repair-headline")).toHaveText("Largest bondline shear 21.09 MPa under 100 N/mm");
  expect(sent.at(-1)?.repair).toEqual(EXTERNAL.repair);
  await expect(page.getByTestId("repair-kind")).toHaveValue("external");
  await expect(page.getByTestId("panel-repair-cover")).toHaveCount(0); // a patch on top has no cover plies
  await expect(page.getByTestId("repair-patch-layup")).toHaveValue("0, 45, -45, 0, 0, 90");
  await expect(page.getByTestId("repair-patch-overlap")).toHaveValue("15");
  await expect(page.getByTestId("repair-cut-faces")).toHaveCount(0); // nothing is cut in steps
  await expect(page.getByTestId("repair-slice-caption")).toContainText("inward to the hole's edge, 12.5 mm from the middle");
  // changing the kind keeps the laminate and takes what only the other kind states from its example
  await page.getByTestId("repair-kind").selectOption("flush");
  await expect.poll(() => (sent.at(-1)?.repair as Record<string, unknown>).kind).toBeUndefined();
  expect((sent.at(-1)?.repair as Record<string, unknown>).patch).toBeUndefined();
  expect((sent.at(-1)?.repair?.parent as Record<string, unknown>).layup).toEqual([45, 0, -45, 90, 90, -45, 0, 45]);
});

test("the repair is saved as a repair file and opened from one through the engine, and its solids download as a STEP file", async ({ page }) => {
  const sent = await playRepairs(page, (body) => body.toml !== undefined
    ? (body.toml.includes("kind = \"external\"") ? { status: 200, body: EXTERNAL } : { status: 422, body: { detail: "The repair has tables it does not read: wing" } })
    : { status: 200, body: ANSWER });
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  const saving = page.waitForEvent("download");
  await page.getByTestId("repair-save").click();
  const saved = await saving;
  expect(saved.suggestedFilename()).toBe("example-stepped-patch-repair.toml");
  expect(readFileSync(await saved.path(), "utf-8")).toBe(readFileSync("tests/fixtures/repair/example-saved.toml", "utf-8"));
  const file = page.getByTestId("repair-file");
  await file.setInputFiles({ name: "wrong.toml", mimeType: "text/plain", buffer: Buffer.from("title = \"A wing\"\n[wing]\n") });
  await expect(page.getByTestId("repair-file-note")).toHaveText("wrong.toml was not opened: The repair calculation: The repair has tables it does not read: wing");
  await expect(page.getByTestId("project-name")).toHaveValue("Example stepped patch repair"); // a file the engine refuses changes nothing
  await file.setInputFiles({ name: "on-top.toml", mimeType: "text/plain", buffer: readFileSync("tests/fixtures/repair/external-saved.toml") });
  await expect(page.getByTestId("repair-file-note")).toHaveText("on-top.toml opened.");
  await expect(page.getByTestId("project-name")).toHaveValue("Example patch bonded on top");
  await expect(page.getByTestId("repair-headline")).toHaveText("Largest bondline shear 21.09 MPa under 100 N/mm");
  expect(sent.filter((s) => s.toml !== undefined)).toHaveLength(2);
  expect(sent.filter((s) => s.repair && (s.repair as Record<string, unknown>).kind === "external")).toHaveLength(0); // the opened file's answer is not asked for twice
  await page.locator("#panel-repair-report > summary").click();
  const stepping = page.waitForEvent("download");
  await page.getByTestId("repair-step").click();
  const step = await stepping;
  expect(step.suggestedFilename()).toBe("example-patch-bonded-on-top.step");
  expect(shapes[0].repair).toEqual(EXTERNAL.repair);
  await expect(page.getByTestId("repair-step-note")).toHaveText("example-patch-bonded-on-top.step saved: 3 solids, in millimetres.");
  await expect(page.getByTestId("repair-solids").locator("tbody tr")).toHaveCount(4);
});

test("the report lays the repair out for paper: what is stated, the slice, the hand calculation and the solved slice that belongs to it", async ({ page }) => {
  const sent = await playRepairs(page);
  await page.goto("/workspace/repair");
  await page.getByTestId("repair-solve-here").click();
  await expect(page.getByTestId("repair-slice-short")).toContainText("Solved slice:");
  await page.locator("#panel-repair-report > summary").click();
  const opening = page.context().waitForEvent("page");
  await page.getByTestId("repair-report-link").click();
  const report = await opening;
  await playRepairs(report);
  await report.reload(); // the new tab asked before its API was played
  await expect(report.getByTestId("repair-report")).toHaveAttribute("data-state", "ready");
  await expect(report.getByTestId("repair-report-title")).toHaveText("Example stepped patch repair");
  await report.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
  await expect(report).toHaveTitle("example-stepped-patch-repair-report"); // while it prints: the name the browser offers for the PDF
  await report.evaluate(() => window.dispatchEvent(new Event("afterprint")));
  await expect(report).toHaveTitle(/Patch repair report/);
  const summary = report.getByTestId("repair-report-summary");
  await expect(summary).toContainText("Largest bondline shear 12.58 MPa under 100 N/mm.");
  await expect(summary).toContainText("Not the repair's strength: the adhesive yields before it fails.");
  await expect(report.getByTestId("repair-report-solve-line")).toContainText("Solved slice: Under 100 N/mm: largest bondline shear 11.5 MPa");
  await expect(report.getByRole("heading", { level: 2 })).toHaveText(["Summary", "1. The repair as stated", "2. The repair as measured", "3. The bondline by hand", "4. The solved slice", "5. What these numbers are not"]);
  const stated = report.getByTestId("repair-report-stated");
  await expect(stated).toContainText("IM7 / 8552");
  await expect(stated).toContainText("[45/0/−45/90/90/−45/0/45], 8 plies");
  await expect(stated).toContainText("100 N/mm");
  await expect(report.getByTestId("repair-slice")).toBeVisible();
  await expect(report.getByTestId("repair-lap").locator("tbody tr")).toHaveCount(5);
  await expect(report.getByTestId("repair-bond-chart").locator("polyline[data-series=peel]").first()).toBeVisible();
  await expect(report.getByTestId("repair-plies").locator("tbody tr")).toHaveCount(6);
  await expect(report.getByTestId("repair-limits").locator("li")).toHaveCount(5);
  await expect(report.getByTestId("repair-report-print")).toBeEnabled();
  // on paper: the page's own buttons and the site's header are not printed, and the sheet is white
  await report.emulateMedia({ media: "print" });
  await expect(report.getByTestId("repair-report-print")).toBeHidden();
  await expect(report.locator(".site-header")).toBeHidden();
  expect(await report.getByTestId("repair-report").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(255, 255, 255)");
  await report.emulateMedia({ media: "screen" });
  // the report names no tool and no machinery either (ADR-0091)
  expect(bannedIn(await report.locator("main").innerText())).toEqual([]);
  await report.close();
  // a repair changed since its slice was solved: the report leaves the solve out and says so
  await page.getByTestId("repair-applied-load").fill("120");
  await expect.poll(() => (sent.at(-1)?.repair?.applied as Record<string, unknown>).load).toBe(120);
  await page.goto("/workspace/repair/report");
  await expect(page.getByTestId("repair-report-solve-line")).toHaveText("The slice was solved for an earlier state of this repair, so its results are left out of this report.");
  await expect(page.getByTestId("repair-report-slice")).toHaveCount(0);
  await expect(page.getByRole("heading", { level: 2 })).toHaveCount(5);
  await page.getByTestId("repair-report-back").click();
  await expect(page).toHaveURL(/\/workspace\/repair\/?$/);
});

/** Sends one message in the repair's chat and gives its answer: the last one in the chat. */
async function ask(page: Page, message: string) {
  const box = page.getByLabel("Message the repair assistant");
  const answers = page.getByTestId("repair-chat-answer");
  const before = await answers.count();
  await box.fill(message);
  await box.press("Enter");
  await expect(answers).toHaveCount(before + 1);
  return answers.last();
}

test("“add a step” and “make each step 0.5 in” are previewed by the engine on a copy, applied by a tap and undone (ADR-0136)", async ({ page }) => {
  const sent = await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  const worked = sent.length;
  const added = await ask(page, "Add a step");
  await expect(added).toHaveAttribute("data-kind", "preview");
  await expect(added.getByTestId("repair-preview-words")).toHaveText(STEP_CHANGE.words);
  // the page sent the repair as it stands and the change as it read it; every number of the preview is the engine's
  expect(changes).toHaveLength(1);
  expect(changes[0].repair).toEqual(ANSWER.repair);
  expect(changes[0].change).toEqual({ action: "add_steps", count: 1 });
  const table = added.getByTestId("repair-preview-table");
  await expect(table.locator("tbody tr").nth(0)).toHaveText("Steps4 of 1 ply5 of 1 ply");
  await expect(table.locator("tbody tr").nth(1)).toHaveText("Repair width (mm)125150");
  await expect(table.locator("tbody tr")).toHaveCount(5); // steps, width, load, largest shear, elastic limit load
  await expect(added.getByTestId("repair-preview-place")).toHaveText("The largest shear stays at the inner end of the ledge of step 1.");
  await expect(added.getByRole("heading")).toHaveText("Preview: not applied yet");
  expect(await table.evaluate((el) => el.scrollWidth <= el.parentElement!.clientWidth + 1)).toBe(true); // the table fits the chat's column
  // nothing has changed yet: the repair is still the example, and it was not worked again
  await expect(page.getByTestId("repair-steps-count")).toHaveValue("4");
  expect(sent.length).toBe(worked);
  await added.getByTestId("repair-apply").click();
  await expect(added.getByTestId("repair-applied")).toContainText("Applied: the repair is worked again.");
  await expect(page.getByTestId("repair-steps-count")).toHaveValue("5");
  await expect.poll(() => sent.at(-1)?.repair).toEqual(STEP_CHANGE.repair); // the changed repair is worked by hand like any other
  await added.getByTestId("repair-undo").click();
  await expect(added.getByTestId("repair-undone")).toHaveText("Undone: the repair is as it was.");
  await expect(page.getByTestId("repair-steps-count")).toHaveValue("4");
  // the plan's other change, with its unit: the engine converts it, the page does not
  const longer = await ask(page, "make each step 0.5 in");
  await expect(longer.getByTestId("repair-preview-words")).toHaveText("The step length goes from 12.5 mm to 12.7 mm (0.5 in as written).");
  expect(changes[1].change).toEqual({ action: "set", quantity: "step_length", value: 0.5, unit: "in" });
  await longer.getByTestId("repair-apply").click();
  await expect(page.getByTestId("repair-steps-length")).toHaveValue("12.7");
  const undone = await ask(page, "undo");
  await expect(undone.getByTestId("repair-chat-heading")).toHaveText("Undone");
  await expect(undone).toContainText("The repair is as it was before “make each step 0.5 in”.");
  await expect(page.getByTestId("repair-steps-length")).toHaveValue("12.5");
  // a change the engine refuses is said in its words and changes nothing; a change with no value asks for one and sends nothing
  chat.change = () => ({ status: 422, body: { detail: "9 steps of 1 plies remove 9 plies, and the laminate has 8" } });
  const refused = await ask(page, "make it 9 steps");
  await expect(refused.getByTestId("repair-chat-problem")).toHaveText("The preview of the repair's change: 9 steps of 1 plies remove 9 plies, and the laminate has 8");
  await expect(refused.getByTestId("repair-apply")).toHaveCount(0);
  const vague = await ask(page, "thicker bondline");
  await expect(vague).toContainText("To what value?");
  expect(changes).toHaveLength(3);
});

test("a sweep names the smallest repair whose adhesive stays elastic at the load, held to its solved slice, and never calls it a strength (ADR-0136)", async ({ page }) => {
  await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  const swept = await ask(page, "sweep the step length from 3 to 25 mm for the smallest repair that stays elastic at 230 N/mm");
  await expect(swept).toHaveAttribute("data-kind", "sweep");
  await expect(swept.getByTestId("repair-sweep-heading")).toHaveText("Step length 4 mm: still elastic at 230 N/mm");
  expect(sweeps[0].repair).toEqual(ANSWER.repair);
  expect(sweeps[0].sweep).toEqual({ quantity: "step_length", start: 3, end: 25, unit: "mm", load: 230, load_unit: "N/mm" });
  expect(sweeps[0].cut_faces).toBe("open");
  // the answer is one sentence; what was swept, the value not worked and the flat stretch are folded under it with the table
  await expect(swept.getByTestId("repair-sweep-words"))
    .toHaveText(["The smallest of these whose adhesive is still elastic at 230 N/mm: a step length of 4 mm, the repair 74 mm across. Its adhesive reaches its elastic limit at 233.5 N/mm."]);
  // the pick solved as a slice: what the solver says of it, and whether the slice holds it
  const check = swept.getByTestId("repair-sweep-check");
  await expect(check).toHaveAttribute("data-holds", "true");
  await expect(check).toHaveText("The pick solved as a slice under 100 N/mm: largest bondline shear 11.72 MPa, largest peel stress 4.117 MPa. As the load grows, the adhesive reaches its elastic limit in shear first, at 256 N/mm. That is at or above the 230 N/mm named: the slice holds the pick.");
  await expect(swept.getByTestId("repair-sweep-caution")).toHaveText([
    "Not the repair's strength: the adhesive yields before it fails, and the hand calculation has no peel stress.",
    "A short step that keeps the adhesive elastic in this model is not a rule for choosing a step length.",
  ]);
  // every value is in the details, the pick and the repair as it stands marked, a value the engine could not work said so
  await swept.locator("details.chat-details > summary").click();
  const rows = swept.getByTestId("repair-sweep-table").locator("tbody tr");
  await expect(rows).toHaveCount(SWEEP.rows.length);
  await expect(rows.nth(0)).toHaveText("36813.15228.1No");
  await expect(swept.locator("tr[data-pick=true]")).toHaveText("4 (pick)7412.85233.5Yes");
  await expect(swept.locator("tr[data-current=true] th")).toHaveText("12.5 (as it is)");
  await expect(rows.last()).toContainText("Not worked: The repair is 0.2 m across");
  await expect(swept.getByTestId("repair-sweep-rest")).toHaveText([
    "The step length from 3 mm to 25 mm, 24 values, each worked by hand under 100 N/mm.",
    "1 of them could not be worked. At 25 mm: The repair is 0.2 m across, so the panel must be longer and wider than that (it is 0.3 m by 0.2 m).",
    "From 6 mm up the elastic limit load stays within 1 % of 238.6 N/mm: past it, the step length no longer changes it.",
  ]);
  const words = await swept.innerText();
  expect(words).not.toMatch(/\bstrong\b|\bsafe\b|\bmargin\b|\bdesign\b|\bcarries\b|restores?\b/i);
  expect(words.match(/strength/gi)).toHaveLength(1); // only in "Not the repair's strength"
  expect(bannedIn(words)).toEqual([]);
  // the pick is applied like any change, and undone
  await swept.getByTestId("repair-apply").click();
  await expect(page.getByTestId("repair-steps-length")).toHaveValue("4");
  await swept.getByTestId("repair-undo").click();
  await expect(page.getByTestId("repair-steps-length")).toHaveValue("12.5");
  // a pick whose slice could not be solved says it is not checked; a pick the slice does not hold says so
  chat.sweep = () => ({ status: 200, body: { ...SWEEP, check: { state: "failed", holds: null, words: ["The pick's slice could not be solved right now, so the pick is not checked by a solved slice."] } } });
  const unchecked = await ask(page, "smallest repair that stays elastic at 230 N/mm");
  expect(sweeps[1].sweep).toEqual({ quantity: "step_length", load: 230, load_unit: "N/mm" });
  await expect(unchecked.getByTestId("repair-sweep-check")).toHaveAttribute("data-holds", "unchecked");
  await expect(unchecked.getByTestId("repair-sweep-check")).toHaveText("The pick's slice could not be solved right now, so the pick is not checked by a solved slice.");
  // a pick its solved slice does not hold, or is too close to say, is headed as the hand calculation's and no more
  const NEAR = "That is within 2 % of the 230 N/mm named, as far as a finer mesh may move a slice's number: too close to say whether the slice holds the pick.";
  chat.sweep = () => ({ status: 200, body: { ...SWEEP, check: { state: "solved", holds: null, close: true, words: [NEAR] } } });
  const near = await ask(page, "sweep the step length 3 to 25 mm at 230 N/mm");
  await expect(near.getByTestId("repair-sweep-heading")).toHaveText("Step length 4 mm by hand; too close in the slice");
  await expect(near.getByTestId("repair-sweep-check")).toHaveAttribute("data-holds", "close");
  await expect(near.getByTestId("repair-sweep-check")).toHaveText(NEAR);
  chat.sweep = () => ({ status: 200, body: { ...SWEEP, check: { state: "solved", holds: false, close: false, words: ["That is below the 230 N/mm named: the slice does not hold the pick."] } } });
  const below = await ask(page, "sweep the step length 3 to 25 mm at 230 N/mm");
  await expect(below.getByTestId("repair-sweep-heading")).toHaveText("Step length 4 mm by hand; the slice says no");
  await expect(below.getByTestId("repair-sweep-check")).toHaveAttribute("data-holds", "false");
  chat.sweep = () => ({ status: 422, body: { detail: "The repair states no load per unit width, so no value can be picked for a load" } });
  const refused = await ask(page, "sweep the bondline for 230 N/mm");
  await expect(refused.getByTestId("repair-chat-problem")).toHaveText("The sweep: The repair states no load per unit width, so no value can be picked for a load");
});

test("the chat answers a question from the page's own results, gives no verdict, takes why from our pages and says what it cannot read (ADR-0136)", async ({ page }) => {
  await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  const shear = await ask(page, "whta is the peak sheer?");
  await expect(shear.getByTestId("repair-chat-heading")).toHaveText("12.58 MPa by hand, at the inner end of the ledge of step 1");
  await expect(shear).toContainText("The largest shear stress in the adhesive under 100 N/mm.");
  const verdict = await ask(page, "is it strong enough?");
  await expect(verdict).toHaveAttribute("data-kind", "verdict");
  await expect(verdict.getByTestId("repair-chat-heading")).toHaveText("This page gives no strength or verdict");
  await expect(verdict).toContainText("By hand, the adhesive reaches its elastic limit in shear at 238.5 N/mm; the load stated is 100 N/mm.");
  // a yes or no by hand, and a fragment after it that takes its question from the message before
  const elastic = await ask(page, "is the adhesive still elastic at 200 N/mm?");
  await expect(elastic.getByTestId("repair-chat-heading")).toHaveText("Yes, by hand: still elastic at 200 N/mm");
  const next = await ask(page, "and at 250?");
  await expect(next.getByTestId("repair-chat-heading")).toHaveText("No, by hand: past its elastic limit at 250 N/mm");
  await expect(next).toContainText("The adhesive reaches its elastic limit in shear at 238.5 N/mm, at the inner end of the ledge of step 1.");
  // what only the solved slice holds is offered, solved from the chat, and then answered from it
  const peel = await ask(page, "what is the peel stress?");
  await expect(peel.getByTestId("repair-chat-heading")).toHaveText("The hand calculation has no peel stress");
  await peel.getByTestId("repair-chat-solve").click();
  await expect(page.getByTestId("repair-slice-short")).toContainText("Solved slice:");
  expect(solves).toHaveLength(1);
  const solved = await ask(page, "what is the peel stress?");
  await expect(solved.getByTestId("repair-chat-heading")).toHaveText("4.112 MPa in the solved slice");
  await expect(solved).toContainText("62.45 mm from the middle (the adhesive under the cover plies)");
  const first = await ask(page, "which ply fails first");
  await expect(first.getByTestId("repair-chat-heading")).toHaveText("Laminate ply 6 (−45°) at 466.1 N/mm");
  // a question of why is answered from our own page, beside the repair's own number, and no model is asked
  const why = await ask(page, "why does the shear stress peak at the ends of a step?");
  await expect(why).toHaveAttribute("data-kind", "reference");
  await expect(why.getByTestId("repair-chat-heading")).toHaveText("Why the shear stress peaks at the ends of a step");
  await expect(why).toContainText("The adhesive moves load from the laminate into the patch.");
  await expect(why).toContainText("Here: 12.58 MPa by hand, at the inner end of the ledge of step 1.");
  await expect(why.locator("details.chat-details > summary")).toHaveText("From our pages: Bonded repairs, Why the shear stress peaks at the ends of a step");
  expect(searched.at(-1)).toMatchObject({ question: "why does the shear stress peak at the ends of a step?", about: "repair" });
  chat.sections = [];
  const none = await ask(page, "why is the sky blue?");
  await expect(none.getByTestId("repair-chat-heading")).toHaveText("Our pages do not cover that yet");
  const unread = await ask(page, "make it lighter");
  await expect(unread.getByTestId("repair-chat-heading")).toHaveText("Not a message I can read yet");
  await expect(unread).toContainText("“add a step”");
  expect(changes).toHaveLength(0);
  expect(bannedIn(await page.getByTestId("repair-chat").innerText())).toEqual([]);
});

test("the repair's page names no tool, no machinery and no record, with every panel open, the slice solved and the solids built (ADR-0091)", async ({ page }) => {
  await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  const folded = page.locator("details.ws-panel:not([open]) > summary");
  while (await folded.count()) await folded.first().click(); // every folded panel opened, one at a time
  await page.getByTestId("repair-solve-button").click();
  await expect(page.getByTestId("repair-slice-short")).toContainText("Solved slice:");
  const download = page.waitForEvent("download");
  await page.getByTestId("repair-step").click();
  await download;
  await expect(page.getByTestId("repair-solids")).toBeVisible();
  const words = await page.evaluate(() => {
    const main = document.querySelector("main") ?? document.body;
    const attributes = [...main.querySelectorAll("[aria-label], [title], [placeholder]")]
      .flatMap((el) => ["aria-label", "title", "placeholder"].map((name) => el.getAttribute(name) ?? ""));
    const hrefs = [...main.querySelectorAll("a[href]")].map((a) => a.getAttribute("href") ?? "");
    return [document.title, main.textContent ?? "", ...attributes, ...hrefs].join("\n");
  });
  expect(bannedIn(words)).toEqual([]);
  // and it gives no verdict: the adhesive's limit is never called the repair's strength
  expect(words).not.toMatch(/\bpasses\b|\bfails at\b|margin of safety|failure load of|strength of the repair/i);
});

test("on a phone the repair's drawings fill the screen and its answer is in the sheet under them, with nothing wider than the screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await playRepairs(page);
  await page.goto("/workspace/repair");
  await expect(page.getByTestId("repair-slice")).toBeVisible();
  await expect(page.getByTestId("repair-headline")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.goto("/workspace/repair/report");
  await expect(page.getByTestId("repair-report-summary")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
