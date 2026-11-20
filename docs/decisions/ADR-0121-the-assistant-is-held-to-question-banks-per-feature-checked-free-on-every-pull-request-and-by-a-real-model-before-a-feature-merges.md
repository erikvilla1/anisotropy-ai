# ADR-0121: The assistant is held to question banks per feature, checked free on every pull request and by a real model before a feature merges

- Status: Proposed; a run can send everything at once at full price, and the MCP conversations go on at the same time, since amendment 1
- Date: 2026-11-20
- Decided by: Founder, 2026-11-19 ("a quality check for our mcp whenever we are adding to the software essentially whenever we add new features our ai assistant needs to be optimized for many case scenario a user will ask the ai chat", on the check; "Before each feature merge", on where the real-model check runs, chosen on a card; "how to make it cheaper for those runs", on its cost) | Drafted by: Claude Code
- Related: [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md), [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md), [ADR-0101](ADR-0101-on-a-plate-the-model-proposes-supports-and-loads-from-the-engineers-words-and-the-element-clicked-and-a-guard-keeps-what-the-words-or-the-click-hold.md), [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md), [ADR-0107](ADR-0107-an-mcp-client-reaches-anisotropy-through-a-local-server-over-stdio-that-calls-the-api-it-solves-a-preview-and-starts-no-full-run-and-the-clients-model-writes-the-words.md), [ADR-0114](ADR-0114-ci-lints-the-python-runs-every-browser-spec-in-three-engines-and-on-a-phone-pins-its-actions-and-checks-the-site-after-each-deploy.md); `tests/assistant-questions/`, `lib/chat-route.ts`, `scripts/assistant-live.py`, `docs/agents/skills/chat-answer-quality/SKILL.md`
- Area: assistant, process, website, api

## Context

A question typed in the workspace chat is answered by one of three kinds of reader: the page's own patterns (ADR-0099, ADR-0110), a model behind the API that reads it into proposals, a typed question of the results or an answer in words (ADR-0088, ADR-0100, ADR-0101, ADR-0102), or, from an MCP client, the client's model with our tools (ADR-0107). Each reader had its own tests, but nothing asked the questions a user types, in the many ways they type them, across the readers together. On 2026-11-17 four of ten questions the founder asked on the hosted site got a poor answer though every number was right (the `chat-answer-quality` skill). The chat chose its reader inside the component's `send()`, so the choice could be tried only in a browser.

## Options considered

1. **A browser test per question.** Tries the real component, but a few hundred questions at seconds each would slow every pull request, and a browser test cannot reach a real model. Rejected.
2. **A review on the hosted site after each feature** (the skill's procedure). Sees the real thing, but needs the founder's time and his key, one page state at a time, and is not repeated. Kept for live reviews, not as the check.
3. **A real model on every pull request.** Catches what only a model gets wrong, but costs on every push, its answers vary from run to run, so a check would fail at random, and a pull request from a fork gets no secret. Rejected; the founder chose a run before each feature merges.
4. **Question banks as data, three checks.** The questions and what a good answer holds are written once per feature; free checks hold the page, the API and the MCP server to them on every pull request; a real-model run reads the rest before a feature merges; and a pull request that changes the assistant brings its questions. Chosen.

For the real-model run's place the founder was offered every pull request, weekly and before merges, before each feature merge, and only on his PC; he chose before each feature merge. For its cost, running every question at full price each time was set against storing answers and the levers below.

## Decision

1. **Banks.** One JSON file per feature in `tests/assistant-questions/`, its fields described in `harness.ts`. A question holds its words, its kind (value, which, yes-no, what-is, why, change, command, off-topic), how it is typed (plain, typo, fragment, loose, jargon, units, terse), the page it is asked on, who answers it with a model and without, and what the answer holds (`answer`), the theory sections a why question finds (`sections`), the MCP tool that answers it (`mcp`) and what a model should make of it (`live`). Each bank asks ten questions or more, of two kinds or more, in three styles or more, one with a typo. A bank names the files it watches. A bank written before its feature (`waiting`) holds the questions the feature must answer; the wing's waits for draft PR #244.
2. **Known gaps fail when they close.** A question whose answer is known to be poor carries `gap`, with the criterion it fails. Its check expects the fault, and fails once the fault is gone, so the mark comes off with the fix.
3. **The chat's choice of reader is a function**, `routeMessage` in `lib/chat-route.ts`, which the component calls and the banks call.
4. **Check 1, on every pull request, free, in the jobs that exist.** `tests/assistant-questions.test.ts` routes each question with a model and without and holds the page's answer to its bank and to the rules every answer keeps (a question never changes the setup, no name of a tool, vendor or model, a heading of 60 characters at most); every way the chat answers is taken by some question. `api/tests/test_assistant_questions.py` holds each why question to the theory sections a model is shown, and maps every `/v1/workspace/` route to the questions that reach it. `mcp-server/tests/test_questions.py` puts each MCP question to its tool and asks every tool about.
5. **Check 3, on every pull request.** `scripts/assistant-questions-check.mjs` (workflow "Assistant questions") fails a pull request that changes a file of the assistant or one a bank watches and changes no bank, unless its description has a line "Assistant questions: none needed" with the reason.
6. **Check 2, a real model, by hand before a feature merges.** The workflow "Assistant check" runs `scripts/assistant-live.py`: each question a model reads is sent as the page sends it (`requests.ts`) to the API's own readers in process, with their instructions and guards, on `claude-opus-5-5`, the site's model; the page's answer is drawn from what they return (`shown.ts`) and held to `live`; `claude-haiku-5-5` grades, against the skill's eleven criteria, each answer a bank describes in words and each answer of why; `scripts/assistant-live-mcp.py` puts each MCP question to `claude-sonnet-5-5`, standing in for an engineer's own assistant, with the server's tools and instructions, the server answering in process from the stored results. The report goes on the run's page, feature by feature, with what changed since the last run, and the run fails when an answer that held now fails. The agent that built a feature starts the run before it calls the pull request ready, within the budget.
7. **What keeps check 2 cheap.** An answer is kept under the exact request (model, instructions, schema, words), between runs as the run's artifact, so a run pays only for what changed; the rest go in one batch at half price, with the instructions marked for the prompt cache; the judge is the small model; a run stops before it would pass its budget (3 dollars unless given), and `--dry-run` says what a run would send. A batch carries no fallback to another model on a decline, which the site's requests carry.

## As built (2026-11-20)

- 14 banks, 13 live and the wing's waiting, 217 questions, 45 of them marked as known gaps: `tests/assistant-questions/*.json`.
- The routing: `lib/chat-route.ts`; `components/studio/coupon-chat.tsx` calls it and keeps its handlers.
- Check 1: `tests/assistant-questions.test.ts`, `api/tests/test_assistant_questions.py`, `mcp-server/tests/test_questions.py`, run by the `website`, `api` and `mcp` jobs of `.github/workflows/tests.yml`.
- Check 3: `scripts/assistant-questions-check.mjs`, `.github/workflows/assistant-questions.yml`, which runs again when a description is edited.
- Check 2: `scripts/assistant-live.py`, `scripts/assistant-live-mcp.py`, `scripts/assistant_live_common.py`, `tests/assistant-questions/requests.ts` and `shown.ts`, `.github/workflows/assistant-live.yml`; it needs the repository secret `ANTHROPIC_API_KEY_QUESTION_CHECKER` (or `ANTHROPIC_API_KEY`), which the founder sets: a key of its own, in a Console workspace with its own spend limit (set 2026-11-19).

## Why (evidence)

- The checks pass on the branch, with the gaps held: `npx tsx --test tests/assistant-questions.test.ts` 17 of 17; `cd api && uv run pytest tests/test_assistant_questions.py` 16 passed; `cd mcp-server && uv run pytest tests/test_questions.py` 15 passed.
- The routing moved without a change in behaviour: the studio's browser suite, 56 of 56, after the move.
- The banks found what the existing tests did not, among the 45 gaps: a typo of "stress" is not read with no model; "which ply fails first by max stress" gets a table of stresses; "how did you get 16740 N" sets a load of 16740 N; "what is ASTM D3039" changes the setup; a yes-or-no question about a result does not open with Yes or No; "can I use inches?" switches the units.
- The real-model run was run end to end against a stand-in for the Messages and Batches API on this machine, with no model and no cost: four features, 81 requests the first time, none the second (all from the store), an answer made to fail after holding failed the run, and a budget of 5 cents stopped it before anything was sent.
- `--dry-run` on all banks: 99 questions for the API's readers and 14 for an MCP client; the readers' first requests about 1.43 dollars on the high side at batch prices. Prices from the claude-api reference (2026-11-19).
- UNVERIFIED: no run against the real model yet (the secret is not set); what a full run and a feature's run cost is not measured.

## Consequences

- A feature that changes the assistant lands with the questions a user would ask of it, and a known poor answer is listed until it is fixed.
- A pull request that changes the assistant writes questions, or a line saying why none are needed.
- The banks' harness draws the page's answers with the page's own functions, but it repeats how the component puts them together; a change to the component can leave it behind. The browser suite still tries the component.
- Check 2 depends on a repository secret, the Batches API and the stored results in `tests/fixtures/`.

## How we will know it was wrong

- A question asked on the hosted site gets an answer its bank holds as good: the harness has drifted from the page.
- A feature's run of check 2 costs more than 5 dollars, or its verdicts change on answers that did not.
- Most pull requests that change the assistant say "none needed": the rule is noise. Look again after ten such pull requests.

## Amendment 1, 2026-11-20 (a fast switch; requests and conversations sent at the same time)

**Context.** The founder asked, while the first real run waited on its batch: "is it not possible to deploy multiple agents at the same time ... instead of just one by one" (2026-11-19, 5:52 PM PT). The readers' questions already went in one batch, answered side by side, but a batch is answered when the provider has room (most within minutes, at most 24 hours), and two parts went one at a time: the full-price path (`--now`) and the fourteen MCP conversations.

**Options.** (1) Keep the batch alone: the report waits on the batch queue. Rejected. (2) Always send at once at full price: about twice the cost of every first run. Rejected as the default. (3) An agent with a browser per question: no browser is needed, the banks' harness calls the chat's own functions, and the browser suites already run in parallel. Rejected. (4) The batch stays the default; a "fast" input on the Run button (`--now`) sends every request at once at full price, eight at a time; the MCP conversations always go on eight at a time, each conversation's turns still in order; requests sent together reserve their estimate first, so together they cannot pass the budget. Chosen.

**Decision.** Option 4: `AT_ONCE = 8` in `scripts/assistant_live_common.py`, `talk_all` in `scripts/assistant-live-mcp.py`, the input `fast` in `.github/workflows/assistant-live.yml`.

**Evidence.** Against the stand-in for the Messages API with each answer held back one second, on every bank: a whole fast run took 202.7 s before and 33.2 s after, with the same report; the MCP half 30.4 s before and 6.2 s after, with the same answers; a rerun sent nothing and answered 195 requests from the store; a budget of 5 cents stopped a fast run with nothing sent. The readers' first requests at full price: about 2.86 dollars on the high side (`--dry-run --now`). What a real fast run costs and takes: UNVERIFIED.

