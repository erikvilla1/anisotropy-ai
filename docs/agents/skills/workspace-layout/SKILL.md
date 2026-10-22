---
name: workspace-layout
description: Where files go in the local workspace of the Anisotropy AI repository. Every private file lives under .local in a folder named for its purpose (sources, research, website, manual, services, notes, backup, questions). Each problem has one folder named for it with everything about it inside: an FEA coupon is .local/fea/<coupon name>/ (from-team, our-runs, comparison, documents), the same name as the committed fea/models/<coupon name>/ whose README is the case page; the one coupon document, its LaTeX and its zip sit in that coupon's documents/; a homework set is .local/homework/<set>/ (provided, ours, documents). Load before saving, moving or looking for any FEA deck, result export, comparison record, document, homework file or input file, when a new coupon or a new homework arrives, and before every new attempt at a problem.
version: 0.5.2
---

# Workspace layout

## When to use

Whenever a file arrives from the team or the course, whenever our tools write a deck, run, record, picture or document, and whenever you look for one. Read `project-rules` first: it decides what is committed; this skill decides where the rest sits.

## The top level (ADR-0037)

Every private file lives under `.local/`, in a folder named for its purpose; the only files at the top are `README.md` and `INDEX.md`. `.local/README.md` has the full table.

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
  projects/     customer or research problems, one folder per case with a case-page README (none yet)
  INDEX.md      every case in the four categories, written by fea/tools/case_pages.py --local
```

`References/` and `output/` at the repository root are gone: dated reference snapshots go to `.local/sources/references/<date>/`, a built manual to `.local/manual/`. A downloaded source document goes to the `sources/` folder of its publisher; a screenshot to `website/screenshots/`; a one-off script beside the files it reads or writes.

## The two trees inside (ADR-0040 for FEA, ADR-0032 for homework)

Both live under `.local/`, which git ignores. `.local/fea/README.md` and `.local/homework/README.md` carry the current inventory.

```
.local/fea/<coupon>/                 one folder per coupon, named by it (X840PW-UNT-L1), the same name as fea/models/<coupon>/
  from-team/<date>/                  the team's files exactly as received, one dated folder per version they send; never edited
  our-runs/attempt-NN_<date>/run/    the runs of try NN, the row of that number in the case page's attempt log (ADR-0039)
    kernel/                          build_model.py: our deck copy, pictures, .vtu, summary.txt
    calculix/                        run_calculix.py: .inp .dat .frd .sta (open the .frd in PrePoMax)
    team-in-calculix/                the team's deck converted by convert_to_calculix.py and run (the model is still theirs)
  comparison/                        what we compare with: team-comparison.toml + .md, records against the team's numbers
                                     (+ .md readings), notes/, figures/
  documents/                         the coupon document <coupon>.pdf (docs/models/coupon.py, ADR-0041), its LaTeX in
                                     latex/<coupon>/, and one dated zip to send: <date>_<coupon>.zip
.local/fea/checks/<test>/runs/       our runs of the committed checks (fea/checks/<test>/); fixture plots and smoke runs go in .local/fea/checks/

.local/homework/<set>/               one folder per set (HW1 ... HW5, PRACTICE, course-reader), ADR-0040
  provided/                          what the course provided, as received (PDFs, *_Input.xlsx)
  ours/                              what we made to solve it, with a README mapping each problem to its engine case and input
  documents/                         <set>.pdf, one chapter per problem (docs/problems/homework.py), its LaTeX in latex/<set>/
.local/homework/course_audit.py      every problem with an answer key through the engine
```

Committed counterparts: `fea/models/<coupon>/` (specs, `decks/`, `records/`, README) for the models we show the team; `fea/checks/` for the proofs that are not team models (cases, tiny decks, the IM7/8552 regression set, the Kirsch plate). Every location is defined once in `fea/src/anisotropy_fea/paths.py`. Homework numbers go to `engine/validation/cases/se142-*.toml` with a source reference.

## Rules

1. One coupon, one name, in the repository and locally: `fea/models/X840PW-UNT-L1/` and `.local/fea/X840PW-UNT-L1/` are the same coupon, and the name is its designation (ADR-0038, ADR-0040). Dates only in `from-team/<date>/`, attempt folders and note file names.
2. `from-team/<date>/` is what we compare against, exactly as received. A new version from the team goes in a new dated folder; a comparison names the version it read.
3. Every try at a problem is an attempt and a row of the case page's attempt log. When it runs something, start its folder with `fea/tools/new_attempt.py <coupon>` and pass the `--out` paths it prints (`our-runs/attempt-NN_<date>/run/<kind>`). Never write into an earlier attempt. The engine's code is not copied. A `.frd` is kept only in the latest run of each kind; the tool deletes the earlier ones and names them. No `prompt.md` or `notes.md`: the founder found no value in them (2026-10-21); the attempt log row is the record.
4. `comparison/` holds what we compare with: the manifest, the records against the team's numbers, notes and figures. Record paths are relative to the record (`../from-team/<date>/...`).
5. `documents/` holds the one coupon document and its zip, written by `docs/models/coupon.py <coupon>` (ADR-0041): `<coupon>.pdf`, its LaTeX in `latex/<coupon>/`, and `<date>_<coupon>.zip`. Nothing is unzipped there and no CalculiX results go in the zip. The script replaces only a zip this project wrote. Delete an older dated zip by hand once the newer one has been sent.
6. Homework: one folder per set, the same name everywhere. Provided files stay unchanged in `provided/`; a corrected copy goes to `ours/` with `-fixed` in its name and the correction stated in the README; the document goes to `documents/`.
7. Never commit anything under `.local/`. A model moves to `fea/models/<coupon>/` only when its material is a library record that may be cited (ADR-0030 amendment 4). The team's own files never move.

## Procedure: a new FEA coupon arrives

1. Name the coupon (ADR-0038: `<material>-<test>-<layup>`). Create `.local/fea/<coupon>/from-team/<date>/` and move the files there as received.
2. Write `from-team/<date>/README.md`: who made the files, when, with which software version, and what each file is. Name the material and whether its rights class is known.
3. Build our model in `fea/models/<coupon>/` (see `fea/models/README.md`), with its identity card (`[coupon]`, ADR-0038): the team's own model of the same coupon has the same name. Seed the spec as the team seeded theirs (`mesh.y_partitions`, `mesh.y_seeds`) so every node lands on theirs, write the decks with `fea/tools/regenerate_decks.py`, run CalculiX into an attempt's `run/calculix/` and write the record.
4. Write `comparison/team-comparison.toml` and its reading `team-comparison.md`, run `docs/models/coupon.py <coupon>`, and hand over `documents/<date>_<coupon>.zip`. Commit the `records/<coupon>-team-summary.toml` it writes, add a row to the case page's attempt log (ADR-0039) and run `fea/tools/case_pages.py`.
5. Add the test's row to `.local/fea/README.md` and `fea/models/README.md`.

## Procedure: every attempt (ADR-0039)

1. `uv run python tools/new_attempt.py <coupon>` from `fea/`. It makes `attempt-NN_<date>/run/`, NN being the next row of the attempt log.
2. Run the tools with the `--out` paths it prints. Engine code goes in the repository through a pull request.
3. Add the attempt's row to the attempt log of `fea/models/<coupon>/README.md` (number, date, what was tried, result, outcome, evidence), then run `uv run python tools/case_pages.py --local`.

## Procedure: an attempt is accepted

1. Its record goes to `fea/models/<coupon>/records/` (`record_from_dat.py`, with `--notes`), and the case line's accepted attempt becomes its number. The committed model folder is the final result; nothing is copied to a `final/` folder.
2. Set the case line's status: verified when it agrees with a reference solver, validated when it agrees with test data.
3. Run `fea/tools/case_pages.py --local` and rebuild the documents that quote the record.

## Procedure: a new homework arrives

1. Put the provided files in `.local/homework/<set>/provided/` unchanged.
2. Create `.local/homework/<set>/ours/README.md` listing each problem, the engine case that will carry its numbers, and the input file.
3. Turn the answer key into engine cases under `engine/validation/cases/` with numbers and a source reference only; never the problem text.
4. Build the set's document with `docs/problems/homework.py <set>` and add the set's row to `.local/homework/README.md`.

## Verification

- `git status` shows nothing under `.local/` and no `*.pdf`; nothing is left at the top of `.local/` outside its folders.
- `fea/tools/case_pages.py --check` reports every page current, and `.local/INDEX.md` shows as many attempt folders as each attempt log has rows.
- `fea/tests/test_local_tension_deck.py` finds the team deck at `.local/fea/X840PW-UNT-L1/from-team/2026-10-16/Tension-test.inp` and the record at `.local/fea/X840PW-UNT-L1/comparison/tension-test-abaqus.toml` (it skips, with the reason shown, on a machine without them).
