import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// The live run: the real API, the real fea tools, CalculiX and Tectonic. Two ways in, both local and only when asked for:
//   STUDIO_LIVE=1 npm run test:studio-live          the API started here with recording off, the site served from out/
//   PREVIEW_URL=https://... npm run test:studio-live   the hosted site behind Cloudflare Access (ADR-0056), reached with a service
//       token: CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET, which the Access application's policy must admit (Service Auth).
//       The API records such runs with no signed-in email, as a service token carries none. The spec adds the token's two headers to
//       the site's own requests only (a route), not to every request of the browser: a done job's files are read from the bucket by
//       a signed link, and a cross-origin request carrying extra headers needs a preflight the bucket does not answer for them
//       (seen live on 2026-11-07: the page's reads of the fields failed with the headers on every request).
const preview = process.env.PREVIEW_URL?.trim();

export default defineConfig({
  ...base,
  testMatch: "studio-live.spec.ts",
  timeout: 600_000,
  use: { ...base.use, ...(preview ? { baseURL: preview } : {}) },
  webServer: preview ? undefined : [
    { command: "uv run --project api uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000", url: "http://127.0.0.1:8000/openapi.json", reuseExistingServer: true, env: { ANISOTROPY_RUN_RECORDS: "off" } },
    { command: "npm run preview", url: "http://localhost:3001/studio", reuseExistingServer: true },
  ],
});
