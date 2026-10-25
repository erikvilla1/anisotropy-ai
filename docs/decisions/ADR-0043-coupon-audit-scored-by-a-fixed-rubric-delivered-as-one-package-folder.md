# ADR-0043: Every coupon delivery is audited against one fixed rubric and sent as one package folder

- Status: Proposed. The rubric stays a draft until the cofounder confirms its items and tolerances.
- Date: 2026-10-23
- Decided by: Founder, 2026-10-23. The workflow is the founder's diagram, and the rubric is the cofounder's request. The founder chose both a chapter in the PDF and an Excel form. Any team member may audit. The deliverable is "per coupon package so its own folder". | Drafted by: Claude Code
- Related: `docs/audit/rubric.toml`, `fea/src/anisotropy_fea/audit.py`, `fea/tests/test_audit.py`, [ADR-0035](ADR-0035-team-models-matched-node-for-node-and-a-short-comparison-with-a-share-folder.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), [ADR-0040](ADR-0040-one-folder-per-problem-named-for-it.md), [ADR-0041](ADR-0041-one-document-per-coupon-in-chapters.md) (amended here), [ADR-0042](ADR-0042-course-keys-and-team-models-stay-off-the-repository.md)

## Context

- **The founder's loop.** An engineer builds a coupon in Abaqus. The founder runs our engine on it. The engineer audits what comes back: the decks, the document and the step-by-step Abaqus build. Then one of two things happens:
  - Pass: the case is kept as a benchmark.
  - Fail: the findings go back, the code is fixed, and the engine is run again in a new folder.
- **The cofounder's request.** An audit report scored against a rubric, so that every engineer checks the same things: geometry, layup, material, boundary conditions and stresses.
- **What exists:**
  - the item-by-item model match (`equivalence.deck_equivalence`, ADR-0035);
  - the stresses side by side, element by element (`side_by_side`);
  - the laminate theory hand check (`report.laminate_check`);
  - the coupon document with its Abaqus/CAE build guide (ADR-0041);
  - attempt folders and the case page's attempt log (ADR-0039).
- **What is missing:**
  - acceptance criteria fixed before the run;
  - a verdict finer than pass or fail;
  - a way for findings to come back that we can read;
  - a deliverable kept apart from its build files. Today `documents/` holds the LaTeX source, the figures, the PDF and a dated zip side by side.

## Options considered

1. **One versioned rubric, partly scored by our tools.** It is shown as a chapter of the coupon PDF and answered on an Excel form, and each delivery is one package folder. Chosen.
2. **A free-form findings document per audit,** as in the diagram's Findings folder. Rejected:
   - two audits would not check the same things;
   - we cannot read the findings back;
   - the founder rejected per-run notes (ADR-0039).
3. **The rubric in the PDF only, with findings by email.** Rejected by the founder, who chose both.
4. **The Excel form only.** Rejected by the founder, who chose both; engineers read the PDF.
5. **Keep the dated zip as the deliverable.** Replaced, at the founder's request, by one folder per package.
6. **A OneDrive findings folder as the record.** Rejected. OneDrive carries files to and from the team. The record stays in `.local/fea/<coupon>/`, as ADR-0039 decided against OneDrive as a record location.

## Decision

Option 1.

- **The workflow:**
  0. The coupon's acceptance criteria (the rubric version, any tolerance a coupon changes and why, and the regions left out of the comparison) are fixed before the run.
  1. The founder runs the engine. Each run is an attempt (`ours/runs/attempt-NN_<date>/`).
  2. The package goes to the team.
  3. Any team member audits it, except the person who ran that attempt.
  4. Every finding gets a cause: engine, our input, their model, documentation or tolerance. The cause decides who fixes it. A failure does not always mean a code change.
  5. A package that passes makes the case **verified**, which means it agrees with another solver. **Validated** is kept for agreement with test data.
  6. A verified coupon is re-run before every engine merge. It cannot run on CI (ADR-0042), so this is a local command.
- **The rubric,** `docs/audit/rubric.toml`, version 0.1, draft. It has five sections:
  - A, identity and traceability;
  - B, the model match;
  - C, the results match;
  - D, physics independent of both solvers;
  - E, documentation.

  Each item states:
  - the check and what counts as Pass;
  - `method`: `auto`, where our tools give the result, or `auditor`, where the auditor judges it;
  - whether a Pass verdict needs it;
  - its tolerance, in SI;
  - the tests it applies to;
  - what the team must export for it.

  `anisotropy_fea.audit.load_rubric` refuses a rubric that is incomplete or inconsistent (ADR-0003). Changing an item or a tolerance raises the version.
- **The words on the form:**
  - results: Pass, Fail, N/A, Not checked;
  - verdicts: Pass, Pass with observations, Fail;
  - severities: Blocker, Major, Minor, Observation;
  - causes, as above.

  A verdict can be given only when every required item that applies has a result other than Not checked. It is:
  - **Fail** if a required item fails, or a Blocker or Major finding is open;
  - **Pass with observations** if anything else failed or any finding is open;
  - **Pass** otherwise.
- **The package** (amends ADR-0041). The build source (`<coupon>.tex`, `figures/`) is kept in `ours/latex/` since ADR-0040 amendment 3, so `documents/` holds packages only. Each delivery is a folder, `documents/<date>_<coupon>/`, holding:
  - `README.txt`;
  - the one PDF, built straight into the folder, with an Audit chapter;
  - `<date>_<coupon>-audit.xlsx`;
  - `1-team-model/` (the team's deck; absent when the team has not built the coupon), `2-our-model/` (`abaqus/`, `calculix/`, `spec/`), `3-material/` and `4-results/` (amendment 2; before it, a coupon without a team model used `abaqus/`, `calculix/`, `spec/` and `material/`).

  The folder replaces the zip. Earlier packages stay, because a returned form names its package. What the team sends back goes in `team/<date>/` (named `from-team/` before ADR-0040 amendment 3).
- **The chunks:**
  1. this record, the rubric and its reader;
  2. scoring, the PDF chapter, the Excel form and the package folder;
  3. reading a returned form into the case page's attempt log and status;
  4. checking the deck an auditor rebuilds from our guide (E2), and the regression command.

## As built (2026-10-23)

The founder asked for every chunk to be built without commits ("keep working on what is left").

- **Chunk 2, scoring and the package.**
  - `anisotropy_fea.audit.score` takes an `Evidence`: what our tools found for one package.
    - For the 21 rows our tools judge, it gives a result and the reason.
    - For the 7 rows the auditor judges, it gives what our tools can show.
    - It maps the items of `deck_equivalence` to B1 to B9 by their whole names, and a test fails when an item has no row.
  - `write_form` writes the form:
    - a cover with the package's identity and a digest of our results;
    - the rubric sheet, with our results locked and the auditor's cells open and offering lists;
    - a findings sheet.

    The sheets are protected without a password, against accidents only.
  - `docs/models/audit.py` gathers the evidence and prints Chapter 8.
  - `coupon.py` writes the package folder, compiles the PDF into it (Tectonic `--outdir`), and adds an audit line to the title page.
- **Chunk 3, a returned form.**
  - `read_form` reads a returned form and refuses one that is incomplete or inconsistent, naming every reason. That includes a result of ours that was changed (by the digest) and a verdict other than the rule's.
  - `verdict_of` applies the rule.
  - `case_pages.file_audit` and `fea/tools/read_audit.py` refuse a form for another coupon, another team deck or an attempt the case page does not log. They keep an accepted form as `team/<date>/<package>-audit.xlsx` and add a generated `audit` block to the case page.
  - **Changed from the plan:** the tool does not edit the case line. It prints the status it suggests, because the case line and the attempt log are written by hand (ADR-0039).
- **Chunk 4, after the audit.**
  - A deck rebuilt from the guide goes in `team/<date>/rebuilt/`. It is compared with ours by `deck_equivalence`, at B1's tolerance, and scored as E2.
  - `coupon.py --check` builds each coupon again in a scratch folder. It fails when a row our tools passed in the newest returned audit no longer passes. A2 is not counted, because it records how a package was built, not what the engine computes.

## Why (evidence)

- The founder's decisions of 2026-10-23, listed above.
- Most items need no new physics:
  - B1 to B9 are the checks `deck_equivalence` already makes;
  - C2 and C3 are `side_by_side.agreement`;
  - D1 is `report.laminate_check`;
  - D2 is `MembraneSolution.total_reaction`.

  The reader refuses a `source` that names no function, so the rubric cannot point at code that does not exist.
- **The tolerances:**
  - B4, B5 and B8 use the relative tolerance that `deck_equivalence` applies (`equivalence.RELATIVE`, 1e-9), and a test keeps the two equal.
  - B1 uses the tension coupon's node tolerance, 1e-5 mm. Abaqus/CAE writes coordinates in single precision.
  - C uses 1 %, the agreement fraction in the tension coupon's manifest. Whether 1 % suits other coupons: no evidence yet.
  - D3 and D4 use 2 %, from the convergence study of the isotropic open hole ([evaluation](../evaluations/fea/2026-10-19-gmsh-open-hole.md)).
  - D1 at 0.5 % and D2 at 1e-6: no evidence yet.
- **Not required yet** (`required = false`, pending the cofounder):
  - C1, C4 and C7 need exports the team does not send today: the reaction force, U and E, and failure indices.
  - D3 and D4 are not built.
  - E2 costs the auditor a rebuild in Abaqus/CAE.
- **Tests, 2026-10-23:**
  - `cd fea && uv run pytest`, on main after ADR-0042 and without `.local/`, as on CI: 321 passed, 25 skipped;
  - `tests/test_audit.py`: 45;
  - `tests/test_coupon_document.py`: 8, one of which runs only where the coupons are local;
  - `tools/case_pages.py --check`: every page current.
- **What the draft tolerances found on public data:**
  - On the grips fixture (2 by 8 elements), the centre element's strain is 2.4 % and its ply stresses 2.95 % from laminate theory, so D1 fails at the proposed 0.5 %.
  - The fixture's deck types the material to two decimals in MPa, and our library carries more digits, so B5 fails at 1e-9. That is the difference B5 exists to show, and the evidence now gives its size.
- **The team's tension coupon, built locally:**
  - The package compiles with the PDF in the package folder.
  - B1 to B9, C2 and C3 pass.
  - D1 fails at the proposed 0.5 %.
  - A2 fails, because the build came from uncommitted changes.

  The figures stay local (ADR-0042). Whether D1's 0.5 % suits a coupon whose tabs hold the width is for the cofounder to decide; the tolerance is not changed after seeing the result.

## Consequences

- **Easier.** Every audit checks the same items. The `auto` items cost the auditor no time. A returned form can be read back. A failure points at its cause.
- **Harder.** A change to the rubric means a new version, and earlier audits stay scored against the version they used. Several items wait on the team's exports.
- **We depend on** the team filling in the form, and on `openpyxl` (already an engine dependency, ADR-0015) to write and read it.

## How we will know it was wrong

- Returned forms leave most required items Not checked.
- Two auditors give different results for an `auto` item of the same package.
- Engineers stop filling in the Excel form and send findings another way.
- A verified coupon breaks after an engine change, and the regression command did not catch it.

## Amendment 1, 2026-10-24 (rubric 0.2: the hand check's tolerance and reach; confirmed by the founder)

**Context.** The first packages built on the real coupons scored D1, the laminate-theory hand check at the gauge centre, as Fail on both tension-type coupons: 0.93 % from free-edge laminate theory on the tension coupon (free length 5.0 widths) and 10.2 % on the compression coupon (free length 1.1 widths: 13 mm between 63.5 mm tabs on a 12 mm wide coupon), against the proposed 0.5 %. Both decks pass the equilibrium check, and the tension coupon passes the solver comparison. The cause is physical, not numerical: the coupled grips hold the width at the ends, so the Poisson contraction that free-edge theory assumes is suppressed near them, and the effect fades with distance from the grips. Free-edge theory describes a gauge centre only where that distance is long compared with the width. The cofounder, who asked for the rubric, does not work on the code side, so the founder confirms it.

**Options.**
1. Keep 0.5 % and let the item fail. Rejected: it would fail every short-gauge coupon by design, which says nothing about the model.
2. Raise the tolerance until both coupons pass (11 %). Rejected: it would hide real errors.
3. Hold the hand check to the solver comparison's tolerance, 1 % (rows C2 and C3), and make it apply only where free-edge theory describes the gauge centre: a free length of at least three widths; a shorter coupon gets N/A with its distance from theory stated. The evidence states the free length in widths and the lateral section force N_x at the centre as a share of N_y, which is zero with free edges and measures the hold the grips still have there. Chosen.
4. Replace the check with laminate theory under the strain state the kernel found. Rejected: the kernel's ply stresses are that computation (`recovery.element_ply_states` calls the engine's `ply_surfaces`), so it would check nothing.

**Decision.** Option 3. Rubric version 0.2, status confirmed by the founder on 2026-10-24 ("complete it all", on the plan that proposed it). An item may carry `condition = { min_free_length_widths = n }` (`audit.Condition`); `audit.end_effect` and `audit.laminate_distance` give the numbers.

**Evidence.** The two coupons above (local packages of 2026-10-24), and the 25 by 100 mm grips fixture in `fea/tests/test_audit.py`: free length 4 widths, 2.4 % strain and 2.95 % ply stress from theory on its 2 by 8 mesh, so it still fails, as the tests expect. The threshold of three widths sits between 1.1 widths (10 %) and 5 widths (0.9 %); no other evidence yet. The 1 % was chosen knowing the tension coupon stands at 0.93 %.

## Amendment 2, 2026-10-24 (one package layout)

**Context.** The package of a coupon with a team model was written in numbered folders (`1-team-model/`, `2-our-model/`, `3-material/`, `4-results/`) and the package of a coupon without one in `abaqus/`, `calculix/`, `spec/` and `material/`: two layouts for one kind of folder. The founder asked for everything standardized.

**Decision.** Every package uses the numbered folders. Without a team model, `1-team-model/` is absent and the README says so, and `4-results/` holds `ours-all-plies.csv` (our S11, S22, S12 and Mises for every ply of every element, as with a team model, without the team's element numbers; `docs/models/team.py`, `write_all_plies`). The package list in the decision above is amended accordingly; the form of ADR-0044 points the reader at `4-results/`.
