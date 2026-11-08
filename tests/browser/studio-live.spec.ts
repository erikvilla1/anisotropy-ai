import { test, expect } from "@playwright/test";

// The whole chain: the public example through the real API, our engine, CalculiX and the package. On this machine it writes a
// coupon under .local/fea (IM7-UNT-L<n>, the next free layup code); against the hosted site (PREVIEW_URL, with a service token for
// Cloudflare Access) it writes one in the hosted tier's store. So it runs only when asked for: STUDIO_LIVE=1 or PREVIEW_URL.
test.skip(!process.env.STUDIO_LIVE && !process.env.PREVIEW_URL, "set STUDIO_LIVE=1 for the API on this machine, or PREVIEW_URL for the hosted site");

// Against the hosted site, the service token's two headers go on the site's own requests. A job's file is answered with a redirect to
// a signed link on the bucket's origin, which Chromium would follow with the same added headers (a continued request keeps them across
// redirects), and the bucket refuses such a request's preflight (403), rightly, since a browser adds no headers of its own. So a file's
// redirect is followed here, from the site's origin as a browser would, and the bucket's answer is checked below for the CORS header a
// browser from the site's origin needs (the bucket's CORS policy, docs/walkthroughs/hosted-deploy.md). Seen live on 2026-11-08.
const FILE_PATH = /\/v1\/coupon-jobs\/[^/]+\/files\/[^/]+$/;
const bucketAnswers: string[] = []; // the bucket's Access-Control-Allow-Origin on each file read, against the hosted site

test.beforeEach(async ({ page }) => {
  bucketAnswers.length = 0;
  const preview = process.env.PREVIEW_URL?.trim();
  const id = process.env.CF_ACCESS_CLIENT_ID, secret = process.env.CF_ACCESS_CLIENT_SECRET;
  if (!preview || !id || !secret) return;
  const origin = new URL(preview).origin;
  await page.route((url) => url.origin === origin, async (route) => {
    const headers = { ...route.request().headers(), "CF-Access-Client-Id": id, "CF-Access-Client-Secret": secret };
    if (!FILE_PATH.test(new URL(route.request().url()).pathname)) return route.continue({ headers });
    const answer = await route.fetch({ headers, maxRedirects: 0 });
    const link = answer.headers()["location"];
    if (answer.status() !== 307 || !link) return route.fulfill({ response: answer });
    const file = await page.request.get(link, { headers: { Origin: origin } });
    bucketAnswers.push(file.headers()["access-control-allow-origin"] ?? "(none)");
    return route.fulfill({ response: file });
  });
});

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" }); // a file read in flight when the test ends is let go, not an error
});

test("the example coupon solves end to end from the studio", async ({ page }) => {
  await page.goto("/workspace/fea"); // the rows are the left column of the workspace (ADR-0062)
  await page.getByRole("button", { name: "Load example" }).click();
  // the coupon's codes are derived or reused (ADR-0038 amendment 1); "Filled in by" sits under Advanced and takes the Run by name when blank
  await page.getByLabel("Run by", { exact: true }).fill("Studio live test"); // names who fills and who runs the coupon
  await page.getByTestId("check-button").click();
  await expect(page.getByTestId("checklist")).toHaveAttribute("data-state", "ready", { timeout: 120_000 });
  await page.getByTestId("solve-button").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 300_000 });
  await expect(page.getByTestId("summary-reaction")).toContainText("N (in tension)");
  await expect(page.getByTestId("job-progress")).toHaveAttribute("data-state", "done", { timeout: 300_000 });
  await expect(page.getByTestId("job-message")).toContainText("recorded values agree with CalculiX");
  if (process.env.PREVIEW_URL) { // the bucket let a browser from the site's origin read every file the page asked for
    expect(bucketAnswers.length).toBeGreaterThan(0);
    expect(new Set(bucketAnswers)).toEqual(new Set([new URL(process.env.PREVIEW_URL).origin]));
  }
  await page.screenshot({ path: ".local/website/screenshots/studio-live.png", fullPage: true });
});
