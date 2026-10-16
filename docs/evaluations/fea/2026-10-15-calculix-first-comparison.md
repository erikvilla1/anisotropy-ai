# Evaluation: finite element chunk B, CalculiX as the independent solver and the first comparison with our kernel (ADR-0030) | 2026-10-15

- Scope: `fea/` gains `write_calculix.py` (the CalculiX-dialect deck: S8R composite shells, four-field layer lines, one `*ORIENTATION` per ply angle, ENGINEERING CONSTANTS, numeric boundaries, CalculiX print requests with COORD), `calculix.py` (`find_ccx`, `run_calculix`, `parse_dat`), `compare.py` (comparison records with provenance and the floor rule, the mapping from a `.dat` to our per-ply quantities), `tools/record_from_dat.py`, `examples/run_calculix.py`, `examples/build_model.py --target`, the conventions file, the first committed record, a CalculiX step in CI.
- Environment: Windows 11; CalculiX 2.22 from the PrePoMax v2.6.0 bundle (`C:\Tools\PrePoMax v2.6.0\Solver\ccx_dynamic.exe`, `ANISOTROPY_CCX`); one thread; `fea/uv.lock` unchanged.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` with CalculiX available

```text
586 passed in 13.60s
```

The same without CalculiX on the path: `173 passed, 2 skipped`, both skips reading "CalculiX not found: set ANISOTROPY_CCX or put ccx on PATH (docs/installation-fea-tools.md)".

From `fea/`: `uv run python examples/run_calculix.py validation/specs/unnotched-im7-8552-nodal.toml --out ../.local/calculix/unnotched`

```text
written ..\.local\calculix\unnotched\unnotched-im7-8552-nodal-ccx.inp (4021 nodes, 1250 S8R elements)
CalculiX 2.22: 1.7 s, 0 warnings; results in ..\.local\calculix\unnotched (.dat, .frd)
Grip-Top: CalculiX total force [-1.5814, 16162.2] N; kernel [1.38016e-10, 16211.7] N
Grip-Bottom: CalculiX total force [1.5814, -16162.2] N; kernel [1.02204e-10, -16211.7] N
probe node centre (node 688): CalculiX U [1.14231e-05, 0.492717]; kernel [-1.49556e-14, 0.492716]
probe node grip_corner (node 309): CalculiX U [0, 0]; kernel [0, 0]
probe element centre (element 626): CalculiX mean strain [-0.002295, 0.007283, gamma -2.597e-06]; kernel centroid [-0.002296, 0.007284, -1.598e-16]
probe element near_grip (element 286): CalculiX mean strain [-0.0002749, 0.006268, gamma -0.0002706]; kernel centroid [-0.0002653, 0.006283, -0.0003263]
equilibrium (kernel): sum of reactions [0. 0.] N
```

## The conventions, detected by running CalculiX (`fea/validation/records/_calculix-conventions.toml`)

On the unnotched coupon with `*EL PRINT ... S, E, COORD` at the centre element (64 integration points):

- **Layer order**: the first layer line is the bottom ply. The four points at the lowest z (−0.6929 mm) carry sxx 176.55, syy 266.37, sxy +191.87 MPa; the engine's ply 1 (+45) from the kernel's centre strain gives 176.70, 266.53, +192.03. The next level is the 0 ply (sxx −353.45 against −353.45), then −45 (sxy −192.11 against −192.03), then 90 (syy 1180.67 against 1180.75), and the mirror image above the midplane.
- **Integration points**: 2 per layer through the thickness at z = ply centre ± t/(2√3), 4 in plane; numbered by z level from the bottom up, four consecutive points per level.
- **Axes**: with `GLOBAL=YES` the stresses are global and each ply's `*ORIENTATION` is honoured (the ±45 plies print equal and opposite sxy).
- **Shear strain**: tensor. A one-element isotropic S8R shell with every node given u = 0.01 y printed exy = 5.000E-03 at all eight points, sxy = 263.158 MPa = G γ, reaction 5263.158 N = τ h w, all three to seven digits against the closed form.

A small two-ply-material check was not needed: the modulus contrast between the 0 and 90 plies (syy 1181 against 59 MPa) makes the mapping unambiguous.

## The first comparison record (`fea/validation/records/unnotched-im7-8552-nodal-calculix.toml`)

Reference: CalculiX 2.22, S8R, 1250 elements, 4021 nodes. Kernel: the order-1 twin on the same 1386 corner nodes (the committed `unnotched-im7-8552-nodal-abaqus.inp`). Tolerance 3 % with a floor of 2 % of each group's largest magnitude. 53 numbers compared: both grip reactions, two probe displacements, the centre element's strain, and its eight plies' stresses and strains in material axes. All agree; the largest difference is 0.3 % (the axial reaction: 16162 against 16212 N).

| Quantity at the centre element | CalculiX | Kernel | Difference |
| --- | --- | --- | --- |
| Reaction at the top grip, N | 16162.2 | 16211.7 | 0.31 % |
| Axial displacement at the centre node, mm | 0.492717 | 0.492716 | 2e-6 |
| Axial strain | 0.007283 | 0.007284 | 0.01 % |
| Ply 4 (90 deg) sigma_2, MPa | 1180.67 | 1180.75 | 0.01 % |
| Ply 1 (45 deg) tau_12, MPa | 191.87 | 192.03 | 0.08 % |

Next to the grip (element 286, the first gauge row past the tab) the two element types disagree more, and those numbers are **not** in the record: axial strain 0.006268 against 0.006283 (0.2 %), transverse strain −0.000275 against −0.000265 (3.6 %), shear strain −0.000271 against −0.000326 (20 %), the 0 ply's sigma_1 −26.5 against −25.3 MPa (4.7 %), the 45 ply's stresses within 1.9 %. The kernel's shear strain at that element's four Gauss points ranges from −0.00013 to −0.00052, so the difference is the element formulation and the sampling (one centroid value against an average of 64 points) in a gradient region, as risk R-15 foresaw. The eight-node element planned for the kernel (chunk E) is the test of that explanation.

**Agreement targets for later records**: 3 % relative with a 2 % floor at probes away from constraint corners (met here with margin); gradient-region probes are reported in the note, not in the record, until the kernel has the eight-node element.

## What the tests cover (14 new in `test_write_calculix.py`, `test_calculix.py`, `test_records.py`)

Writer: orientation names, the deck's syntax line by line (S8R connectivity, engineering constants, orientations, the eight four-field layer lines, numeric boundaries, print requests with COORD), refusals (order 1, coupled grips, force control with nodal grips), the committed CalculiX deck regenerated from its spec. Runner and parser: `find_ccx` precedence, every block of a real `.dat` fixture (`tests/fixtures/small-coupon-ccx.dat.txt`, 69 nodes, 16 S8R elements) with nodal forces summing to the printed total, malformed rows refused and tagged rows accepted, the conventions file complete, layer grouping by z. With CalculiX present: the small coupon runs in equilibrium, its reaction within 2 % of the kernel's, two integration levels per layer, points numbered by level, every ply's printed stress equal to the engine's ply stress from CalculiX's own strain (so layer order and orientation hold), and the one-element shear deck prints tensor shear. Records: the kernel reproduces the committed record, it covers reactions, displacements, strain and all eight plies, the floor rule, a changed deck digest refused, incomplete or wrong records refused, the TOML writer round-trips.

## Not run

Gmsh (chunk A2), Abaqus (unavailable), the website suites and the manual build (unaffected). CI's `apt-get install calculix-ccx` step: UNVERIFIED until the first run of this pull request's checks. PrePoMax opening the CalculiX deck and the `.frd`: the founder's check.
