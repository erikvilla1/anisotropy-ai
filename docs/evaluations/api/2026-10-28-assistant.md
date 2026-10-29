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

No evidence yet. The founder's machine holds no Anthropic credential (checked 2026-10-28: `ANTHROPIC_API_KEY` unset, no `ant` profile), so
the Claude writer has not answered a real request here: UNVERIFIED. To run it: set `ANISOTROPY_ASSISTANT_PROVIDER=anthropic`,
`ANISOTROPY_ASSISTANT_MODEL=claude-opus-5-5` and `ANTHROPIC_API_KEY` in `.env`, start the API, solve a coupon in the studio and read the
explanation panel: it names the writer, and a withheld draft says which numbers the guard refused. Its run record will show the model.

## Not done here

- The setup explanation in the studio before a run (the endpoint explains a job's checklist; a check without a job has none).
- A second provider (Claude on Bedrock in a customer's account, an open-weight model); the interface is where it goes (ADR-0052).
- The model drafting inputs (ADR-0048's remaining tools).
