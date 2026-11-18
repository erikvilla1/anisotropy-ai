# ADR-0064: A coupon job reports its result before it draws and builds the package

- Status: Proposed; the drawings in the report's step, the run's study printed by the package and every step's seconds on the page, amendment 1 (2026-11-14); Report ready only with the PDF and files once the run has ended, amendment 2 (2026-11-14); the mesh study after the result and the PDF written when it is asked for, amendment 3 (2026-11-17)
- Date: 2026-11-07
- Decided by: Erik Villa (asked for "point 2": plots, the package and the PDF out of the job's critical path) | Drafted by: Claude
- Related: ADR-0049 (one command per coupon), ADR-0050 (coupon jobs), ADR-0051 (the studio), ADR-0056 amendment 3 (the job queue); `fea/tools/run_coupon.py`, `fea/examples/build_model.py`, `api/src/anisotropy_api/coupon_jobs.py`, `api/src/anisotropy_api/schemas.py`; tests `fea/tests/test_run_coupon.py`, `fea/tests/test_build_model_script.py`, `api/tests/test_coupon_jobs_api.py`, `api/tests/test_job_queue.py`, `tests/browser/studio.spec.ts`
- Area: fea

## Context

A coupon job told the studio its result (how many recorded values agree with CalculiX, our reaction against CalculiX's) only when
the whole run ended: our engine with its two pictures and the ParaView file, CalculiX, the record, then the package and its PDF.
On the public IM7/8552 coupon in a cloud container, without the PDF, the run took 14.9 s and 15.9 s; the package was 5.3 s of it,
the drawings and the ParaView file about 2 s of the engine's 4.9 to 6.0 s. With the PDF the founder's machine took 80 s. None of
the drawings, the package or the PDF changes a number in the result.

## Options considered

1. Keep the order: the result with the package. Simple; the engineer waits for documents nobody reads first.
2. Report the result as soon as the record is written, then draw and build the package in the same run, the job still `running`
   until they end (chosen). One process, one attempt, one receipt; the coupon stays claimed while its package is written, so a
   second job on the coupon cannot number an attempt under it, and the queue's consumer keeps the solver awake until the end.
3. End the job `done` at the result and build the documents as a follow-on. The person could start the next job sooner, but the
   one-running-job-per-coupon index (migration 0008), the one-running-job-per-person limit and the queue's consumer all key on
   `running`; a follow-on would need a new state or table, a migration and a consumer change. Deferred.
4. Build the documents only on request. Saves their time when nobody wants them, but the package is the delivery the team keeps
   (ADR-0043) and a request needs a route, a state and a button. Deferred.
5. Draw in a thread beside CalculiX. Saves wall time too, but matplotlib in a thread of a script that also writes the result
   files is harder to reason about than a later step. Rejected.

## Decision

`run_coupon.py` gains two stages: **the result** after the CalculiX record and **the drawings** before the package. Our engine
runs `build_model.py --drawings without` (the fields, the explanation and the summary; matplotlib is no longer imported);
at the result the tool checks the result's files, computes the line from the record and writes it to the progress file
(`result`). Then `build_model.py --drawings only` draws the deck that run wrote (the model, the solution, the `.vtu`), and the
package is built. A drawing or package that fails after the result no longer stops the run: the attempt's row, the outcome's
`documents` and its message say what is missing and why, and the outcome is `done` with `result` kept apart.

The API's job status gains `result` (the line as soon as the tool reports it) and `documents` (`building` until the job ends,
then `written` or what is missing). Under the job queue the solver's heartbeat writes the result to the row's `message`, so the
API's container reads it back; the record and the engine's summary join the files filed while a job runs. The studio's job panel
and the chat show the result line while the drawings and the package are made.

## Why (evidence)

Measured in this container (Linux, CalculiX 2.21 from apt, no Tectonic, so without the PDF), public IM7/8552 coupon, three runs
each, timed from the tool's own stages:

| | before | after |
| --- | --- | --- |
| our engine | 4.9, 6.0 s | 2.3 to 2.6 s |
| result reported at | 14.9, 15.9 s (with everything) | 6.4 to 6.7 s |
| the drawings | inside the engine | 3.6 to 4.1 s, after the result |
| the package | 5.3 s | 5.4 to 5.8 s, after the result |
| whole run | 14.9, 15.9 s | 16.1 to 17.2 s |

The run is about a second longer, since `--drawings only` reads and solves the deck again (about 0.6 s) and loads matplotlib in a
second process. With the PDF the gain should be larger, since the PDF follows the result; that is UNVERIFIED here (no Tectonic).

## Consequences

- The engineer sees the full result, CalculiX comparison included, in under half the time on this coupon; the files follow.
- The job is `running` until its documents end, so the per-person limit and a second job on the same coupon still wait for the
  package and its PDF, as before.
- A package that fails no longer hides the result; whoever reads the row or the outcome must read `documents` too.
- `build_model.py` without `--drawings` behaves as before.

## How we will know it was wrong

If the hosted tier's measurements show people waiting on the per-person limit while a PDF builds (a second job refused while the
first job's `documents` is `building`), take option 3. If the drawings' second solve grows past a few seconds on a large mesh,
write the solution once and draw from it.

## Amendment 1, 2026-11-14 (the drawings count in the report's step, the package prints the run's study, every step shows its seconds; asked for by the founder: "the meshing to the solving to post processign takes wayyyy to long")

**Context.** The page showed the result while the strip still said Post-processing: `lib/studio-copy.ts` put the drawings, which come after the result, in that step. The package solved the three-mesh convergence study again, 4.3 s of its 32.1 s on the founder's machine, though the run had just written it to `<coupon>-convergence.json`. The stage timings (ADR-0056 amendment 6) stayed in the job's record, so the page could not say where a run's time went.

**Options.**
- The drawings: in the report's step (chosen); left in Post-processing (rejected: the step says the result is not ready when it is).
- The study: the run's file passed to the package, `build_document(study=...)`, solved there only when none is given (chosen); a cache inside the convergence module (rejected: state hidden across runs).
- The times: each finished step's seconds under it and "Finished in N s." once done (chosen); nothing (rejected: the founder asked why the run is slow and the page could not say); the pipeline's stage names (rejected: ADR-0091).
- The Abaqus build script, written twice by the package: left as is (0.11 s, measured).

**Decision.** As chosen. A step's seconds are the sum of its stages and of the solver's phases in it, the coupons' fetch in Meshing and the upload in Report; the waits for the naming lock and at the gate fall inside the first stages and are not added again; Queued runs from filed to taken up.

**Evidence.** `tests/studio-copy.test.ts` reads the 2026-11-14 job's row: queued 10.2 s, meshing 18.0 s, solving 16.2 s, post-processing 5.0 s, report 51.1 s, finished in 106 s. `fea/tests/test_run_coupon.py` asserts that the package receives the run's study. The package's LaTeX of that coupon matches main's in its convergence section; it differs only in the build line and in CalculiX's numbers, which differ between two runs of main too.

## Amendment 2, 2026-11-14 ("Report ready" means the PDF exists, and files are offered once the run has ended; the founder asked "once it checks report is ready where are the report where are the files?")

**Context.** The report is "Report (PDF)" under Files at the foot of the left column, where the founder chose to keep it. Reading the code for his question showed two faults. A job read back from its row in the jobs table, as every hosted job is, had its documents "written" whenever the package was there (`Job.from_row`), and the page's fallback checked the package too, so a PDF that failed to compile still ticked Report ready with no Report (PDF) to download. And Files listed a running job's files: on the hosted tier they are stored only when the job ends, so a link could fail, and the package asked for by its file key before the end reached `package_archive` with no outcome and raised.

**Options.**
1. *Documents "written" only with the PDF, unless the job asked for none; files listed once the job has ended; the package by its key while the job runs answers 409* (chosen).
2. *Keep ticking Report ready for the package and add a separate line for the PDF.* Rejected: "Report ready" with no report is the fault.
3. *List the files that are already stored while the job runs.* Rejected: on the hosted tier that is a few of them for a few seconds, and the customer's two files come last.

**Decision.** Option 1: `documents_of_row` in `api/src/anisotropy_api/coupon_jobs.py`, `reportMissing` and `downloadable` in `lib/studio-copy.ts`, `JobNotDone` mapped to 409 in `main.py`. A run whose PDF failed shows "Done, report not written", its Report ready step crossed out and the sentence asking to run it again, as a local run already did.

**Evidence.** `api/tests/test_job_queue.py`: a job read back from its row with the PDF is "written" and one without it is not (both pass; the file's 15 tests passed twice). `api/tests/test_coupon_jobs_api.py`: the package asked for while the job runs is 409. `tests/studio-copy.test.ts`: a package without its PDF crosses the step out, and no file is offered while the run goes.

## Amendment 3, 2026-11-17 (the mesh study runs after the result, and the report's PDF is written when someone asks for it; the founder chose "Both: PDF on request, wake early" on a card)

**Context.** The founder, 2026-11-17, of a user's run: "Takes too long". In nine finished hosted runs of his, read that day, the result came after 29 s of timed work (18 to 42 s), 7 s of it the mesh convergence study, and the package with its PDF then took 35 s (21 to 44 s), nearly all of it Tectonic typesetting a report that most runs never open. The study changes no number of the result: it is a reading beside it ([ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md), whose "How we will know it was wrong" names this move). Option 4 of this record, documents on request, was deferred for want of a route, a state and a button. What makes the result itself come sooner on the hosted tier is [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md) amendment 11.

**Options.**

- The mesh study: (1) *before the result* (as it was); (2) **after it, as the first step of the documents** (chosen): the result's table is on the page and the study's table joins it a few seconds later; (3) *on request*: rejected, the package and the PDF print it and the page shows it with every result.
- The PDF: (1) *typeset in every run* (as it was); (2) **written when someone asks for it, from what the run kept** (chosen, the founder's "PDF on request"); (3) *typeset by a solver through the queue*: rejected, a second kind of job with its own states for half a minute of work; (4) *no PDF on the hosted tier*: rejected, the report is the delivery.
- What the run keeps for it: (1) *the LaTeX folder as it lies in the coupon's folder*: rejected, the next attempt writes over it; (2) **one zip per attempt, the report's `.tex` and its figures, filed with the job's files as `document_source`** (chosen).
- Where it is typeset: (1) **the API's container** (chosen): it is the solver's image, Tectonic and its warmed cache included, and it is awake while a page is open; one report at a time; (2) *a solver*: rejected with option 3 above.

**Decision.** As chosen.
- `fea/tools/run_coupon.py`: the stages read "the CalculiX record", "the result", "the mesh study", "the drawings", "the package", "the outputs"; the study's old name, "the convergence study", is kept by the page for runs of before this. `mesh_study` writes the study into the fields after the result is reported and never stops the run. A run with `--no-pdf` whose package was written reports `document_source` (`report_source`). A run with its PDF is unchanged: the command line and a local machine still write the PDF into the package.
- `api/src/anisotropy_api/coupon_jobs.py`: `write_document` typesets the job's own source in a folder of the job's (`_typeset`, Tectonic with a limit of 300 s, one at a time) and files the PDF as the job's `document`, in the store beside its other files or, with no store, in the package folder (`_file_document`). `POST /v1/coupon-jobs/{id}/document` answers 202 with `report: "writing"`, 200 when the PDF is already there, 409 for a run that has not finished or kept no source, 503 without Tectonic; the status carries `report` (`writing`, `failed` or null), kept in the API's process, so after a restart the report is simply asked for again. `documents_of_row`: a job that asked for no PDF has its documents "written" once its source is filed.
- The page: a run is asked for without its PDF (`startSolve` sends `pdf: false`). Under Files, "Report (PDF)" is a button that asks, says "Writing the report. It downloads when it is ready, in about half a minute.", downloads the PDF when it is there and is from then on the usual link (`components/studio/job-files.tsx`, `askReport`, `reportOnRequest` and `REPORT_WORDS` in `lib/studio-copy.ts`). A report that failed says so and can be asked for again.

**What it changes.** Amendment 2's "Report ready means the PDF exists" becomes: the step is ticked when the PDF exists or can be had by asking, and a run that kept neither is still crossed out. The package's zip of a hosted run no longer holds the PDF; the report is a file of its own beside it. The mesh study's seconds count in the report's step on the page, not in the solving.

**Evidence.** The public T650 tension coupon at 2 mm in a cloud container, no PDF, 2026-11-17: the result 3.4 s after the attempt was numbered with the study after it, 7.0 s with the study before it (the same two runs as ADR-0056 amendment 11); the study itself 3.0 s and 2.7 s. Tests: `fea/tests/test_run_coupon.py` (a real run ends with `document_source`, a zip of the `.tex` and the figures; the study is in the fields after the result), `api/tests/test_job_queue.py` (a report is written on request from the job's own attempt's source and filed with its files; one under way is not started twice and a failed one can be asked again; the refusals in the page's words; Report ready without a PDF needs the source), `api/tests/test_coupon_jobs_api.py` (with no store the report lands in the package), `tests/studio-copy.test.ts` and `tests/studio-api.test.ts` (the button's states, the ask), `tests/browser/studio.spec.ts` (a run ends without its PDF; the button writes it, says so, and it downloads). The API's tests stand in a script for Tectonic. UNVERIFIED: a real report typeset by Tectonic from a `document_source` (no Tectonic in the cloud container the tests ran in), the half minute the page names for it, and all of it on the hosted tier.
