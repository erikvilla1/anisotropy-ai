---
name: workspace-layout
description: Where files go in the local workspace of the Anisotropy AI repository. Finite element files sit test by test under each tool (Abaqus, CalculiX/PrePoMax) with team, ours and comparison folders; course homework sits as assignments beside the code that solves it. Load before saving, moving or looking for any FEA deck, result export, comparison record, homework file or input file, and when a new test or a new homework arrives.
version: 0.1.0
---

# Workspace layout

## When to use

Whenever a file arrives from the team or the course, whenever our tools write a deck, run, record, picture or document, and whenever you look for one. Read `project-rules` first: it decides what is committed; this skill decides where the rest sits.

## The two trees (ADR-0032)

Both live under `.local/`, which git ignores. `.local/fea/README.md` and `.local/homework/README.md` carry the current inventory.

```
.local/fea/<tool>/<test>/            tool: abaqus | calculix-prepomax
  team/                              files made by others that we compare against; never edited
  ours/                              the model our generator wrote for the same test (spec, deck, run, pictures, summary)
  comparison/                        <record>.toml, <record>.md, notes/, figures/, report/<record>/,
                                     team-comparison.toml + .md and report/<test>-comparison/ (the short document for the team)
.local/fea/share/<test>/             what we hand the team: the short PDF, their deck, our decks, our results in their CSV layout,
.local/fea/share/<test>.zip          the material record; written and zipped by docs/models/team.py, never edited by hand (ADR-0035)
.local/fea/scratch/                  regenerable output of the committed fixtures; safe to delete

.local/homework/assignments/<HW>/    what the course provided, as received (PDFs, *_Input.xlsx)
.local/homework/code/<HW>/           what we made to solve it, with a README mapping each problem to its engine case and input
```

Under each tool, `public-im7-8552/` holds the earlier builds on the public IM7/8552 material. They are a regression set, not team models (ADR-0035). `.local/fea/share/our-models/` and `our-models.zip` hold every coupon we built the team's way, written by `docs/models/share.py` from `docs/models/our-models.toml`.

Committed counterparts: `fea/validation/{specs,decks,records}` for models whose library material may be cited (ADR-0030, amendment 4); `engine/validation/cases/se142-*.toml` for homework numbers with a source reference.

## Rules

1. One test, one name, under every tool. `abaqus/tension-coupon/` and `calculix-prepomax/tension-coupon/` are the same coupon. Lower-case, hyphens, no dates in folder names; dates go in file names of notes.
2. `team/` is what we compare against. A team deck converted to another solver by us stays `team/` under that solver: the model is still theirs.
3. `ours/` is what our generator wrote. Pass `--out ../.local/fea/<tool>/<test>/ours` to `build_model.py` and `run_calculix.py`.
4. `comparison/` holds the record and everything derived from it. Record paths are relative to the record (`../team/...`, `../ours/...`). `docs/models/build.py` writes the document to `comparison/report/<record>/` by default.
5. Homework: the same folder name on both sides. Provided files stay unchanged in `assignments/`; a corrected copy goes to `code/` with `-fixed` in its name and the correction stated in the README.
6. Never commit anything under `.local/`. A local model moves to `fea/validation/` only when its material is a library record that may be cited (ADR-0029, ADR-0030 amendment 4). The team's own files never move.
7. A new coupon we build the team's way goes into `docs/models/our-models.toml`; rerun `docs/models/share.py` so the share folder holds it.

## Procedure: a new FEA test arrives

1. Pick the test name. Create `.local/fea/<tool>/<test>/team/` and move the files there as received.
2. Write `team/README.md`: who made the files, when, with which software version, and what each file is. Name the material and whether its rights class is known.
3. Build our model into `ours/` from a spec; keep the spec in `ours/` (local) or `fea/validation/specs/` (public material).
4. Write the record into `comparison/` with `fea/tools/record_from_report.py` (Abaqus CSV field reports) or `fea/tools/record_from_dat.py` (CalculiX `.dat`), then the document with `docs/models/build.py`.
5. When the team built the model, seed our spec as they seeded theirs (`mesh.y_partitions`, `mesh.y_seeds` from their partitions and seeds) so every node lands on theirs. Then write `comparison/team-comparison.toml` and its reading `team-comparison.md`, and run `docs/models/team.py` on it. Hand over `.local/fea/share/<test>.zip`.
6. Add the test's row to `.local/fea/README.md`. Mirror the folder under the other tool when that side exists.

## Procedure: a new homework arrives

1. Put the provided files in `.local/homework/assignments/<HW>/` unchanged.
2. Create `.local/homework/code/<HW>/README.md` listing each problem, the engine case that will carry its numbers, and the input file.
3. Turn the answer key into engine cases under `engine/validation/cases/` with numbers and a source reference only; never the problem text.
4. Add the row to `.local/homework/README.md`.

## Verification

- `git status` shows nothing under `.local/`, `output/` or `References/` and no `*.pdf`.
- `fea/tests/test_local_tension_deck.py` finds the team deck at `.local/fea/abaqus/tension-coupon/team/Tension-test.inp` and the record beside it (it skips, with the reason shown, on a machine without them).
