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
    // Firefox gives no WebGL at all without a window (Mozilla bug 1375585), and the 3D views then say so instead of drawing, so it
    // runs with its window; on Linux that needs a display, which CI gives it with `xvfb-run`. Chromium and WebKit draw without one.
    headless: engine !== "firefox",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  reporter: "list",
});
