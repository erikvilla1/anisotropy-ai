import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// The live run: the real API, the real fea tools, CalculiX and Tectonic. Two ways in, both local and only when asked for:
//   STUDIO_LIVE=1 npm run test:studio-live          the API started here with recording off, the site served from out/
//   PREVIEW_URL=https://... npm run test:studio-live   the hosted site behind Cloudflare Access (ADR-0056), reached with a service
//       token: CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET, which the Access application's policy must admit (Service Auth).
//       The API records such runs with no signed-in email, as a service token carries none.
const preview = process.env.PREVIEW_URL?.trim();
const serviceToken = preview && process.env.CF_ACCESS_CLIENT_ID && process.env.CF_ACCESS_CLIENT_SECRET
  ? { "CF-Access-Client-Id": process.env.CF_ACCESS_CLIENT_ID, "CF-Access-Client-Secret": process.env.CF_ACCESS_CLIENT_SECRET }
  : undefined;

export default defineConfig({
  ...base,
  testMatch: "studio-live.spec.ts",
  timeout: 600_000,
  use: { ...base.use, ...(preview ? { baseURL: preview, extraHTTPHeaders: serviceToken } : {}) },
  webServer: preview ? undefined : [
    { command: "uv run --project api uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000", url: "http://127.0.0.1:8000/openapi.json", reuseExistingServer: true, env: { ANISOTROPY_RUN_RECORDS: "off" } },
    { command: "npm run preview", url: "http://localhost:3001/studio", reuseExistingServer: true },
  ],
});
