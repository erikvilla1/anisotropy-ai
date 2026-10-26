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

## Amendment 3, 2026-10-24 (no findings sheet: a failed row is the finding)

**Context.** The founder read the first forms built on the real coupons: "too much noise", and "the findings sheet is also not necessary". The Findings sheet, with its own IDs, severities, owners and statuses, repeated what the rubric row already says, and the auditor had to write the finding's ID back on the row.

**Options.**
1. Keep the Findings sheet and shorten it. Rejected by the founder.
2. A failed row is the finding. The auditor writes what was found in the row's Observation and picks its Cause (engine, our input, their model, documentation or tolerance) beside it; whether the failure fails the audit is the row's `required` flag, so severities are not needed. Chosen.

**Decision.** Option 2. The words on the form are now: results Pass, Fail, N/A, Not checked; verdicts Pass, Pass with observations, Fail; causes as before. Severities and statuses are gone. The verdict: Fail if a required row fails; Pass with observations if any other row fails or an observation is written; Pass otherwise; no verdict while a required row has no result other than Not checked (`audit.verdict_of` and the cover's formula, both pinned by `fea/tests/test_audit.py`). A row that fails must name its cause; `read_form` refuses one that does not. The case page's audit block lists the failed rows and the number of observations where it listed findings. Workflow step 4 above now reads: every failed row gets a cause.

**Evidence.** The founder's words of 2026-10-24. No returned form has used the Findings sheet (none has come back), so nothing is lost. `cd fea && uv run pytest`: 366 passed on 2026-10-24 (`tests/test_audit.py` alone: 48). The rule as a formula, recalculated in Excel 16 through COM on the tension coupon's rebuilt form with the auditor's entries scripted: as built "no verdict yet: 7 required row(s) have no result other than Not checked"; every auditor row Pass, "Fail" (A2 fails as built, because the tree had uncommitted changes); A2 scripted to Pass, "Pass"; plus an observation on B3, "Pass with observations"; B6 set to Fail, "Fail"; E1 cleared, "no verdict yet: 1 required row(s)"; 0 formula errors in every scenario.

## Amendment 4, 2026-10-24 (rubric 0.3: the evidence is the claim the team verifies; our values where the team's are missing)

**Context.** The founder read the v0.3 form on the tension coupon. Row A2 (the files identified by digest, commit and attempt) was "too complicated to follow"; A3's evidence cited ADR-0002 and the SI conversion where "just the unit system" was wanted; B1's largest node offset and the "team as written" wording were things "our team won't be reading or make sense of". The rule the founder gave: evidence is what needs to match, and the team verifies that it is true. And the team sent only S11, S22 and Mises, yet our model gives every other quantity: the rubric should state our values (the reaction, the displacements and strains, the first-ply failure, S12) and leave the team's side blank, "since that is the team's job to try to validate".

**Options.**
1. Keep A2 and simplify its words. Rejected by the founder ("I don't need A2"): the digest, the commit and the attempt stay on the form's Record sheet and the case page, where the tools read them.
2. Rubric 0.3. A2 is removed and the unit row becomes A2, with the unit system of each deck and of the audit as its whole evidence. Every equivalence item is written as a claim: the shared value once when the decks agree ("Nodes: 891 on the part, 2 reference points", "Node positions: the same, node for node"), both values only when they differ; no offsets, no "as written". An `auto` item whose team value is not in the export (C1, C4, C7; C2 and C3 when one of their quantities is missing, S12 today) states our value and is judged by the auditor; a reported quantity outside the tolerance still fails the row ("Judged by: auditor" on the form, the Result open), with the line "Team: left blank, for the team to validate against its own model". Chosen.

**Decision.** Option 2, confirmed by the founder on 2026-10-24. `audit._claim` writes the B rows; `audit._facts` computes our reaction at the top grip from `report.gripped_groups` and the centre element for every coupon, so C1 and C4 state our values with or without a laminate-theory check; `_our_largest_in_band` gives our largest |S12| in the graded band from `side_by_side.ply_values`. A scorer returns a result of None to hand a row to the auditor; the form writes "auditor" in Judged by for every such row, so the digest covers only the rows our tools decided. `NOT_REGRESSIONS` is empty: nothing in 0.3 is about how a package was built. The to-send list on the cover still names C1, C4, C7 and E2. Row B8 is the one exception to the single-value style, at the founder's request: it lists the team's boundary conditions and loads and then ours in full (`audit._boundary_lines`), each reference point by its position and set name with its prescribed dofs in Abaqus/CAE's names, so the two sides are read against each other. Section E, documentation (E1 to E4), is off the rubric for now, at the founder's request ("might not be important for right now"); its scorer and the reading of a rebuilt deck stay in the code, dormant. Each section carries a `meaning` for the cover, and B3 no longer cites a decision record.

**Evidence.** The founder's words of 2026-10-24. `cd fea && uv run pytest`: 366 passed on 2026-10-24; `tests/test_audit.py::test_the_scores_say_why` pins the B1 claim, the unit row's text, the absence of offsets and "as written", our S12 in the band, our reaction and displacement lines and the blank team line, and `test_the_same_model_with_the_same_stresses_scores_pass_where_our_tools_judge` pins which rows are the auditor's. The tension coupon's package was rebuilt with rubric 0.3.

## Amendment 5, 2026-10-25 (one gauge element for the hand check, the results and rows C4, D1 and D5; D5 states the laminate's shear coupling)

**Context.** The first reviews of the three X840 packages by the document reviewer ([ADR-0047](ADR-0047-a-read-only-peer-review-subagent-for-generated-documents.md), amendment 1) found the hand check, the results chapter and rows C4, D1 and D5 reading their values at the element whose centroid is nearest the coupon's centre. On the open-hole coupon that element is at the edge of the hole: the hand check set a local value beside a free edge against laminate theory with no verdict, and the results chapter showed it as the coupon's state. On the compression coupon a tie between equally distant centroids picked a neighbour of the spec's centre probe, which is the element the CalculiX record compares, so the hand check's reference column was empty. D5's evidence offered the shear strain at that element as the sign of in-plane coupling, beside an "unbalanced" layup whose A16 is zero: for a ply as stiff across its fibres as along them (E1 = E2), the 45-degree ply's Q16, which is (Q11 - Q22)/4, vanishes. The coupons' numbers stay in their local packages (ADR-0042).

**Options.**
1. Keep the element nearest the centre and state where it is. Rejected: on an open-hole coupon it is a local value at a free edge, which laminate theory does not describe and the record does not hold.
2. One rule for every reader, `report.gauge_element`: the spec's centre probe; when the coupon's centre lies in no element (an open hole), the far-field probe; failing both, the element nearest the centre, as before. Chosen: the record compares exactly these probes, and on an open-hole coupon the far field is where a strain gauge is read.
3. Reword row C4 ("at the gauge centre") for open-hole coupons. Not needed: the evidence names the element, where it is and why it was chosen, so the rubric's text and its version (0.3) stay.

For D5: the evidence adds the laminate's in-plane shear coupling from our engine's stiffness, A16 and A26 against A11, stated as none (below 1e-9 of A11) or present with its share; when an unbalanced layup has none because its plies have E1 = E2, it says so; and it says that shear strain the model still shows comes from the grips' hold on the width.

**Decision.** Option 2 and the D5 evidence, drafted by Claude Code to fix the reviewers' findings, which the founder asked to have fixed ("fix it all", 2026-10-25); the rule itself is not yet confirmed by the founder. `report.GaugeElement` carries the element, its centroid, the basis and whether the centre is in a hole; `LaminateCheck.gauge` replaces `centre_element`; `audit.gauge_text` says where the element is for the form and the chapter. Row D1 states its measure: the largest difference as a share of the largest laminate-theory strain, and of the largest laminate-theory ply stress. Row C1 says whether the reaction is tension or compression; row C7 leads with the earliest of the spec's criteria and names the others.

**Evidence.** On the public open-hole check (`fea/checks/open-hole-im7-8552`) the rule picks the far-field probe, which its record compares, and our engine there is within 1 % of laminate theory along the coupon: `fea/tests/test_report.py::test_the_gauge_element_of_an_open_hole_coupon_is_its_far_field_probe`. `test_without_probes_the_gauge_element_is_the_one_nearest_the_centre`, `fea/tests/test_audit.py::test_the_scores_say_why` (D5 states the coupling of an unbalanced IM7 layup as present) and `fea/tests/test_documents_for_the_team.py` pin the rest. On each of the three X840 coupons the rule picks a probe its CalculiX record holds (checked locally on 2026-10-25; the numbers stay local, ADR-0042).
