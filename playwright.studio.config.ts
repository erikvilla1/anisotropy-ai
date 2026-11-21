import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// The studio's browser test plays the API from tests/fixtures/studio (route interception), so it needs the site only;
// the site must be built with NEXT_PUBLIC_ANISOTROPY_API_URL set to any address, which the test intercepts.
export default defineConfig({
  ...base,
  testMatch: ["studio.spec.ts", "workspace.spec.ts", "abaqus-card.spec.ts", "import.spec.ts", "wing.spec.ts", "repair.spec.ts"],
  // A scenario's whole budget. A plate now previews after each settled edit (ADR-0101 amendment 1), which doubled its scenario on the
  // tests' software renderer (17 s to 34 s on a GitHub runner), and a runner 40 % slower took it past 60 s on 2026-11-16. Each wait
  // inside a scenario keeps its own, shorter limit, so a page that hangs still fails at the step that hung.
  timeout: 120_000,
  webServer: [{ command: "npm run preview", url: "http://localhost:3001/studio", reuseExistingServer: !process.env.CI }],
});
