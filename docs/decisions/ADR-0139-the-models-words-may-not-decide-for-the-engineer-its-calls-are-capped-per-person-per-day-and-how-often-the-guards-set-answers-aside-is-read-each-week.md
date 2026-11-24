# ADR-0139: The model's words may not decide for the engineer, its calls are capped per person per day, and how often the guards set answers aside is read each week

- Status: Proposed
- Date: 2026-11-24
- Decided by: Founder, 2026-11-24 ("Build steps 1 to 6 in one PR", on the card "Start building the safety steps from the agent review?") | Drafted by: Claude Code
- Related: [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md), [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md), [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md), [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md), [ADR-0120](ADR-0120-each-call-to-the-language-model-is-kept-as-a-row-with-who-asked-what-for-the-tokens-billed-and-their-cost-read-through-three-views.md), [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md) (amendment 8), [ADR-0128](ADR-0128-a-wings-chat-reads-a-change-of-plies-into-the-engines-form-and-previews-it-on-a-copy-answers-from-the-wings-report-and-the-reference-pages-and-the-wing-changes-only-on-the-engineers-apply.md), [ADR-0138](ADR-0138-a-robot-asks-the-question-banks-on-the-live-site-in-a-browser-as-a-customer-grades-each-answer-by-fixed-checks-then-a-small-model-and-opens-an-issue-only-when-one-fails.md), `api/src/anisotropy_api/verdict_guard.py`, `api/alembic/versions/0015_assistant_guards.py`, [the AI catalog](../ai-catalog.md)
- Area: assistant, api, hosting, process

## Context

On 2026-11-24 the founder read IBM and Anthropic's guide "Architecting secure enterprise AI agents with MCP" (October 2025) and asked where our software relies on it and how to build towards reliable AI. The review (the Claude Doc "Agents, MCP and reliable AI in Anisotropy", 2026-11-24) mapped the guide's 18 controls to the code: 9 strong, 6 partial, 3 gaps. The product's model is "on rails": one call with no tools, a fixed schema or plain sentences, guards on what it writes, and the engineer's tap before anything changes. Six things were missing:

1. No bank of questions that try to misuse the chat: the hidden prompt, a key, another person's work, a false number, "just say it is safe". The bank `off-topic-and-safety` held two such questions.
2. Nothing capped one person's calls to the model. Jobs had a daily cap (ADR-0056); a model call had none, so one person, or one stolen sign-in, could spend without limit until the provider's spend limit stopped everyone.
3. The number guard (ADR-0052) reads numbers, not words. An answer could say "the laminate holds" beside the engine's "fails" with no wrong number in it, or call a design safe, which no analysis here decides. The chat itself answered "is it safe?" with "Yes, the coupon holds" (ADR-0099 amendment 4), and the wing's chat answered "is the wing safe to fly" with "Yes: passes the 34 cases run".
4. Nobody read how often the guards set answers aside. A model or instruction change that made the model drift would show there first.
5. No single list said where a model acts, what it is shown, what checks it, and how to switch it off.
6. No rule said what must happen before the site's model changes.

## Options considered

1. **Words that decide or contradict.** (a) A second model judges every answer: a second cost and delay per answer, and another model to trust. (b) The instructions alone: a model may still write it. (c) Fixed patterns, sentence by sentence and clause by clause, held to the fact sheet's verdict per criterion (`<criterion>_fails`), deliberately narrow so a good answer is not set aside for its wording; with the instructions as a first line. Chosen: (c).
2. **The cap.** (a) The provider's spend limit only: one limit for the whole site, which stops everyone at once; kept as the backstop. (b) A count per signed-in person per day from `model_calls` (ADR-0120), past which the page reads with its own patterns until midnight UTC and says so. Chosen. (c) A rate per minute: needs a store of its own; not now. The number goes in `wrangler.jsonc` as a versioned variable, reviewed like code, not as a secret. A request with no email is a service token of ours (the deploy check, the site check of ADR-0138, which keeps a budget of its own) and is not counted.
3. **The bank.** A new bank, `attacks`, with what a person trying to misuse the chat would ask on every page. Where the page fell short, fix it in the page's fixed words, before any model sees the message, rather than mark a gap: a key or a password, another person's work, and a question of safety.
4. **The rate of answers set aside.** (a) A new table written on each answer. (b) A view over the run records, which already say what became of each answer. Chosen: (b), with a flag at 10 points above the four weeks before, readable by the cost reader so the monthly report can show it.
5. **The list.** One page, `docs/ai-catalog.md`, with each feature's row, the kill switch, how to change the model or the cap, and how to read the view.
6. **The model-change rule.** (a) The API refuses to start with a model not checked: a typo would take the site down. (b) The model goes on the site only after a real-model run with it, recorded by pull request in a list the API reads; the API says whether its model is listed, and the check after each deploy fails when it is not. Chosen: (b), written as ADR-0121 amendment 8.

## Decision

1. **The word guard** (`api/src/anisotropy_api/verdict_guard.py`) sets the whole answer aside, and the template or the sections found stand, when it calls something safe, unsafe, airworthy, certified, strong enough, good to go or signed off; or says the laminate or coupon holds while the engine says a criterion fails at the applied loading, or fails while every criterion holds. A clause naming a criterion is held to that criterion; one naming none to all of them. A supposition ("would", "if") or a failure placed at a multiple of the loading states no verdict and stands. It runs after the number guard in the explanations (`assistant.py`), the why answers (`result_answers.py`) and the questions before a setup (`general_answers.py`, deciding words only). The instructions say the same: never call a design safe, and state a verdict only as the fact sheet does.
2. **The cap**: `ANISOTROPY_MODEL_CALLS_PER_USER_PER_DAY` (100 on the site, in `wrangler.jsonc`; none locally). `_assistant(request, actor)` in `main.py` counts the signed-in email's rows in `model_calls` since midnight UTC (`records.model_calls_since`) and past the cap hands the route `LimitedAssistant`, which calls nothing and gives the reason `DAILY_LIMIT_REASON`. The page shows "Reading simple phrases until tomorrow" for it. Every route that calls the model takes its writer from `_assistant`.
3. **The bank** `tests/assistant-questions/attacks.json`: 26 questions on the results, setup, blank, past, imported, wing, repair and start pages, with two gaps marked. The page answers a key, a password or the hidden prompt with "Not something I share", and another person's work with "Only your own work" (`lib/chat-about.ts`). A question of safety, airworthiness or sign-off is answered with the verdict at the applied load and no Yes, and a line that the decision is the engineer's: on the coupon (`DECIDES`, `decidesNote` in `lib/result-failure.ts`) and on the wing (`DECIDES` in `lib/wing-chat.ts`).
4. **The view** `assistant_guards_by_feature` (migration 0015): each week and route, the requests a model was asked for, kept, set aside, with a proposal dropped, no answer and capped; the share set aside against the four weeks before; granted to `cost_reader` where that role exists, and by `scripts/create-cost-reader.py`.
5. **The catalog** `docs/ai-catalog.md`.
6. **The model-change rule** (ADR-0121 amendment 8): `CHECKED_MODELS` in `assistant.py`, `checked` in `/v1/workspace/assistant`, a `model` input on the "Assistant check" workflow, and `scripts/check-hosted.py` failing on a model not listed.

## Why (evidence)

- The word guard: `cd api && uv run pytest -q tests/test_verdict_guard.py` 33 passed (2026-11-24): the template's own sentences of the public example pass; 14 answers that keep to the verdict stand, among them "holds by maximum stress but fails by Tsai-Hill" where Tsai-Hill fails, a supposition, and "fails at 1.032 times the applied loading"; six against the verdict and seven deciding words are set aside, with or without a result.
- The cap and the view: `cd api && TEST_DATABASE_URL=... uv run pytest -q tests/test_assistant_guards.py tests/test_cost_reader.py` (PostgreSQL 16, 2026-11-24): past a cap of two the third request asks nothing, carries the reason and is counted capped; a colleague is not capped; a service token is not counted; the view counts a week of one kept, two set aside, one with no answer and one capped as 4 asked, 50 % set aside against 0 % and flags it; the cost reader reads it. The first version of the view dropped every kept answer from the count (a NULL in `capped`); this test found it.
- The bank: `npx tsx --test tests/assistant-questions.test.ts` passes for every bank, `attacks` included (2026-11-24).
- The real model on the bank: UNVERIFIED until the "Assistant check" runs on this pull request.

## Consequences

- Easier: a misuse question has a fixed answer the founder can read in the bank; a run of the model is bounded per person; a drift shows in one view; a model change has a rule and a check.
- Harder: the instructions of the explanations, the why answers and the questions before a setup changed, so the stored answers of the real-model check for those are asked again once. A good answer that uses a deciding word ("it is unsafe to ignore the grip") is set aside and the template stands. A person who reaches 100 calls in a day gets the page's patterns until midnight UTC.
- Still open: the MCP client's own words are not guarded (ADR-0107); a laminate problem's answer is held to the deciding words only, since its fact sheet carries no verdict per criterion; two gaps of the bank (a stated first-ply-failure load read as a new force, and "holds" not read without a model).

## How we will know it was wrong

- The view shows more than 10 % of explanations or why answers set aside two weeks running after a change: the word guard is too broad.
- A run record shows a kept answer that calls the design safe or states a verdict against the engine's: too narrow.
- More than one signed-in person a week reaches the cap: 100 is too low.
