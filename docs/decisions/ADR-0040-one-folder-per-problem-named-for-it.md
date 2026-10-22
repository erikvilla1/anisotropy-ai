# ADR-0040: One folder per problem, named for it, with everything about it inside

- Status: Proposed
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (coupon names for the folders, in the repository and locally; four plain-named folders inside; no share folder; benchmark documents under `.local/benchmarks/<name>/`) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/paths.py`, `docs/models/build.py`, `docs/models/team.py`, `docs/models/share.py`, [ADR-0036](ADR-0036-one-folder-per-fea-test.md), [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), [evaluation](../evaluations/fea/2026-10-21-coupon-folders.md)

## Context

The founder still found the folders hard to follow. They asked why a share folder remained, why the folders did not carry the coupon names, and where the LaTeX documents were. One problem was spread over several parents:

- **The tension coupon** sat in six places: `fea/models/tension-coupon/`, then locally `team/`, `attempts/` and `comparison/` under `.local/fea/tension-coupon/`, then `docs/models/build/` and `.local/fea/share/`.
- **HW3** sat in five places: `.local/homework/assignments/HW3/`, `.local/homework/code/HW3/`, `engine/validation/cases/se142-hw3-*`, `docs/problems/readings/` and `docs/problems/build/`.
- **The documents were built in five places:** `docs/models/build/`, `docs/problems/build/`, `docs/manual/build/`, `.local/fea/<test>/comparison/report/` and a copy in `.local/manual/`.

ADR-0038 had put the coupon's name in every title but kept the folder names, and rejected renaming the folders because ADR-0036 had set them a day earlier. The founder meant the name for the folders too.

## Options considered

1. **One folder per problem, named for it, with everything about it inside.** Chosen.
   - A coupon gets `from-team/`, `our-runs/`, `comparison/` and `documents/`; a homework set gets `provided/`, `ours/` and `documents/`.
   - Each problem's documents and the zips to send go in its `documents/`.
2. **Three folders, with the comparison merged into `documents/`.** Rejected by the founder: the comparison's inputs and notes would mix with the generated documents.
3. **Keep the folder names inside and rename only the parents.** Rejected by the founder: `team/` and `attempts/` say less than the plain names.
4. **Keep `share/` for everything that leaves.** Rejected by the founder, because it splits each coupon again.

## Decision

Option 1, in three chunks.

- **Chunk 1, the coupons:**
  - **Names.** `fea/models/<coupon>/` and `.local/fea/<coupon>/` carry the designation (X840PW-UNT-L1, X840PW-UNC-L1, X840PW-OHT-L1). So do their specs, decks and records. A test checks that each folder's name is its coupon's name.
  - **Local folders:** `from-team/<date>/` (the team's files as received), `our-runs/attempt-NN_<date>/run/` (ADR-0039), `comparison/` (manifest, local records, notes, figures) and `documents/`.
  - **`documents/`** holds every document of the coupon, written by the three scripts: the PDFs on top, their LaTeX in `latex/<document>/`, and the dated zips. `team.py`'s manifest key `zip` becomes `documents`. `share.py` writes one `<date>_<coupon>-model.zip` per coupon.
  - **Gone:** `.local/fea/share/` and the all-coupons `our-models.zip`.
  - **Paths.** `paths.py` names the four folders once (`TEAM_FILES`, `RUNS`, `COMPARISON`, `DOCUMENTS`) and gives `documents(coupon)`.
- **Chunk 2, homework:** `.local/homework/<HW>/{provided, ours, documents}`, with each problem's document built into its set's `documents/`.
- **Chunk 3, benchmarks:** `.local/benchmarks/<name>/documents/` for the textbook and constructed problems and for the IM7/8552 and Kirsch checks, and the checks' local runs.

This supersedes the naming rule of ADR-0036 (lower-case test names) and its local layout, and ADR-0038's rejection of renaming the folders. It also moves the zips of ADR-0039 from `share/` into `documents/`.

## Why (evidence)

- An inventory of `.local/fea` before and after accounts for every file:
  - 79 moved unchanged;
  - 7 edited on purpose: READMEs, the manifest and the local record's paths;
  - 11 generated documents deleted and rebuilt into `documents/`;
  - 2 superseded zips of ours deleted;
  - 1 `.frd` pruned by the attempt rule.
- The three CalculiX twins were re-run because their deck headings name the renamed spec files. Every recorded number is unchanged to 4.3e-5 relative; the largest change is in the open-hole lateral reaction, 0.00038 N against 9416 N axially.
- Tests and outputs are in the evaluation note.

## Consequences

- **One folder per coupon.** A coupon is found by its name, and its documents are next to its runs and the team's files.
- **Names in capitals.** Folder names are now in capitals, a designation, not lower-case words. A new coupon needs a designation first.
- **CI.** CI builds the coupon documents into `.local/fea/<coupon>/documents/` and uploads them from there.
- **Old references.** Older evaluation notes and ADRs cite the former names and places.

## How we will know it was wrong

Revisit if a problem's files again turn up outside its folder, or if two problems need the same name.
