# ADR-0137: Every coupon run writes its quality checks into a QA record that is never edited, and gets one verdict from them

- Status: Proposed
- Date: 2026-11-24
- Decided by: Founder, 2026-11-24 ("ok let's do it, make sure it doesn't create any risks on data, impose any data leaks, no hacking leaks, needs to be safe", on the QA/QC plan and its first step) | Drafted by: Claude Code
- Related: [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md), [ADR-0104](ADR-0104-behind-the-sign-in-a-run-a-job-its-files-and-a-coupon-are-their-owners-alone-a-stranger-is-answered-as-if-there-were-none-and-the-local-api-narrows-nothing.md), `fea/src/anisotropy_fea/qa.py`, `api/alembic/versions/0016_qa_checks.py`, `api/src/anisotropy_api/records.py`, `lib/qa.ts`; the plan: the QA/QC plan page of 2026-11-21, step 1
- Area: fea, api, website, data

## Context

A coupon run already checks its own work, each check in a file of its own: the setup checklist before the solve (ADR-0051), the second solver's comparison after it (ADR-0030, the record's 3 % tolerance with its 2 % floor), the mesh study after the result (ADR-0068). Nothing set them beside each other, nothing kept them as one account of the run, and the after-solve checks only reported. On 2026-11-21 the public example coupon checked after a deploy agreed with the second solver on 52 of 57 values, and nothing in the run said so as a verdict. The founder asked for QA and QC "big, optimized and spot on", with checks before an engineer's approval and a dashboard over them, and, on 2026-11-24, that it create no risk to data. The plan's first step is the record the rest reads: the gates, the dashboard and the agents come later.

## Options considered

1. **A QA record: one row per check per run, written by the run's tool, kept by the API in a table never edited, with the run's verdict computed from the rows** (chosen). The fea package writes the checks from what the run computed, so no number is computed in the API or the page (ADR-0001); the table is the one source for the run's page, a later dashboard and an audit.
2. **The verdict as a column of the jobs table.** Rejected: a stored verdict can drift from its checks, and the jobs table's rows change by design (ADR-0050 amendment 2) where a record must not.
3. **Checks judged by a language model or an agent.** Rejected: the same run could be judged differently on another day, and the reason could not be audited. Agents may later find problems and propose checks; a check that judges is code.
4. **Leave the checks in their files and show them on the page.** Rejected: nothing would hold one account of a run, and nothing could block a result later.

## Decision

- **The checks.** `fea/src/anisotropy_fea/qa.py` turns what a run made into checks: each setup item (pass, warn; fail and missing as block, pending as warn), the second solver's comparison (pass when every compared value agrees within the record's tolerance, warn otherwise or when there was none), the mesh study (pass when every quantity it follows settled on the last refinement, warn otherwise or when there was no study). Each check has a layer (data, physics, fea, output, software), an id, its rule's version, a verdict (pass, warn, block), a label and message in the customer's words (ADR-0091), the values it measured and the decision record behind it. `fea/tools/run_coupon.py` writes them to `run/qa.json` after the mesh study and reports the file as the output `qa`; a failure to write it never stops the run.
- **The verdict.** From the checks alone: blocked when one blocks, needs engineer when one warns, ready when every one passes, unchecked when there are none. In this step no check that was not already blocking blocks: a run reaches its result only past the setup check.
- **The record.** Migration 0016 adds `qa_checks`: per row the job, the check's place in the run's list, when it was recorded and the check's columns, with the layers and verdicts constrained. When a job ends done, the API reads the run's `qa.json` only from the job's own folder or its owner's coupons (ADR-0106) and only up to a record's size, refuses it whole unless every check is one the record can keep (a known layer and verdict, an id, text of a check's length, evidence of a few finite values, at most 200 checks), and writes the rows once. A trigger refuses every update and delete, as the runs table's does (ADR-0026), and a second one refuses any row for a job whose checks were recorded at another moment, so nothing can be added to a record afterwards; the API refuses a second write as well. A record that cannot be written, for whatever reason, leaves the job as it ended, unchecked, and the reason goes to the log; the fea package keeps every check within what the record accepts (text cut at its limit, a number that is not finite written as null). The one clearing of the hosted trials deletes the checks before their jobs, the trigger off for that statement only.
- **Who reads it.** `GET /v1/coupon-jobs/{id}/qa` answers the run's checks, their counts and its verdict to the job's owner alone, through the same guard and the same 404 as the job itself (ADR-0104); without the jobs table, from the run's own file under the same rules. Behind the sign-in the API checks Access's token on every request as before (ADR-0056).
- **What the page shows.** Read once when the run is done and once more a moment later if the record is not there yet; a run that wrote checks whose record holds none says so ("The quality checks of this run were not recorded: ask an engineer to look at it before using the result") rather than nothing. Under a done run's progress, one line: "Every quality check passed", "Quality checks passed with notes for an engineer to review" or "A quality check stops this result" in the product's view, and with counts in the founders' (`lib/qa.ts`), the checks folded under it, the ones that need attention first: in the product's view each with its verdict in words, since a check's message may hold counts a customer is not asked to judge (the founder, 2026-11-17, on the second solver's line), and with its message in the founders'.

## As built (2026-11-24)

As decided. The fea checks: `fea/src/anisotropy_fea/qa.py`, `fea/tools/run_coupon.py` (`write_qa`), tested by `fea/tests/test_qa.py` and the public form's run in `fea/tests/test_run_coupon.py`. The record: `api/alembic/versions/0016_qa_checks.py`, `records.QACheckRow`, `qa_rows`, `qa_verdict`, `insert_qa_checks`, `fetch_qa_checks`, `CouponJobs._record_qa` and `qa_file`, the route `coupon_job_qa`; `scripts/clear-hosted-trials.py` deletes the checks first; tested by `api/tests/test_qa_record.py` and `api/tests/test_clear_hosted_trials.py`. The page: `lib/qa.ts`, `components/studio/qa-line.tsx` in `job-progress.tsx`, tested by `tests/qa.test.ts`.

## Why (evidence)

- The checks come from files the run already writes: `checks.Checklist.as_dict` (`fea/src/anisotropy_fea/checks.py`), `case_pages.record_rows` and `reaction_row` (`fea/src/anisotropy_fea/case_pages.py`), `convergence.settled_of` (`fea/src/anisotropy_fea/convergence.py`).
- The 52 of 57 on 2026-11-21: the deploy check's log of run 44854919472, attempt 2, on the public example coupon.
- An independent security review of the change before its pull request (2026-11-24) found no way for anyone but a job's owner to read its checks or learn the job exists, and no path traversal, injection, rendering or data leak; its seven robustness findings are answered in this record (a QA failure never keeps a job from ending or a run from its result, the file read only from the owner's folders and up to a record's size, finite evidence only, the database's own written-once trigger, the clearing reporting what it deleted, the page reading again and never silent). Two remain as for the runs table: a TRUNCATE skips row triggers, and the table's owner can switch a trigger off; the API's database role is not narrowed to SELECT and INSERT (UNVERIFIED which role it uses).
- The tests' output is in the pull request.

## Consequences

- Every done run from now on has an account of its checks that cannot be changed afterwards, which the dashboard (the plan's step 2) and the gates (step 3) read without touching the runs.
- Adding a check is a change to `qa.py` with a test; changing a rule raises its version, so an old row still says which rule judged it.
- The API refuses to start against a database without migration 0016, as for every table it writes.
- A run started by a coupon's name, without its setup checklist, gets a warning that its setup was not checked again.

## How we will know it was wrong

- A done run on the hosted site with no rows in `qa_checks` and no line in the log saying why.
- A check's verdict that an engineer, an Abaqus comparison or the weekly coupon check shows to be wrong, twice for the same check.
- Customers ignoring the line because most runs show notes: the share of runs that need an engineer is looked at each month once the dashboard shows it.
