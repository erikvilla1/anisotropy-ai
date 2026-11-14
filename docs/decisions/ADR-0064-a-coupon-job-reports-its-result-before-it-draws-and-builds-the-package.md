# ADR-0064: A coupon job reports its result before it draws and builds the package

- Status: Proposed
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
