# ADR-0051: The coupon studio is a browser page in the existing site that builds, checks, solves and views coupons through the API; the fea package computes the checklist, the preview, every field and the template explanation

- Status: Proposed
- Date: 2026-10-28
- Decided by: Founder, 2026-10-28 ("get the browser up and running and not get terminal execution anymore": an engineer with no FEA software enters geometry, material, laminate, loads, constraints and failure criterion in the browser, sees an interactive 3D model, gets a setup check, solves with one click, reads stress, displacement, failure index, factor of safety and the critical location in a 3D viewer with an explanation, and every existing output keeps being produced; on the four choices asked the same day: coupon first, then general edges; a bending element in this phase; a deterministic checklist and template prose with a model provider behind a setting; the founder's machine only) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0012](ADR-0012-browser-calculator.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0027](ADR-0027-deployment-tiers-and-assistant-model-location.md), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (amendments 2 and 3), [ADR-0048](ADR-0048-the-assistant-drives-tested-jobs-built-after-one-command-per-job-and-an-api-job.md), [ADR-0049](ADR-0049-one-command-takes-a-coupon-from-its-input-form-to-its-package.md), [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md) (amendment 1), `fea/src/anisotropy_fea/{checks,quality,preview,fields,explain}.py`, `fea/tools/studio_tool.py`, `fea/tools/export_form_definition.py`, `lib/coupon-form-definition.json`, `api/src/anisotropy_api/coupon_jobs.py`, the plan `C:/Users/erikv/.claude/plans/gonna-start-ramping-up-melodic-kitten.md` (local)

## Context

- A coupon reaches our engine through the Excel input form (ADR-0046) and one command (ADR-0049), or the same job through the API (ADR-0050). Every step is typed in a terminal, and the results are read in PrePoMax, ParaView and the PDF. The founder wants the team to work in the browser with nothing installed.
- The website is a static Next.js export that calls the API from the browser (ADR-0012). It has no 3D library and computes no result (ADR-0001). The API answers only in JSON and has no file download but the package zip.
- The fea package solves flat coupons in plane stress and writes its results as a `.vtu` for ParaView, PNG figures and a text summary; nothing in it is shaped for a browser: no JSON of the fields, no mesh quality measure, no setup check before a run, and the words that say where the first ply fails live in `docs/models/coupon.py`.
- ADR-0046 rejected a web form "for now" because there was nothing to host. ADR-0050 built the thing to host and left "a website page" unbuilt. ADR-0027 and ADR-0048 require the assistant's own record before a language model writes anything.
- This record covers the foundations (the package's new modules, the API) and the page's architecture. The page itself, the assistant, plate bending and the general `plate` kind follow in their own parts, each with its record; the plan file lists them.

## Options considered

Where the page lives:
1. **A new route in the existing site.** One codebase, one build, the API's loopback CORS as it is (ADR-0012, ADR-0027 "features by configuration, not forks"). Chosen.
2. **A separate single-page application.** A second build and deployment for one page.
3. **A server-side viewer (a Python web framework rendering VTK in the browser).** Fast to a first picture; a second web stack beside Next.js and the API, and the fields leave the API's contract.

How the page draws:
1. **three.js through React Three Fiber and drei, loaded only in the browser.** MIT licences; React state drives the scene; the installed Next.js docs allow `ssr: false` only inside a client component, which is where the scene lives. Chosen.
2. **Plain three.js.** Imperative code beside React's state.
3. **vtk.js.** Built for scientific fields, large, and a second mesh model to keep in step with ours.

Where the numbers come from:
1. **The fea package computes everything the page shows, including the per-node averages that smooth a contour, and writes it as JSON; the browser only draws.** Chosen (ADR-0001).
2. **The browser averages, picks extremes and words the result.** A number the engine did not compute, shown as a result.

How the page reaches the package:
1. **Through the API, which runs the fea tools as programs (`uv run --project fea`), as ADR-0050 does for the job.** The setup check and the coupon listing wait for a short run of `fea/tools/studio_tool.py`; the solve is the job of ADR-0050, which now also reports its stage and the files made so far. Chosen.
2. **The fea package imported into the API process.** Rejected by ADR-0050.

What the page sends:
1. **The form's rows as one JSON object (a values file), judged by the same checks as the Excel form.** One definition of the rows, exported once to `lib/coupon-form-definition.json` with a drift test, as the material library is exported. Chosen (ADR-0046 amendment 3).
2. **A TypeScript schema of the rows beside the Python one.** Two sources of truth.
3. **The browser fills an Excel file.** A spreadsheet library in the browser to make a file a tool reads back.

How the setup is checked and the result explained:
1. **A deterministic checklist (`checks.py`) from the tools' own refusals, the mesh quality measures and what is installed; a template (`explain.py`) that writes sentences from a fact sheet of the solve's numbers.** Testable, never wrong about a pass, and the fact sheet is what a later assistant rephrases under a number guard (ADR-0048 step 3, its own record). Chosen.
2. **A language model judges the setup and writes the explanation from the start.** It would judge before the assistant's record exists (ADR-0027 item 2) and could pass a setup the tools refuse.

## Decision

- **The studio** is a route of the existing site, `/studio`, with its viewer openable in a second window by its job's link. It draws with three.js through React Three Fiber, in a client component loaded only in the browser. It computes no result: every number it shows, the averages included, is in a JSON file the fea package wrote.
- **The fea package** gains, under `fea/src/anisotropy_fea/`: `quality.py` (aspect ratio, smallest and largest angle, Jacobian ratio per element; our thresholds, which only warn, carry no evidence yet), `checks.py` (the setup checklist: twelve items, each pass, warn, fail, missing or pending, with the form rows it concerns; a fail or a missing row blocks the run), `preview.py` (what to draw before a solve), `fields.py` (every field of a solve, the display averages labelled as such, and a summary of the extremes with the critical element, ply, mode and place), and `explain.py` (the fact sheet and the template's sentences). `report.fpf_place` moves from the document code into the package and `units.UNIT_LABEL` from the document builder, so the PDF and the studio use one wording and one unit table.
- **The inputs:** the form gains the rows Failure criterion and Tsai-Wu interaction f12* (form 0.3, ADR-0046 amendment 2); the same rows may arrive as a values file, `<name>.json`, read by `intake.read_values` and filed with the coupon on every run (ADR-0046 amendment 3). `intake.values_of_spec` reads a coupon's spec back into its rows, so the studio reopens a coupon to change it. The rows' definition is exported to `lib/coupon-form-definition.json` by `fea/tools/export_form_definition.py`; a test fails when it drifts.
- **The tools:** `fea/tools/studio_tool.py` answers the studio's questions (`check`, `coupons`, `values`, `fixtures`); `fea/tools/run_coupon.py` accepts a values file, runs the setup check first and refuses a blocked one before writing anything, rewrites a progress file after every step (`--progress`), keeps the checklist and the preview in the attempt's `run/studio/`, and reports the new files `fields` and `explanation`, which `examples/build_model.py` writes beside the `.vtu`.
- **The API** (ADR-0050 amendment 1): `POST /v1/coupon-jobs` also takes `values`; `POST /v1/coupon-jobs/check` runs the setup check and answers with the checklist and the preview, recorded by the values' digest; `GET /v1/coupon-jobs` lists this process's jobs; a job's status carries its stage and the files made so far, and `GET /v1/coupon-jobs/{id}/files/{key}` serves one by key, so the viewer loads the fields as soon as our engine has run while CalculiX and the PDF continue; `GET /v1/coupons` and `GET /v1/coupons/{name}/values` list the coupons and read one back. The studio is the actor `studio` (migration 0004).
- **The order of the parts:** 1 these foundations; 2 the page for the four in-plane tests; 3 the assistant (ADR-0048 step 3, its own record); 4 plate bending (its own record); 5 the `plate` kind with any edge, tab, hole or face held or loaded (its own record). Authentication, a job queue and hosting stay where ADR-0027 and ADR-0050 put them.

## As built (2026-10-28)

Part 1, the foundations, on `feat/studio-foundations`: the five modules, the two tools, the moved `fpf_place` and `UNIT_LABEL`, form 0.3, the values file, the run tool's progress and studio outputs, the API's six changes and the migration. Tests: `fea/tests/{test_values_input,test_checks,test_fields,test_studio_tool}.py` and the extended `test_intake.py` and `test_run_coupon.py`; `api/tests/test_coupon_check_api.py` and the extended `test_coupon_jobs_api.py`. The page (part 2) is not built; the plan file lists its files.

## Why (evidence)

- The founder's words and choices of 2026-10-28, above.
- The installed Next.js docs: `node_modules/next/dist/docs/01-app/02-guides/lazy-loading.md` ("`ssr: false` option will only work for Client Components") and `static-exports.md` (dynamic routes without `generateStaticParams` are unsupported, so the viewer's window is `/studio/view?job=<id>`).
- A check costs one `uv run` start and a model build, 2 to 4 s on the founder's machine for a structured mesh (UNVERIFIED for a Gmsh mesh).
- The test runs are in the evaluation note `docs/evaluations/fea/2026-10-28-studio-foundations.md`.
- The thresholds in `quality.py`: no evidence yet; they warn and never refuse.

## Consequences

- Easier: the team states a coupon in the browser with the same rows and the same refusals as the form; every number the page shows is the package's; the attempt keeps the checklist and the preview it was run from; the assistant has a fact sheet to rephrase.
- Harder: three.js is the site's first runtime dependency for drawing; the fields JSON of a fine mesh is a few megabytes; the form's rows now live in three places kept in step by a test (the package, the exported JSON, the Excel form).
- Depends on: uv, the fea environment, CalculiX and Tectonic on the machine that serves the API (ADR-0050); Gmsh for an open-hole coupon, whose licence is now risk R-19.

## How we will know it was wrong

- If the page needs a number the package does not write, the JSON contract is wrong, not the rule.
- If the checks take longer than a user waits for a button (more than a few seconds for a structured mesh), the subprocess boundary of ADR-0050 is wrong for the check.
- If the team keeps sending the Excel form instead of using the page, the page is wrong.
