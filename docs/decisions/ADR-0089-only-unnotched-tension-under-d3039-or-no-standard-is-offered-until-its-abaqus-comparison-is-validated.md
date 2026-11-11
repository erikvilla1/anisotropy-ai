# ADR-0089: Only unnotched tension, under ASTM D3039 or no standard, is offered until its comparison with Abaqus is validated

- Status: Proposed
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
