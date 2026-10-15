import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  testMatch: "calculator.spec.ts",
  webServer: [
    // Recording is switched off on purpose: this server exists only for the browser test (ADR-0026).
    { command: "uv run --project api uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000", url: "http://127.0.0.1:8000/openapi.json", reuseExistingServer: !process.env.CI, env: { ANISOTROPY_RUN_RECORDS: "off" } },
    { command: "npm run preview", url: "http://localhost:3001/calculator", reuseExistingServer: !process.env.CI },
  ],
});
