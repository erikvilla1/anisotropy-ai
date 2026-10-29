import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// The studio's browser test plays the API from tests/fixtures/studio (route interception), so it needs the site only;
// the site must be built with NEXT_PUBLIC_ANISOTROPY_API_URL set to any address, which the test intercepts.
export default defineConfig({
  ...base,
  testMatch: "studio.spec.ts",
  timeout: 60_000,
  webServer: [{ command: "npm run preview", url: "http://localhost:3001/studio", reuseExistingServer: !process.env.CI }],
});
