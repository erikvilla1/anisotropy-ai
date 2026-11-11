# ADR-0089: Only unnotched tension, under ASTM D3039 or no standard, is offered until its comparison with Abaqus is validated

- Status: Proposed (parts 1 and 2 built); round (a) run and compared, amendment 1; S4 for the tension deck and its CAE build, amendment 2; the team's engineers verify from the package, amendment 3
- Date: 2026-11-11
- Decided by: Founder, 2026-11-11 ("we are going to take a step back and focus on one workflow ... we will need to hide not delete all the other type of tests until we have established the first workflow and have validated so that we scale with the same workflow"; in answer to the plan's questions: the reference coupon is the D3039 IM7/8552 check, hidden "everywhere, with a switch", tension keeps "D3039 + No standard") | Drafted by: Claude Code
- Related: [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md) (the quantities compared), [ADR-0072](ADR-0072-a-coupons-test-standard-is-a-profile-of-clause-tagged-requirements-the-specimen-is-checked-against-and-a-deviation-is-reported-never-refused.md) (standard profiles), [ADR-0075](ADR-0075-a-plastic-coupon-is-one-isotropic-material-with-no-plies-cut-as-a-dog-bone-the-structured-mesh-follows-and-astm-d638-is-its-profile.md) (D638, the dog-bone), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (the workspace), [ADR-0056](ADR-0056-the-hosted-tier-runs-on-cloudflare-with-one-solver-image-r2-access-and-neon-postgres-invite-only.md) (hosted tier); `fea/src/anisotropy_fea/enabled.py`, `lib/enabled-tests.ts`, `api/src/anisotropy_api/settings.py`, `fea/checks/d3039-im7-8552/`

## Context

On 2026-11-11 the studio offered eight tests (unnotched tension, unnotched compression, open-hole tension, in-plane shear, three- and four-point bending, a plate, and the fibre tow of ASTM D4018) and four standard profiles (D3039, D638, C1869, D4018). None of them had been closed end to end against an Abaqus model with every output compared. The founder asked to step back: one test first, every FEA output (S11, S22, S12, S13, S23, von Mises, Tresca, "all of the FEA analysis") compared with Abaqus until they match, then the same workflow for each next test.

What a test list looked like before this record:

- The page's lists come from `lib/coupon-form-definition.json`, which `fea/tools/export_form_definition.py` writes from `intake.TESTS` and `standards.PROFILES`; about twenty places on the page also name tests (the chat's test buttons, its message reader, the model's offered rows, the reopen lists, the project list).
- There was no switch. A test was offered when it was on the Test row and a standard when it was in `PROFILES` (ADR-0075 kept D638 out of `PROFILES` until it was ready).
- D638 shares the kind `unnotched_tension` with D3039, so hiding by kind alone would still offer the plastic dog-bone.
- The API cannot import the fea package; every fea call is a subprocess that inherits the API's environment.

## Options considered

1. **Delete or move the other tests.** Rejected: the founder said hide, not delete; their code, checks and records are the starting point when each comes back.
2. **Hide them on the page only.** Rejected for the end state: a stored coupon, a server project, an Excel form or a direct API call would still run them. Kept as the first step (part 1), with the server's gate as part 2.
3. **A build-time flag on the site (`NEXT_PUBLIC_*`).** Rejected: the site is a static export, so both states need two builds to test, and a page could be built "all" against an API that refuses.
4. **One list in the fea package, carried to the page by the form's definition, and one switch read by the API and the fea processes, which the page asks for at run time (chosen).**

## Decision

**The list.** `anisotropy_fea.enabled` holds it: the test `unnotched tension`; the standards ASTM D3039 and no standard; the material kind `plies`; no dog-bone. D638, the isotropic material and the dog-bone rows wait with the other tests.

**The switch.** `ANISOTROPY_ALL_TESTS=on` offers every test again, for development. Unset, blank or `off` keeps the list; any other word is refused (ADR-0003). The API reads it at startup; the fea package reads it from the environment its processes inherit. The hosted tier never passes it to its containers, so it always offers tension only.

**The page.** The form's definition carries the list (its `enabled` block), never the switch, so the file is the same however it was made. The page asks `GET /v1/coupon-tests` once (`{"all": bool}`) and offers the list until the API says all: before the answer, without an answer, and without an API. The shared helpers stay as they are; the places that offer a test filter through `lib/enabled-tests.ts`.

**Kept, not offered.** A project or stored coupon of a hidden test stays listed, says "not available yet" and is not sent for a check, a live solve or a run. Every hidden test's code, specs, committed checks and records stay and keep being tested.

**The server's gate (part 2).** The setup check refuses a hidden test, standard, material kind or dog-bone by row, with the switch off; so do the tow calculation, reopening a stored coupon and a run by name. Specs, decks, records and naming read every kind.

**Validated, and what comes back next.** The unnotched tension coupon is validated when, for the D3039 IM7/8552 check, both rounds agree with Abaqus: (a) our generated deck run in Abaqus, compared element by element; (b) the coupon built by hand in Abaqus/CAE with the same seeds. Proposed acceptance: reaction within 1 %; in the gauge zone every compared quantity, every ply and every section point within 1 % (or 2 % of the group's largest for a small component); along the free length within 3 %; at the tab lines reported, not judged (ADR-0066). The founder says when it is validated. Then the next test is enabled and goes through the same steps; which one is the founder's choice.

## As built (2026-11-11, part 1)

- `fea/src/anisotropy_fea/enabled.py`: the list, `all_tests()` (the switch, read per call), `is_test_enabled`, `is_standard_enabled`, `is_material_kind_enabled`, `definition()`; `fea/tools/export_form_definition.py` writes the `enabled` block; `fea/tests/test_enabled.py`.
- API: `ALL_TESTS_VARIABLE` and `Settings.all_tests` in `settings.py`, `GET /v1/coupon-tests` in `main.py`, `CouponTests` in `schemas.py`, `api/tests/test_coupon_tests.py`; `.env.example`.
- Page: `lib/enabled-tests.ts`; `allCouponTests` in `lib/studio-api.ts`; `allTests` in the project context (`useAllTests`); filtered at the Test step and its standards, the standard card, the rail's rows and reopen list, the tow rail, the chat's test buttons, its message reader (a hidden test is answered "not available yet") and the rows offered to the model (`couponOffer(form, all)`), the check's fix-in selects, the project list, and the live solve.
- Tests: `tests/enabled-tests.test.ts`; `tests/worker-routing.test.ts` (the hosted container never gets the switch); a browser scenario of the closed list in `tests/browser/studio.spec.ts`; the nine scenarios of hidden tests turn the switch on in their stand-in API; `tests/browser/workspace.spec.ts` sees the server's open-hole project listed as not available yet.

## As built (2026-11-11, part 2)

- The setup check (`intake.check_form`) refuses, with the switch off, a hidden test on the Test row, a standard other than D3039 on the
  Standard row, one isotropic material on the Material kind row and a dog-bone on its rows, each "... is not available yet: the studio
  offers the unnotched tension coupon, under ASTM D3039 or no standard, until its comparison with Abaqus is validated". Every input passes
  through it (the Excel form, a values file, the studio's check, live solve and warm workers, `run_coupon` on a form or values file), so a
  hidden test is a blocked checklist with the row named, as any other refusal is.
- The paths that never reach the check refuse the same way: the tow calculation (`tow_test.tow_answer`, a blocked checklist),
  reopening a stored coupon (`studio_tool.py values`, which the API answers with a 422 through `coupon_jobs.NotOffered`) and a run by
  name (`run_coupon.refuse_hidden`, before anything is written). `enabled.refuse_hidden_kind` and `enabled.NotOffered` carry the rule.
- The blank Excel form lists the offered tests, standards and material kinds only (`enabled.offered_words`).
- Not gated, on purpose: `load_spec`, `spec_from_values`, the coupon names, `build_model` and `regenerate_decks`, so the committed checks,
  records and stored coupons of every kind keep loading.
- `fea/tests/conftest.py` turns the switch on for every fea test, so the hidden tests stay tested; `fea/tests/test_enabled.py` turns it off
  for the refusals. The studio's fixtures of hidden tests (`studio_tool.py fixtures`) are written with `ANISOTROPY_ALL_TESTS=on`.

## Why (evidence)

- The inventory of 2026-11-11 (the Context above): no switch existed, D638 shares the tension kind, the API runs the fea package as subprocesses (`api/src/anisotropy_api/coupon_jobs.py`, `live.py`).
- The tests of part 1 and their output are in its pull request.

## Consequences

- The studio shows one test. The hidden tests' browser scenarios keep running with the switch on, so their code stays healthy while hidden.
- A change of the switch needs an API restart: its warm workers keep the environment they started with.
- Two places hold the switch's rule (the API's settings and `anisotropy_fea.enabled`), each tested against the same words.

## How we will know it was wrong

- A hidden test reaches a check, a live solve or a run with the switch off (a test of part 2 fails, or a run record names one).
- The founder needs a hidden test before the tension comparison is validated: then the list grows by that test, through this record.

## Amendment 1, 2026-11-11 (round (a) run: our deck in Abaqus 2025, every output compared; the founder ran nothing by hand, his licence did)

**Context.** The founder connected his UCSD VPN so the Abaqus 2025 on his machine had a licence, and asked for the parts to go on. Before our deck asked Abaqus for more, `fea/tools/abaqus_detect.py` ran one deck per candidate request through datacheck and a full run: every one was accepted, and what Abaqus printed is in `fea/checks/abaqus-conventions.toml` (the section points listed under `*Element Output`; S of a shell layer is S11, S22, S33 = 0, S12, with the transverse shear as TSHR13, TSHR23; the principal stresses ordered with the zero among them; E12 the engineering shear strain; CFAILURE's indices 1/R; Tsai-Wu's f12* 0 when `*Fail Stress` gives none).

**Decision.** The deck of a tension coupon asks for every layer's middle section point in the ODB (`output.abaqus.every_layer`, written by the studio for unnotched tension and set in the D3039 check), so CAE shows every ply and the comparison reads every element. `fea/tools/abaqus_every_output.py` (under Abaqus's Python) writes, per element and layer, S11, S22, S12, Mises, Tresca, the pressure, the three principal stresses and E11, E22, E12 at the centroid with no averaging, and the reactions; `fea/tools/abaqus_compare.py` puts our kernel beside them by zone. The `.dat` reader takes Fortran's short exponent ("1.5633561-189"), which Abaqus printed; `tools/regenerate_decks.py` counts `*Element Output` and comment lines as output only when it refreshes a record's digests.

**Evidence (round (a), `fea/checks/d3039-im7-8552/README.md`).** With the deck's S4R: reaction +0.031 %; in the gauge 13784 of 13824 values within 1 % and all within 3 % (the 40 others the 0° ply's middle principal stress, about 0.05 MPa); along the free length 36032 of 36864 within 3 %. With the same deck in S4, a check of the cause: reaction +0.007 %, every gauge value within 0.0074 %, every free-length value within 0.65 %. The S4R differences outside the gauge are its reduced integration's, not our code's. Round (b), the hand-built CAE model, is the founder's next step; whether our deck writes S4R or S4 is his decision.

## Amendment 2, 2026-11-11 (the tension coupon's deck and its CAE build use S4; decided by the founder)

**Context.** Round (a) with our deck's S4R left the 0° ply's middle principal stress, about 0.05 MPa, up to 1.61 % from our kernel in the gauge, and the small transverse and shear components of the 0° and 90° plies off along the free length; the same deck in S4 agreed everywhere within 0.65 % and in the gauge within 0.0074 % (amendment 1).

**Options.** (1) Keep S4R, CAE's default, and explain the differences as its reduced integration's: rejected, every comparison would need that explanation. (2) **Write S4, full integration as our kernel's element is, and build the CAE model with S4 (chosen).**

**Decision.** The founder, 2026-11-11: "ok lets do the switch". The spec key `output.abaqus.element` (S4R unless a spec says S4) sets the deck's element for a mesh of order 1; the studio writes S4 for the tension coupon, and the D3039 check says S4. The runbook's round (b) builds with S4 (Reduced integration unticked in CAE). The odb extractor reads every value at the element's centroid, S4R's one point or S4's four brought there by Abaqus, and takes a layer's middle section point from its place in the section; `tools/run_abaqus.py` names the deck's element. Every other deck keeps S4R.

**Evidence.** The committed D3039 deck in S4, run in Abaqus/Standard 2025 on 2026-11-11: reaction +0.007 %; all 13824 gauge values within 0.0074 %; all 36864 free-length values within 0.65 % (`fea/checks/d3039-im7-8552/README.md`). Round (a)'s acceptance is met. The CalculiX record was re-pinned on its run of the same day: its values are unchanged, only the Abaqus deck's digest.

## Amendment 3, 2026-11-11 (the team's engineers verify, from the package the founder builds in the studio; decided by the founder)

**Context.** The Decision had the founder check both rounds himself, and amendment 1 ran round (a) on his licence. On 2026-11-11 he set the roles: "i will create a model through anisotropy in the browser/software then i will be exporting everything, then this will be put inside the one drive for the engineers to go and verify, my job isn't to verify it is the engineers in the team job to verify, we are the ones improving the software and getting their feedback". He also set the order: the comparison with Abaqus under the aerospace standard first, physical tests in person after. The package (ADR-0043) held our deck, the document with the steps in Abaqus/CAE, the audit form, and our S11, S22, S12 and Mises per ply. Nothing in it let an engineer compare every output Abaqus shows. Its README and audit form also named the case page's accepted attempt, which on a new coupon is attempt 01, the reading of its input, not the run that built the package.

**Options.** (1) The engineers export field reports by hand, one CSV per quantity (the document's old step), and we compare them: rejected, since the comparison would then be ours, and twelve quantities for every ply of 1488 elements by hand invite mistakes. (2) The engineers send back their ODB and we run our tools: rejected for the same reason. (3) **The package carries every output of ours and two scripts the engineer runs with Abaqus's own Python. One reads the job's ODB into the same columns. The other pairs it with ours, by element number for our deck or by position for a coupon built in CAE, and gives the verdict against this record's acceptance (chosen).**

**Decision.**
- **Words (proposed, the founder to confirm).** "Verified" means our engine agrees with Abaqus on the same model: this record's two rounds, now run by the team's engineers. "Validated" is kept for agreement with physical test data, the step after; this is the coupon document's own definition. Where this record says the Abaqus comparison is "validated", read "verified".
- **What the package carries.** For a coupon whose deck asks Abaqus for every ply's middle, which is every tension coupon of the studio and the D3039 check:
  - `4-results/ours-every-output.csv`, in the columns of `tools/abaqus_every_output.py` plus the zone;
  - `ours-every-output.json`, with the zones, our reaction at the top grip and the acceptance;
  - `5-verify/` with `abaqus_every_output.py`, `abaqus_extract_fields.py` and `compare_every_output.py`, the standard library only.
- **What the engineer reads.** The README gives the four steps: run, read the ODB, compare, send back. The document's steps in CAE say S4 with Reduced integration unticked, and the field output request lists the middle section point of every ply. The scripts replace the export by hand.
- **The attempt.** The package and its audit form name the attempt that built them.
- **OneDrive.** The founder takes the zip from the studio's Files to the team's OneDrive by hand; nothing here writes to OneDrive.
- **The audit form is unchanged** (rubric 0.3). Its rows C2 and C3 name S11, S22, S12 and Mises. Rows for the other quantities would raise the rubric's version, which needs the founder.

**Evidence.**
- **Round (a), from the team's script.** `compare_every_output.py` on round (a)'s run (`.local/fea/checks/d3039-im7-8552/runs/abaqus-round-a-s4-2026-11-11/every-output/`), beside our file for the D3039 check, reproduces amendment 2's numbers and meets all three criteria: reaction +0.007 %, gauge worst 0.0074 %, free length worst 0.65 %.
- **A part built in CAE.** The same run renumbered and moved by (-12.5, -125) mm, as a part sketched about its centre, is paired by position and gets the same verdict.
- **Tests.** `fea/tests/test_every_output.py` runs the script under a Python without site packages. `fea/tests/test_coupon_document.py` and `fea/tests/test_run_coupon.py` cover the package and the attempt it names.

