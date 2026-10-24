# ADR-0040: One folder per problem, named for it, with everything about it inside

- Status: Proposed; `fea/models/<coupon>/` is gone by [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md): each coupon's model moves into its `.local/fea/<coupon>/`, which still holds everything about it
- Date: 2026-10-21
- Decided by: Founder, 2026-10-21 (coupon names for the folders, in the repository and locally; four plain-named folders inside; no share folder; benchmark documents under `.local/benchmarks/<name>/`) | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/paths.py`, `docs/models/build.py`, `docs/models/team.py`, `docs/models/share.py`, [ADR-0036](ADR-0036-one-folder-per-fea-test.md), [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), local evaluation note `.local/notes/evaluations/fea/2026-10-21-coupon-folders.md` (ADR-0042)

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
  - **`documents/`** holds every document of the coupon, written by the three scripts: now, by ADR-0041, one document built in place (`<coupon>.tex`, `<coupon>.pdf`, `figures/`) and one dated zip. `team.py`'s manifest key `zip` becomes `documents`. `share.py` writes one `<date>_<coupon>-model.zip` per coupon.
  - **Gone:** `.local/fea/share/` and the all-coupons `our-models.zip`.
  - **Paths.** `paths.py` names the four folders once (`TEAM_FILES`, `RUNS`, `COMPARISON`, `DOCUMENTS`) and gives `documents(coupon)`.
- **Chunk 2, homework (done):**
  - `.local/homework/<set>/{provided, ours, documents}` for HW1 to HW5, PRACTICE and course-reader, with `course_audit.py` beside them.
  - One document per set (founder's choice), `docs/problems/homework.py <set>`: the physics chapter once, then one chapter per problem, built into the set's `documents/`.
  - The per-problem documents of `docs/problems/build.py` remain for the other problems and for CI.
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

## Amendment 1, 2026-10-23 (a homework set's reading stays local, in its comparison/)

**Context.** The founder found the homework layout hard to follow. A set's reading sat in `docs/problems/readings/`, away from the set. The founder also wanted it off the repository: it discusses the course's answer key and its misprints. The repository is private.

**Options.**
1. Move the reading into the set as `.local/homework/<set>/comparison/key-comparison.md`, the counterpart of a coupon's `comparison/team-comparison.md`, git-ignored. Chosen by the founder.
2. Keep it committed under `docs/problems/readings/`, reviewed in pull requests and versioned. Rejected by the founder: it is course material and stays on our machine.
3. Put it in `documents/`. Rejected for the reason option 2 of this record was: written inputs would mix with generated documents.

**Decision.** Option 1. `docs/problems/build.py` finds a homework case's reading through its set (`set_of`, moved there from `homework.py`); `homework.py` reads it under its `--root`. A document built where the note is absent, as in CI, says where it is kept instead. `docs/problems/readings/` is removed.

**Evidence.**
- The five notes were copied with identical SHA-256 digests.
- `fea/tests/test_problem_documents.py` and `fea/tests/test_homework_document.py`: 6 passed. Both read a note from a temporary set folder, so they do not need `.local/`.
- `homework.py --all`: HW2 to HW5 and course-reader built, 371 of 371 values agree, each document printing its reading from `.local/homework/<set>/comparison/key-comparison.md`.

**Consequences.** The readings lose version history and review; `.local/` is backed up only by hand. The per-problem documents CI uploads no longer print homework readings. Earlier commits keep the notes in the private repository's history.

## Amendment 2, 2026-10-23 (the engine's output of a homework set is written beside its reading)

**Context.** The founder asked where the engine's output of a homework problem is. Nothing kept it: the calculator printed to the terminal, and `pytest`, `course_audit.py` and `homework.py` computed in memory.

**Options.**
1. JSON and CSV. One `<case>.json` per problem, with the results, criteria, comparison and problems as `POST /v1/cases/solve` returns them (ADR-0024), plus the case, source, units, engine version, commit and date; and one `key-vs-engine.csv` per set, one row per compared number. Chosen by the founder.
2. CSV only: the fewest files; the full results stay in the PDF.
3. JSON only: everything, but nothing that opens in Excel.

**Decision.** Option 1, written by `homework.py` into `<root>/<set>/comparison/` at every build. A JSON that matches no current case is named in the output and left for a person to delete.

**Evidence.**
- `fea/tests/test_homework_document.py` checks three things: one JSON per HW3 case and the CSV, as many CSV rows as compared values, and the CSV's verdicts and engine values equal to the JSON's.
- `homework.py --all`: 371 rows over five sets, none failing.

**Consequences.** A homework result can be read without building the PDF or running the engine. The files are rebuilt from the cases and are never edited by hand.
