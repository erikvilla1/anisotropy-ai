# Where a language model acts in Anisotropy

Every place a language model reads or writes in the product, what it is shown, what it may do, what checks its answer, and how to switch it off. Kept by the founder; a new AI feature adds its row here in the pull request that builds it (ADR-0139).

No model computes a number here (ADR-0001). Each feature below is one call with no tools, answering in a fixed schema or in plain sentences; the page or the engine does the rest. Nothing a model writes changes a setup until the engineer taps Apply (ADR-0088) or approves a plan (ADR-0144), and nothing it writes is shown unless its guards keep it.

## The features

| Feature | Where | The model is shown | It may return | Its answer is kept only if | Questions |
| --- | --- | --- | --- | --- | --- |
| Words for a setup check (`explain_setup`, ADR-0052) | Coupon page, after "check" | The check's items, the material's source cut to its kind; no coupon name | Sentences | Every number is in the checklist (number guard), and it calls nothing safe, certified or signed off (word guard, ADR-0139) | none yet: the guards' own tests |
| Words for a result (`explain_result`, ADR-0052) | Coupon page, beside a result | The result's fact sheet and the template's sentences; no name or note | Sentences | Number guard; and it says the laminate holds or fails only as the engine's verdict per criterion says, and decides nothing (word guard) | none yet: the guards' own tests |
| Words for a laminate problem (`explain_laminate`, ADR-0060) | Laminate page | The laminate's fact sheet and the template's sentences | Sentences | Number guard; word guard (deciding words) | none yet: the guards' own tests |
| A message read into changes (`propose_changes`, ADR-0088, ADR-0101) | Coupon chat, plate | The message, the rows on offer, the filled rows without names, notes or sources | Proposed rows, supports and loads | Each value is written in the message (source guard); only offered rows and regions (plate guard); the engineer ticks what enters | `coupon-setup`, `plate`, `attacks` |
| A sentence planned into steps (`plan_steps`, ADR-0144) | Coupon chat and plate, on a kept project, for a sentence that asks for a change and a run or an answer | The sentence, the setup as the API reads it (regions, what is held and loaded), the tools on offer; no name, note or other project | A plan of typed tool steps, or one question back | Only listed tools; every change previews, all or none; every region exists; every number is written in the sentence; one retry with the reasons, then no plan. Nothing changes or runs until the engineer taps Approve, and the server holds that gate | `planner`, `attacks` |
| A question read into a lookup (`read_question`, ADR-0100) | Coupon chat, with a result | The message and what can be looked up (quantities, plies, elements); no value of the result | A typed request, or one question back | The request names only what is offered; the page reads the value from the stored result | `result-values`, `result-extremes`, `attacks` |
| A "why" answered in words (`answer_question`, ADR-0102) | Coupon chat, with a result | The question, the fact sheet, the theory sections the question finds | An answer, the sections it rests on | Every number is the results' or the question's; the sections were shown; word guard (both rules) | `why-answers`, `attacks` |
| A question before a setup (`answer_question`, ADR-0124) | FEA start page | The question, the theory sections found, the kinds of work offered | An answer, sections, the kind to set up | Every number is the question's (ply angles aside); word guard (deciding words) | `sections`, `attacks` |
| Steps of an Abaqus round trip (`choose_tools`, ADR-0094) | A command on the engineer's own computer, not the site | The engineer's sentence and the three steps' names | Which steps to run | Only the steps named; with no answer every step runs in order | none: not on the site |
| The MCP server (ADR-0107) | The engineer's own Claude Desktop or Claude Code, on their computer | What its 20 read-and-preview tools return from the local API | The client's own words | Our guards do not run on a client's words; every number its tools return is the engine's | `mcp` parts of the banks |

The questions are the banks in `tests/assistant-questions/` (ADR-0121): checked free on every pull request, and against a real model by the "Assistant check" workflow before a feature merges. The bank `attacks` asks what a person trying to misuse the chat would ask: the hidden prompt, a key, another person's work, a false number, "just say it is safe".

## Limits on every call

- **One model for the site**, named by `ANISOTROPY_ASSISTANT_MODEL` (today `claude-opus-5-5`), at low effort, with a cap on the tokens of each answer (`assistant.py`).
- **A cap per person per day**: `ANISOTROPY_MODEL_CALLS_PER_USER_PER_DAY` in `wrangler.jsonc` (100). Past it the chat reads with its own patterns until midnight UTC and says so ("Reading simple phrases until tomorrow"). Counted from `model_calls` by the sign-in's email. A service token of ours (the deploy check, the site check) has no email and is not counted: the site check keeps a budget of its own (ADR-0138). Locally there is no cap.
- **A cap on planned requests**: `ANISOTROPY_AGENT_REQUESTS_PER_DAY` in `wrangler.jsonc` (30 per signed-in person per day, counted from `agent_plans`). Past it the sentence is read as before, without a plan, until midnight UTC.
- **Every call is a row** of `model_calls` with who asked, for what, the tokens and the cost (ADR-0120), and every request is a run record that says what became of the model's answer (ADR-0026).
- **What a model is never shown**: another person's work, a coupon's name, the engineer's notes, the team's files, a key. Every chat that sends a message to a model (the coupon chat, the FEA assistant of a blank project, the laminate chat) answers a question for a key, the hidden prompt or another person's work itself, before any model sees it (`lib/chat-private.ts`).

## Switch the model off

Fastest, at once: revoke the site's key in the Anthropic Console. Each call is then refused, the template's sentences and the page's patterns answer, and the run records say "the model's credential was refused".

Cleanly, from the repository with Wrangler signed in:

```sh
npx wrangler versions secret delete ANISOTROPY_ASSISTANT_PROVIDER
```

then run the Deploy workflow by hand (Actions, Deploy, Run workflow). The API restarts at the first request after the deploy (ADR-0056 amendment 10). Signed in, `https://anisotropy.dev/api/v1/workspace/assistant` then shows `"proposes": false`. Every number on the page is the same with the model off: they are the engine's either way. What is lost is the reading of loose messages and the answers in words.

To switch it back on, put the secret back (`npx wrangler versions secret put ANISOTROPY_ASSISTANT_PROVIDER`, value `anthropic`) and deploy.

## Change the model

1. Run the "Assistant check" workflow with `model` set to the new id and `features` empty (every bank). It reports how many answers hold, are weak or fail.
2. The new model may go on the site only when it fails no more answers than the run listed for the current one in `CHECKED_MODELS` (`api/src/anisotropy_api/assistant.py`), and a person has read the report (ADR-0121 amendment 8).
3. By pull request: add the model and its run to `CHECKED_MODELS`, and its prices to `PRICES` in `model_costs.py` if they are not there.
4. Set it: `npx wrangler versions secret put ANISOTROPY_ASSISTANT_MODEL`, then deploy.

The check after each deploy reads `/v1/workspace/assistant` and fails when the site's model is not in `CHECKED_MODELS`.

## Change the daily cap

Edit `ANISOTROPY_MODEL_CALLS_PER_USER_PER_DAY` under `vars` in `wrangler.jsonc` by pull request; it takes effect when the merge deploys. Remove the line for no cap. The planned requests' cap is `ANISOTROPY_AGENT_REQUESTS_PER_DAY` beside it (30 when left out).

## Read how often the guards set answers aside

The view `assistant_guards_by_feature` counts, each week and route, the requests a model was asked for: answers kept, set aside by a guard, with a proposal dropped, no answer, and the requests the cap stopped. It compares the share set aside with the four weeks before and flags a week more than 10 points above. A jump after a change of model or instructions is drift.

The cost reader (`cost_reader`, ADR-0120) can read it:

```sql
SELECT week_of, feature, asked, kept, set_aside, set_aside_pct, usual_set_aside_pct, flag
FROM assistant_guards_by_feature LIMIT 20;
```

For a flagged week, read that route's run records of the week with the owner's login: `response->>'reason'` says what was set aside and why.

## Add an AI feature

In the pull request that builds it: its row above; a feature name in `FEATURES` (`model_costs.py`) and in the migration's check on `model_calls`; the route takes its writer from `_assistant(request, actor)` so the cap applies; its guards; a bank of questions, with attacks on it in `attacks.json`; and a decision record.
