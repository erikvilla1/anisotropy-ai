# ADR-0086: Every edit is answered by our kernel as a labelled preview, from warm workers; CalculiX, the mesh study and the package stay on the full run

- Status: Proposed
- Date: 2026-11-10
- Decided by: Founder, 2026-11-10 (asked what should update within seconds of an edit: "Live kernel, full run on request (Recommended)"; the plan of that day, part 3, approved) | Drafted by: Claude Code
- Related: `fea/tools/studio_tool.py` (`live`, `serve`), `api/src/anisotropy_api/live.py`, `api/src/anisotropy_api/main.py` (`POST /v1/coupon-jobs/live`), `api/src/anisotropy_api/settings.py` (`ANISOTROPY_LIVE_WORKERS`), [docs/evaluations/fea/2026-11-10-live-solve.md](../evaluations/fea/2026-11-10-live-solve.md), [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md), [ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md), [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md), risk R-23

## Context

The founder wants the analysis to update within seconds of an edit, as the engineer changes values in the chat or on the panels. The only way the page had to a result was the full job: setup check, decks, our kernel, the mesh study (ADR-0068), the CalculiX twin, drawings and the PDF. That gives a first result after about 3 to 4 s locally and minutes on the hosted tier. Edits only cleared the old result.

Our kernel alone solves a strip in hundredths of a second (ADR-0067). Measured on 2026-11-10 (the evaluation note):
- A fresh `studio_tool.py live` per call takes 4 to 5 s.
- About 2 s of that is importing the fea package, and 1.5 to 2 s is starting Python and `uv`. The work is under a second.
- A warm worker that keeps the package imported answers the same strips in 0.4 to 0.9 s, and the public open hole in 3.4 to 3.6 s.

## Options considered

What answers an edit:

1. **Our kernel alone, labelled a preview; the full run on request** (chosen by the founder). It is accurate where our kernel is: the same kernel and answer as the full run. CalculiX and the mesh study check it when the engineer asks.
2. The full job on every edit. Rejected: 8 to 17 s locally, minutes hosted.
3. No automatic answer, only a faster button. Rejected: not the founder's "within seconds".

How the API runs it:

1. **Warm `studio_tool.py serve` workers, one JSON line in and one out** (chosen). The imports are paid once, and the API still depends on the engine alone (ADR-0051).
2. A fresh `studio_tool.py live` per call. Kept as the fallback, with `ANISOTROPY_LIVE_WORKERS=0`: 4 to 5 s.
3. The API imports the fea package. Rejected: ADR-0051 keeps the API on the engine alone, and the package's own processes on a separate side.

How the fields reach the page:

1. **As the tool wrote them, compact, gzipped in transit** (chosen). A fine mesh's fields run to megabytes, and parsing and re-encoding them costs more than the solve.
2. Through Pydantic. Rejected for that cost.

## Decision

- **`studio_tool.py live` and `serve`.**
  - `live` runs the setup check and, when nothing blocks, our kernel on the deck as a run writes it. It writes the fields with the answer (ADR-0085), the explanation, the summary apart, and each stage's seconds.
  - There is no mesh study, no CalculiX, no attempt folder and no document.
  - `serve` is `live` kept warm: it imports once, says it is ready, then answers one JSON request per line on stdin with one JSON line on stdout.
  - `fixtures` is `live` and the mesh study, so the two cannot drift.
- **`POST /v1/coupon-jobs/live`** takes the setup check's request. It answers with the check, the preview drawing, and the fields and explanation as the tool wrote them, plus the API's seconds and the tool's stage seconds.
  - **The pool:** `LiveSolver` keeps `ANISOTROPY_LIVE_WORKERS` warm workers (default 1, 0 to 8), started on the first live request.
  - **Failures:** a worker that does not answer in 30 s, or stops, is killed and replaced. The request is answered 504 or 503. When every worker stays busy for 20 s, the answer is 429.
- **The run record** (amends ADR-0026) keeps the check's state, the designation, the summary and the fields' SHA-256, never the arrays.
- **Compression:** the API compresses its responses for a browser that asks.
- **A preview is not a result** (amends ADR-0068). It carries no mesh study and no CalculiX comparison, and the page labels it so (part 4). The full run stays `POST /v1/coupon-jobs`.

## As built (2026-11-10)

- **fea:**
  - `studio_tool.py`: `solved`, `live`, `serve`, `write_compact`, and `fixtures` through `live`. The deck is now solved in a folder of its own, so a fixture folder no longer collects decks.
  - `fea/tests/test_studio_tool.py`: live, a blocked live call, and serve.
- **API:**
  - `api/src/anisotropy_api/live.py` (`LiveSolver`); `POST /v1/coupon-jobs/live` in `main.py`; `LiveSolveResponse` (for the documentation); `GZipMiddleware`; the setting `ANISOTROPY_LIVE_WORKERS`.
  - `api/tests/test_live_api.py`: ready, blocked, one warm worker kept, a worker that errs kept, one that stops replaced, slow is 504 and replaced, busy is 429, no workers, no uv, the setting, and the record.
- **The page's use of it is part 4.**

## Why (evidence)

- The measurements: [docs/evaluations/fea/2026-11-10-live-solve.md](../evaluations/fea/2026-11-10-live-solve.md).
- The tests named above. Running the fixtures through `live` left them byte-identical but for the mesh study's measured solve seconds.

## Consequences

- **Easier:** an edit is answered in under a second for a strip, a bending coupon or a plate; the chat and the panels can keep the answer current (part 4).
- **Harder:**
  - Each warm worker holds the fea package in memory in the API's container.
  - Every edit is a run record (R-23).
  - The open hole's preview still takes about 3.5 s, mostly computing its fields and its Gmsh mesh.
- **We now depend on** the tool's one-line protocol, and on the API container's memory for its workers.

## How we will know it was wrong

- Hosted, a warm preview of a strip takes more than 2 s, or the API container runs out of memory with its workers.
- A preview and the full run of the same rows disagree on the answer.
- The records table grows faster from previews than R-23's controls can carry.
