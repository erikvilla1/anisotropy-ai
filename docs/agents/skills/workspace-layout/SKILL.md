---
name: workspace-layout
description: Where files go in the local workspace of the Anisotropy AI repository. Every private file lives under .local in a folder named for its purpose (sources, research, website, manual, services, notes, backup, questions). Each problem has one folder named for it with everything about it inside. An FEA coupon is .local/fea/<coupon>/ in three parts, team (what they sent), ours (specs, decks, verification, runs, latex) and documents (the packages), and its README is the case page. A homework set is .local/homework/<set>/ (provided, ours, comparison, documents), with its engine cases in ours/ and its reading in comparison/. Load before saving, moving or looking for any FEA deck, result export, comparison record, document, homework file or input file, when a new coupon or homework arrives, and before every new attempt at a problem.
version: 0.7.2
---

# Workspace layout

## When to use

Whenever a file arrives from the team or the course, whenever our tools write a deck, run, record, picture or document, and whenever you look for one. Read `project-rules` first: it decides what is committed; this skill decides where the rest sits.

## The top level (ADR-0037)

Every private file lives under `.local/`, in a folder named for its purpose; the only files at the top are `README.md` and `INDEX.md`. `.local/README.md` has the full table.

```
.local/
  fea/          FEA tests and the packages for the team (below)
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
.local/fea/<coupon>/                 one folder per coupon, named by it (X840PW-UNT-L1); never committed (ADR-0042); three parts
                                     beside its case page (ADR-0040 amendment 3)
  README.md                          the case page: case line, problem, result, audits, attempt log, where to look (ADR-0039)
  team/<date>/                       everything the team sent, exactly as received, one dated folder per delivery; never edited;
                                     also a returned audit form (<package>-audit.xlsx) and rebuilt/ (a deck rebuilt from our guide)
  ours/                              everything we built
    <coupon>.toml, <coupon>-nodal.toml   the team's build and its CalculiX twin, one [coupon] card (ADR-0038)
    decks/                           written from the specs by fea/tools/regenerate_decks.py; never edited by hand
    verification/                    how our model was checked: <coupon>-calculix.toml + .md (CalculiX), and when the team built
                                     it team-comparison.toml + .md (the manifest), <coupon>-team-summary.toml, records against
                                     the team's numbers (+ .md readings), notes/, figures/
    runs/attempt-NN_<date>/run/      the runs of try NN, the row of that number in the case page's attempt log (ADR-0039)
      kernel/                        build_model.py: our deck copy, pictures, .vtu, summary.txt
      calculix/                      run_calculix.py: .inp .dat .frd .sta (open the .frd in PrePoMax)
      team-in-calculix/              the team's deck converted by convert_to_calculix.py and run (the model is still theirs)
      abaqus/                        run_abaqus.py: our deck solved by Abaqus/Standard without the GUI, its .odb .dat .sta .msg, the CSV field
                                     reports and reactions from abaqus_extract_fields.py, and the record against the kernel (ADR-0045)
    latex/                           <coupon>.tex and figures/, the coupon document's source (docs/models/coupon.py, ADR-0041)
  documents/<date>_<coupon>/         the package that goes out, one per delivery (ADR-0043): the PDF, the audit form (its Results and
                                     Compared values sheets hold the numbers, ADR-0044), 1-team-model/ (absent without a team model),
                                     2-our-model/, 3-material/, 4-results/ (ADR-0043 amendment 2)
.local/fea/checks/<test>/runs/       our runs of the committed checks (fea/checks/<test>/); fixture plots and smoke runs go in .local/fea/checks/

.local/homework/<set>/               one folder per set (HW1 ... HW5, PRACTICE, course-reader), ADR-0040
  provided/                          what the course provided, as received (PDFs, *_Input.xlsx)
  ours/                              what we made to solve it: the engine cases (<case>.toml; those with an [expected] answer key
                                     are the set's problems, ADR-0042), corrected inputs (-fixed), scripts
  comparison/                        key-comparison.md: the set's reading, written by a person (what agrees with the key, its
                                     misprints, what the corrected inputs change); ADR-0040 amendment 1. Written by homework.py
                                     at every build (amendment 2): <case>.json per problem, the engine's output, and
                                     key-vs-engine.csv, one row per compared number
  documents/                         <set>.tex and <set>.pdf, one chapter per problem (docs/problems/homework.py)
.local/homework/course_audit.py      every problem with an answer key through the engine
```

Committed counterpart: `fea/checks/` only, the public proofs in the same shape (cases, tiny decks, the IM7/8552 regression set, the Kirsch plate). Our models of the team's coupons are never committed (ADR-0042). Every location is defined once in `fea/src/anisotropy_fea/paths.py`. Homework cases stay in `.local/homework/<set>/ours/`, never in `engine/validation/cases/` (ADR-0042); that folder holds public and constructed cases only.

## Rules

1. One coupon, one name: `.local/fea/X840PW-UNT-L1/` holds the coupon X840PW-UNT-L1, its specs, decks, records and documents carry the name, and the name is its designation (ADR-0038, ADR-0040). Dates only in `team/<date>/`, attempt folders, packages and note file names.
2. `team/<date>/` is what we compare against, exactly as received. A new version from the team goes in a new dated folder; a comparison names the version it read.
3. Every try at a problem is an attempt and a row of the case page's attempt log. When it runs something, start its folder with `fea/tools/new_attempt.py <coupon>` and pass the `--out` paths it prints (`ours/runs/attempt-NN_<date>/run/<kind>`). Never write into an earlier attempt. The engine's code is not copied. A `.frd` is kept only in the latest run of each kind; the tool deletes the earlier ones and names them. No `prompt.md` or `notes.md`: the founder found no value in them (2026-10-21); the attempt log row is the record.
4. `ours/verification/` holds how our model was checked: the CalculiX record, and when the team built the coupon the manifest, the records against the team's numbers, the team summary, notes and figures. Record paths are relative to the record (`../../team/<date>/...`).
5. `documents/` holds the packages `docs/models/coupon.py <coupon>` writes (ADR-0041, ADR-0043), one folder per delivery, `<date>_<coupon>/`, which goes to the team as it is; the LaTeX it is built from stays in `ours/latex/`. The PDF is compiled into the package, so there is one copy. The package holds the audit form `<date>_<coupon>-audit.xlsx` and no CalculiX results. The script replaces only a package this project wrote. Keep earlier packages: a returned audit form names its package. Older dated zips from before ADR-0043 may be deleted by hand.
6. Homework: one folder per set, the same name everywhere. Provided files stay unchanged in `provided/`; a corrected copy goes to `ours/` with `-fixed` in its name, and the correction is stated in the set's reading, `comparison/key-comparison.md`, which stays local like the course's files (the founder, 2026-10-23); no README per set (the founder found no value in them, 2026-10-22); the document goes to `documents/`.
7. Never commit anything under `.local/`. Our models of the team's coupons stay there too, whatever their material (ADR-0042, replacing ADR-0030 amendment 4); a public model of our own design goes to `fea/checks/<test>/`. The team's own files never move.

## Procedure: a new FEA coupon arrives

1. Name the coupon (ADR-0038: `<material>-<test>-<layup>`). Create `.local/fea/<coupon>/team/<date>/` and move the files there as received.
2. Write `team/<date>/README.md`: who made the files, when, with which software version, and what each file is. Name the material and whether its rights class is known.
3. Build our model in `.local/fea/<coupon>/ours/` (see `.local/fea/README.md`), with its identity card (`[coupon]`, ADR-0038): the team's own model of the same coupon has the same name. Seed the spec as the team seeded theirs (`mesh.y_partitions`, `mesh.y_seeds`) so every node lands on theirs, write the decks with `fea/tools/regenerate_decks.py`, run CalculiX into an attempt's `run/calculix/` and write the record.
4. Write `ours/verification/team-comparison.toml` and its reading `team-comparison.md`, run `docs/models/coupon.py <coupon>`, and hand over the package folder `documents/<date>_<coupon>/`. It writes `ours/verification/<coupon>-team-summary.toml` for the case page (local, never committed); add a row to the case page's attempt log (ADR-0039) and run `fea/tools/case_pages.py`.
5. Add any new coupon-name code to `.local/fea/README.md`; `fea/tools/case_pages.py` adds the coupon's row there.

## Procedure: every attempt (ADR-0039)

1. `uv run python tools/new_attempt.py <coupon>` from `fea/`. It makes `ours/runs/attempt-NN_<date>/run/`, NN being the next row of the attempt log.
2. Run the tools with the `--out` paths it prints. Engine code goes in the repository through a pull request.
3. Add the attempt's row to the attempt log of `.local/fea/<coupon>/README.md` (number, date, what was tried, result, outcome, evidence), then run `uv run python tools/case_pages.py --local`.

## Procedure: an attempt is accepted

1. Its record goes to `.local/fea/<coupon>/ours/verification/` (`record_from_dat.py`, with `--notes`), and the case line's accepted attempt becomes its number. The coupon's folder is the final result; nothing is copied to a `final/` folder.
2. Set the case line's status: verified when it agrees with a reference solver, validated when it agrees with test data.
3. Run `fea/tools/case_pages.py --local` and rebuild the documents that quote the record.

## Procedure: moving a coupon folder from the layout before ADR-0040 amendment 3

From `fea/`: `uv run python tools/migrate_coupon_layout.py` lists every move and rewritten path and changes nothing; show the list to the founder, then run it with `--apply`. It deletes nothing: the old PDF and zip it leaves in `documents/` are deleted by hand only if the founder agrees. Then run `tools/case_pages.py` and update each case page's 'Where to look' by hand.

## Procedure: an audit comes back (ADR-0043)

1. From `fea/`: `uv run python tools/read_audit.py <coupon> <form>.xlsx`. It refuses an incomplete, inconsistent or foreign form and names why; send the reasons back to the auditor. A form it accepts is kept as `team/<date>/<package>-audit.xlsx` and listed in the case page's audit block.
2. Add the attempt log row the audit closes, and change the case line by hand if you agree with the tool's suggestion.
3. A deck the auditor rebuilt from our guide goes in `team/<date>/rebuilt/` (one `.inp`); the next package scores it as row E2.
4. Before merging an engine change: `uv run --project fea python docs/models/coupon.py --all --check` from the repository root. It fails when a row our tools passed in a coupon's newest returned audit no longer passes.

## Procedure: a new homework arrives

1. Put the provided files in `.local/homework/<set>/provided/` unchanged.
2. Put anything we make to solve it (a corrected input, a script) in `.local/homework/<set>/ours/`; the set's document lists each problem with its engine case.
3. Turn the answer key into engine cases in `.local/homework/<set>/ours/`, numbers and a source reference only, never the problem text; they are never committed (ADR-0042).
4. Write the set's reading in `.local/homework/<set>/comparison/key-comparison.md`: what agrees with the key, what the key misprints, what each corrected input changes.
5. Build the set's document with `docs/problems/homework.py <set>` (it prints the reading) and add the set's row to `.local/homework/README.md`.

## Verification

- `git status` shows nothing under `.local/` and no `*.pdf`; nothing is left at the top of `.local/` outside its folders.
- `fea/tools/case_pages.py --check` reports every page current, and `.local/INDEX.md` shows as many attempt folders as each attempt log has rows.
- `fea/tests/test_local_tension_deck.py` finds the team deck in `.local/fea/X840PW-UNT-L1/team/<date>/` (by place, `paths.team_deck`) and the record at `.local/fea/X840PW-UNT-L1/ours/verification/tension-test-abaqus.toml` (it skips, with the reason shown, on a machine without them).
