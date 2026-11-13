# ADR-0091: The workspace speaks to the customer in the product's own words, mapped in the page and guarded by a test

- Status: Proposed; one number rule, more banned words and a neutral assistant avatar since amendment 1
- Date: 2026-11-11
- Decided by: Founder, 2026-11-11 (a brief pasted into the session: "Every screen should read like Ansys or Abaqus/CAE: clear, short and confident, with no trace of how we build it internally"); Founder, 2026-11-12 ("accept", audit decision D22: a neutral assistant avatar) | Drafted by: Claude Code
- Related: [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md) (the writer is no longer shown), [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md) (the columns' names), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md) and [ADR-0090](ADR-0090-a-tension-coupon-is-built-from-its-material-and-layup-and-the-standard-and-the-software-choose-the-rest-and-say-so.md) (the tension screen), [the copy style guide](../copy-style-guide.md), `lib/studio-copy.ts`, `tests/studio-copy.test.ts`, `tests/browser/studio.spec.ts`, `lib/number-format.ts`, `tests/number-format.test.ts`

## Context

The hosted workspace is used by outside engineers (ADR-0056). On 2026-11-11 a walk through every state with the browser fixtures found its text written for the team: the done page's text named CalculiX 16 times, PrePoMax 7, Abaqus 6, "our engine" 3, "for the team" 2, a script path (`tools/abaqus_beside.py`), "the founder", and the model and its vendor ("written by anthropic (claude-opus-5-5)"). The run card listed eleven pipeline stages, a job id, the attempt folder and a console; a stopped run showed the solver's exit code. The probe table ran under the chat panel and its headings wrapped over three lines. The full audit table is in the pull request.

The words come from three places: the page's own strings, the API and fea package's messages (the queued message, the setup check's lines, the explanation templates, the tension screen's reasons), and the model's prompts. The pipeline's stage names and output keys are read by the API's tests and stored with every job.

## Options considered

1. **Rename at the source** (stage names, output keys, every message in the pipeline). Rejected: the API and fea tests read the stage names, and jobs stored in R2 before the change would still show the old words.
2. **Map in the page, guard what comes through, and fix display text at the source.** `lib/studio-copy.ts` maps the stages to five steps, the states to words and the keys to download labels; `customerText` and `checkText` replace any message that still holds a banned term, a path or an exit code with its plain state; the text written only for display (the queued message, the setup check's environment lines, the explanation's viewer aside, the tab-length reason, the prompts) changes at the source. Chosen.
3. **Keep the provenance on the page** (the writer badge, CalculiX by name) for transparency. Rejected by the brief. The writer and model stay in the run record (ADR-0052) and in the `data-writer` attribute.
4. **Hide verification altogether.** Rejected: one status line keeps the evidence, "Verified against reference solver: 57 of 57 values agree".

## Decision

Every word a customer reads in `/workspace` follows [the copy style guide](../copy-style-guide.md):

- No team language, job ids, paths, script or record names, decision numbers or people; no model, AI or vendor; no internal tools: the second solver is "the reference solver" and the page's own result is "FEA".
- A run is Queued, Meshing, Solving, Post-processing, Report ready, a five-step stepper above the model; a stopped run says where it stopped and what to do.
- Downloads are named plainly (Report (PDF), Full package (ZIP), Solver input (.inp), Reference solver input and results) and saved as `<standard>_<layup>_<what>`, for example `D3039_[0-90]2s_report.pdf`, through `?name=` on the file endpoints.
- Tables scroll inside their panel with a sticky first column, right-aligned numbers and units in the heading.
- `BANNED_TERMS` in `lib/studio-copy.ts` is the one list; a browser test fails if any of them reaches the product view, folded details, labels and saved names included.

The PDF's contents are not changed: the package and its document are the team's verification package (ADR-0089 amendment 3), which names Abaqus by design. Only their labels and saved names change here.

## As built (2026-11-11)

- `lib/studio-copy.ts`: the steps, the words, `customerText`, `checkText`, `shownSentence`, `withSymbols`, `verificationLine`, `downloadName`, `BANNED_TERMS`; unit tests in `tests/studio-copy.test.ts`.
- `components/studio/job-progress.tsx` (the stepper), `components/studio/job-files.tsx` (the files with their names), `results-view.tsx`, `coupon-chat.tsx`, `laminate-*`, `proposal-card.tsx`, `components/workspace/tension-screen.tsx` and `fea-rail.tsx`, `app/studio/studio.css` (tables, stepper).
- API: the queued message is "queued" or "queued; N ahead"; `?name=` on `/files/{key}` and `/package`, checked by `storage.download_name`, set as `Content-Disposition` or the store link's `response-content-disposition`; the prompts carry `VOICE`.
- fea: the setup check's solver and document lines name no program or path, a refused material says "not physically valid", the explanation's aside about another viewer is gone, the default tab length reads "56 mm by default".
- The development view (`ANISOTROPY_ALL_TESTS=on`) keeps the form's Abaqus row labels under Advanced; the hosted tier never shows it.
- After an independent review of the pull request (2026-11-12): the reasons the package gives for its default rows (the test, the units, the grips) and the setup check's units, transverse-modulus and mesh-size lines no longer name a program, and a fea test keeps every tension reason free of one; "Verified" is said only when every value agrees; a check item the guard hides still says what to do; a run that ended before any stage stopped "before it started"; a finished job with no stored package shows its report as not written; the verification line appears once, on the run card.

## Why (evidence)

- The before and after text of the done page, from the same fixtures: 38 banned-term occurrences before, 0 after (screenshots and counts in the pull request).
- `npm test`: 248 tests, 247 passed, 0 failed, 1 skipped; `npm run typecheck`: clean; `npm run test:studio`: 28 passed, among them the two new tests (no banned term from a fresh start to a finished run; a stopped run in plain words).
- API, `uv run pytest`: 366 passed, 82 skipped, 2 failed: `test_a_slow_tool_is_a_504_and_a_broken_one_a_503` in the check and tow tests, which fail the same way on unchanged main (cca3928) on this machine. The database tests, the queue's message among them, need `TEST_DATABASE_URL` and are UNVERIFIED locally (CI runs them). The store link's `response-content-disposition` is signed offline in a test; that R2 honours it on a live link is UNVERIFIED.
- fea and engine, `uv run pytest -q -ra tests ../engine/tests`: 1426 passed, 7 skipped (the team's local coupons), 1 failed: `test_calculix_gives_the_same_answer_on_every_run_of_a_deck`, which fails the same way on unchanged main (cca3928) on this machine.
- CI on the pull request (first commit and the CI-timing fix): every job passed, the API's database tests among them.

## Consequences

- New text must pass the guard; a banned term in a message makes the page show the plain state instead, so a useful detail can be hidden until its words are fixed at the source.
- The page no longer says when a model wrote the explanation. Where a law requires telling a user that they are reading or talking to an AI system (for example Article 50 of the EU AI Act), that requirement wins over this record; whether it applies to the invite-only beta is UNVERIFIED.
- Stage names, output keys and stored jobs are unchanged, so older jobs display in the new words.
- The PDF and the package still speak to the team. A customer report is a separate decision.

## How we will know it was wrong

- A customer or auditor cannot tell which solver verified a result and needs to: the report, or a "Details" line, then names it.
- The banned-term test blocks a legitimate word more than once; the list is then narrowed.
- Engineers ask for the pipeline's detail (stages, timings, console) to diagnose stopped runs: it returns behind "Details".

## Amendment 1, 2026-11-12 (one number rule; the engine, the decks and the case runner banned; a neutral avatar)

**Context.** The professional audit of the site on 2026-11-12 found the laminate pages printing programmer notation and machinery words (findings laminate-2, laminate-5, laminate-6, laminate-7). The laminate workspace wrote "Under Nx = 1e+05 N/m", "1.863e-15" for an A26 that is roundoff, and "3.22" beside "3.474" in one column; the calculator printed seven figures in e-notation with the hint "e−4 means × 10⁻⁴". Three formatters disagreed: the laminate table's `shown()` switched to an exponent at 10⁶, `printed()` in `lib/studio-colors.ts` at 10⁵, and the API's sentence writer `_words` at 10⁴. The pages said "the engine converts, never this page", "the units the coupon decks use" and "the engine's case runner lists both"; none of these words was in `BANNED_TERMS`, and the guard test did not visit `/workspace/laminate` or `/calculator`. The assistant's avatar was a sparkles icon, the common sign for AI-written content (finding laminate-27).

**Options.** (1) Keep a formatter per page. Rejected: the same number reads differently a few lines apart. (2) One rule in `lib/number-format.ts` that the page's tables and readouts use, and the same rule in the API's and the fea package's sentences, written in ASCII (plain digits from 0.001 up to a million, e-notation outside) and printed by the rule, with the minus sign, by `shownSentence` on the page. Chosen. (3) Write "× 10ⁿ" and U+2212 in the sentences at the source. Rejected: the number guard (ADR-0052) reads ASCII numbers and would need a second parser. For the avatar: a neutral speech icon (`MessagesSquare`) or the product mark, the audit's recommendation.

**Decision.** Every number the site prints has four significant figures, plain digits from 0.001 up to a million, "3.207 × 10⁶" outside, and the minus sign U+2212; a table column keeps its zeros ("3.220"), a readout or a sentence drops them. `printed()` delegates to the rule, and the home page's small matrices print it at three figures; the API's `_words` and the fea package's `number` write it in ASCII, and the page prints a sentence's exponent by the rule, its significant digits as written, so a job explained before the rule reads "16220 N" as its Summary does, not "1.622 × 10⁴ N". The laminate results show arithmetic noise as zero at the stack summary's tolerance (ADR-0059): B when the stack has no extension–bending coupling, A16 and A26 when it has no extension–shear coupling, any other entry below a billionth of its set's largest. `BANNED_TERMS` adds "engine" (as a word: "engineer" passes), "decks" and "case runner"; the browser tests run the guard on `/workspace/laminate` before and after a solve, and on `/calculator` with the values its fields hold. The number rule and the banned words are the audit's fix list, applied in the PR-LAM group; the founder has not confirmed them as a decision. The avatar: the founder accepted the audit's recommendation on 2026-11-12 (decision D22, "accept" on "A neutral MessagesSquare icon or the product mark"); the laminate and coupon assistants show `MessagesSquare`.

**Evidence.** `tests/number-format.test.ts` (the rule, that `shown`, `formatted`, `shortened` and `printed` share it, and that a sentence's exponent is printed by it), `tests/studio-colors.test.ts`, `tests/studio-copy.test.ts` (the new banned words; every sentence of the captured laminate answers shown with no banned word and no e-notation), `api/tests/test_laminate_problems.py` and `fea/tests/test_fields.py` (the ASCII rule, read back by the number guard); the counts are in the pull request. The browser tests that run the guard on the laminate workspace and the calculator were written but not run in this change: UNVERIFIED until the coordinator runs them.

**Consequences.** The coupon workspace's readouts and tables print through `printed()` and change with it: a value from 10⁵ to 10⁶ is now plain, one below 0.001 or from a million up reads "× 10ⁿ", a negative value has the minus sign. A setup-check message that says "the decks" (the units line of `fea/src/anisotropy_fea/checks.py`) now shows its plain state until its words change at the source. The home page's and the tour's small matrices read "9.88 × 10⁷" where they read "9.88e+7". The calculator's request (`requestAnalysis` in `lib/laminate-api.ts`) now reports a network failure or a status of 500 or more as the one outage message (`ANALYSIS_UNAVAILABLE`, finding laminate-13); the home page's calculator and the tour use the same request and show it too, so their own fallback, "Cannot reach the calculation service", is no longer reached and goes with their copy. The fibre tow record's waiting text (`components/workspace/tow-rail.tsx`, "every number computed by the engine") still uses a word this amendment bans and changes with that page's copy.
