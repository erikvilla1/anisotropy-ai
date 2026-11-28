# ADR-0143: A model's setup is changed through typed tools in the API that the page, the MCP server and the workspace's planner share, and the server keeps its versions

- Status: Proposed; a force and a set move of one direction take each other's place since amendment 1
- Date: 2026-11-26
- Decided by: Founder, 2026-11-25 ("Mockup and plan first", on the card about making the workspace agentic, after he asked whether the software runs agents "like PhysicsX"); 2026-11-26 ("let's cpntinue with our agentic engineering tell me what you need to continue", on the plan's build step 1, the tool layer with no model) | Drafted by: Claude Code
- Related: `api/src/anisotropy_api/setup_tools.py`, `api/src/anisotropy_api/records.py` (`ModelVersionRow`, `add_version`, `apply_setup`), `api/alembic/versions/0016_model_versions.py`, `mcp-server/src/anisotropy_mcp/server.py` (`read_plate`, `preview_plate_change`), `components/studio/use-versions.ts`, `lib/model-versions.ts`, `tests/fixtures/setup-tools/plate-setup.json`, [ADR-0113](ADR-0113-each-settled-change-to-a-setup-is-kept-as-a-version-in-the-browser-with-who-made-it-why-and-its-runs-answer-and-going-back-is-a-new-version.md) (versions, until now in the browser), [ADR-0101](ADR-0101-on-a-plate-the-model-proposes-supports-and-loads-from-the-engineers-words-and-the-element-clicked-and-a-guard-keeps-what-the-words-or-the-click-hold.md) (a plate's supports and loads), [ADR-0107](ADR-0107-an-mcp-client-reaches-anisotropy-through-a-local-server-over-stdio-that-calls-the-api-it-solves-a-preview-and-starts-no-full-run-and-the-clients-model-writes-the-words.md) (the MCP server reads and previews only), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (projects kept on the server), [ADR-0139](ADR-0139-the-models-words-may-not-decide-for-the-engineer-its-calls-are-capped-per-person-per-day-and-how-often-the-guards-set-answers-aside-is-read-each-week.md) (the model does not decide for the engineer)
- Area: api, website, assistant, data

## Context

- No agent runs in the product today (`docs/ai-catalog.md`). The founder wants the workspace to plan and carry out engineering steps, not only chat. The plan he asked for, "Agentic workspace plan" (2026-11-25), has five build steps. In step 1 the steps an agent takes become typed tools with no model. Step 2 adds one planner in the API that proposes a plan the engineer approves once. Step 3 shows the steps live, step 4 adds checks, and step 5 reaches the repair and the wing.
- Before this record, a plate's supports and loads were changed only in the browser, by the page's own sentence reader (`lib/plate-edits.ts`). The API could replace a kept project's content whole (`PUT /v1/projects/{id}`), but it could not read a setup, work out a change or refuse one in words. The MCP server could solve a coupon and read its results, but it could not reach a plate's supports and loads (`docs/components/mcp.md`, limits).
- A model's versions (ADR-0113) were kept in the browser's storage alone. A change made anywhere but that browser, on another computer or by a tool on the server, had no place in the history.
- An agent's change has to be checked and kept by the server, since the server is where a planner runs and where an approval can be enforced. The engineer still applies it (ADR-0139).

## Options considered

1. Typed tools in the API, in Python, with the page's own rules, held to the page by one shared fixture of plates and sentences, and a table of versions on the server. Chosen.
2. Let a planner write sentences for the page's reader to apply in the browser. Rejected: a change made in the browser cannot be checked or gated by the server, and an MCP client has no browser.
3. One TypeScript copy of the rules, run by the API under Node. Rejected: a second runtime in the API's container for one module, while the fea package, which judges every row, is Python.
4. An agent framework with its own store and queue (LangGraph, Celery, Redis, named in the founder's roadmap). Rejected for now: Postgres already holds the truth and the API already runs the jobs. A framework adds services and does not remove a step.
5. Keep versions in the browser and upload copies of them. Rejected: two numberings of one history, and a change applied by the server needs its version written in the same transaction as the content.

## Decision

Option 1. The workspace's steps over a model's setup are typed tools in the API, shared by the page, the MCP server and, from build step 2, the planner. Each takes the project's content as the page keeps it and answers in data. No model is asked and no number is computed (ADR-0001); the fea package judges the rows at check time, as always (ADR-0051).

- **Read**: what the model is, in its own units, the regions a plate can be held and loaded on with where each lies, and what is held and loaded, one line each. A plate's ends are the edges across its width at y = 0 and y = length, plus the tabs there; its sides are the long edges.
- **Change**: `hold`, `move`, `force`, `pressure`, `free`, `unload` and `row`, at most 24 in a request. They are made on a copy, every one or none, with the reason for each one refused.
  - The rules are the page reader's: a new hold takes the place of the region's hold, a force takes the place of the one in its direction, and tension pulls along the edge's outward normal.
  - A unit is converted only within the model's own system, and degrees become radians.
  - The test and the unit system are never changed by a tool.
- **Apply**: only on a kept project, only with the digest of the setup the preview was worked out on, and with who made the change and why. The content and a new version are written in one transaction, and a project changed since the preview is refused with 409.
- **Versions**: kept by the server with the project, numbered there; a setup the same as the last one adds none. The page shows its own copy at once and sends what the server lacks. It keeps its versions alone when the API keeps no projects.
- **MCP**: the server reads a plate and previews a change. It applies nothing (ADR-0107).

## As built (2026-11-26)

- `api/src/anisotropy_api/setup_tools.py`:
  - `read_setup`, `regions` (roles all, ends, sides, edges, areas), `change_setup` (the `Changed` result: content, done, refused, ok) and `plate_values` (the values the fea package takes, as `lib/tension-screen.ts` writes them).
  - `content_digest`, which is exact and used for the stale check. `setup_key`, which ignores the date and blank rows and is used for a version.
- Routes:
  - `POST /v1/workspace/setup` and `POST /v1/workspace/setup-changes`: read and preview, nothing kept.
  - `POST /v1/projects/{id}/setup-changes`: a preview, or an apply with `apply`, `base`, `by` and `why`. Refusals: 409 when stale, 422 when a change is refused or no base is given, 422 for a project that is not FEA.
  - `GET` and `POST /v1/projects/{id}/versions` and `PUT /v1/projects/{id}/versions/{n}/run`.
- Table `model_versions` (migration 0016): key project and number; who made it, why, the lines of what changed, the setup, its key, and the run and its answer. If the QA/QC pull request (#269), which also numbers a migration 0016, lands first, this one is renumbered.
- MCP server: `read_plate` and `preview_plate_change`, and rules 21 and 22 for the client's model: read the plate first, and say which edge was read when the words could mean an end or a side.
- The page: `useVersions` reads the server's versions with the project, merges this browser's newer ones after them (`mergeVersions`, `unsent`), sends them and the runs marked on them (`runsToSend`), and tries again while a new project has not yet reached the server.
- Parity: `tests/fixtures/setup-tools/plate-setup.json` holds what the page writes for three plates and what its reader makes of fourteen sentences, with the typed change for each. `tests/setup-tools.test.ts` holds the page to it, and `api/tests/test_setup_tools.py` holds the tools to it.
- Not built in this step: the planner, the approval card, the live steps and the coupon's grips and loading as typed changes. A coupon's rows can be changed (`row`), but its supports and loads cannot.
- Corrected 2026-11-28: the page did not send only what the server lacks. `setupKey` (`lib/model-versions.ts`) told two setups apart by the order their keys were written in, and the server answers `GET .../versions` and the project with a kept setup's keys in its database's order, so on any opening or reload of a kept FEA project the page took the server's last version for another setup and sent its own again each time the server answered. `setupKey` now reads a setup by its values, as the server's `setup_key` does (`tests/model-versions.test.ts`; the browser scenario "a kept project opened again sends no version the server holds" counts 9 sends in 5 s on main's page code and at most one here). Whether the hosted site ran the merged page long enough to add rows is UNVERIFIED.

## Why (evidence)

- `cd api && TEST_DATABASE_URL=… uv run pytest -q tests/test_setup_tools.py`: 62 passed against a local Postgres 16 (2026-11-26). Covered: the parity cases, the refusals, unit conversion, the routes, the stale apply and the version numbering.
- `cd mcp-server && uv run pytest -q`: the two tools through the SDK's client, against a stand-in that answers with the API's own answers (`mcp-server/tests/fixtures/plate-setup.json`, held to the API by `test_the_mcp_servers_stand_in_holds_the_apis_own_answers`).
- `npx tsx --test tests/setup-tools.test.ts tests/model-versions.test.ts`: the page agrees with the fixture, and its merge with the server's versions behaves as described.
- `tests/browser/workspace.spec.ts` ("a model's versions are kept on the server with its project…"): a version made elsewhere shows in the history after this browser's copy is cleared.
- No measurement yet of what the extra version calls cost the hosted API.

## Consequences

- The page, the MCP server and the planner to come change a model by the same rules, and a change the server applies is in the history with who made it and why.
- The rules exist twice: in the page's reader, for an edit applied as it is typed, and in the tools. The fixture is what keeps them together. A new sentence on the page needs a typed change and a fixture case, or one of the two test files fails.
- The page now writes a version to the API for each settled change, in addition to the project itself.
- The API's database gains a table, and a migration that may need renumbering at merge.

## How we will know it was wrong

- The fixture has to be rewritten for a disagreement between the page and the tools more than twice in a month. One copy of the rules is then worth its cost.
- Step 2's planner needs a change these actions cannot state, and it is not one action more.
- The history in a browser and on the server disagree for an engineer, or the version calls show among the API's errors after deploy.

## Amendment 1, 2026-11-26 (a force and a set move of one direction take each other's place; a force on a held direction is refused)

**Context.** A walk-through of the planner on a plate made from the tension screen showed the card "Edge-Top: force of 2000 N along y (tension)" while the run was driven by the 1 mm move of Edge-Top along y that the plate kept from the coupon's pull: the move carries any force along its direction, so the force did nothing and the answer was of a 1 mm pull. The page's reader and the typed `force` both left the move in place, and the parity fixture's cases held that.

**Options.** Refuse a force on a moved direction and make the engineer free it first: rejected, since "pull the top edge with 2 kN" plainly means a pull by force in place of the pull by travel. Leave both and warn in the setup check: rejected, since the card would still show a change the run does not make. Let the newer one take the other's place and say so in its line: chosen.

**Decision.** A force along a direction of a region takes the place of the region's set move along it, and a set move takes the place of its force along it; the line says what it replaced ("…, in place of its move of 1 mm along y"). A force along a direction the region is held in is refused by the tools and noted by the page, in the same words, since the support would carry it. Holds are unchanged. Drafted after the walk-through; not yet confirmed by the founder.

**Evidence.** `tests/fixtures/setup-tools/plate-setup.json`: three cases now replace a move or a force; `api/tests/test_setup_tools.py` and `tests/setup-tools.test.ts` hold both sides to them and to the refusal.
