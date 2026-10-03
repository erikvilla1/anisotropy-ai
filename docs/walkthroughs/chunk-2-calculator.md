# Chunk 2: the website calls the engine

## What you can do now

Open `/calculator`, edit one material, add/remove plies, enter six load resultants and select **Analyze laminate**. The page displays the engine's stiffness matrices, mid-plane strains and curvatures. The navigation includes a Calculator link. **Load example** restores the same sourced practice inputs used by the API tests.

## Run the connection locally

From the repository root in PowerShell, create the local configuration if it does not already exist:

```powershell
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
uv sync --project api --locked
uv run --project api uvicorn anisotropy_api.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
npm run build
npm run preview
```

Open <http://localhost:3001/calculator>. Alternatively use `npm run dev` and <http://localhost:3000/calculator>. Stop a foreground server with Ctrl+C.

`NEXT_PUBLIC_ANISOTROPY_API_URL` is the public API address, initially `http://127.0.0.1:8000` in `.env.example`. Next.js embeds it during the build. Restart development or rebuild after changing it. Never put a credential in this variable. With no configured address, the page disables calculation and makes no request. Keep `.env.local` uncommitted. Public deployment and authentication remain future work.

## Follow the data

Browser form -> validated SI-base request -> HTTP POST -> FastAPI/Pydantic -> Python engine -> checked JSON response -> result tables.

| Piece | What it does | File |
| --- | --- | --- |
| `CalculatorPage()` | Defines `/calculator`, its heading and the configured service address | `app/calculator/page.tsx` |
| `LaminateCalculator()` | Owns the current inputs, pending state, errors and last result | `components/laminate-calculator.tsx` |
| `exampleForm()` | Loads the shared cited example and converts Pa/metres into GPa/mm for display | `lib/laminate-api.ts` |
| `update()` | Changes the form and clears the old result, preventing stale results after an edit | `components/laminate-calculator.tsx` |
| `buildAnalysisRequest()` | Rejects blank/malformed entries and converts GPa to Pa, mm to metres | `lib/laminate-api.ts` |
| `analyze()` | Handles submission, pending/cancel/timeout state and displayed errors | `components/laminate-calculator.tsx` |
| `requestAnalysis()` | Uses the browser's `fetch()` to send JSON to the existing endpoint | `lib/laminate-api.ts` |
| `readAnalysisResult()` | Checks matrix/vector shapes, finite values and that echoed inputs match the submitted problem | `lib/laminate-api.ts` |
| `apiFieldErrors()` | Maps API error locations such as `E1_pa` back to the visible `E1_GPa` field | `lib/laminate-api.ts` |
| `Matrix()` and `formatted()` | Render engine values in tables and scientific notation; do not solve equations | `components/laminate-calculator.tsx` |

The API still follows the [chunk 1 walkthrough](../../api/README.md). Its only new behavior is the CORS middleware described below; its calculation contract and engine equations are unchanged.

## What the libraries and browser features mean

- **React** draws the screen. `useState()` retains the current form/result between renders; each input's `onChange` calls `update()`. `useRef()` holds the active request controller; `useEffect()` cancels it when the page unmounts.
- **Next.js** supplies the route and static build. The interactive calculator is a Client Component (`"use client"`), so its event handlers run in the browser.
- **TypeScript** checks the code's expected types before running. Network data still needs runtime checks, which is why `readAnalysisResult()` exists.
- **fetch, AbortController and JSON** are built into the browser. `fetch()` sends the request, `AbortController` cancels waiting, and JSON carries named fields and arrays. The wait times out after 20 seconds. Cancellation does not guarantee an already-started server calculation stops.
- **CORS** is a browser rule for access across different origins (scheme, host and port). FastAPI's middleware permits JSON POST requests from `localhost` and `127.0.0.1` on ports 3000/3001. It does not authenticate callers or make this a public deployment.
- **Playwright** operates a real browser for tests. Success cases reach the actual Python API; only error/cancellation scenarios intercept traffic. No new runtime dependency was added.

## Units and state to watch

Material moduli are entered in GPa; thicknesses in mm; angles in degrees. Loads are already per unit width: N/m and N*m/m. The frontend sends `SI_BASE` to the API and leaves output matrices in their labelled SI units. These are input/display conversions permitted by ADR-0002, not a second laminate solver.

Blank fields remain blank until corrected; they never become implicit zero loads. Adding a ply creates empty angle/thickness fields. Requests disable edits while pending; Cancel restores editing. Any edit clears the result. A failed request never substitutes a demo answer. Inputs/results live only in browser memory and disappear on reload.

## Checks and next boundary

After building with the API address configured, `npm run test:calculator` starts missing local servers and runs the six browser cases. It reuses running servers locally, so restart an old API process after code changes. CI builds the site and starts clean servers. `npm run test:e2e` checks the whole website and now requires the API to be running for the calculator cases.

Evidence: [chunk 2 evaluation](../evaluations/website/2026-10-03-calculator-chunk-2.md). Decision: [ADR-0012](../decisions/ADR-0012-browser-calculator.md).

This chunk supports one typed-in material and a caller-supplied source reference. Curated dataset selection, saved run records, AI conversation and public deployment are later chunks. The source citation is not verified by this screen. First-ply failure, ply stresses and hole geometry are not exposed here.
