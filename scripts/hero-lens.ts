/**
 * Records the hero lens loop (ADR-0071): three of our own public results, each turning slowly in the workspace's viewer while
 * its deformation eases in, joined into one cross-faded loop.
 *
 *   npm run dev                       # in another terminal
 *   npx tsx scripts/hero-lens.ts [http://localhost:3000]
 *   npx tsx scripts/hero-lens.ts --still     # one frame per model, fully deformed, to check the framing
 *
 * Writes public/assets/hero-lens/lens.mp4, its poster lens.jpg, and components/home/hero-lens.json (when each model shows, which
 * the lens reads for its caption). The results come from the public test fixtures in tests/fixtures/, replayed in place of the
 * API, so no API has to run. Only the recording is coloured with the Turbo map: the script swaps the viewer's two ramps for it in
 * the page's code as it loads, and the workspace keeps its own colours. Needs ffmpeg, and Playwright's Chromium
 * (npx playwright install chromium).
 */
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium, type Page } from "@playwright/test";

const ROOT = join(__dirname, "..");
const STILL = process.argv.includes("--still");
const BASE = process.argv.slice(2).find((arg) => !arg.startsWith("--")) ?? "http://localhost:3000";
const OUT = join(ROOT, "public", "assets", "hero-lens");
const MANIFEST = join(ROOT, "components", "home", "hero-lens.json");
const WORK = join(ROOT, ".local", "hero-lens");

const WIDTH = 960, HEIGHT = 720; // 4:3, recorded larger than the lens shows it and scaled down when encoded
const VIDEO_WIDTH = 800, VIDEO_HEIGHT = 600; // about twice the lens's widest size, for 2x screens
const FPS = 30;
const SEGMENT = 6; // seconds each model is recorded for
const FADE = 1; // seconds of cross-fade between models, and from the last back to the first
const EASE_IN = 2.5; // seconds the deformation takes to reach its full scale

/** The three applications, in the order the lens shows them. `orbit` is the turn over the segment in degrees, `zoom` the mouse
 * wheel steps from the viewer's own framing (negative is closer; each step is about 5 %). */
const MODELS = [
  { id: "tension", fixture: "studio", orbit: 36, zoom: -5 },
  { id: "bending", fixture: "studio-bending", orbit: 36, zoom: -4 },
  { id: "plate", fixture: "studio-plate", orbit: 36, zoom: 4 },
] as const;

/** Google's Turbo colour map (Mikhailov 2019, the published polynomial fit), from t = 0 (blue) to 1 (red). */
function turbo(t: number): string {
  const r = 0.13572138 + t * (4.6153926 + t * (-42.66032258 + t * (132.13108234 + t * (-152.94239396 + t * 59.28637943))));
  const g = 0.09140261 + t * (2.19418839 + t * (4.84296658 + t * (-14.18503333 + t * (4.27729857 + t * 2.82956604))));
  const b = 0.1066733 + t * (12.64194608 + t * (-60.58204836 + t * (110.36276771 + t * (-89.90310912 + t * 27.34824973))));
  const hex = (v: number) => Math.round(Math.max(0, Math.min(1, v)) * 255).toString(16).padStart(2, "0");
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}
/** Seven stops, as the viewer's ramps have: Turbo without its near-black ends, which would vanish on the dark background. */
const STOPS = Array.from({ length: 7 }, (_, i) => turbo(0.08 + (0.88 * i) / 6));

const fixture = (dir: string, name: string) => JSON.parse(readFileSync(join(ROOT, "tests", "fixtures", dir, `${name}.json`), "utf8"));
const easeInOut = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));

async function open(page: Page, dir: string) {
  let swapped = 0;
  // The viewer's sequential ramp starts at #10170f and its diverging one at #2a78d6 (lib/studio-colors.ts); both become Turbo.
  await page.route(/\.js(\?|$)/, async (route) => {
    const response = await route.fetch();
    let body = await response.text();
    if (body.includes("#10170f")) {
      const before = body;
      body = body.replace(/\[\s*["']#10170f["'][^\]]*\]/, JSON.stringify(STOPS)).replace(/\[\s*["']#2a78d6["'][^\]]*\]/, JSON.stringify(STOPS));
      if (body !== before) swapped += 1;
    }
    await route.fulfill({ response, body });
  });
  // The API, replayed from the fixtures. The critical element's frame is left out: the lens shows the field alone.
  const fields = fixture(dir, "fields");
  fields.summary = { ...fields.summary, earliest: null };
  await page.route(/https?:\/\/[^/]+\/v1\//, async (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
    if (/^\/v1\/coupon-jobs\/[^/]+$/.test(path)) return json(fixture("studio", "job-done"));
    if (path.endsWith("/files/fields")) return json(fields);
    if (path.startsWith("/v1/projects")) return json({ detail: "not used here" }, 503);
    return json({ detail: "not used here" }, 404);
  });
  await page.goto(`${BASE}/workspace/fea/view?job=0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00`, { waitUntil: "networkidle", timeout: 180_000 });
  await page.waitForSelector('select[aria-label="Field"]', { timeout: 60_000 });
  if (!swapped) throw new Error("The viewer's colour ramps were not found in the page's code: has lib/studio-colors.ts changed?");
  await page.selectOption('select[aria-label="Field"]', "u_mag");
  await page.selectOption('select[aria-label="Contours"]', "10");
  // The scene alone, at the recording's size, in the page's top left corner.
  await page.addStyleTag({ content: `
    .studio-canvas { position: fixed !important; inset: 0 auto auto 0 !important; width: ${WIDTH}px !important; height: ${HEIGHT}px !important; z-index: 2147483647 !important; margin: 0 !important; border: 0 !important; border-radius: 0 !important; }
    .studio-scene-key, nextjs-portal, .page-transition { display: none !important; }` });
  await page.waitForTimeout(1500);
}

/** Sets the deformation scale as typing it would, without moving focus or the pointer (the pointer is holding the turn). */
async function deform(page: Page, scale: number) {
  await page.evaluate((value) => {
    const input = document.querySelector<HTMLInputElement>('input[aria-label="Deformation scale"]');
    if (!input) throw new Error("no deformation scale input");
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, String(value));
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }, scale);
}

const frames = async (page: Page) => page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))));

async function record(page: Page, model: (typeof MODELS)[number], dir: string) {
  const full = Number(await page.inputValue('input[aria-label="Deformation scale"]'));
  if (!(full > 0)) throw new Error(`${model.id}: no suggested deformation scale`);
  // Closer than the viewer's framing, by mouse wheel over the scene's centre.
  await page.mouse.move(WIDTH / 2, HEIGHT / 2);
  for (let i = 0; i < Math.abs(model.zoom); i++) { await page.mouse.wheel(0, model.zoom < 0 ? -100 : 100); await page.waitForTimeout(120); }
  // The turn: one drag from the empty top left corner, so no element is picked. The orbit control turns the camera by a full
  // turn per canvas height dragged.
  if (STILL) {
    await deform(page, full);
    await frames(page);
    await page.locator(".studio-canvas canvas").first().screenshot({ path: join(dir, "still.png") });
    return;
  }
  const count = SEGMENT * FPS;
  const step = ((model.orbit / 360) * HEIGHT) / count;
  const x0 = 12, y0 = 12;
  await page.mouse.move(x0, y0);
  await page.mouse.down();
  const canvas = page.locator(".studio-canvas canvas").first();
  for (let i = 0; i < count; i++) {
    await deform(page, Number((full * easeInOut(i / (EASE_IN * FPS))).toPrecision(4)));
    await page.mouse.move(x0 + step * i, y0);
    await frames(page);
    await canvas.screenshot({ path: join(dir, `${String(i).padStart(4, "0")}.png`) });
  }
  await page.mouse.up();
}

const ffmpeg = (args: string[]) => execFileSync("ffmpeg", ["-y", "-v", "error", ...args], { stdio: "inherit" });

async function main() {
  rmSync(WORK, { recursive: true, force: true });
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch();
  try {
    for (const model of MODELS) {
      const dir = join(WORK, model.id);
      mkdirSync(dir, { recursive: true });
      const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
      await open(page, model.fixture);
      await record(page, model, dir);
      await page.close();
      console.log(STILL ? `${join(dir, "still.png")}` : `${model.id}: ${SEGMENT * FPS} frames`);
    }
  } finally {
    await browser.close();
  }
  if (STILL) return;

  // One loop: each model cross-fades into the next, and the last back into the first. The first model's opening second is
  // cut from the start and laid under the end, so the loop's last frame leads straight into its first.
  const inputs = MODELS.flatMap((m) => ["-framerate", String(FPS), "-i", join(WORK, m.id, "%04d.png")]);
  const n = MODELS.length;
  const length = SEGMENT - FADE; // how long each model has the lens to itself, fades included once
  let graph = `[0:v]split[first][head];[first]trim=start=${FADE},setpts=PTS-STARTPTS[s0];[head]trim=end=${FADE},setpts=PTS-STARTPTS[h];`;
  let last = "s0", at = SEGMENT - FADE;
  for (let i = 1; i < n; i++) {
    graph += `[${last}][${i}:v]xfade=transition=fade:duration=${FADE}:offset=${at - FADE}[x${i}];`;
    last = `x${i}`; at += length;
  }
  graph += `[${last}][h]xfade=transition=fade:duration=${FADE}:offset=${at - FADE},scale=${VIDEO_WIDTH}:${VIDEO_HEIGHT}:flags=lanczos,format=yuv420p[out]`;
  ffmpeg([...inputs, "-filter_complex", graph, "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "26",
    "-profile:v", "high", "-movflags", "+faststart", join(OUT, "lens.mp4")]);
  ffmpeg(["-i", join(OUT, "lens.mp4"), "-frames:v", "1", "-q:v", "3", join(OUT, "lens.jpg")]);

  // When each model fills the lens, for the caption: the cross-fades split at their midpoints, and the last half second belongs
  // to the first model again, which the loop is fading back to.
  const duration = n * length;
  const segments = MODELS.map((m, i) => ({ id: m.id, start: i === 0 ? 0 : i * length - FADE / 2, end: (i + 1) * length - FADE / 2 }));
  writeFileSync(MANIFEST, `${JSON.stringify({ duration, segments }, null, 2)}\n`);
  console.log(`wrote ${join(OUT, "lens.mp4")} (${duration} s), lens.jpg and ${MANIFEST}`);
}

main().catch((error) => { console.error(error); process.exit(1); });
