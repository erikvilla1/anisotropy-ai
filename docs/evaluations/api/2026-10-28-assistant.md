# The assistant: a template writer, a Claude writer behind a setting, and the number guard (2026-10-28)

Part 3 of the plan behind ADR-0051, the assistant's own record ADR-0052, on `feat/assistant`, stacked on the page of part 2. What was
built is in the record's "As built" section; this note holds the runs and their output.

## Test suites

| Suite | Command | Result |
| --- | --- | --- |
| api + engine, with the test database | `docker compose up -d && cd api && uv run pytest -q -ra tests ../engine/tests` | 623 passed in 56 s (604 before this part) |
| the assistant and the settings alone | `cd api && uv run pytest -q tests/test_assistant.py tests/test_settings.py` | 29 passed without the database, plus the one recorded test above |
| website | `npm test`; `npm run typecheck` | 97 passed (96 before); `tsc --noEmit` clean |
| the studio in the browser | `NEXT_PUBLIC_ANISOTROPY_API_URL=http://127.0.0.1:8000 npm run build && npm run test:studio` | 3 passed in 29 s; the mocked API now answers the explain call and the panel shows the writer |

## What the tests hold (`api/tests/test_assistant.py`)

- **The guard.** It reads every number on its own and not the digits of a name (`Coupon-1.1068`). `16211 N` and `1.62e+04 N` stand for the
  reaction 16211.2; `16212` does not; a computed `10.4 %` or an `18000 N` that is not in the sheet withholds the draft and the answer names
  the offending tokens; a fact rounded to fewer digits (`0.90` for 0.8961) is allowed, since it lies within half the unit of the last
  digit written; list facts (the tied plies) and the numbers inside the sheet's words (an element's label) count as facts.
- **The writers.** The template returns the fea package's sentences. The Claude writer, with a stub in place of the SDK's client, keeps a
  clean draft and names the model; is withheld on an invented number; returns the template's words with the reason on a refusal, a
  connection error (`anthropic.APIConnectionError`) and an empty answer. The request it sends: the model named in the settings, `fallbacks:
  "default"` with the `server-side-fallback-2026-07-01` beta, effort low, the fact sheet's numbers in the user message, no sampling
  parameters, no `thinking` parameter (the SDK's own types were read on 2026-10-28, `anthropic` 1.17.0).
- **What the model sees.** The material item's message loses the team's source ("the team's own constants: a datasheet of 2026" becomes
  "the team's own constants"); the setup draft is written without it.
- **The endpoint, on a stand-in job.** 409 with "no explanation yet" before our engine has run; 200 with the template once it has; the
  setup kind reads the checklist; an unknown kind is 422; the actor is required; with a stub Claude writer in the app's state the answer
  names `anthropic` and `claude-opus-5-5`, and a draft with `10.4 %` comes back withheld with the template's words.
- **No outbound request with the assistant off.** Every socket connection to a host other than this machine, and every name lookup,
  raises for the whole flow of a job and its explanation; the test passes with the template writer, which the app builds when no
  provider is named.
- **The record** (with the database): an explanation's run record holds the job, the kind and the facts' digest as inputs, the answer as
  the response, `llm_provider` and `llm_model_version` empty for the template and `anthropic` / `claude-opus-5-5` for the stub model.
- **The settings** (`api/tests/test_settings.py`): off unless the provider is named; a named provider without its model, without a
  credential, or with an unknown name refuses to start naming the variable.

## A live model

On 2026-10-28 there was no evidence: the founder's machine held no Anthropic credential, so the Claude writer had not answered a real
request. On 2026-11-06 the founder put a key in `.env` with `ANISOTROPY_ASSISTANT_PROVIDER=anthropic` and
`ANISOTROPY_ASSISTANT_MODEL=claude-opus-5-5`, the API was started from `api/` with run records on (migration 0006 applied first), and
three requests went to the model. Every one came back written by `anthropic`, model `claude-opus-5-5`, nothing withheld, no reason:

| Request | Run id | Time | What the draft did |
| --- | --- | --- | --- |
| `POST /v1/laminates/solve`, the homework problem of ADR-0060 (AS4/3501-6 typed, [0/45/-45/90]s, Nx = 100 N/mm), SI | 55e7a478-9ab1-4dc8-a962-d833a07cead0 | 12.0 s | Six sentences; every number the sheet's (Nx written as 100000.0 N/m, the SI reporting unit, not the typed N/mm) |
| The same problem reported in US units | 4f70b4dc-e21b-41ca-a5bb-6baf969fee89 | 4.1 s | Nine shorter sentences, 571 lb/in, 8.438 Msi, R = 3.207 |
| `POST /v1/coupon-jobs/{id}/explain`, kind `result`, the IM7/8552 example coupon solved by `STUDIO_LIVE=1 npm run test:studio-live` (job aee06c6d-6980-40d8-b137-35ed9a527941, passed in 1.4 min) | dc8c67a4-ee84-47cf-8533-2d63b14a632c | 8.3 s | Eight sentences; names the grip-edge element and reads both criteria as first damage at the grip |

The run record of the first call, read back with `GET /v1/runs/{id}`, carries `llm_provider = anthropic` and
`llm_model_version = claude-opus-5-5`, with the commit of `main` at 924d5ff. The coupon draft copies the fact sheet's numbers at full
precision ("16211.196890295483 N", "1.0000000000000002 mm"), because the coupon sheet prints the floats as computed and the guard
accepts a number only as the sheet writes it; the laminate sheet rounds its facts to four figures first (`printed`), and its drafts read
as an engineer would write them. Rounding the coupon sheet the same way is the next change for this writer, in the fea package, not here.

Two things the live run exposed, fixed in the same pull request: the API test session loaded the developer's `.env`, so four tests that
start the app's lifespan called the real model and failed on its words (`conftest.py` now forces the provider off and drops the
credential), and `test_an_explanation_is_recorded_with_its_writer` left a stub writer on the app that wrote every later answer of the
session (restored by `monkeypatch`). The hosted site has not had the three secrets yet: UNVERIFIED there until the founder sets them.

## Not done here

- The setup explanation in the studio before a run (the endpoint explains a job's checklist; a check without a job has none).
- A second provider (Claude on Bedrock in a customer's account, an open-weight model); the interface is where it goes (ADR-0052).
- The model drafting inputs (ADR-0048's remaining tools).
