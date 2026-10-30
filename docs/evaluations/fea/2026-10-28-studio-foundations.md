# The coupon studio's foundations: the values file, the setup checklist, the fields and the API (2026-10-28)

Part 1 of the plan behind ADR-0051, on `feat/studio-foundations`. What was built is in the record's "As built" section; this note
holds the runs and their output.

## Test suites

| Suite | Command | Result |
| --- | --- | --- |
| fea + engine | `cd fea && uv run python tools/case_pages.py && uv run pytest -q -ra tests ../engine/tests` | 943 passed, 2 failed in 422 s (see below) |
| api + engine, with the test database | `docker compose up -d && cd api && uv run alembic upgrade head && uv run pytest -q -ra tests ../engine/tests` | 604 passed in 52 s |
| website | `npm test`; `npm run typecheck` | 71 passed, 0 failed; `tsc --noEmit` clean |
| the form definition | `cd fea && uv run python tools/export_form_definition.py --check` | `lib/coupon-form-definition.json: current` |

The two fea failures are conditions of this machine, not of the change:

- `tests/test_abaqus.py::test_abaqus_solves_the_public_check_deck_and_the_kernel_reproduces_the_export`: the Abaqus run needs the UCSD teaching licence over the VPN (ADR-0045); the reason captured on the rerun is quoted at the end of this note.
- `tests/test_write_abaqus.py::test_every_test_folder_has_the_same_shape`: the local coupon `.local/fea/IM7UNT-UNT-L5/`, made on 2026-10-27 by the founder's end-to-end run of ADR-0050, has its CalculiX record but not yet the hand-written reading `IM7UNT-UNT-L5-calculix.md` beside it (the run tool prints "Next, by hand: the record's reading"). The test asks for one; it is the founder's to write or the coupon's to remove. Nothing on this branch touches it.

New tests on this branch, all in the counts above: `fea/tests/test_values_input.py` (28), `test_checks.py` (14), `test_fields.py` (8), `test_studio_tool.py` (6), the extended `test_intake.py` (35) and `test_run_coupon.py` (8, two with CalculiX); `api/tests/test_coupon_check_api.py` (12, one with the database) and the extended `test_coupon_jobs_api.py` (30, two with the database).

## The run tool, end to end with CalculiX

`fea/tests/test_run_coupon.py::test_a_filled_form_goes_to_its_package_in_one_command` runs `tools/run_coupon.py` on the public IM7/8552 form under a temporary root with the installed CalculiX 2.22 and `--progress`. Its console, 2026-10-28:

```
Done: attempt 02 of IM7-UNT-L1; its row is in .../fea/IM7-UNT-L1/README.md. 57 of 57 recorded values agree with CalculiX; our reaction +0.31 % from CalculiX's.
  our engine: every field and the summary, for the studio's viewer .../run/kernel/IM7-UNT-L1-fields.json
  our engine: the explanation of the result            .../run/kernel/IM7-UNT-L1-explanation.json
  the setup check of this attempt's input              .../run/studio/checklist.json
  the model the studio showed before the run           .../run/studio/preview.json
```

The progress file ended at stage "the outputs" with the eight earlier stages done and eleven files by key. The same numbers as the
form's first end-to-end run on 2026-10-25 (ADR-0046): 57 of 57, +0.31 %.

## The setup check on this machine

`uv run python tools/studio_tool.py check <values>.json --out <dir>` on the public values against the real `.local/fea` (reads only):

- With the layup code L1: `blocked: 2 pass, 1 fail, 9 pending`; the item "Who and which coupon" fails with "Layup code: L1 already names
  another stacking sequence on this machine; give another code", the naming rule of ADR-0038 as the form applies it.
- With the layup code left blank: `ready: 12 pass; IM7-UNT-L2`. Every item passed, among them "Constraints defined: bottom grip held in every
  direction (319 nodes), top grip held across the width (319 nodes), through a reference point at each end; no rigid-body motion is left",
  "Mesh quality acceptable: 1200 elements, 1331 nodes (structured mesh, order 1); aspect ratio 1.25 at worst (warns above 10) ...",
  "Reference solver installed: CalculiX 2.22 at C:\Tools\PrePoMax v2.6.0\Solver\ccx_dynamic.exe" and "Document builder installed: Tectonic at
  ...". The preview holds 1331 nodes, 1200 elements, the held sets Grip-Bottom and Grip-Top and the pull of 1 mm on Grip-Top.

The check took a few seconds including the `uv run` start (not timed; UNVERIFIED against the two-minute limit for a Gmsh mesh).

## What the fields hold

On the public nodal check deck (`fea/tests/test_fields.py`): every array equals the solution after unit conversion to a relative 1e-8;
the display averages equal the means over the elements sharing a node; the summary's extremes are the arrays' extremes; the first-ply
failure factor, element, ply, mode and place equal `strength_ratios` and `fpf_place`; the strength ratio of an unstressed ply (the rigidly
gripped tabs) is infinite and is written as null with a failure index of 0. Every number in the template's sentences is in the fact
sheet (`test_every_number_in_a_sentence_is_a_fact`).

## The API

With the stand-in tools: the values run as a file the tool reads, written with sorted keys; a running job's status shows its stage and the
files so far, and `files/fields` serves the fields before the job ends; a file outside the repository and the job's folder is refused; the
jobs are listed newest first; the check answers with the checklist and the preview, a slow tool is a 504 and a broken one a 503, and the
check's folder is removed afterwards. With the database: a values job is recorded by its digest and version, a check by its digest, version
and row count, never the rows; a request under the actor `studio` is recorded, which only migration 0004 allows.

## Not done here

- The page itself (part 2), the assistant (part 3), bending (part 4) and the `plate` kind (part 5).
- A run of `run_coupon.py` on the real `.local/fea` from this branch: the end-to-end run above is in a temporary root with the real
  CalculiX; the founder's coupons were not touched.
- A timing of the check on an open-hole coupon (Gmsh).

## Appendix: the Abaqus rerun

`cd fea && uv run pytest -q tests/test_abaqus.py` on 2026-10-28: 1 failed, 4 passed in 41 s. The failing solve's message file,
`unnotched-im7-8552-coupling-abaqus.msg`, holds `*** Error: Abaqus Error: License for standard is not available.`: the UCSD teaching
licence (ADR-0045) was not reachable from this machine at the time. The deck is unchanged on this branch.
