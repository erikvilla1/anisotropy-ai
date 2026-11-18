# ADR-0109: A person's past analyses are listed from their own jobs, each with the answer its run wrote, and one opens again as it was solved, from the files that run stored

- Status: Proposed; while a past run or an imported model has the stage the chat shows the talk about it alone, since amendment 1
- Date: 2026-11-17
- Decided by: Founder, 2026-11-17 (the decision card "Choose what I build next now that the short answers are merged": "Run history per person", over "Accept more Abaqus models" and "Aerospace security plan"; the card says a list of past analyses to reopen, with the result and the answer, private to each person. How the list looks, that a past run opens read only and the rest of the choices below are the drafter's, built while the card waited) | Drafted by: Claude Code
- Related: `fea/tools/run_coupon.py` (`rows_of_run`, `answer_of_run`), `fea/src/anisotropy_fea/fields.py` (`run_answer`), `api/alembic/versions/0012_job_answer.py`, `api/src/anisotropy_api/coupon_jobs.py` (`answer_of_outcome`), `lib/run-history.ts`, `components/studio/use-past-run.ts`, `components/workspace/past-rail.tsx`, `components/studio/past-stage.tsx`, `components/workspace/chooser.tsx`, [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md) (a job and its files are their owner's alone), [ADR-0106](ADR-0106-behind-the-sign-in-each-person-has-a-folder-of-coupons-of-their-own-on-the-disk-and-in-the-store-and-the-coupons-already-saved-stay-where-they-are.md) (a folder of coupons per person), [ADR-0050](ADR-0050-coupon-jobs-through-the-api-run-the-tool-in-the-background-one-at-a-time.md) (the jobs table and the store), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (the workspace and its projects), [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md) (the answer), [ADR-0105](ADR-0105-a-model-brought-in-as-an-abaqus-input-file-is-read-as-it-stands-solved-by-our-kernel-and-asked-about-nothing-in-it-is-changed-and-nothing-of-it-is-kept.md) (a model that takes the stage and is read as it stands), [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md) (the assistant answers from the results on the page), [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md) (the live preview)
- Area: website, api, fea

## Context

- On 2026-11-07 the founder asked whether a person's solver history is confined to their sign-in and can be viewed. Since ADR-0104 it is confined: `GET /v1/coupon-jobs` lists the requester's own jobs and a job's files are answered to no one else. Nothing on the page showed it: `/workspace` lists projects, which hold a setup and no result.
- A finished run's results could be seen again only through the link "Open results in a new window" of the page that ran it, or by running the coupon again.
- A job's row said which coupon ran and when, and for the result one line that counts the values agreeing with the reference solver. Whether the coupon held, at what factor and which ply fails first was in the run's fields file alone, megabytes per run.
- A coupon's name is its material, test and layup. Its size, load and mesh can change between runs, and the coupon's folder keeps the latest rows only. "Reopen a coupon" therefore gives the latest rows, not those of an earlier run.
- The fea package changes: the gauge section's reading changed on 2026-11-16 (ADR-0108), so the same rows solved today can give another number than a run of last week stored.

## Options considered

1. **Leave the history to the projects list.** Rejected: a project keeps no result, and the link to a run's results is lost with the page.
2. **Keep the history in the browser.** Rejected: it would not follow the person to another machine, and the jobs are already kept per person on the server.
3. **A new table of analyses.** Rejected: the jobs table already holds each run with its owner, its coupon, its state and where its files are.
4. **List the jobs, and fetch each run's fields to show its answer.** Rejected: megabytes per row to show three values.
5. **Open a past run by solving its rows again.** Rejected: the answer could differ from the one the run gave, and the report of that run would no longer match the page.
6. **Open a past run into a new project, or over the open project's rows.** Rejected: the first fills the projects list with copies, the second overwrites rows the person may not have run yet.
7. **List the person's own jobs with the answer each run wrote, and open one as it stored itself, read only, with its rows offered to be taken up.** Chosen.

## Decision

- **The list.** `/workspace` shows "Your analyses" under the projects: the requester's finished runs that have results, newest first, from `GET /v1/coupon-jobs`. Each row gives the coupon, the answer ("Holds at 1.032 × the applied load"), the first ply to fail with its criterion and where it is read, and when the run finished. Eight rows show, then "Show all". A stopped or refused run is not listed: it has nothing to open.
- **The answer is the run's own.** When a run reports its result, its tool picks from the summary our engine wrote the verdict's basis, criterion, fails or holds and factor, and the ply with its angle and face (`fields.run_answer`), and writes them into the outcome. The API keeps them on the job's row (`jobs.answer`, migration 0012) only in that shape and hands them out on the job's status. Nothing is computed for it by the API or the page. A run from before this record, and a result without a criterion or with no stress, has none, and the list shows a dash.
- **A run keeps its own rows.** The tool writes the rows of the attempt as the studio edits them (`intake.values_of_spec` on the attempt's spec) into the attempt's `run/studio/values.json` before anything runs, and reports the file under the key `values` with the checklist and the preview. A spec the form cannot state leaves none, and the run goes on.
- **Opened as it was solved.** "Open" shows the run in the coupon workspace: its results in the centre from its stored fields and explanation, under a line that says it is a past run and when; on the left the coupon, the time, the answer and the run's files. Nothing is checked or solved to show it. The project behind it keeps its rows, its check and its run.
- **Read only until asked.** While a past run has the stage the assistant answers questions about its results from those results (ADR-0099, ADR-0102, ADR-0103), and a message that would change a row is answered once: a past run is shown as it was solved. "Use these inputs" puts the run's rows in the project in place of the ones there and closes the past run; a run without rows does not offer it.
- **Which run to open** passes from the list to the workspace through the tab's session storage, a job's id and nothing else, taken once; no address carries it. Where that storage is blocked, "Open" goes to the results page of the run (`/workspace/fea/view`).
- **Whose runs.** No new rule: the list and every file are answered by ADR-0104's, so a person sees their own runs and no one else's, and the local API shows every run on the machine.

## As built (2026-11-17)

- fea: `fields.run_answer(summary)`; `run_coupon.py` writes `run/studio/values.json` (`rows_of_run`) right after the checklist and the preview, keeps the three keys on a run's outputs whatever became of it (`SETUP_KEYS`), and writes `answer` into the outcome (`answer_of_run`, `write_result`).
- API: migration `0012` adds `jobs.answer` (JSONB, null allowed); `coupon_jobs.answer_of_outcome` keeps a done run's answer only in its seven values, with a finite factor; `Job.answer()`; `CouponJobOutput.answer` (`schemas.JobAnswer`). The `values` file is served by the existing route for a job's files.
- Page: `lib/run-history.ts` (`pastRuns`, `readJobAnswer`, `answerWords`, `askToOpen`, `takeRunToOpen`); `lib/studio-api.ts` (`fetchRunValues`, `JobStatus.answer`); `components/studio/use-past-run.ts` (the run's status, fields, explanation and rows, held in the page); `components/workspace/past-rail.tsx` and `components/studio/past-stage.tsx`; `resultsOnPage` gained `past` and `readOnly`; the chooser's "Your analyses"; the assistant's "Past run opened" line and its read-only answer.
- Differences from a fuller history, left for later: no search or filter, no delete, no list inside the coupon workspace, the newest 50 runs only (the API's list), and the laminate workspace's solves are not listed.

## Why (evidence)

- The pieces existed: ADR-0104's list of a person's own jobs, and each done run's files in the store by key (ADR-0050 amendment 2), which a later process already serves (`CouponJobs.output_file` for a job read back from its row).
- `cd fea && uv run pytest -q tests/test_run_coupon.py tests/test_fields.py`: the outcome carries the answer picked from the summary and nothing else; a stand-in run keeps its rows under `values`; a summary without a verdict gives none.
- `cd api && uv run pytest -q tests/test_coupon_jobs_api.py tests/test_run_records_db.py` with a database: a done job says its answer and hands out its rows; an answer outside the shape, and a stopped run, say none; the row keeps the answer for a later process (migration 0012).
- `npx tsx --test tests/run-history.test.ts tests/imported-model.test.ts`: which jobs are listed, the answer's shape and words, the id passed once, and a past run's results taking the stage over the project's live answer.
- The browser scenario "your analyses lists the finished runs with their answers, and one opens again as it was solved" (`tests/browser/workspace.spec.ts`): two finished runs listed, the older with a dash; one opened with its banner, its answer and its files; "which ply fails first?" answered from it; "make the mesh finer" changes nothing; no check, solve or model call is made; "Use these inputs" puts the run's own length in the project; a reload does not open it again.
- The whole suites, 2026-11-17: `cd fea && uv run pytest -q -ra tests ../engine/tests`: 1624 passed, 43 skipped, 3 failed and 1 error; the same four fail on main unchanged in the container this was drafted in, where Gmsh is not installed. `cd api && uv run pytest -q` with a database: 666 passed, 1 skipped. `cd mcp-server && uv run pytest -q`: 39 passed. `npm test`: 387 pass, 1 skipped, 0 fail. `npm run typecheck`: clean. The studio browser suite: 49 passed.
- UNVERIFIED: nothing of this has run on the hosted site. No full run with CalculiX was made in the container this was drafted in (no `ccx` there), so the tool's two new files were written by its tests' stand-in steps and by the test that CI runs with CalculiX. Two sign-ins were not tried against the list on the hosted site; ADR-0104's tests cover the rule.

## Consequences

- A person finds what they ran, with its answer, on any machine they sign in from, and opens it without running it again.
- A past run reads as it was solved. After a change to the package such as ADR-0108, an old run still shows its old numbers, and the list can show two answers for the same rows on two dates. The banner says the run is a past one; it does not say which version of the package solved it.
- Runs made before this record list without an answer and cannot hand their rows back; they still open with their results.
- The jobs table gains one column, and every run one small file in its attempt and in the store.
- Opening a past run asks for its explanation's words as any result's view does (`POST .../explain`), which writes a run record.
- The workspace has a third thing that can take the stage, after the coupon and an imported model. An imported model keeps it when both are asked for.
- The store keeps every run's files with no end date, as before; the list makes that visible. There is no way to delete a run.

## How we will know it was wrong

- A person looks for a run older than the newest 50, or cannot find one among them without a search.
- An engineer takes a past run's numbers for today's answer to the same rows after the package has changed, and is misled.
- Someone needs to delete a run, or to share one with a colleague, which this record offers neither of.
- The list is slow to load on an account with many runs.

## Amendment 1, 2026-11-17 (while a past run or an imported model has the stage, the chat shows the talk about it alone; not yet confirmed by the founder)

**Context.** On the hosted site, the day this record was merged, a past run was opened from "Your analyses" (the founder: "i have the site opened for you to take control and go over"). The chat beside it still showed the project's own cards: "Picked up where you left off", "Checking the setup…" and "Ready to run" with a live "Run analysis" button. That button runs the project behind the past run, not the run on the stage. The same holds beside an imported model (ADR-0105).

**Options.** Leave the cards and switch their buttons off: the card "Ready to run" still reads as a statement about the run on the stage. Dim the project's cards under a heading: more words on a pane that is asked to be short. Show, while something read-only has the stage, only what was said while it had it: chosen.

**Decision.** While a past run or an imported model has the stage (`resultsOnPage(...).readOnly`), the chat shows only the entries said while it had the stage, and none of the project's own cards (a question, a check, a run, its results, a proposal); "Checking the setup…", "All inputs" and "Start a new coupon" are not shown either. Back in the project everything is shown again, the talk about the run included. Nothing is removed from the conversation. Drafted by Claude Code; the founder has not confirmed it.

**Evidence.** `components/studio/coupon-chat.tsx` (`Entry.stage`, `PROJECT_KINDS`, `render`). The browser scenario "your analyses lists the finished runs with their answers, and one opens again as it was solved" (`tests/browser/workspace.spec.ts`) now finds no question, no check and no "Start a new coupon" beside the past run, and finds them again after "Use these inputs". Not yet seen on the hosted site (UNVERIFIED).
