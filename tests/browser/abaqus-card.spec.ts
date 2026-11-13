import { test, expect, type Page } from "@playwright/test";
import { bannedIn, bannedInAbaqusCard } from "../../lib/studio-copy";
import { comparisonOf, exchangeState, JOB, LIMITS, mockExchange, mockRun, TOKEN, uploadOf } from "./abaqus-api";

/** The card of the user's own Abaqus on a finished run (ADR-0094 part 7, step 6), in the viewer window, against a stand-in API. The
 * comparisons shown are the fea package's own (tests/fixtures/abaqus). No Abaqus and no API run here. */
const VIEW = `/workspace/fea/view?job=${JOB}`;
const BUILD = { abaqus_build: ".local/fea/IM7-UNT-L1/documents/2026-10-28_IM7-UNT-L1/2-our-model/abaqus/IM7-UNT-L1-build.py" };
const file = (bytes = 2048) => ({ name: "Job-1-anisotropy.zip", mimeType: "application/zip", buffer: Buffer.alloc(bytes, "PK") });
const card = (page: Page) => page.getByTestId("abaqus-card");
/** Every word of the card a person can read: its text, folded details included, and what a link is saved as. */
const cardWords = (page: Page) => card(page).evaluate((el) => [el.textContent ?? "", ...[...el.querySelectorAll("a[download], [aria-label], [placeholder]")]
  .flatMap((a) => ["download", "aria-label", "placeholder"].map((name) => a.getAttribute(name) ?? ""))].join("\n"));

test("a finished run offers the way to Abaqus and back; a file sent is compared and the answer comes first", async ({ page }) => {
  // the comparison is the D3039 check's, on 1488 elements; the run this window shows is the studio fixture's, on 250. So that the card's
  // Show has an element of this run to frame, the gauge's largest difference is placed at our element 120 here, and nothing else is changed
  const agrees = comparisonOf("agrees");
  agrees.summary.zones.gauge.our_element = 120;
  const state = exchangeState({ onSend: () => ({ status: 201, body: uploadOf(null, { verdict: "agrees", compared_at: "2026-11-13T09:30:04+00:00", comparison: agrees }) }) });
  await mockRun(page, { outputs: BUILD });
  await mockExchange(page, state);
  await page.goto(VIEW);
  await expect(card(page)).toHaveAttribute("data-verdict", "none", { timeout: 20_000 });
  await expect(card(page).locator("h3")).toHaveText("Compare with your Abaqus model");
  const build = card(page).getByTestId("abaqus-build"); // one action each way: the build script out, the connector's file back
  await expect(build).toHaveAttribute("download", "UnnotchedTension_[45-0--45-90]s_build.py");
  expect(await build.getAttribute("href")).toContain(`/v1/coupon-jobs/${JOB}/files/abaqus_build?name=`);
  expect(await card(page).getByTestId("abaqus-connector").getAttribute("href")).toMatch(/\/v1\/abaqus-connector$/);
  await expect(card(page)).toContainText("abaqus python anisotropy_connector.py <your job>.odb --units mm-MPa");
  await expect(card(page)).toContainText("only you and the Anisotropy team can see it");
  await expect(card(page).getByTestId("abaqus-keys")).toHaveCount(0); // the connector's own route is closed here, so no upload key is offered
  expect(await cardWords(page)).not.toMatch(/\b(bundle|ODB|equivalence)\b/); // the product's own words on the first screen

  await card(page).getByTestId("abaqus-file").setInputFiles(file());
  await expect(card(page).getByTestId("abaqus-verdict")).toHaveText("Agrees with ours");
  expect(state.sent).toEqual([{ query: { job_id: JOB }, contentType: "application/zip", actor: "studio", bytes: 2048 }]); // the file as it is, beside this run
  await expect(card(page)).toHaveAttribute("data-verdict", "agrees");
  await expect(card(page).getByTestId("abaqus-provenance")).toHaveText("Job-1, solved by Abaqus/Standard 2025: 1,488 of its elements beside ours.");
  const rows = card(page).getByTestId("abaqus-rows").locator("tr");
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0)).toHaveText(/The model\s*The same as ours on all 20 items\.\s*same/);
  await expect(rows.nth(1)).toContainText("Yours 16210 N, ours 16210 N");
  await expect(rows.nth(2)).toContainText("13,824 values; the largest difference is 0 % (σ₁, your element 673, ply 1).");
  await expect(rows.nth(3).locator("th")).toHaveText("Between gauge and tabs");
  await expect(card(page).getByTestId("abaqus-differences")).toHaveCount(0);

  await expect(card(page).getByTestId("abaqus-model")).toBeHidden(); // the detail opens on request
  await card(page).getByTestId("abaqus-details").locator("summary").click();
  await expect(card(page).getByTestId("abaqus-model").locator("tbody tr")).toHaveCount(comparisonOf("agrees").model.items.length);
  await expect(card(page).getByTestId("abaqus-zones").locator("tbody tr")).toHaveCount(5);
  await expect(card(page).getByTestId("abaqus-file-facts")).toContainText("SHA-256 abababababab…");
  await rows.nth(2).getByRole("button", { name: "Show" }).click(); // the place of the largest difference, framed in the viewer
  await expect(page.getByTestId("probe")).toContainText("Ply results at element 120");
  await expect(rows.nth(3).getByRole("button", { name: "Show" })).toHaveCount(0); // our element 481 is not in this run's mesh: nothing to frame, no button
  const sentFile = (await card(page).getByTestId("abaqus-sent-file").getAttribute("href"))!;
  expect(sentFile).toContain(`/v1/abaqus-uploads/${state.uploads[0].id}/bundle?actor=studio`);
  expect(await page.evaluate(async (href) => (await fetch(href)).status, sentFile)).toBe(200); // as a link asks for it: no header, the actor in the address
  expect(bannedInAbaqusCard(await cardWords(page))).toEqual([]);

  const sent = state.uploads[0].id;
  await card(page).getByTestId("abaqus-remove").click(); // its owner removes it, and the card is back at the start
  await expect(card(page)).toHaveAttribute("data-verdict", "none");
  expect(state.removed).toEqual([sent]);
});

test("a model that differs says in how many places and shows each where it is; an earlier file can be opened and compared again", async ({ page }) => {
  const first = comparisonOf("agrees");
  first.bundle.job = "Job-0"; // an earlier job of the same model, told from the later one by its name
  const earlier = uploadOf(null, { job: "Job-0", verdict: "agrees", compared_at: "2026-11-13T09:12:00+00:00", comparison: first }), differs = uploadOf("differs");
  const state = exchangeState({ uploads: [differs, earlier] });
  await mockRun(page);
  await mockExchange(page, state);
  await page.goto(VIEW);
  await expect(card(page).getByTestId("abaqus-verdict")).toHaveText("Differs in 2 places", { timeout: 20_000 });
  const rows = card(page).getByTestId("abaqus-rows").locator("tr");
  await expect(rows.nth(0)).toHaveAttribute("data-state", "differs");
  await expect(rows.nth(0)).toContainText("1 of 20 items differ.");
  await expect(rows.nth(1)).toContainText("Yours 17020 N, ours 16210 N (ours -4.762 % from yours).");
  await expect(rows.nth(1)).toContainText("outside 1 %");
  await expect(rows.nth(2)).toHaveAttribute("data-state", "same");
  const what = card(page).getByTestId("abaqus-differences").locator("tbody tr");
  await expect(what).toHaveCount(2);
  await expect(what.nth(0)).toContainText("Layup, bottom first");
  await expect(what.nth(0)).toContainText("[30/0/-45/90/90/-45/0/30]"); // yours beside ours
  await expect(what.nth(0)).toContainText("[45/0/-45/90/90/-45/0/45]");
  await expect(what.nth(1)).toHaveText(/The pull force\s*17020 N\s*16210 N\s*the top grip/);
  await expect(card(page).getByTestId("abaqus-build")).toHaveCount(0); // the steps are for a run without a file yet

  await card(page).getByTestId("abaqus-earlier").getByRole("button").click();
  await expect(card(page).getByTestId("abaqus-verdict")).toHaveText("Agrees with ours");
  await expect(card(page).getByTestId("abaqus-provenance")).toContainText("Job-0");
  await expect(card(page).getByTestId("abaqus-earlier")).toContainText("Job-1");

  state.onCompare = () => ({ status: 409, body: { detail: `Not compared: the package of coupon job ${JOB} is no longer there, so its files cannot stand beside the upload` } });
  await card(page).getByTestId("abaqus-again").click();
  await expect(card(page).getByTestId("abaqus-problem")).toHaveText("This run's files are no longer stored, so nothing can stand beside your model. Run the analysis again, then send the file again.");
  await expect(card(page).getByTestId("abaqus-verdict")).toHaveText("Agrees with ours"); // the comparison there is stays
  state.onCompare = () => ({ status: 200, body: uploadOf("another-mesh") });
  await card(page).getByTestId("abaqus-again").click();
  await expect(card(page).getByTestId("abaqus-provenance")).toContainText("132 of its elements beside ours, by position: the two meshes differ.");
  await expect(card(page).getByTestId("abaqus-problem")).toHaveCount(0);
  expect(state.compared).toEqual([`${earlier.id}?job_id=${JOB}`, `${earlier.id}?job_id=${JOB}`]);
  await expect(rows.nth(3)).toContainText("Shown, not judged: the two meshes differ.");
  await expect(rows.nth(3)).toContainText("not judged");
  expect(bannedInAbaqusCard(await cardWords(page))).toEqual([]);
});

test("a file the connector did not write is refused in plain words, and one too large is never sent", async ({ page }) => {
  const state = exchangeState({ exchange: { uploads: true, connector_route: false, ...LIMITS, max_bundle_bytes: 4096 },
    onSend: () => ({ status: 422, body: { detail: "Not a bundle this version takes, so nothing was stored: no manifest.json in the zip; the entry ../escape.txt leaves the bundle" } }) });
  await mockRun(page);
  await mockExchange(page, state);
  await page.goto(VIEW);
  await expect(card(page)).toHaveAttribute("data-verdict", "none", { timeout: 20_000 });
  await expect(card(page).getByTestId("abaqus-build")).toHaveCount(0); // a run without the build script: the solver input is imported instead
  await expect(card(page)).toContainText("choose File, Import, Model");
  await card(page).getByTestId("abaqus-file").setInputFiles(file(8192));
  await expect(card(page).getByTestId("abaqus-problem")).toContainText("This file is 8 kB, larger than 0 MB, the most that can be sent."); // this stand-in's limit is 4 kB
  expect(state.sent).toEqual([]);
  await card(page).getByTestId("abaqus-file").setInputFiles(file(1024));
  const problem = card(page).getByTestId("abaqus-problem");
  await expect(problem).toContainText("This is not a file the connector wrote, so nothing was stored. Send the file named <job>-anisotropy.zip.");
  await problem.locator("summary").click();
  await expect(problem.locator("li")).toHaveText(["no manifest.json in the zip", "the entry ../escape.txt leaves the bundle"]);
  await expect(card(page)).toHaveAttribute("data-verdict", "none");
  expect(state.sent).toHaveLength(1);

  state.onSend = () => ({ status: 201, body: uploadOf(null, { verdict: "refused", compared_at: "2026-11-13T09:31:00+00:00",
    comparison: { verdict: "refused", problems: ["your model has plies [1, 2, 3, 4, 5, 6, 7] and ours [1, 2, 3, 4, 5, 6, 7, 8]: not the same layup"] } }) });
  await card(page).getByTestId("abaqus-file").setInputFiles(file(1024)); // stored, and not the same coupon: the reason is the fea package's
  await expect(card(page).getByTestId("abaqus-verdict")).toHaveText("Not compared");
  await expect(card(page).getByTestId("abaqus-not-compared")).toContainText("not the same layup");
  state.onSend = () => ({ status: 201, body: uploadOf(null, { in_scope: false, not_compared: "the bundle is out of the comparison's scope; the upload's facts say what our reader did not take",
    facts: { deck: { read: false, reason: "the deck has no *Step; there is nothing to solve" }, every_output: { read: true } } }) });
  await card(page).getByTestId("abaqus-send-another").click({ trial: true });
  await card(page).getByTestId("abaqus-file").setInputFiles(file(1024));
  await expect(card(page).getByTestId("abaqus-not-compared")).toContainText("The comparison does not cover this model yet.");
  await expect(card(page).getByTestId("abaqus-not-compared").locator("li")).toHaveText(["the deck has no *Step; there is nothing to solve"]);
});

test("an upload key is shown once, the command never holds it, and a file sent from Abaqus arrives on the card", async ({ page }) => {
  const state = exchangeState({ exchange: { uploads: true, connector_route: true, ...LIMITS } });
  await mockRun(page);
  await mockExchange(page, state);
  await page.goto(VIEW);
  const keys = card(page).getByTestId("abaqus-keys");
  await expect(keys).toBeVisible({ timeout: 20_000 });
  await expect(keys.getByTestId("abaqus-command")).toBeHidden();
  await keys.locator("summary").click();
  await expect(keys.getByTestId("abaqus-command")).toHaveText(
    `abaqus python anisotropy_connector.py <your job>.odb --units mm-MPa --coupon IM7-UNT-L1 --send http://api.test --token-file anisotropy-key.txt --our-run ${JOB}`);
  await expect(keys.getByTestId("abaqus-waiting")).toHaveText("Waiting for a file from Abaqus…");
  await keys.getByLabel("Where you will use it").fill("lab workstation");
  await keys.getByTestId("abaqus-key-create").click();
  await expect(keys.getByTestId("abaqus-key-value")).toHaveText(TOKEN);
  expect(state.named).toEqual(["lab workstation"]);
  const save = keys.getByTestId("abaqus-key-save");
  await expect(save).toHaveAttribute("download", "anisotropy-key.txt");
  expect(decodeURIComponent((await save.getAttribute("href")) ?? "")).toBe(`data:text/plain;charset=utf-8,${TOKEN}\n`);
  await expect(keys.getByTestId("abaqus-command")).not.toContainText("anisotropy_upload_"); // the key is in its file, never in the command
  await expect(keys.getByTestId("abaqus-key-list").locator("tbody tr")).toHaveText([/lab workstation, ending in kkkk.*never\s*Cancel/]);

  state.uploads.unshift(uploadOf("agrees", { token_id: state.keys[0].id })); // the connector sent it: the card finds it without a click
  await expect(card(page).getByTestId("abaqus-verdict")).toHaveText("Agrees with ours", { timeout: 15_000 });
  await expect(keys.getByTestId("abaqus-waiting")).toHaveCount(0);

  await keys.getByTestId("abaqus-key-list").getByRole("button", { name: "Cancel" }).click();
  await expect(keys.getByTestId("abaqus-key-list")).toHaveCount(0);
  await expect(keys.getByTestId("abaqus-key-value")).toHaveCount(0); // a cancelled key is no longer shown
  expect(state.cancelled).toEqual([state.keys[0].id]);
  const words = await cardWords(page);
  expect(bannedInAbaqusCard(words)).toEqual([]);
  expect(bannedIn(words)).toEqual(["Abaqus", ".py"]); // and those two are what the card alone may name
});

test("where uploads are not kept, or the run is not a finished tension coupon, there is no card", async ({ page }) => {
  const state = exchangeState({ exchange: null }); // an API without the route
  await mockRun(page);
  await mockExchange(page, state);
  await page.goto(VIEW);
  await expect(page.getByTestId("summary")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByTestId("explanation")).toBeVisible();
  await expect(card(page)).toHaveCount(0);

  state.exchange = { uploads: false, connector_route: true, ...LIMITS }; // run records off: nowhere to keep an owner
  await page.reload();
  await expect(page.getByTestId("explanation")).toBeVisible({ timeout: 20_000 });
  await expect(card(page)).toHaveCount(0);
  expect(state.lists).toBe(0);

  state.exchange = { uploads: true, connector_route: true, ...LIMITS };
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await mockRun(page, { fields: (fields) => ({ ...fields, coupon: { ...(fields.coupon as object), kind: "open_hole_tension" } }) }); // a coupon the comparison does not cover
  await mockExchange(page, state);
  await page.reload();
  await expect(page.getByTestId("explanation")).toBeVisible({ timeout: 20_000 });
  await expect(card(page)).toHaveCount(0);
  expect(state.lists).toBe(0);
});
