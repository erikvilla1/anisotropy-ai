---
name: workspace-layout
description: Where files go in the local workspace of the Anisotropy AI repository. Every private file lives under .local in a folder named for its purpose (sources, research, website, manual, services, notes, backup, questions). Finite element files sit in one folder per test (team files as received, our runs per solver, the comparison), with the same test name as the committed fea/models/<test>/; the zips for the team sit in one share folder; course homework sits as assignments beside the code that solves it. Load before saving, moving or looking for any FEA deck, result export, comparison record, homework file or input file, and when a new test or a new homework arrives.
version: 0.3.1
---

# Workspace layout

## When to use

Whenever a file arrives from the team or the course, whenever our tools write a deck, run, record, picture or document, and whenever you look for one. Read `project-rules` first: it decides what is committed; this skill decides where the rest sits.

## The top level (ADR-0037)

Every private file lives under `.local/`, in a folder named for its purpose; there are no loose files at the top. `.local/README.md` has the full table.

```
.local/
  fea/          FEA tests and the zips for the team (below)
  homework/     course homework (below)
  sources/      copies of what our values cite: ncamp/ nasa/ milhdbk/ cmh17/ textbook-daniel-ishai/ textbook-evidence/ course/ references/<date>/
  research/     material-audit/ qualification/, with their scripts
  website/      screenshots/ and the scripts/ that take them
  manual/       the built manual PDF, rendered pages for review, their scripts
  services/     runtime data of local services (material-monitor/monitor.sqlite)
  questions/    the founder's own engine problems
  notes/        one-pager, purge script and support request, project-docs/
  backup/       git bundles from the 2026-10-10 history purge; never delete without the founder
```

`References/` and `output/` at the repository root are gone: dated reference snapshots go to `.local/sources/references/<date>/`, a built manual to `.local/manual/`. A downloaded source document goes to the `sources/` folder of its publisher; a screenshot to `website/screenshots/`; a one-off script beside the files it reads or writes.

## The two trees inside (ADR-0036 for FEA, ADR-0032 for homework)

Both live under `.local/`, which git ignores. `.local/fea/README.md` and `.local/homework/README.md` carry the current inventory.

```
.local/fea/<test>/                   one folder per test, the same name as fea/models/<test>/ in the repository
  team/<date>/                       the team's files exactly as received, one dated folder per version they send; never edited
  runs/                              everything our tools write; safe to delete and rebuild
    kernel/                          build_model.py: our deck copy, pictures, .vtu, summary.txt
    calculix/                        run_calculix.py: .inp .dat .frd .sta (open the .frd in PrePoMax)
    team-in-calculix/                the team's deck converted by convert_to_calculix.py and run (the model is still theirs)
  comparison/                        records against the team's numbers (+ .md readings), team-comparison.toml + .md, notes/, figures/, report/
.local/fea/checks/<test>/runs/       our runs of the committed checks (fea/checks/<test>/); fixture plots and smoke runs go in .local/fea/checks/
.local/fea/share/                    zips only, what leaves for the team: <test>-comparison.zip (docs/models/team.py), our-models.zip (docs/models/share.py)

.local/homework/assignments/<HW>/    what the course provided, as received (PDFs, *_Input.xlsx)
.local/homework/code/<HW>/           what we made to solve it, with a README mapping each problem to its engine case and input
```

Committed counterparts: `fea/models/<test>/` (specs, `decks/`, `records/`, README) for the models we show the team; `fea/checks/` for the proofs that are not team models (cases, tiny decks, the IM7/8552 regression set, the Kirsch plate). Every location is defined once in `fea/src/anisotropy_fea/paths.py`. Homework numbers go to `engine/validation/cases/se142-*.toml` with a source reference.

## Rules

1. One test, one name, in the repository and locally: `fea/models/tension-coupon/` and `.local/fea/tension-coupon/` are the same coupon. Lower-case, hyphens; dates only in `team/<date>/` and in note file names.
2. `team/<date>/` is what we compare against, exactly as received. A new version from the team goes in a new dated folder; a comparison names the version it read.
3. `runs/` holds only what our tools wrote. Pass `--out ../.local/fea/<test>/runs/kernel` to `build_model.py` and `--out ../.local/fea/<test>/runs/calculix` to `run_calculix.py`.
4. `comparison/` holds the records against the team's numbers and everything derived from them. Record paths are relative to the record (`../team/<date>/...`). `docs/models/build.py` writes a local record's document to `comparison/report/<record>/`.
5. `share/` holds zips only, written by the scripts; nothing is unzipped there and no CalculiX results go in. A script replaces only a zip this project wrote.
6. Homework: the same folder name on both sides. Provided files stay unchanged in `assignments/`; a corrected copy goes to `code/` with `-fixed` in its name and the correction stated in the README.
7. Never commit anything under `.local/`. A model moves to `fea/models/<test>/` only when its material is a library record that may be cited (ADR-0030 amendment 4). The team's own files never move.

## Procedure: a new FEA test arrives

1. Pick the test name. Create `.local/fea/<test>/team/<date>/` and move the files there as received.
2. Write `team/<date>/README.md`: who made the files, when, with which software version, and what each file is. Name the material and whether its rights class is known.
3. Build our model in `fea/models/<test>/` (see `fea/models/README.md`). Give it its coupon name and identity card (`[coupon]`, ADR-0038): the team's own model of the same coupon has the same name. Seed the spec as the team seeded theirs (`mesh.y_partitions`, `mesh.y_seeds`) so every node lands on theirs, write the decks with `fea/tools/regenerate_decks.py`, run CalculiX into `runs/calculix/` and write the record.
4. Write `comparison/team-comparison.toml` and its reading `team-comparison.md`, run `docs/models/team.py` on it, and hand over `.local/fea/share/<test>-comparison.zip`. Rerun `docs/models/share.py` so `our-models.zip` holds the new coupon.
5. Add the test's row to `.local/fea/README.md` and `fea/models/README.md`.

## Procedure: a new homework arrives

1. Put the provided files in `.local/homework/assignments/<HW>/` unchanged.
2. Create `.local/homework/code/<HW>/README.md` listing each problem, the engine case that will carry its numbers, and the input file.
3. Turn the answer key into engine cases under `engine/validation/cases/` with numbers and a source reference only; never the problem text.
4. Add the row to `.local/homework/README.md`.

## Verification

- `git status` shows nothing under `.local/` and no `*.pdf`; nothing is left at the top of `.local/` outside its folders.
- `fea/tests/test_local_tension_deck.py` finds the team deck at `.local/fea/tension-coupon/team/2026-10-16/Tension-test.inp` and the record at `.local/fea/tension-coupon/comparison/tension-test-abaqus.toml` (it skips, with the reason shown, on a machine without them).
