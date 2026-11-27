# ADR-0145: The AI's activity is read by founders on a read-only page of our own over the records the API already keeps, with the gaps in those records closed, and a customer's rows show what happened, not what they wrote

- Status: Proposed
- Date: 2026-11-27
- Decided by: Founder, 2026-11-26 ("I want to be able to oversee the agents that is being orchestrated how everything is being communicated and talked to etc. I want to be able to see teh activity on how the AI is connected to everything and how it is communiacted", on overseeing the AI); 2026-11-27 ("Ok launch multiple agents to complete this, we wan tto start deploying fast, make no mistakes.", his go to build). He has not yet read or accepted this record, and what a founder sees of a customer's words awaits his choice | Drafted by: Claude Code
- Related: [ADR-0120](ADR-0120-each-call-to-the-language-model-is-kept-as-a-row-with-who-asked-what-for-the-tokens-billed-and-their-cost-read-through-three-views.md) (a row per call, the costs' view), [ADR-0144](ADR-0144-one-planner-in-the-api-turns-an-engineers-sentence-into-a-plan-of-typed-tool-steps-the-server-checks-it-and-one-approval-applies-it-and-starts-the-run.md) (plans), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md) (run records), [ADR-0139](ADR-0139-the-models-words-may-not-decide-for-the-engineer-its-calls-are-capped-per-person-per-day-and-how-often-the-guards-set-answers-aside-is-read-each-week.md) (the guards' view), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md) (amendment 8, the checked models), [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md) (a person's work is theirs alone), [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md) (the sign-in), [ADR-0138](ADR-0138-a-robot-asks-the-question-banks-on-the-live-site-in-a-browser-as-a-customer-grades-each-answer-by-fixed-checks-then-a-small-model-and-opens-an-issue-only-when-one-fails.md) (the robot's service token), `api/src/anisotropy_api/oversight.py`, `api/alembic/versions/0018_oversight.py`, `app/ai/page.tsx`, `components/oversight/ai-activity.tsx`, `lib/oversight.ts`, `tests/fixtures/oversight/`, [the AI catalog](../ai-catalog.md)
- Area: api, website, assistant

## Context

- On 2026-11-26 the founder asked to oversee the AI (his words above). The review written for him that day (the Claude Doc "Overseeing the AI: orchestration, MCP and APIs", 2026-11-26) read the code and listed what is recorded and what is missing.
- Before this change, every call the API makes to the model left from one function, `ClaudeAssistant._ask` in `api/src/anisotropy_api/assistant.py`, and was kept as a row of `model_calls` (ADR-0120). A plan was a row of `agent_plans` (ADR-0144). A request was a run record in `runs` (ADR-0026).
- Nothing showed them together. Reading them took SQL: the costs' views (ADR-0120) and `assistant_guards_by_feature` (ADR-0139).
- Four things were not kept, or not pointed out:
  1. `planner.plan_with` gives the model one more try when its plan fails the checks. The answers the checks turned back were dropped.
  2. The words sent to the model were not kept in any form. A run record keeps the request the API received. It does not keep the instructions, the request and the answer form the API then sent to the model.
  3. A call was tied to its plan only through its run record's answer (`model_calls.run_id`, then the plan's id inside `runs.response`).
  4. `_ask` lets the provider answer a declined request with another model (`fallbacks="default"`). `model_calls.model` records the model that answered, but nothing held that model to the checked list (`CHECKED_MODELS`, ADR-0121 amendment 8, ADR-0139). The list was read only for the model the site is set to: at start, in `/v1/workspace/assistant` and by the check after a deploy.
- The code was written on 2026-11-26 and parked that day, because the founder asked to keep planning first. His go came on 2026-11-27.

## Options considered

1. **An outside tracing product, such as LangSmith.** It keeps and shows each prompt and answer. Rejected: every prompt and answer, customers' words included, would go to another company's servers unless it is self-hosted, and it is a second place to secure.
2. **OpenTelemetry's GenAI spans, sent to a tracing backend.** Rejected as the record: the conventions for agent spans are still marked Development, and a backend is a new service to run. Kept as a later export, not the record: a plan maps to an agent run, a `model_calls` row to a model call, a typed step to a tool run.
3. **A hosted agent platform's session viewer.** Rejected: we run no hosted agent loop today. The product has one planner, in our API: one call to the model, one more at most, and then the server carries the steps (ADR-0144).
4. **Our own read-only page over the records we already keep, with the gaps in those records closed.** Chosen. No new service, no customer's words leave our database, and the records exist.

Inside option 4, what a founder sees of a customer's words:

- **(a) Hidden.** A customer's rows show what happened, not what they wrote. The proposed default, after ADR-0104. The founder has not yet confirmed it.
- **(b) Visible to a founder who gives a reason, the reason logged.** Not built. Open for him.

What options 1 and 2 say about LangSmith and OpenTelemetry comes from the review. Their own pages were not read again while this record was written: UNVERIFIED here, no source linked yet.

## Decision

Option 4, with (a) as the default until the founder chooses.

- **Who may read.** The three routes answer a signed-in founder only: an email that Cloudflare Access verified and that is in `ANISOTROPY_FOUNDER_EMAILS`. Anyone else, a customer or a service token, is answered 404 as if there were no such page, and nothing is read or kept. On a machine with no sign-in in front of the API, its one user reads (`main._overseer`).
- **Read only.** `oversight.py` writes nothing and calls no model. The page has no control: nothing can be paused, changed or approved from it.
- **Each view is kept.** A read of the feed, of a plan or of the weeks is a run record (ADR-0026) under `/v1/oversight/activity`, `/v1/oversight/plans/{plan_id}` or `/v1/oversight/weekly`, with who looked and how much they were shown. The exception is the page's refresh, every 10 seconds, which asks with `since`: it is written to the log and not kept.
- **The feed**, `GET /v1/oversight/activity`: each call to the model, each plan and each approval, newest first. It gives 50 events unless `limit` says otherwise, and 200 at most. `before` pages back. Each event says who it was for, what for, the model that answered, whether that model was checked, how it ended, the seconds and the cost. A call ended as `declined` or `cut short` by the model; else, for a plan's call, in the plan's state; else `set aside`, `partly dropped`, `kept` or `not used`, read from its run record's answer.
- **One plan's story**, `GET /v1/oversight/plans/{plan_id}`: the sentence, each answer the checks turned back with the reasons, each call, the approval, the version it made, each step as the page reported it, and the job.
- **The weeks**, `GET /v1/oversight/weekly`: the last eight weeks. The guards' view (ADR-0139) and the costs' view (ADR-0120) per feature, the plans of each week by kind and state, the ten commonest reasons plans were refused, and the calls answered by a model outside the checked list.
- **The gaps in the records, closed** (migration 0018; the new columns are empty on the rows made before):
  - `agent_plans.attempts`: each answer of the model the checks turned back, with the reasons.
  - `model_calls.sent_sha256`: a fingerprint of the words sent, the SHA-256 of the instructions, the request and the answer form. The words themselves are not kept. Two calls with one fingerprint were sent the same words. The plan's story gives its first 12 characters.
  - `model_calls.checked`: whether the model that answered was in `CHECKED_MODELS` when the call was made. True or false from this change on, empty on earlier rows. A later change to the list does not change a row.
  - `model_calls.plan_id`: the plan the call was made for. It is emptied if the plan is deleted.
- **A customer's words (the default, awaiting the founder's confirmation).** On a row of anyone who is not a founder, the person is named by a tag: "customer" and six characters from a hash of the email. The sentence reads "a customer's words, not shown". A step shows its number, role, tool and state, without its line or note. Left out: each answer turned back (its reasons stay), the question asked back, the version's reason and change lines (their count stays), and the job's stage and message. Words a reason quotes are replaced by "…". A founder's rows, a robot's (a service token, which has no email) and those of a machine with no sign-in are shown in full.
- **The page**, `/ai`: "Now" (the feed, with a plan's story beside it when a row is picked) and "Weekly". No menu links to it, and it asks search engines not to index it. Anyone the API answers 404 sees "Page not found".
- **Not built**: tabs for connections and agents, alerts, and controls (pause the planner, pause model calls, a limit per person). The review lists them as later steps.

## As built (2026-11-27)

- **API.** `api/src/anisotropy_api/oversight.py` holds the three readings (`activity`, `plan_story`, `weekly`), who a row is for (`who`, `tag_of`), the quoted words taken out (`unquoted`) and how a call ended (`call_outcome`). The routes, `_overseer` and `_seen` are in `main.py`. `model_costs.sent_fingerprint` makes the fingerprint and `ClaudeAssistant._ask` sets it on the call. `planner.plan_with` keeps what was turned back in `Planned.tried`. `records.py` holds the new columns and `record_model_calls` writes them. Migration `api/alembic/versions/0018_oversight.py` adds the four columns and the index `model_calls_plan`.
- **Page.** `app/ai/page.tsx`, `app/ai/ai.css`, `components/oversight/ai-activity.tsx` and `lib/oversight.ts`.
- **Tests and contract.** `api/tests/test_oversight.py`, new tests in `api/tests/test_planner.py` and `api/tests/test_model_costs.py`, `tests/oversight.test.ts`, and the examples the two sides share in `tests/fixtures/oversight/` (`activity.json`, `plan-story.json`, `weekly.json`).
- **Differences from the review's plan, and limits found while this record was written.**
  - The review planned a plan's id on run records too. It is on `model_calls` only.
  - Only the calls that plan are tied to a plan. The call that words a plan's answer goes through an answer route, which carries no plan (for a coupon, `/v1/workspace/result-answers`), and is not in the plan's story.
  - The page does not print the fingerprint. The plan route answers it.
  - While the feed is empty, the page's refresh has no `since`, so each refresh, every 10 seconds, is kept as a run record.
  - Only words between curly quotes are taken out of a reason. A reason that restates a number and its unit from the sentence, or that is the model's own words about the request (ADR-0144 amendment 1), is shown as it is on a customer's row.
  - The feed sorts `agent_plans` by `created_at` and by `approved_at`. No index leads with either: migration 0017's indexes lead with the project and with the email.
  - Not deployed. Migration 0018 has not run on the hosted database.

## Why (evidence)

All run on 2026-11-27 on f72093c, whose files are those of 4a875a5, in a cloud container against PostgreSQL 16.15. The model is a scripted stand-in in every test.

- `cd api && TEST_DATABASE_URL=… uv run pytest tests/test_oversight.py -q`: `15 passed in 9.43s`. A customer, a service token and an email that only starts like a founder's are answered 404 on all three routes and no view is kept; a founder reads. On a customer's plan the feed and the story hold neither the sentence nor the email. A story shows the answer turned back, two calls with a 12-character fingerprint, and no version or job before approval. The week lists a refused plan, its reason and one call by a model outside the checked list. A read with `since` is not kept; every other view is. On a machine with no sign-in its one user reads.
- `cd api && TEST_DATABASE_URL=… uv run pytest -q tests/test_planner.py tests/test_planner_attacks.py tests/test_model_costs.py tests/test_assistant_guards.py`: `143 passed in 9.46s`. Among them: each answer turned back is kept with its reasons, whether the retry passed, failed or got no answer; a plan's two calls name the plan, are marked checked and carry different fingerprints; a call by a stand-in model is marked not checked; the same words give the same fingerprint and the words are not on the call.
- `npx tsx --test tests/oversight.test.ts`: `# tests 5`, `# pass 5`, `# fail 0`. A call by a model outside the checked list reads as bad whatever its outcome; a refresh puts newer events on top, each once; a plan's story reads in the order it happened; a customer's story shows its steps by tool.
- `npx tsc --noEmit`: no output, exit 0. `cd api && uv run ruff check src tests`: `All checks passed!`.
- No evidence yet for: the page in a browser with real records, a real model's calls on it, the hosted site (whether it serves `/ai` and passes the sign-in to the routes is UNVERIFIED), how long the reads take on the hosted database, and a founder's use of it.

## Consequences

- Easier: a founder reads what the AI did, for whom, with which model and at what cost, without SQL. A plan's first answer and why the checks turned it back can be read later. A call answered by a model that was never checked stands out. A change of instructions shows as a new fingerprint.
- Harder: three more routes and a page to keep to the contract in `tests/fixtures/oversight/`. Every view but the refresh writes a run record. `agent_plans` rows grow by the answers turned back.
- We now depend on `ANISOTROPY_FOUNDER_EMAILS` for who may read: a wrong entry opens the page to that sign-in.
- A fingerprint says that two calls were sent the same words, not what the words were. To read the words, they must be built again from the code and the request of that day.
- The tag is the start of the SHA-256 of the email with nothing added, so anyone who knows an email can work out its tag.
- A founder cannot open a customer's sentence from the page, even to help that customer, until option (b) is decided.

## How we will know it was wrong

- A founder cannot answer "which model answered this plan, and was it checked" from the page alone.
- A customer's words, email or setup appear on the page or in an answer of the three routes.
- A founder needs a customer's sentence to settle a problem more than once a month: the default (a) is too strict.
- The page's reads slow the API: a read of the feed takes more than a second on the hosted database, or requests of the workspace slow while the page is open.
- Someone who is not a founder is answered anything but 404.
- We come to run more than one agent, or a hosted agent loop: revisit options 2 and 3.
