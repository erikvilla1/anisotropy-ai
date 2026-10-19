# Evaluation: finite element chunk A2, open-hole coupons on a Gmsh O-grid (ADR-0030, amendment 3) | 2026-10-19

- Scope: `fea/` gains `mesher.gmsh_open_hole_plate` (a transfinite butterfly O-grid around a central hole through Gmsh, corner nodes only; midside nodes and named sets from the code the structured mesher uses; `Hole` set; coordinates rounded to 1 pm and numbering by position), `mesh_for_spec` routes `open_hole_tension` to it, the spec refuses `nx`/`ny`, tabs reaching the inner square and Gmsh for other kinds by name, the deck header names the hole. Specs `open-hole-im7-8552` (D5766 proportions) and `open-hole-isotropic-kirsch` with committed generated decks, the Kirsch validation case, `tools/kirsch_hole.py` (closed form at the kernel's centroids, convergence study), the CalculiX record `open-hole-im7-8552-calculix` with its reading note, `--node-probes` on `tools/record_from_dat.py`, `build_model.py` reporting the fixed grip's reaction and the true residual under force control, the `mesh` extra in CI and the `ccx -v` exit-code fix.
- Environment: Windows 11, uv 0.13, Python 3.12, `fea/uv.lock` gains `gmsh==4.15.2` under the optional extra `mesh`; CalculiX 2.22 from the PrePoMax v2.6.0 bundle through `ANISOTROPY_CCX`; Tectonic for the document.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job)

```text
647 passed in 82.84s (0:01:22)
```

(239 fea tests, 29 of them new in `test_gmsh_mesher.py` and `test_open_hole.py`; 408 engine tests. No skips: Gmsh and CalculiX were both present.)

From `fea/`: `uv run python examples/build_model.py validation/specs/open-hole-im7-8552.toml --out ../.local/fea/abaqus/open-hole-im7-8552/ours --target both` (lines of `summary.txt`)

```text
mesh: gmsh, order 1, 3356 nodes, 3168 elements
node sets: Grip-Bottom 546, Grip-Top 546, Edge-Left 153, Edge-Right 153, Tab-Bottom-Line 21, Tab-Top-Line 21, Hole 32, Probe-centre_top 1, Probe-hole_side 1, Probe-gauge 1
element sets: Tab-Bottom 500, Gauge 2168, Tab-Top 500, Probe-hole_side 1, Probe-hole_top 1, Probe-far 1
kernel solve: reaction at Grip-Top = [1.71542e-09, 15915.1] N; equilibrium residual 1.22e-09 N; largest free-dof residual 1.6e-10 N
first-ply failure, max_stress: factor 0.590055 on the applied loading, element Coupon-1.1583, ply 2, transverse tension
first-ply failure, tsai_hill: factor 0.577195 ...; tsai_wu: factor 0.551911 ... (same element and ply, beside the hole)
```

From `fea/`: `uv run python tools/kirsch_hole.py validation/specs/open-hole-isotropic-kirsch.toml` with mesh overrides, far-field stress 100 MPa, hole radius 3 mm; the hoop stress beside the hole (`hole_side`, element centroid on the net section) and the differences kernel minus Kirsch as a percentage of the far-field stress:

| Mesh (element size, nodes around the hole, radial layers, growth) | Elements | r/a of the centroid | Kirsch sigma_yy | Kernel sigma_yy | hole_side sxx, syy | hole_top sxx, syy | ring_side sxx, syy | far_side sxx, syy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 6 mm, 20, 3, 1.2 | 1484 | 1.1267 | 232.45 | 223.89 | 2.28, -8.56 | 6.60, 1.01 | -1.85, -1.22 | -0.55, 0.15 |
| 3 mm, 36, 6, 1.2 | 5760 | 1.0467 | 270.58 | 267.12 | 1.77, -3.47 | 2.62, -0.95 | -0.43, 0.21 | -0.37, 0.19 |
| 3 mm, 60, 10, 1.15 (committed) | 7056 | 1.0233 | 284.55 | 282.71 | 0.73, -1.85 | 1.20, -0.45 | 0.04, 0.44 | -0.34, 0.19 |
| 2 mm, 60, 10, 1.15 | 13416 | 1.0233 | 284.55 | 283.51 | 0.75, -1.05 | 0.61, -0.47 | -0.17, 0.38 | -0.33, 0.19 |
| 1.5 mm, 72, 12, 1.2 | 23040 | 1.0117 | 290.75 | 290.15 | 0.57, -0.59 | 0.23, -0.40 | -0.23, 0.43 | -0.32, 0.20 |

Reaction at Grip-Bottom [0, -12000] N on every mesh (the applied force). The case `open-hole-isotropic-kirsch` carries the committed mesh's values with a 2 % relative tolerance; the small components (the radial stress beside the hole, the hoop stress at its top, the transverse stress far out, each a few percent of the far-field stress) are written `nan` with the reason in the case.

From `fea/`: `uv run python examples/run_calculix.py validation/specs/open-hole-im7-8552.toml --out ../.local/fea/calculix-prepomax/open-hole-im7-8552/ours`

```text
written ...open-hole-im7-8552-ccx.inp (9880 nodes, 3168 S8R elements)
CalculiX 2.22: 9.5 s, 0 warnings
Grip-Top: CalculiX total force [-0.99759, 15862.6] N; kernel [1.71542e-09, 15915.1] N
probe node gauge (node 1061): CalculiX U [0.000137295, 0.245616]; kernel [2.60912e-13, 0.245802]
probe node hole_side (node 1691): CalculiX U [-0.0171875, 0.501001]; kernel [-0.0157717, 0.5]
probe element far (element 1011): CalculiX mean strain [-0.001562, 0.004961, gamma 7.753e-07]; kernel centroid [-0.001564, 0.004967, 2.075e-06]
probe element hole_side (element 1584): CalculiX mean strain [-0.001381, 0.01373, gamma 0.004329]; kernel centroid [-0.0034, 0.01312, 0.002856]
probe element hole_top (element 1658): CalculiX mean strain [-0.004078, 0.001072, gamma -0.0003496]; kernel centroid [-0.003844, 0.001, 0.0004622]
```

`tools/record_from_dat.py ... --tolerance 0.03 --floor 0.02 --element-probes far --node-probes gauge`: record with rf 2, u 1, strain 1, ply_stress_local 1, ply_strain_local 1; `record_disagreements` empty. From the root, `uv run --project fea python docs/models/build.py fea/validation/records/open-hole-im7-8552-calculix.toml`:

```text
57 numbers compared, 57 agree; LaTeX written ... Document written to docs/models/build/open-hole-im7-8552-calculix/open-hole-im7-8552-calculix.pdf
```

(47 pages; the closest value to its limit is the gauge node's lateral displacement at 0.93 of what the floor allows.)

## Reading

- The bilinear element converges to Kirsch's closed form at the hole: the hoop-stress error falls from 8.6 % to 0.6 % of the far-field stress over four refinements, and two radii out every component is within half a percent on every mesh but the coarsest. What remains at the committed mesh (1.8 %) is the centroid value of an element 0.15 mm thick on a gradient plus the plate's finite width (d/w = 0.05; the far field is 0.2 % above the infinite-plate value, which is the finite-width share).
- CalculiX and the kernel agree on the open-hole coupon where the field is smooth (reactions 0.3 %, gauge within 0.15 %) and differ beside the hole as the two element formulations should (the eight-node element bends with the concentration, the bilinear one gives one value per element): the record carries the smooth region, the reading note the rest, and chunk E (the eight-node element in the kernel) removes the difference.

## Not run, and UNVERIFIED

- Not run: Abaqus on either generated deck (the team has not run them); the website and API suites (no change there).
- Verified after the first CI run: the committed Gmsh decks regenerate to the same text on Ubuntu (the `fea` job's `test_open_hole.py` passed once `libglu1-mesa` was installed; the first run could not import the Gmsh wheel without it), and the `manual` job builds the open-hole document with the `mesh` extra.
- UNVERIFIED: the article number of the Kirsch solution in Timoshenko and Goodier (cited by chapter; no copy in the reference archive); opening `open-hole-im7-8552-ccx.inp` and its `.frd` in PrePoMax was not done in this session.
