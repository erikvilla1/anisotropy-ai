# ADR-0035: Our models reproduce the team's node for node, and each team test gets a short comparison with a share folder

- Status: Proposed
- Date: 2026-10-20
- Decided by: Founder, 2026-10-20 (direction); the options below await review | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/equivalence.py`, `fea/src/anisotropy_fea/side_by_side.py`, `docs/models/team.py`, spec keys `mesh.y_partitions` and `mesh.y_seeds`, [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0031](ADR-0031-one-generated-document-per-model-comparison.md), [ADR-0032](ADR-0032-local-workspace-layout-by-tool-and-test.md), [evaluation](../evaluations/fea/2026-10-20-team-comparison.md)

## Context

On 2026-10-20 the founder asked that our finite element models match what the team builds, and for a simple comparison: the team's Abaqus model, ours, our material from the library with its source, and the results side by side, with files the team can pull easily. Our generated tension coupon used evenly spaced 1 mm rows. The team's Abaqus/CAE mesh is seeded by partition (lines at 15, 35.97, 44.03 and 65 mm; 15, 21, 8, 21 and 15 rows, from their FEA report template), so the nodes differed by up to 0.03 mm and no element-by-element comparison was exact. The existing comparison document (ADR-0031) runs to dozens of pages of theory and code, which the team does not need to read.

## Options considered

Mesh:
1. Seed the structured mesher by segment, as CAE does: partition lines and a row count per segment in the spec. Every node then lands on the team's. Chosen.
2. Keep even rows and interpolate the team's values onto our elements. Rejected: an interpolated comparison tests the interpolation as much as the solver.
3. Read the team's deck and solve it directly, without our generator. Already done (ADR-0029); it does not show that our generator builds their model.

Proof that the models are the same:
1. Compare the two parsed decks item by item, matching nodes by position and elements by their corner nodes, and list names without judging them. Chosen.
2. Compare the deck files as text. Rejected: names and numbering differ, so text never matches.

The comparison:
1. A separate short document per team test, built from a manifest: equivalence table, material with citation, stress at named points, agreement over bands, maps, reaction, first-ply failure, reading, open items, file list. Chosen.
2. A `--short` mode of the ADR-0031 builder. Rejected: that document is built around a record of a reference solver's numbers on one deck; this one pairs two decks.

Handing files over:
1. A share folder per test under `.local/fea/share/<test>/`, zipped beside itself, with numbered subfolders and a README. Our results are written in the layout of the team's own Abaqus field reports, with the team's element numbers. Chosen.
2. Commit the package. Rejected for now: it holds the team's deck and Abaqus results, which are theirs to publish.

Names (part, instance, material):
1. Leave our names and list them as name-only differences. Chosen for this chunk.
2. Give the spec the team's names. Not done: the names are hard-coded across the CalculiX record tooling. A later chunk if the founder wants it.

## Decision

Option 1 in each group. The tension coupon specs `tension-coupon-x840-{coupling,nodal}` are re-seeded with the team's partitions and seeds, their decks regenerated, and the CalculiX record re-run. `deck_equivalence` proves the coupling twin is the team's model. `docs/models/team.py` builds the short document and the share folder from `.local/fea/abaqus/<test>/comparison/team-comparison.toml`. The library export now carries a source's authors, so the citation can name them.

## Why (evidence)

- With the new seeding, all 891 nodes sit within 1.87e-6 mm of the team's, the single-precision rounding of CAE coordinates. All 800 elements match one to one and 20 of 20 physical items agree. Our kernel run on both decks gives stresses that differ by 0.005 MPa against a largest stress of 17535 MPa.
- In the band from 25 to 55 mm, the team's Abaqus S11, S22 and Mises and ours agree within 0.43 %, 0.16 % and 0.20 % of each quantity's largest value.
- Our CSV in the team's layout reads back with the same element numbers, centroids, faces and instance name as the team's own report.
- Output is in `docs/evaluations/fea/2026-10-20-team-comparison.md`.

## Consequences

A team test now needs one manifest and one reading note to produce a document and a share folder. The spec gains two optional keys. Uniform meshes are unchanged, so older decks keep their text. The share folder depends on the team's field-report layout. A change in CAE's CSV columns would break both the reader and the writer, and the tests would show it. The document's stress comparison covers only what the team exports, which today is the outer plies without RF or U.

## How we will know it was wrong

Revisit if the team builds a model our spec cannot seed node for node, such as an unstructured or Gmsh mesh. Revisit if the team reports that the share folder is not what they open. Revisit if they need our deck to carry their names to run their own scripts on it.
