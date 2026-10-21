# Evaluation: our tension coupon matches the team's node for node, and a short comparison with a share folder (ADR-0035) | 2026-10-20

- Scope: spec keys `mesh.y_partitions` and `mesh.y_seeds`, with `spec.row_coordinates` and the `ys` argument of `mesher.structured_rectangle`. The tension coupon specs carry the team's partitions (15, 35.97, 44.03, 65 mm) and seeds (15, 21, 8, 21, 15), taken from their FEA report template and confirmed against `Tension-test.inp`. Their decks are regenerated and the CalculiX record and its reading note are re-run. New modules: `equivalence.deck_equivalence` and `side_by_side` (`pair_reports`, `agreement`, `kernel_difference`, `ply_values`), plus `abaqus_report.write_field_report`. New script `docs/models/team.py`, with the manifest and reading under `.local/fea/abaqus/tension-coupon/comparison/`. `LibraryMaterial.authors` comes through the library export, and the LaTeX converter maps the section sign. New tests: `test_equivalence.py`, `test_side_by_side.py`, `test_team_document.py`, seeding cases in `test_spec.py` and `test_mesher.py`, and a local case in `test_local_tension_deck.py`.
- Branch: `feat/team-comparison`, stacked on `feat/validation-x840-coupon` (PR #61).
- Environment: Windows 11, uv 0.13, Python 3.12; CalculiX 2.22 from the PrePoMax v2.6.0 bundle; Tectonic; Node for the website tests.

## Commands and captured output

The team's node rows against the planned seeding, from `Tension-test.inp` (scratch script):

```text
unique x 11 unique y 81
planned rows 81 max |team - planned| mm 1.8714285801024744e-06
```

From `fea/`: `uv run python examples/run_calculix.py validation/specs/tension-coupon-x840-nodal.toml --out ../.local/fea/calculix-prepomax/tension-coupon/ours`

```text
CalculiX 2.22: 3.1 s, 0 warnings; results in ..\.local\fea\calculix-prepomax\tension-coupon\ours (.dat, .frd)
Grip-Top: CalculiX total force [0.0410718, 105884] N; kernel [-1.34605e-09, 105993] N
probe element centre (element 395): CalculiX mean strain [-0.07728, 0.2018, gamma 1.237e-06]; kernel centroid [-0.07731, 0.2019, 1.068e-06]
probe element near_grip (element 165): CalculiX mean strain [-0.02981, 0.1789, gamma 0.008496]; kernel centroid [-0.02884, 0.1782, 0.008446]
```

The deck that ran is byte-identical to the committed `tension-coupon-x840-nodal-ccx.inp`. `tools/record_from_dat.py` wrote the record with `{'rf': 2, 'u': 1, 'strain': 1, 'ply_stress_local': 1, 'ply_strain_local': 1}`.

From the root: `uv run --project fea python docs/models/team.py .local/fea/abaqus/tension-coupon/comparison/team-comparison.toml`

```text
equivalence: 20 of 20 items the same; largest node offset 1.87e-06 mm; 800 elements matched
free length: S11 752/1000 agree, largest difference 23.802 %; S22 936/1000 agree, largest difference 4.063 %; Mises 920/1000 agree, largest difference 7.173 %
inner: S11 600/600 agree, largest difference 0.425 %; S22 600/600 agree, largest difference 0.160 %; Mises 600/600 agree, largest difference 0.200 %
Document written to ...\comparison\report\tension-coupon-comparison\tension-coupon-comparison.pdf
Share folder written to ...\.local\fea\share\tension-coupon and zipped to ...\.local\fea\share\tension-coupon.zip
```

The document prints our kernel on both decks: the largest stress difference is 0.00516 MPa against a largest stress of 17535 MPa. Reading `ours-S22.csv` back with `read_field_report` gives the same element and layer keys, centroids, faces and instance as the team's `Test_01_S22.csv`.

From `fea/`: `uv run pytest -q`

```text
268 passed in 75.22s (0:01:15)
```

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job)

```text
705 passed in 113.91s (0:01:53)
```

From `engine/`: `uv run pytest -q` gives `437 passed in 40.89s`. From the root: `npm run export:library`, then `npm test` gives 71 pass and 0 fail, and `npm run typecheck` is clean. From `api/`: `uv run pytest -q tests/test_library_api.py` gives `5 passed in 1.84s`.

`docs/models/build.py fea/validation/records/tension-coupon-x840-nodal-calculix.toml --no-pdf` gives `69 numbers compared, 69 agree`.

## What the numbers show

- With the team's seeding, our generated coupon is the team's model: every node within 2e-6 mm, every element on the same nodes, and the same layup, material constants, couplings, boundary conditions and step.
- Against the team's Abaqus field reports, every value agrees within 0.43 % of its quantity's largest value from 25 to 55 mm. The differences beside the tab lines, up to 23.8 % for S11 in the corner element, are at the singular tab-line corner (reading note beside the manifest).
- The PDF was rendered to page images and read: 10 pages, the tables, the citation with its author, the mesh figure and the three maps.

## Not run, UNVERIFIED

- Opening our Abaqus deck in Abaqus/CAE through File, Import, Model. The click path in the README and the document is not checked; no Abaqus licence here.
- Opening the share folder's files on the team's machines, including Excel's reading of the CSVs.
- The team's reaction force, displacement, inner plies, S12 and strains: not exported.
- The Linux CI run of the new tests.
