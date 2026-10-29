import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// The live run: the real API (recording off), the real fea tools and CalculiX on this machine. Local only: `STUDIO_LIVE=1 npm run test:studio-live`.
export default defineConfig({
  ...base,
  testMatch: "studio-live.spec.ts",
  timeout: 600_000,
  webServer: [
    { command: "uv run --project api uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000", url: "http://127.0.0.1:8000/openapi.json", reuseExistingServer: true, env: { ANISOTROPY_RUN_RECORDS: "off" } },
    { command: "npm run preview", url: "http://localhost:3001/studio", reuseExistingServer: true },
  ],
});
