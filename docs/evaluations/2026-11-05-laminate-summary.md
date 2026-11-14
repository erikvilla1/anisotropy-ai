# Evaluation, 2026-11-05: the engine describes the stack and evaluates first-ply failure on the response endpoint (ADR-0059)

- Scope: `engine/src/anisotropy_engine/summary.py` (thickness, symmetry, antisymmetry, balance, kind, coupling, areal mass, the failure summary); `library.py` citing `density` and `Vf`; `units.py` with `POUND_MASS`, `FOOT` and the `areal_mass` unit kind; `cases.py` reporting `total_thickness` and `areal_mass`; the validation case `library-as4-3501-stack-summary.toml`; theory Section 10; the physics card "Laminate symmetry, balance & areal mass"; the API's `summary` and `first_ply_failure` on `POST /v1/laminates/response` and `density_kg_per_m3` and `fiber_volume_fraction` on the provenance. Part 2 of the website audit plan; the home page calculator that reads these fields is a later part.
- Branch: `feat/laminate-summary`, from `origin/main` at `6704f78`, built in a worktree.

## Commands and captured output

From `engine/`, `uv run pytest`:

```text
463 passed in 50.54s
```

Of these, `tests/test_summary.py` holds 36 new checks (ten stacks for symmetry, antisymmetry and balance; ten for the kind; six for the coupling flags; roundoff of a symmetric stack is not coupling; the areal mass of eight plies of 0.125 mm at 1600 kg/m³ is 1.6 kg/m² and the three refusals name their plies; `face_of`; the failure summary equal to the direct `first_ply_failure` call per criterion, the four criteria when strain limits and f12* are given, and the three reasons it does not run) and `tests/test_library.py` two new ones (AS4/3501-6: 1600 kg/m³ and 0.63 from "1.6 g/cm³" and "63 %"; IM7/8552 NCAMP: 1580 kg/m³ and 0.573 from `density-LT` and `Vf-LT`; a record without one lists it under `not_provided`). The validation case reproduces h = 1.0 mm and ρh = 1.6 kg/m² at 1e-9 with A16 = A26 = 0; its first draft also expected `B11 = 0` and the runner reported `B11: expected 0, engine gives -9.09495e-16`, roundoff judged against its own roundoff, so the line was dropped as the validation README says.

From `fea/`, `uv run pytest -q -ra tests ../engine/tests` (the fea CI job's command, which runs the engine tests too): see the line at the end of this note.

From `api/`, `uv run pytest -q -rs`, without a test database (the worktree has no `.env`, so `TEST_DATABASE_URL` is unset):

```text
1 failed, 233 passed, 49 skipped in 98.06s (0:01:38)
```

The 49 skips are the run-record and storage tests that need `TEST_DATABASE_URL` or the S3 settings. The one failure is `tests/test_coupon_check_api.py::test_a_slow_tool_is_a_504_and_a_broken_one_a_503` (`assert (504 == 503)`), a timing test of the coupon check's stand-in tool with a 0.5 s timeout; it fails the same way on a clean checkout of `origin/main` at `6704f78` in a second worktree on this machine (`1 failed, 10 passed, 1 skipped in 15.97s`), so it is not this change. `tests/test_laminate_summary.py` (5 new tests) and the older laminate, library, curvature and case endpoint tests:

```text
92 passed in 10.85s   (tests/test_api.py tests/test_library_api.py tests/test_curvature_api.py tests/test_cases_api.py)
5 passed in 4.69s     (tests/test_laminate_summary.py)
```

From the root, `npm test` and `npm run typecheck`:

```text
tests 113, pass 112, fail 0, skipped 1
tsc --noEmit: clean
```

The physics card count is now 40 (19 in the laminate topic) and the card names `laminate_summary` (ADR-0019). The skipped test reads the course appendix from `.local/`, absent in a worktree.

The manual's theory check, `docs/manual/build.py` imported from the fea environment and `theory("anisotropy_engine")` called: every "computed by" or "checked by" sentence has its `<!-- code: … -->` marker and the listing of `summary.py` appears (`theory() ok: markers and sentences paired; LaTeX length 96961`, five listings of the new module found); `decisions()` parses ADR-0059 with its six sections. The PDF itself was not built here (LaTeX is not installed on this machine): UNVERIFIED until the `manual` CI job runs.

## Not run, UNVERIFIED

- The API tests that need PostgreSQL (`TEST_DATABASE_URL`) and the object store; CI runs them.
- The full manual build to PDF.
- The browser calculator test against this branch's API (`npm run test:calculator`); the response's older fields are unchanged and `readAnalysisResult` ignores fields it does not know, so the page is expected to pass; the CI job `calculator-browser` runs it.

## The fea run

`uv run pytest -q -ra tests ../engine/tests` from `fea/`, run again after the two citations moved to `extra_values`:

```text
2 failed, 1026 passed, 7 skipped in 359.53s (0:05:59)
FAILED tests/test_abaqus.py::test_abaqus_solves_the_public_check_deck_and_the_kernel_reproduces_the_export
FAILED tests/test_write_abaqus.py::test_every_test_folder_has_the_same_shape
```

Both failures are on `main` before this change: the first needs the Abaqus licence over the VPN, the second asserts two
check records where `fea/checks/` has held four since the bending and plate records (pull request #115, `fix/ci-red-jobs`,
changes that count to four). Every deck-writer test passes: the committed Abaqus and CalculiX decks are what their specs
write, so the deck headers are unchanged by the two new citations. The seven skips are the local coupons and the Gmsh
cases not on this machine.
