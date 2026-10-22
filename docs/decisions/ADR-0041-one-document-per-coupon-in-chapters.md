# ADR-0041: One document per coupon, in chapters, written to show that the engine works

- Status: Proposed
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 ("I only need the LaTeX document of the solution using our engine, the physics, everything needed to showcase to engineers or possibly investors that our engine works"; building the part in Abaqus and in our engine as separate chapters; one zip per coupon) | Drafted by: Claude Code
- Related: `docs/models/coupon.py`, `docs/models/team.py`, `docs/models/rebuild.py`, `docs/models/build.py`, `fea/tests/test_coupon_document.py`, [ADR-0031](ADR-0031-one-generated-document-per-model-comparison.md), [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md), [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md), [evaluation](../evaluations/fea/2026-10-21-coupon-document.md)

## Context

After ADR-0040, the tension coupon's `documents/` held three PDFs and two zips:
- the CalculiX record against our kernel (`build.py`, ADR-0031);
- the comparison for the team (`team.py`, ADR-0035);
- the local Abaqus field-report record (`build.py`), which repeats part of the comparison for the team;
- a comparison zip and a model zip (`share.py`).

The founder asked why there were so many. They wanted one LaTeX document that shows engineers or investors that the engine works: the solution, the physics, and how the part is built, in Abaqus and in our engine, in separate chapters.

The pieces existed but were split, and building the part was one section that interleaved Abaqus/CAE and PrePoMax steps:
- the theory with code;
- the hand check;
- the step-by-step rebuild guide;
- the equivalence with the team's deck;
- the side-by-side;
- the CalculiX comparison.

## Options considered

1. **One document per coupon, in chapters.** It is assembled from the existing sections by a new builder and has one zip. Chosen. The order:
   1. the problem;
   2. the physics;
   3. building the part in our engine;
   4. building the part in Abaqus/CAE;
   5. our results;
   6. verification against other solvers;
   7. what it shows and what it does not;
   8. appendices.
2. **The same chapters with results and verification first.** Offered; the founder chose option 1.
3. **No zip, or keep the two zips.** Rejected by the founder in favour of one zip.

## Decision

Option 1.

- **The builder.** `docs/models/coupon.py <coupon>` (or `--all`) writes into `.local/fea/<coupon>/documents/`: `<coupon>.tex` and `<coupon>.pdf` side by side with their `figures/`, and `<date>_<coupon>.zip`. The first version built in `latex/<coupon>/` and copied the PDF up; the founder saw two documents, so it is now built in place, with one copy (2026-10-22). The title page carries the coupon card and a verdict: our engine's reaction and first-ply failure, CalculiX's agreement, the team's when they built the coupon, and "not validated" with the card's test-data line.
- **The chapters reuse the existing code.** Nothing is typed by hand.
  - **Chapter 2** prints `engine/docs/theory.md` sections 1 to 3 and 5 and the whole of `fea/docs/theory.md`, each equation followed by the code that computes it. To do so, `manual.theory` gains an `only` filter for numbered sections.
  - **Chapter 4** has the team's equivalence and the rebuild guide with Abaqus/CAE steps only. `rebuild.Helpers.tools` filters the GUIs.
  - **Chapter 5** is new: our engine's solution of the team's build (coupled grips), with the reaction, the centre strains, every ply's stress and first-ply failure by each criterion of the spec.
- **The team comparison is no longer a document of its own.** `team.py` keeps the manifest, the comparison and its sections, the files it puts in the zip, and the team summary. Its command line points to `coupon.py`. The manifest loses its `documents` key.
- **The model zip.** `share.py` is removed; its zip is the coupon zip.
- **The record documents.** `build.py` stays for the checks' records (`--all` leaves out the coupons') and for any record named explicitly.
- **CI** builds the coupon documents and the checks' documents and uploads both.

## Why (evidence)

- The tension document has 79 pages with every chapter. It builds in 36 s with Tectonic, and its title page states the first ply fails at 0.0382 of the applied 10 mm pull by maximum stress.
- `fea/tests/test_coupon_document.py` covers:
  - a coupon the team has not built: seven chapters, one zip, no other document;
  - a fixture coupon with a team comparison: the team's sections and files, and the summary;
  - the refusals.
- The full test output is in the evaluation note.

## Consequences

- **One document.** A coupon has one document to send and one zip, which holds the document.
- **Length.** The physics chapter is about 25 pages and the same in every coupon document; `--no-theory` leaves it out.
- **The verdict.** A coupon's title page now says plainly when the model's loading is past first-ply failure.

## How we will know it was wrong

Revisit if readers outside engineering find the document too long to reach the verdict and results, or if a coupon needs content that fits no chapter.
