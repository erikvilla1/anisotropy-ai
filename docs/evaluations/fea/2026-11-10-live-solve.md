# The live solve, measured (2026-11-10)

What a call of `fea/tools/studio_tool.py live` costs, and where the time goes, before deciding how the API should run it (ADR-0086).

**Setup.**
- **Machine:** the founder's Windows 11 laptop, 16 logical processors.
- **Code:** branch `feat/live-solve` (on top of #172 and #173).
- **Runs:** three calls of each case. Wall seconds are measured at the caller; the stage seconds are the tool's own `timings.json`.
- **Cases:**
  - the public unnotched coupon at 5 mm elements (`tests/fixtures/studio/values.json`);
  - the public three-point bending coupon (`studio-bending`);
  - the public plate (`studio-plate`);
  - the public open hole, meshed by Gmsh (`fea/checks/open-hole-im7-8552`, read back to values).

## A fresh process per call

| Case | Through `uv run`, wall (s) | The venv's python, wall (s) | Imports | Check | Deck | Solve | Fields and answer | Write | In-process total (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Unnotched, 5 mm | 5.15, 4.43, 4.44 | 4.04, 4.05, 4.06 | 2.03 | 0.15 | 0.03 | 0.01 | 0.14 | 0.09 | 2.46 |
| Three-point bending | 4.86, 4.87, 4.86 | 4.54, 4.51, 4.46 | 2.05 | 0.14 | 0.02 | 0.29 | 0.20 | 0.18 | 2.89 |
| Plate | 4.93, 4.78, 4.71 | 4.42, 4.45, 4.45 | 2.03 | 0.15 | 0.03 | 0.50 | 0.07 | 0.05 | 2.84 |
| Open hole (Gmsh) | not solved: the values lacked Size from | — | 2.06 | 0.79 | 0.11 | 0.09 | 1.83 | 1.14 | 6.09 |

- The stage columns are from the venv-python calls.
- The open hole's row is one later call with the missing row added, the fields still written indented. Its fields were 13.2 MB.

**Reading.**
- The work itself (check, deck, solve, answer, writing) takes 0.4 to 0.9 s on the three strips and plates.
- Every call also pays about 2.0 s of imports, plus 1.5 to 2.0 s of starting Python and `uv` (wall minus in-process total).
- Start-up is about 80 % of a call. It exceeds both of the plan's thresholds for a warm worker: start-up over 40 % of the time, or a total over 3 s.

## A warm worker (`studio_tool.py serve`)

One process started once, ready after 2.60 s (imports 2.04 s), then answering requests one after another.

| Case | Wall at the caller, 1st and 2nd (s) | Check | Deck | Solve | Fields and answer | Write | Fields file |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Unnotched, 5 mm | 0.50, 0.44 | 0.18 | 0.04 | 0.01 | 0.17 | 0.03 | 0.5 MB |
| Three-point bending | 0.74, 0.77 | 0.12 | 0.03 | 0.36 | 0.20 | 0.05 | 0.9 MB |
| Plate | 0.89, 0.71 | 0.13 | 0.03 | 0.46 | 0.06 | 0.02 | 0.2 MB |
| Open hole (Gmsh) | 3.64, 3.36 | 0.77 | 0.17 | 0.10 | 1.92 | 0.33 | 6.4 MB |

The stage columns are from the second request.

**Reading.**
- A warm worker answers a strip, a bending coupon and a plate in 0.4 to 0.9 s. That is the "within seconds" the founder asked for.
- Writing the fields compactly halved them: the strip's from 1.0 to 0.5 MB, the open hole's from 13.2 to 6.4 MB.
- The open hole is the slow case.
  - Most of it is computing the fields and the answer on its fine mesh (1.9 s).
  - Next is the Gmsh mesh in the check (0.8 to 1.1 s).
  - Both are open, for a later change.

## Not measured

- **Hosted, on Cloudflare's containers:** UNVERIFIED until the next deploy. The live test (`PREVIEW_URL`) is the place.
- **Transfer of the fields to the browser, gzipped:** UNVERIFIED.
