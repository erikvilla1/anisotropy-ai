import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { bannedInAbaqusCard } from "../../lib/studio-copy";

const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio-import/${name}.json`, "utf8"));
const API = /https?:\/\/[^/]+\/v1\//;
const DECK = readFileSync("fea/checks/decks/coupon-2x8-grips-im7-8552.inp");
const REFUSAL = "line 15: element type 'C3D8R' is not supported; this version reads S4, S4R, S4R5 (four-node shells)";

/** The API a model is brought in through (ADR-0105), played from the package's own answer for the public gripped coupon
 * (tests/fixtures/studio-import, which fea/tests/test_imported.py keeps the package's); a file that opens with *Solid is refused as the
 * reader refuses one. `sent` keeps each import as it was asked, and `others` every other request that would compute something. */
async function mockApi(page: Page, sent: { url: string; name: string | null; bytes: number }[], others: string[], allTests = true) {
  await page.route(API, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (url.pathname === "/v1/coupon-tests") return json({ all: allTests });
    if (url.pathname === "/v1/workspace/assistant") return json({ proposes: false, provider: null, model: null });
    if (url.pathname === "/v1/coupons") return json([]);
    if (url.pathname.startsWith("/v1/projects")) {
      return route.fulfill({ status: 503, contentType: "application/json", headers: { "X-Anisotropy-Records": "off", "Access-Control-Expose-Headers": "X-Anisotropy-Records" },
        body: JSON.stringify({ detail: "Records are switched off on this server, so there is nothing to read" }) });
    }
    if (url.pathname === "/v1/imported-models" && request.method() === "POST") {
      const body = request.postDataBuffer() ?? Buffer.alloc(0);
      sent.push({ url: url.pathname + url.search, name: await request.headerValue("x-anisotropy-model-name"), bytes: body.length });
      const head = { run_id: "run-import", solver: "kernel", warm: true, seconds: 0.4, timings: { model: 0.02 } };
      if (body.subarray(0, 6).toString() === "*Solid") {
        return json({ ...head, state: "refused", name: "solid.inp", units: url.searchParams.get("units"), problem: { message: REFUSAL, line: 15 },
          reading: null, preview: null, fields: null, explanation: null });
      }
      return json({ ...head, ...fixture("import"), preview: fixture("preview"), fields: fixture("fields"), explanation: fixture("explanation") });
    }
    others.push(`${request.method()} ${url.pathname}`);
    return json({ detail: "not in this scenario" }, 404);
  });
}

const say = async (page: Page, text: string) => {
  const box = page.getByTestId("ws-assistant").locator("textarea").last();
  await box.fill(text);
  await box.press("Enter");
};

test("a model brought in as a file is read, solved as it stands and asked about, and the coupon behind it is left alone (ADR-0105)", async ({ page }) => {
  const sent: { url: string; name: string | null; bytes: number }[] = [];
  const others: string[] = [];
  await mockApi(page, sent, others);
  await page.goto("/workspace/fea");
  await page.getByTestId("import-open").click();
  const rail = page.getByTestId("import-rail");
  await expect(rail).toBeVisible();
  await expect(page.getByTestId("studio-form")).toHaveCount(0); // the coupon's panels wait behind it
  await expect(page.getByTestId("import-empty")).toHaveAttribute("data-state", "none");
  await expect(rail.getByText("Abaqus input file (.inp)")).toBeVisible();

  // nothing is sent until the file and the units it is written in are both stated: a file carries none
  const send = page.getByTestId("import-send");
  await expect(send).toBeDisabled();
  await page.getByTestId("import-file").setInputFiles({ name: "coupon 2x8 grips.inp", mimeType: "text/plain", buffer: DECK });
  await expect(send).toBeDisabled();
  await page.getByTestId("import-units").selectOption("mm-MPa");
  await send.click();

  const stage = page.getByTestId("import-stage");
  await expect(stage).toHaveAttribute("data-state", "solved", { timeout: 20_000 });
  expect(sent).toEqual([{ url: "/v1/imported-models?units=mm-MPa", name: "coupon%202x8%20grips.inp", bytes: DECK.length }]); // the name in a header, the file as it is
  await expect(page.getByTestId("import-banner")).toContainText("Solved as the file states it: no mesh study, and not checked against a second solver.");
  await expect(stage.getByTestId("results")).toHaveAttribute("data-source", "run");
  await expect(stage.getByTestId("live-banner")).toHaveCount(0); // no "run the analysis to verify it": an imported model has no full run
  await expect(page.getByTestId("import-status")).toHaveText("coupon-2x8-grips-im7-8552.inp: read and solved.");
  const reading = page.getByTestId("import-reading");
  await expect(reading).toContainText("16 elements (16 S4R), 27 nodes");
  await expect(reading).toContainText("[0/30/-30/30/0]s, 1.829 mm thick");
  await expect(reading).toContainText("12 boundary lines, 2 couplings");
  await expect(page.getByTestId("import-notes")).toContainText("reference node Assembly.2"); // the reader's own note on this file
  await page.getByTestId("panel-import-skipped").locator("summary").click();
  await expect(page.getByTestId("import-skipped").locator("li")).toHaveCount(4);

  // the assistant says what came in, answers from this model's results, and changes nothing by talking
  await expect(page.getByTestId("chat-imported")).toHaveAttribute("data-state", "solved");
  await expect(page.getByTestId("chat-imported")).toContainText("16 elements, [0/30/-30/30/0]s, solved as the file states it.");
  await say(page, "where is the shear stress highest?");
  const extremes = page.getByTestId("chat-extremes");
  await expect(extremes).toBeVisible();
  await expect(extremes).toHaveAttribute("data-source", "run");
  await expect(extremes).not.toContainText("preview");
  await say(page, "show me the formula");
  await expect(page.getByTestId("chat-working")).toBeVisible();
  await say(page, "finer mesh");
  await expect(page.getByTestId("chat-import-read-only")).toContainText("nothing is changed by talking yet");
  await say(page, "start over");
  await expect(page.getByTestId("chat-import-read-only")).toHaveCount(2);
  await expect(stage).toHaveAttribute("data-state", "solved"); // still there
  expect(others.filter((o) => !o.endsWith("/live"))).toEqual([]); // no check, no run, no model asked: nothing of the coupon's was touched

  // the words on the import's own panels and stage: Abaqus may be named, the file being the engineer's own; nothing else that is banned
  expect(bannedInAbaqusCard(await rail.innerText())).toEqual([]);
  expect(bannedInAbaqusCard(await page.getByTestId("import-banner").innerText())).toEqual([]);

  // a file outside what is read is refused with the reader's line, and no result is left on the page to be taken for its own
  await page.getByTestId("import-file").setInputFiles({ name: "solid.inp", mimeType: "text/plain", buffer: Buffer.from("*Solid\n") });
  await send.click();
  await expect(page.getByTestId("import-problem")).toHaveText("Line 15: element type 'C3D8R' is not supported; this version reads S4, S4R, S4R5 (four-node shells)");
  await expect(page.getByTestId("import-empty")).toHaveAttribute("data-state", "refused");
  await expect(page.getByTestId("results")).toHaveCount(0);
  await expect(page.getByTestId("import-status")).toHaveText("solid.inp: not read.");
  await expect(page.getByTestId("chat-imported").last()).toHaveAttribute("data-state", "refused");
  await say(page, "where is the shear stress highest?");
  await expect(page.getByTestId("chat-value-none")).toContainText("This model has no results");

  // back to the coupon: its panels return, and the import is gone
  await page.getByTestId("import-close").click();
  await expect(page.getByTestId("studio-form")).toBeVisible();
  await expect(rail).toHaveCount(0);
  await expect(page.getByTestId("empty-scene")).toBeVisible();
});

test("where one workflow is offered, a model cannot be imported (ADR-0089)", async ({ page }) => {
  await mockApi(page, [], [], false);
  await page.goto("/workspace/fea");
  await expect(page.getByTestId("tension-screen")).toBeVisible();
  await expect(page.getByTestId("import-open")).toHaveCount(0);
});
