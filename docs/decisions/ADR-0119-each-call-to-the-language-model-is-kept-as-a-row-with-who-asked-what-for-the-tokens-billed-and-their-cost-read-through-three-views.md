# ADR-0119: Each call to the language model is kept as a row with who asked, what for, the tokens billed and their cost, read through three views

- Status: Proposed
- Date: 2026-11-19
- Decided by: Founder, 2026-11-19 ("so essentially the table will have what we are getting billed for then, so we will have a history of the billing and can physically see the acutal cost on what is running in our software using the api key"; then "ok let's do it, this sounds goo dfo rus to monitor costs over tiem as well and what users are using up the costs, create the table make it opimale and easy to udnerstand for someone to read and see who it is what is is etc", choosing to record who asked as well as what for. The columns, the views, the 30% flag, pricing at the time of the call and the report command are the drafter's) | Drafted by: Claude Code
- Related: `api/src/anisotropy_api/model_costs.py`, `api/src/anisotropy_api/assistant.py` (`ClaudeAssistant._ask`), `api/src/anisotropy_api/main.py` (`_deliver`, `_record_calls`), `api/src/anisotropy_api/records.py` (`ModelCallRow`, `record_model_calls`), `api/alembic/versions/0013_model_calls.py`, `api/src/anisotropy_api/cost_report.py`, `api/tests/test_model_costs.py`, [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md) (the assistant and its one provider interface), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md) (the run records), [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md) (records by signed-in email)
- Area: api, assistant, hosting

## Context

- Every call the assistant makes goes through `ClaudeAssistant._ask` (ADR-0052): the hosted site names `claude-opus-5-5`, effort `low`, and a cap of 1,000 to 8,000 output tokens per call. Its response carries a `usage` block: input tokens, output tokens, prompt cache reads and writes, `output_tokens_details.thinking_tokens` (the part of the output that was hidden thinking) and, when a refusal was followed by a fallback model, `iterations` with one entry per attempt (`anthropic` 1.17.0, `types/beta/beta_usage.py`). `_ask` read the text and dropped the rest.
- The model's thinking is billed as output tokens whatever is shown of it; the API returns a summary or nothing. The run records (ADR-0026) name the model that wrote an answer, not what it cost.
- On 2026-11-19 the founder read a paper on auditing hidden reasoning tokens (arXiv 2508.00912) and asked how auditing would look in our workflow. It was put to him that the counts are the provider's own and cannot prove the hidden count true, but that a history per call shows what we are billed, by whom and for what, and when that changes. He chose to build it, with who asked.
- Prices per million tokens, from https://platform.claude.com/docs/en/about-claude/pricing.md read on 2026-11-19: Claude Opus 5.5 4 USD input, 5 and 8 for cache writes kept 5 minutes and 1 hour, 0.20 cache read, 20 output; the other current models in `model_costs.PRICES`. Claude Haiku 5.5 pays more above 100,000 prompt tokens; US-only inference is 1.1 times every price; fast mode is priced apart.
- With a fallback, the top-level `usage` covers only the attempt that answered; `iterations` is the per-attempt record, each at its own model's rates. A refusal before any output is billed in some categories only (https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback, "How refusals are billed").

## Options considered

1. **Read the provider's usage page and nothing more.** Rejected: it splits by key, model and day, never by person, feature or run.
2. **A log line per call.** Rejected: the container's log is not kept or summed, and a person's month cannot be asked of it.
3. **Columns on `runs`.** Rejected: a run is the receipt of a request and is never edited (ADR-0026), and the clearing of trial runs (ADR-0026 amendment 2, proposed) would take the cost history with it.
4. **Pull the provider's usage and cost API on a schedule.** Rejected for now: it needs an admin key and still knows nothing of our people or features. It stays the way to automate the monthly match.
5. **One row per call in a table of its own, read through views.** Chosen.

Within it:

- **Price at the time of the call, with the date of the list** (chosen), over pricing at read time: a later change of price does not rewrite last month. A model not on the list is left unpriced and counted, so the list is brought up to date.
- **Every token the API reports is priced** (chosen), over modelling which refusals are billed: the cost can only be above the bill, by a refusal's input tokens, and the monthly match shows it.
- **A row that cannot be written is named in the log and the answer still goes back** (chosen), over withholding it as a run is withheld: the call was made and paid for, and the provider's usage page holds it.

## Decision

- **Measured where it is made.** `_ask` times the call and turns the response's `usage` into a `ModelCall` (`model_costs.measure`): the feature, the model that answered, the effort, the input and output tokens (every attempt summed), the thinking tokens, the cache reads and writes, the length of the answer received, how it ended, the seconds, and the cost at the list of `PRICES_AS_OF`. A call is measured whatever became of its answer (kept, set aside by a guard, refused, cut short); one that never answered (no network, a rate limit) has nothing to bill and leaves none.
- **Written with who asked.** Each route that asks the assistant passes its calls to `_deliver`, which writes them after the run with the signed-in email Cloudflare Access verified (empty for none), the client (`studio`, `browser`, `assistant` for the MCP server ...) and the run's id, however the request ends. No route returns them: what a call cost is ours to read.
- **The table** `model_calls` (migration 0013): `called_at`, `user_email`, `actor`, `feature`, `model`, `effort`, `input_tokens`, `output_tokens`, `thinking_tokens`, `cache_read_tokens`, `cache_write_tokens`, `answer_characters`, `stop_reason`, `seconds`, `cost_usd`, `prices_as_of`, `run_id`, `attempts`, each with a comment in the database. The features are a fixed list: `explain_setup`, `explain_result`, `explain_laminate`, `propose_changes`, `read_question`, `answer_question`, `choose_tools`. Rows are only added; a cleared run empties the link and keeps the row. The downgrade refuses over a row.
- **Three views, in UTC as the provider's usage and invoices are.** `model_costs_by_person`: each month and person, the calls, what they were for, the tokens and the cost. `model_costs_by_feature`: each week and feature, the share of the output that was hidden thinking and the cost per call, beside the average of the four weeks with calls before, and `flag` says "look" when either is more than 30% above. `model_costs_by_day`: each day and model, the counts and cost to set beside the provider's usage page.
- **The report.** `uv run --project api python -m anisotropy_api.cost_report [--month YYYY-MM] [--weeks N]` prints the three for a month from the database the migrations use, and says how many weeks are flagged. Once a month its total by model is set beside the provider's usage page for the key.
- **Not recorded:** the Abaqus round trip's `choose_tools`, a command on the engineer's own machine with no database; a local API with recording off.

## As built (2026-11-19)

- `api/src/anisotropy_api/model_costs.py` (`FEATURES`, `PRICES`, `measure`, `price`), `api/src/anisotropy_api/cost_report.py`, `api/alembic/versions/0013_model_calls.py`; `Draft` and `Reading` carry `call`; `main._billed` collects a writer's call in the five routes that ask the assistant (explain, laminate, proposals, result questions, result answers).
- `api/README.md`, "What the model costs", says how to read the table.

## Why (evidence)

- `cd api && TEST_DATABASE_URL=... uv run pytest -q tests/test_model_costs.py`: 14 passed on 2026-11-19 against PostgreSQL 16 in a cloud container. They price a call by hand-worked numbers (3,000 input and 900 output tokens of Claude Opus 5.5 are 0.030000 USD), cache writes by how long they are kept, a refusal followed by a fallback at each model's prices, Haiku's long prompts, US-only inference, fast mode and an unlisted model left unpriced; check that every writer carries its call when its answer is kept, set aside, refused or cut short; write a call through `/v1/laminates/solve` behind Access with the email, the client and the run; add up the views over five weeks and flag a 0.05 USD call against 0.03 USD weeks; and leave a call with its link empty when its run is cleared.
- How the hosted site's counts compare with the provider's usage page: no evidence yet. The first rows come with the deploy that runs migration 0013.

## Consequences

- The cost of the model can be read per person, per feature and per day, from the same database as the runs, and a run's cost found from its id.
- The price list is ours to keep: when a price changes or another model is named, `PRICES` and `PRICES_AS_OF` change in a pull request. The report counts unpriced calls until then.
- A new feature of the assistant is a migration (the table's check), as a new actor is.
- The rows hold the signed-in email as the runs do (ADR-0104). No route serves them; they are read in the database or by the report.
- It depends on the `usage` block of the `anthropic` SDK 1.x; an upgrade to 2.x is checked against `test_model_costs.py`.

## How we will know it was wrong

- A month's total by model differs from the provider's usage page for the key by more than 5%: either the key is used somewhere we do not record, or the pricing here is wrong.
- A week is flagged and no change of model, effort or prompt explains it: that is what this was built to show, and it is taken up with the provider.
- Nobody reads the views or the report in three months: the table is then a cost without a use.
