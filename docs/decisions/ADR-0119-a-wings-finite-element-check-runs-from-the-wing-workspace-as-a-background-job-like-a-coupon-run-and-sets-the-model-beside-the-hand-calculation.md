# ADR-0119: A wing's finite element check runs from the wing workspace as a background job, like a coupon run, and sets the model beside the hand calculation

- Status: Proposed
- Date: 2026-11-19
- Decided by: Founder, 2026-11-19 ("Background job, like a coupon run", his choice on how to run the wing's finite element check from the page) | Drafted by: Claude Code
- Related: [ADR-0117](ADR-0117-a-wing-is-checked-in-calculix-with-composite-shells-under-superposed-load-patterns-its-panels-buckle-as-the-engines-ritz-plates-on-the-models-loads-and-flutter-is-a-typical-section-estimate.md), [ADR-0118](ADR-0118-the-wing-workspace-works-the-engines-hand-calculation-through-the-api-on-every-settled-change-draws-what-the-engine-returns-and-keeps-the-wing-as-its-wing-file.md), [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md), [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md), `fea/src/anisotropy_fea/wing_check.py`, `api/src/anisotropy_api/coupon_jobs.py` (`start_wing`, `_solve_wing`), `api/src/anisotropy_api/main.py` (`start_wing_check`, `wing_check`), `components/workspace/wing-rail.tsx` (`FeCheckPanel`), `components/workspace/wing-stage.tsx` (`FeResults`), `fea/tests/test_wing_check.py`, `api/tests/test_wing_checks_api.py`, `tests/browser/wing.spec.ts`
- Area: fea, api, website, hosting

## Context

Step 4 of the wing generator asks for a button on the wing page that checks the wing with its finite element model (ADR-0117). That model is built and solved by the fea package in CalculiX: the example wing takes 28 s on a development machine at the 40 mm mesh (build 3 s, the four load patterns 16 s, the first six modes 6 s), where the hand calculation answers in a tenth of a second (ADR-0118). Coupon runs already go through the job system (ADR-0050): a row in the jobs table, the tool in a process of its own, its stage in a progress file, a run record when it ends; on the hosted tier the API's container files the job and a solver container from the pool runs it, watched by the Worker with a 12-minute limit and held to the per-user limits (ADR-0056 amendments 3 to 6). A coupon job names a coupon and takes the naming gate; a wing names none. The STEP file (ADR-0118 option 8) is built inside one request because it takes half a second.

## Options considered

1. **How the check runs.**
   - (a) A background job, like a coupon run: the page starts it, follows its stage and shows the answer when it ends. Chosen by the founder.
   - (b) One request that waits for the answer, as the STEP file does. Rejected: half a minute or more inside the API's own container, which answers every other request, and longer than a browser or the hosted gateway should hold a request open.
   - (c) No button: the command line only (`python -m anisotropy_fea.wing_model`). Rejected: step 4 asks for it on the page.
2. **Where the job lives.**
   - (a) The coupon jobs' own table, queue, solvers, limits and receipts, the job marked `kind = "wing"` in its row's inputs. Chosen: no migration, no change to the Worker, and the per-job limit, the heartbeat and the sweep apply as they are.
   - (b) A jobs table and queue of its own. Rejected: a second copy of the machinery ADR-0056 took six amendments to settle.
3. **How the description reaches the solver.**
   - (a) In the row's inputs, which the solver reads when it claims the job. Chosen: a few kilobytes, and the run record keeps it there too, as the hand calculation's does (ADR-0118, option 6).
   - (b) Filed in the store first, as a coupon's values are. Rejected: one more upload and download for nothing the row cannot hold.
4. **Which skins count.** The model's skins between the spars (`skins = "box"`), as the hand calculation counts them, so the two answer the same question. Running both extents (ADR-0117) doubles the time; the airfoil extent waits until the description says whether the skin ahead of and behind the box is structure.
5. **What comes back.** One report in the wing file's units (`check_report`): the lowest margin by the model and by the hand calculation outboard of the root zone, the model's at the clamped root, every case side by side, the wing as a beam, the modes, divergence, flutter and the panel that buckles first. Kept as the job's one file, under the job's own key in the store (`jobs/<id>/output/`), and sent with the job's status once it is done, so the page makes one kind of call.
6. **What the page says.** The stage in words (Building the model, Solving the flight loads, Vibration modes and flutter), the engine's or the model's words when the description cannot be checked, and "The check could not be finished. Start it again; if it keeps failing, contact us." for a stop, its cause in the log (ADR-0091 amendment 2). The button names no tool.

## Decision

A wing's finite element check is a job of the coupon jobs' kind (ADR-0050, ADR-0056), marked `kind = "wing"` with the wing's description in its row. `POST /v1/wings/checks` reads the description by the engine's rules, refuses a bad one at once with 422, and starts the job: here in the background, one at a time, or filed for the queue with the header the Worker reads. The solver runs `anisotropy_fea.wing_check` with no gate and no coupon's folder, and files its report under the job's own key. `GET /v1/wings/checks/{id}` answers the state, the stage and, once done, the report. The wing page's panel 9, Finite element check, starts it, keeps its id in the browser, follows it every 2 s and shows the result in the centre beside the hand calculation, marked out of date when the wing has changed since it started.

## As built (2026-11-19)

- fea: `anisotropy_fea/wing_check.py`: `solve_check` (the model, the static solve, the modes and the hand calculation, in SI), `check_report` (the report in a reporting system), `main` (the job's tool: `--out`, `--result`, `--progress`; done, refused with exit 2, or stopped).
- API: `coupon_jobs.py`: `wing_check_command`, `is_wing`, `CouponJobs(wing=...)`, `start_wing`, `_solve_wing`, `_store_wing`; `storage.job_output_key`; `main.py`: `start_wing_check`, `wing_check`, the receipt at `/v1/wings/checks`; `schemas.WingCheckOutput`.
- Website: `lib/wing.ts` (`WingFeCheck`, `WingFeReport`, `feProgress`, `feWords`), `lib/studio-api.ts` (`startWingFeCheck`, `getWingFeCheck`), `wing-context.tsx` (the check's state, `anisotropy.wing-check.v1`, the wake-up when the panel opens), `wing-rail.tsx` (`FeCheckPanel`; Shape for CAD becomes panel 10), `wing-stage.tsx` (`FeResults`), `tests/fixtures/wing/example-check.json` (the tool's report of the example).
- No change to the Worker, the jobs table or the image: the Worker queues any job whose answer carries the enqueue header, and the image holds Gmsh and CalculiX already.

## Why (evidence)

- `cd fea && uv run --extra mesh pytest tests/test_wing_check.py`: 8 passed (2026-11-19). The hand columns equal the hand calculation's own report, the lowest margins are the lowest of the columns, the model agrees with the hand calculation on the example (lowest margin +0.146 by the model, +0.154 by hand, tip deflection within 5 %), SI and US reports differ only by their units, and a refusal ends with the reason.
- `cd api && TEST_DATABASE_URL=… uv run pytest`: 724 passed, 1 skipped (2026-11-19), among them `tests/test_wing_checks_api.py`, 9 passed: a check in the background and its report, a refusal before any start, one at a time here, the stop's words, through the queue with the report read back from the store and its receipt at `/v1/wings/checks`, the per-job timeout, and the real tool on the example.
- `npx tsx --test tests/wing.test.ts`: 5 passed; `npx playwright test --config playwright.studio.config.ts wing.spec.ts workspace.spec.ts`: 11 passed on Chromium (2026-11-19), with the check's stage, its result, the out-of-date mark and a page that names no tool.
- On the local page with the local API, the example's check showed its three stages and its answer 30 s after the click (the tool's own time 28 s).
- The hosted time is not measured yet: UNVERIFIED.

## Consequences

- A check counts as a job: it waits behind a person's running coupon job, and counts toward the daily cap where one is set (ADR-0056).
- A check's answer is kept as one file per job in the store and its description in the jobs table; nothing deletes them yet, as with coupon jobs.
- The list of past analyses on `/workspace` keeps coupon runs only (`lib/run-history.ts` filters on a coupon and its fields), so a wing's check is not listed there.
- A larger wing has more elements at 40 mm and takes longer; the 12-minute limit stops it.

## How we will know it was wrong

- The hosted check of the example takes more than two minutes from the click to the answer.
- Checks crowd out coupon runs in the solver pool, or people reach the daily cap with checks.
- The model and the hand calculation disagree on a wing whose skins are only between the spars: then the comparison, not the job, is what needs revisiting (ADR-0117).
