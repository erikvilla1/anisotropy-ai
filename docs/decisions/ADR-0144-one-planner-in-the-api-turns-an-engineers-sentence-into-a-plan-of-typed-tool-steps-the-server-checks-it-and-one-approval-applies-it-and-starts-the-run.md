# ADR-0144: One planner in the API turns an engineer's sentence into a plan of typed tool steps, the server checks it, and one approval applies it and starts the run

- Status: Proposed
- Date: 2026-11-26
- Decided by: Founder, 2026-11-25 ("Mockup and plan first"); 2026-11-26 ("let's cpntinue with our agentic engineering"; on the four choices of the plan: "number 4 everyone gets it no need for foudners anymore we need to scale fast now and progress faster", the other three taken as recommended; "ok i need you to deploy agents to finsiht eh rest of the plans") | Drafted by: Claude Code
- Related: [ADR-0143](ADR-0143-a-models-setup-is-changed-through-typed-tools-in-the-api-that-the-page-the-mcp-server-and-the-workspaces-planner-share-and-the-server-keeps-its-versions.md) (the typed tools and the versions), [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md) (the engineer applies), [ADR-0139](ADR-0139-the-models-words-may-not-decide-for-the-engineer-its-calls-are-capped-per-person-per-day-and-how-often-the-guards-set-answers-aside-is-read-each-week.md) (guards and caps), [ADR-0120](ADR-0120-each-call-to-the-language-model-is-kept-as-a-row-with-who-asked-what-for-the-tokens-billed-and-their-cost-read-through-three-views.md) (cost rows), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md) (question banks), [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md) (answers in words), `api/src/anisotropy_api/planner.py`, `components/studio/plan-card.tsx`, `tests/fixtures/planner/`
- Area: api, website, assistant

## Context

- Build step 1 (ADR-0143) made a model's setup changeable by typed tools on the server, with a preview, a stale check and a version. No model chooses those tools yet.
- The plan "Agentic workspace plan" (2026-11-25) puts one planner in the API (build step 2), live steps on screen (step 3), question banks and attacks (step 4), and the repair and the wing (step 5). The founder settled its four choices on 2026-11-26: one approval per plan, 30 planned requests per person per day, steps shown as named roles, and everyone gets it when it ships (no founders-first stage).
- Today a chat message is read by the page's patterns, or by one model call into a fixed form (`/v1/workspace/proposals`); the engineer ticks and applies, then presses Run, then asks about the result. That is three or four separate acts for one intention.

## Options considered

1. Plan then run: one model call returns a plan made only of typed tool steps; the server checks it; one approval applies the changes as a version and starts the run; the page reads the result's checks and a second, guarded call words the answer. Chosen.
2. A free-running agent that calls the model after every tool. Rejected: several times the calls and cost of option 1, harder to predict, and every step would need its own approval or none.
3. Keep the page's fixed readers and add a "run after apply" button. Rejected: it cannot read "clamp, pull, run and tell me if it holds" as one request, which is the founder's ask.
4. An agent framework (LangGraph and a queue). Rejected for the reasons in ADR-0143: Postgres and the API's jobs already hold the state.

## Decision

Option 1. The contract between the API and the page, held by `tests/fixtures/planner/` (the API's tests check its answers have these keys; the page's tests and browser mocks use these files):

- **Plan**: `POST /v1/projects/{id}/plans` with `{"ask": "<the engineer's sentence>"}`, on a kept `fea` project. One model call (feature `plan_steps`) sees the setup as `read_setup` reads it and the tools on offer, and returns steps. The server keeps a plan only when every step names a listed tool, every change previews (ADR-0143, every one or none), every region exists, and every number in a step is written in the sentence; otherwise the model gets one more try with the reasons, then the answer says why there is no plan. The server adds `check` before a `run` and `qa` after it. A plan has at most 12 steps.
- **Answer** (`PlanOutput`, `plan-proposed.json`): `id`, `project`, `ask`, `state` (`proposed`, `question`, `refused`, `unavailable`, `capped`, `approved`, `running`, `done`, `stopped`), `steps` (each `n`, `role`, `tool`, `line`, `quote`, `regions`, `change`, `question`, `state` of `planned`/`running`/`done`/`failed`/`skipped`, `note`), `done` (the preview's lines), `base` (the digest of the setup it was worked out on), `question` (asked back when the words fit two regions, `plan-question.json`), `unread`, `reason`, `writer`, `model`, `job`, `version`, `requests_left`, `created_at`, `approved_at`.
- **Roles**: `Geometry` for a row of size or shape, `Setup` for supports, loads, material and layup, `Solver` for `check` and `run`, `QA` for `qa`, `Report` for `answer`.
- **Approve**: `POST /v1/projects/{id}/plans/{plan_id}/approve` with `{"base": "<digest>"}` (`approve-running.json`). In order: the changes and a version by `assistant` with the ask as why, in one transaction (409 when the project changed since the plan); the setup check (a failed check stops the plan with its lines); the run, through the same start as `POST /v1/coupon-jobs`, inside the daily cap on analyses. The answer is the plan, the project, the version, the job and the check. A plan is approved once (409 after).
- **Steps the page carries**: `qa` (the result's own checks read into pass, warning or stop, with the evidence named; no number computed) and `answer` (the step's question through `/v1/workspace/result-answers`, under its number and word guards). The page reports each to `POST /v1/projects/{id}/plans/{plan_id}/steps/{n}` with `{"state", "note"}`; `GET /v1/projects/{id}/plans/{plan_id}` reads the plan as it stands.
- **Limits**: 30 planned requests per person per day (`ANISOTROPY_AGENT_REQUESTS_PER_DAY`), counted by plans kept since midnight UTC; a request past it answers `capped` with a fixed reason and calls no model. A service token is not counted (as ADR-0139). With no model, `unavailable`, and the page reads the sentence as before.
- **Kept**: table `agent_plans` (migration 0017), and every call a row of `model_calls` with feature `plan_steps`. Each request is a run record (ADR-0026).
- **On the page**: a message that asks for a change and a run or an answer in one sentence goes to the planner when a model reads and the project is kept; a single edit stays with the page's patterns. The plan card lists the steps under their roles, draws the regions dashed on the model before anything applies (ADR-0110), and has Approve and Edit. Once approved, the steps tick off as they run, the model tree takes the new setup, and the Results tab opens.
- **Everyone** gets it when it ships; the real-model Assistant check still runs before the merge (ADR-0121).

## Why (evidence)

- No evidence yet. The build is in progress on the branch of PR #287.

## Consequences

- One sentence does what took three or four acts, and the engineer still approves before anything changes or runs.
- Two model calls per request at most (plan and answer), each a cost row; the cost per request is measured in this step.
- The page and the API share one contract file set; a change to the plan's shape changes the fixtures and both sides' tests.

## How we will know it was wrong

- The guards refuse more than a third of plans for real asks in the question bank, or engineers edit most plans before approving them.
- The cost per request is more than twice the plan's estimate of 5 to 15 cents.
- A plan applies or runs something its card did not show.
