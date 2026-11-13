# ADR-0091: The workspace speaks to the customer in the product's own words, mapped in the page and guarded by a test

- Status: Proposed
- Date: 2026-11-11
- Decided by: Founder, 2026-11-11 (a brief pasted into the session: "Every screen should read like Ansys or Abaqus/CAE: clear, short and confident, with no trace of how we build it internally") | Drafted by: Claude Code
- Related: [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md) (the writer is no longer shown), [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md) (the columns' names), [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md) and [ADR-0090](ADR-0090-a-tension-coupon-is-built-from-its-material-and-layup-and-the-standard-and-the-software-choose-the-rest-and-say-so.md) (the tension screen), [the copy style guide](../copy-style-guide.md), `lib/studio-copy.ts`, `tests/studio-copy.test.ts`, `tests/browser/studio.spec.ts`

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
