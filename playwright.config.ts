import { defineConfig } from "@playwright/test";

// The engine the browser tests run in (ADR-0114): Chromium unless BROWSER names another. Chromium runs as an installed Edge locally,
// or as BROWSER_CHANNEL names it (CI's bundled `chromium`); BROWSER=firefox runs Firefox, BROWSER=webkit runs WebKit, Safari's engine
// and the one every browser on an iPhone or iPad uses.
const ENGINES = ["chromium", "firefox", "webkit"] as const;
type Engine = (typeof ENGINES)[number];
const engine = (process.env.BROWSER || "chromium") as Engine;
if (!ENGINES.includes(engine)) throw new Error(`BROWSER=${engine}: one of ${ENGINES.join(", ")}`);

export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  use: {
    baseURL: process.env.PREVIEW_URL || "http://localhost:3001",
    browserName: engine,
    channel: engine === "chromium" ? process.env.BROWSER_CHANNEL || "msedge" : undefined,
    // Firefox refuses WebGL drawn in software, which is all a CI runner has, and the 3D views then say so instead of drawing;
    // a visitor's Firefox has a GPU. Chromium and WebKit draw in software as they are.
    launchOptions: engine === "firefox" ? { firefoxUserPrefs: { "webgl.force-enabled": true, "webgl.forbid-software": false } } : {},
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  reporter: "list",
});
