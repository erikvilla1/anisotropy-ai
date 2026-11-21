import { readFileSync } from "node:fs";
import { test, expect, type Page, type Route } from "@playwright/test";
import { bannedIn } from "../../lib/studio-copy";

/** The repair's page and its report (ADR-0135), with the API played from the engine's and the solver's own answers to the two examples
 * (tests/fixtures/repair, written by scripts/repair-choices.py and checked against the API by api/tests/test_repairs_api.py). What the
 * page sends is recorded, so each test can say what was asked. */
const read = (name: string) => JSON.parse(readFileSync(`tests/fixtures/repair/${name}.json`, "utf-8"));
const ANSWER = read("example-answer"), EXTERNAL = read("external-answer"), SOLVE = read("example-solve");
const SHAPE = { run_id: null, step: "ISO-10303-21;\nEND-ISO-10303-21;\n", parts: { title: "Example stepped patch repair", units: { length: "mm", volume: "mm^3" },
  parts: [{ name: "Laminate ply 1 (45°)", kind: "parent", angle: 45, volume: 10972.8 }, { name: "Patch ply 1 (90°)", kind: "patch", angle: 90, volume: 89.77 },
    { name: "Adhesive on the floor", kind: "adhesive", angle: null, volume: 49.09 }], volumes: { parent: 85089, patch: 2678.8, cover: 2244.3, adhesive: 1241.5 } } };

type Sent = { repair?: Record<string, Record<string, unknown> & unknown>; toml?: string; cut_faces?: string };
type Reply = { status: number; body: unknown };
const solves: Sent[] = []; // what "Solve the slice" sent, in the test that runs
const shapes: Sent[] = []; // what Download STEP sent

/** Plays the three addresses of a repair. `answer` says what the hand calculation answers to a body; by default the engine's answer to
 * whichever example's kind the body states. */
async function playRepairs(page: Page, answer: (body: Sent) => Reply = (body) => ({ status: 200, body: (body.repair as Record<string, unknown> | undefined)?.kind === "external" ? EXTERNAL : ANSWER }),
  solve: (body: Sent) => Reply = () => ({ status: 200, body: SOLVE })) {
  const sent: Sent[] = [];
  solves.length = 0;
  shapes.length = 0;
  await page.route(/\/v1\/.*/, (route: Route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const body = (request.method() === "POST" ? request.postDataJSON() : {}) as Sent;
    const reply = (r: Reply) => route.fulfill({ status: r.status, contentType: "application/json", body: JSON.stringify(r.body) });
    if (path.endsWith("/v1/repairs/analyze")) { sent.push(body); return reply(answer(body)); }
    if (path.endsWith("/v1/repairs/solve")) { solves.push(body); return reply(solve(body)); }
    if (path.endsWith("/v1/repairs/shape")) { shapes.push(body); return reply({ status: 200, body: SHAPE }); }
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
  // the assistant's column says what the numbers are, and that the page has no chat yet
  await expect(page.getByTestId("repair-explain")).toContainText("12.58 MPa by hand, at the inner end of the ledge of step 1.");
  await expect(page.getByTestId("repair-not-strength")).toContainText("Neither answer is a failure load.");
  await expect(page.getByTestId("repair-no-chat")).toBeVisible();
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
