# ADR-0120: A wing is a project of its own kind, kept like a coupon or a laminate, with its versions in the browser

- Status: Proposed
- Date: 2026-11-20
- Decided by: Founder, 2026-11-19 ("Finish step 4: saved wing + chat", his choice on what to build after the wing's finite element check; and "Plan order: project, rules, caps, chat", his choice on the order of the wing chat's plan, whose first step is this) | Drafted by: Claude Code
- Related: [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md), [ADR-0113](ADR-0113-each-settled-change-to-a-setup-is-kept-as-a-version-in-the-browser-with-who-made-it-why-and-its-runs-answer-and-going-back-is-a-new-version.md), [ADR-0118](ADR-0118-the-wing-workspace-works-the-engines-hand-calculation-through-the-api-on-every-settled-change-draws-what-the-engine-returns-and-keeps-the-wing-as-its-wing-file.md), [ADR-0119](ADR-0119-a-wings-finite-element-check-runs-from-the-wing-workspace-as-a-background-job-like-a-coupon-run-and-sets-the-model-beside-the-hand-calculation.md), [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md), `api/alembic/versions/0013_wing_project_kind.py`, `api/src/anisotropy_api/records.py` (`PROJECT_KINDS`), `api/src/anisotropy_api/schemas.py` (`ProjectInput`, `WingCheckRequest`), `lib/project-store.ts` (`WingProject`), `lib/wing-versions.ts`, `components/workspace/wing-context.tsx`, `components/workspace/use-wing-versions.ts`, `components/workspace/wing-history.tsx`, `components/workspace/chooser.tsx`
- Area: website, api, data

## Context

ADR-0118 kept one wing in the browser (`anisotropy.wing.v1`) and as a wing file the person saves, and left a project of kind `wing` for later. A person could hold one wing at a time, lose it with the site's data, and not see it from another machine; the list of projects on `/workspace` did not show it, and a finite element check (ADR-0119) belonged to no project. The founder's next asks need more: a chat that changes the wing ("Add 2 0 plies to the spar caps from the root to 40% span", 2026-11-19) must change one saved version of one wing, and the person must be able to go back. Coupons and laminates already live in the `projects` table (ADR-0062 part 6, migration 0007) under the signed-in email, and a coupon's settled changes are kept as versions in the browser (ADR-0113).

## Options considered

1. **Where a wing is kept.**
   - (a) A project of kind `wing` in the `projects` table, its description under `content.wing`, listed with the others; the browser's list of projects holds it too. Chosen: one store, one list, the same owner rules (ADR-0104) and the same sync as the other kinds.
   - (b) A table of its own for wings. Rejected: it would repeat the projects table's owner, sync and list for one more kind.
   - (c) The browser and the wing file only, as ADR-0118. Rejected: one wing at a time, on one machine, with no history.
2. **The wing project's name.**
   - (a) The wing's own title, which the wing file carries; the page's name box edits the title. Chosen: the list of projects and the wing file never disagree.
   - (b) A name of the project's own beside the title. Rejected: two names for one wing.
3. **Versions.**
   - (a) In this browser per project, each settled change (1.2 s) a version with who, why and what changed in the page's labels, going back a new version, the last 50 kept; a check marks the version it was started from and keeps its headline. Chosen: the same rule as a coupon's (ADR-0113), and what a chat's Apply needs.
   - (b) Versions on the server. Later: no kind keeps versions on the server yet, and the description of each version is small enough for the browser.
   - (c) No versions. Rejected: a change from the chat could not be undone.
4. **The wing kept before this.**
   - (a) Brought over once: a browser with no wing project and a wing under `anisotropy.wing.v1` makes it its first wing project, with its check, and the old key is removed once the project is kept. Chosen: no one loses a wing.
   - (b) Left behind. Rejected: the wing on the page would be replaced by the example.
5. **The finite element check.**
   - (a) `POST /v1/wings/checks` takes an optional `project_id`; when it is the requester's project the job row names it and the project lists it, as a coupon job (ADR-0062 part 6); otherwise it is ignored and the check still runs. Chosen.
   - (b) Checks belong to no project. Rejected: a project could not list its checks.

## Decision

Options 1(a), 2(a), 3(a), 4(a) and 5(a).

- **Server.** Migration 0013 adds `wing` to the kinds `projects_kind_known` admits; the downgrade refuses while a wing project exists. `PUT /v1/projects/{id}` takes `kind = "wing"` with the description under `content.wing`, and refuses a wing whose `content.wing` is not an object. `POST /v1/wings/checks` takes `project_id`.
- **Page.** The wing workspace opens the wing project the person last changed or opened from the list; with none, the wing kept before (option 4), else the example, which is kept and sent only once it is changed or checked. A moment after each change the project is sent to the server, as the other kinds are; a browser with no wing project is offered the newest one on the server. "New Wing design project" starts a project from the example. The check under way is kept with the project it was started for.
- **History.** Panel 11, History: every version newest first, who and why, what changed, the check made from it, "Undo the last change" and "Go back to this".
- **List of projects.** A wing shows as "Wing design", its size ("2 m half span, 0.45 m chord") and its material by name.

## As built (2026-11-20)

- `api/alembic/versions/0013_wing_project_kind.py`; `PROJECT_KINDS` in `api/src/anisotropy_api/records.py`; `ProjectInput`, `ProjectOutput` and `WingCheckRequest` in `api/src/anisotropy_api/schemas.py`; `start_wing_check` in `api/src/anisotropy_api/main.py`; `CouponJobs.start_wing(project_id=...)` in `api/src/anisotropy_api/coupon_jobs.py`.
- A project read while one of its jobs was queued failed its own answer's contract (`ProjectJobOutput.state` lacked `queued`); found by this record's test and fixed with it.
- `WingProject`, `newWingProject`, `reduceWing`, `wingProjects`, and the wing in `uploadOf` and `projectOfRecord` in `lib/project-store.ts`; `startWingFeCheck(..., projectId)` in `lib/studio-api.ts`; `wingAbout` and `wingMaterial` in `lib/wing.ts`.
- `lib/wing-versions.ts` (`wingChanges`, `withWingVersion`, `withWingCheck`, `withWingCheckResult`, `readWingVersions`, `writeWingVersions`, `MAX_WING_VERSIONS` 50, key `anisotropy.wing-versions.v1.<project>`); `components/workspace/use-wing-versions.ts`; `components/workspace/wing-history.tsx`.
- `components/workspace/wing-context.tsx` on the project store; `components/workspace/chooser.tsx` lists, opens and starts wings.

## Why (evidence)

- `cd api && uv run pytest -q tests/test_projects.py tests/test_wing_checks_api.py tests/test_run_records_db.py` with the test database: 50 passed, 2026-11-20. It holds the wing project created and refused as another kind, a wing without `content.wing` refused, migration 0013 admitting a wing and refusing to be undone over one, and a check started for the requester's wing project listed with it while queued, another's project id ignored.
- `npx tsx --test tests/wing-versions.test.ts tests/project-store.test.ts`: 7 passed; `npm test`: 438 passed, 1 skipped (the course appendix is not on this machine).
- `npx playwright test --config playwright.studio.config.ts wing.spec.ts workspace.spec.ts` (Chromium): 13 passed, the new specs included: a wing listed with its size and material, a second wing from the example, each opened as left with its check, versions gone back to, and the wing kept before brought over with its check.

## Consequences

- Every wing a person changes is saved to their account and listed with their coupons and laminates; the chat of the next steps changes a saved version that can be undone.
- A new kind of project now exists in the database; undoing migration 0013 needs the wing projects gone first.
- Versions stay in one browser, as a coupon's do; another machine sees the latest wing, not its history.
- The example opened on a fresh browser is not saved until it is changed or checked, so opening the page does not add a project.

## How we will know it was wrong

- A person reports a wing lost across machines or after clearing site data, or two wings that should differ showing the same description.
- A wing description grows past the projects' content limit (`VALUES_LIMIT_BYTES`), for example once zones along the span are added: then the description or the limit must change.
- People ask for a wing's history on another machine: then versions move to the server, for every kind at once.
