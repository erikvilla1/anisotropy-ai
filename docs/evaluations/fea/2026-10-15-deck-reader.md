# Evaluation: finite element chunk 1, the Abaqus deck reader (ADR-0029) | 2026-10-15

- Scope: the new `fea/` package reads the subset of the Abaqus input format coupon decks from Abaqus/CAE use, refuses everything else by line number, converts to SI from a stated unit system, and builds engine plies from composite shell sections. No solver yet; no number is computed.
- Environment: Windows 11, Python 3.12 through uv 0.13, `fea/uv.lock` (NumPy, SciPy 1.18.1, Pydantic 2, the engine as an editable path dependency). A team coupon deck (Abaqus/CAE 2026) copied into `.local/`, git-ignored.

## Commands and captured output

From `fea/`: `uv sync --locked`

```text
Checked 17 packages in 1ms
```

From `fea/`: `uv run pytest -q -ra tests`

```text
57 passed in 0.48s
```

The local-deck test ran (the team deck is present on this machine); on a machine without it the test is skipped with the reason shown, so CI will report 56 passed, 1 skipped.

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (what the new CI job runs)

```text
465 passed in 29.56s
```

From `fea/`: `uv run python examples/deck_summary.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa`. The first lines below are from a re-run on 2026-10-23, after the fixture's size, layup and names became generic (ADR-0042); the rest is the 2026-10-15 output, unchanged by that:

```text
part 'Strip': 27 nodes, 16 S4R elements, 0 node sets, 1 element sets
  shell section on 'Layup-A-1': composite, symmetric, 10 plies, orientation Ori-1
   angles bottom-first: 0, 30, -30, 30, 0, 0, 30, -30, 30, 0
assembly: 1 instance(s), 2 reference node(s), 7 node sets, 3 element sets, 3 surfaces
material 'IM7-8552': LAMINA E1 162096 E2 8963.18 nu12 0.316 G12 4688.43 with *Fail Stress
coupling 'Grip-Top': reference Assembly.1 drives 3 nodes, dofs [1, 2, 3, 4, 5, 6]
coupling 'Grip-Bottom': reference Assembly.2 drives 3 nodes, dofs [1, 2, 3, 4, 5, 6]
step 'Step-1': linear static, 12 boundary entries, 0 concentrated loads
ignored keywords: line 8: *preprint, line 127: *restart, line 128: *output, line 129: *output
note: line 106: reference node Assembly.2 is listed inside its own coupled set 's_Bottom'; it is dropped from the coupled nodes
```

Run on the team's deck as well, with its material values withheld; that output stays in a local note (ADR-0042). Every keyword in it was read or listed as ignored, and its couplings grip whole tab regions, so the membrane kernel treats each region as a rigid translation of its reference node.

## What the tests cover

- Tokenizer: comments, blank lines, CRLF, trailing commas, parameter flags and case, repeated parameters, data before a keyword (7 tests).
- Fixtures: the gripped 2 by 8 coupon parsed field by field (counts, connectivity, `generate`, symmetric expansion to ten plies bottom-first, orientation, LAMINA values, assembly nodes, set union, surfaces, couplings, ENCASTRE expansion, the 0.8 mm pull, ignored list, SHA-256); validation notes; SI conversion and engine plies with `B` vanishing and `A16` nonzero; the one-element coupon; the isotropic homogeneous plate with an `Instance.label` target; the supported keyword list (6 tests).
- Rejections: 30 parametrized decks, each a one-line change to a fixture, refused with the expected message (unsupported element type, `nlgeom=YES`, translated instance, rotated orientation, offset, second step, unknown keyword, unknown parameter, temperature-dependent elasticity, other elastic types, nonzero rotation or out-of-plane displacement, amplitude, `z != 0`, unresolved set, element without section, out-of-plane load, `*Static` parameters, `*Shell General Section`, two sections on one element, two `*Fail Stress` lines, conflicting prescriptions, free coupled dof, free reference rotation, distributing coupling, antisymmetry boundary, surface weight, influence radius, missing node); every message names a line or the offending part or set; units missing or unknown; unfinished decks (4 tests).
- Units: the two systems, scalar round trips, refusals, deck conversion of lengths, stresses and prescribed displacements only, `m-Pa` identity with the modulus plausibility warning (9 tests).
- Local team deck: read in full, counts, the pull in SI, note, reference nodes excluded from their coupled sets (1 test, skipped when absent).

## Not run

The website suites (`npm test`, `npm run typecheck`, browser tests): no website file changed. The manual build: unaffected, the `fea/` package is not in its scope. Both UNVERIFIED for this chunk.

## UNVERIFIED against Abaqus

The layer order under `symmetric` (assumed bottom-first and mirrored, matching ADR-0004), the sign Abaqus expects for compressive limits in `*Fail Stress` (stored as written; magnitudes used), and every keyword in `docs/abaqus-export-recipe.md`. The team confirms these when they run the export.
