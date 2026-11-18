import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// Every browser spec the other configurations do not run (ADR-0114): the public pages, the home page's demo, the shell, the
// libraries and the phone check. They need the built site only, so a new spec file is run here by default and CI cannot miss it.
// The calculator needs the real API (playwright.calculator.config.ts), the workspace's scenarios play the API from fixtures
// (playwright.studio.config.ts), and the live run reaches a real API on purpose (playwright.studio-live.config.ts).
export default defineConfig({
  ...base,
  testIgnore: ["calculator.spec.ts", "studio.spec.ts", "workspace.spec.ts", "abaqus-card.spec.ts", "import.spec.ts", "studio-live.spec.ts"],
  // Twice Playwright's 30 s: Firefox and WebKit draw the 3D views in software on a CI runner, more slowly than Chromium.
  timeout: 60_000,
  webServer: [{ command: "npm run preview", url: "http://localhost:3001/", reuseExistingServer: !process.env.CI }],
});
