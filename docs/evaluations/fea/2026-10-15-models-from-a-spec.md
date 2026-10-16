# Evaluation: finite element chunk A1, coupon models generated from a spec (ADR-0030) | 2026-10-15

- Scope: `fea/` gains `spec.py` (the TOML coupon spec, validation by name, SI conversion, material and plies from the engine's library), `mesher.py` (structured order-1 and order-2 quad meshes with checked invariants), `femodel.py` (the solver-neutral model: section, orientations, reference points, couplings, boundary table, consistent edge loads, probes, provenance header), `write_abaqus.py` (the deck our reader round-trips), `examples/build_model.py` and `examples/plot_model.py`, three committed specs with their generated decks. No new physics: the kernel, recovery and reader are unchanged except the `__version__` constant.
- Environment: as chunk 3; `fea/uv.lock` unchanged.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job)

```text
567 passed in 11.28s
```

(159 fea tests, 53 of them new in `test_spec.py`, `test_mesher.py`, `test_femodel.py`, `test_write_abaqus.py`; 408 engine tests.)

From `fea/`: `uv run python examples/build_model.py validation/specs/unnotched-im7-8552-nodal.toml --out ../.local/fea-models/unnotched-im7-8552-nodal` (last lines of `summary.txt`)

```text
mesh: structured, order 1, 1386 nodes, 1250 elements
node sets: Grip-Bottom 319, Grip-Top 319, Edge-Left 126, Edge-Right 126, Tab-Bottom-Line 11, Tab-Top-Line 11, Probe-centre 1, Probe-grip_corner 1
element sets: Tab-Bottom 280, Gauge 690, Tab-Top 280, Probe-centre 1, Probe-near_grip 1
layup bottom-first: [45, 0, -45, 90, 90, -45, 0, 45], ply thickness 0.18288
material IM7-8552: library im7-8552 / ncamp-im7-8552-2019-rtd-measured-v1 (record 2026-10-10.1); rights open-publisher
  E1 = 23.51 Msi (Measured mean), page 30 ... tply = 0.0072 in (Reported nominal), page 28   (ten cited values, each with its page URL)
boundary conditions: Grip-Bottom dofs 1..6 = 0; Grip-Top dofs 1..1 = 0; Grip-Top dofs 3..6 = 0; Grip-Top dofs 2..2 = 1
kernel solve: reaction at Grip-Top = [1.38016e-10, 16211.7] N; equilibrium residual 4.55e-10 N; largest free-dof residual 1.16e-10 N
first-ply failure, max_stress: factor 0.931786 on the applied loading, element Coupon-1.281, ply 2, transverse tension
first-ply failure, tsai_hill: factor 0.9125 ...; tsai_wu: factor 0.886424 ... (same element and ply)
```

The same spec with coupled grips (`unnotched-im7-8552-coupling`): reaction at `RF-Top` = 16211.7 N and the same first-ply failure; the two grip idioms give identical displacements (test to 1e-15). The compression coupon (`compression-im7-8552`, 3360 elements, 0.1 mm shortening): reaction −8439.74 N, first-ply failure at 1.18 of the applied loading, a 90 degree ply in longitudinal compression, in the gauge.

Generated decks committed under `fea/validation/decks/generated/`, a test regenerates each from its spec and asserts byte equality; the header names the spec file and its SHA-256, never a path, so the deck is identical from any working directory.

Figures written and viewed: `unnotched-im7-8552-nodal-model.png` (mesh with the tab and gauge element sets, the 319 gripped nodes at each end, probes, the pull arrow) and `unnotched-im7-8552-nodal-solved.png` (zero strain in the gripped tabs, uniform gauge strain, Poisson contraction, shear at the tab corners, first-ply failure marked at the first element row past the bottom tab). The `.vtu` files open in ParaView (not installed here: UNVERIFIED).

## What the tests cover

- Spec: the committed specs load, convert to SI, resolve to public library datasets with citations and strengths; conversion touches only dimensioned numbers; symmetric layups expand bottom-first; element counts from a size; twenty-one invalid specs refused by name (wrong kind keys, tab longer than the coupon, a node count that misses a tab line with the admissible counts named, nx without ny, size and counts together, empty layup, library plus explicit constants, incomplete constants, transverse constants both ways, wrong sign for the kind, zero load, maximum strain, unknown criterion, Tsai-Wu without f*, f* out of range, a probe outside the coupon, a missing grips table, an unknown table, unknown units); tabs grips without tabs; compression sign; shear ±45 balance; bending key rules including the midspan node row.
- Mesher: counts, coordinates, default and named sets, bands, order-2 midside nodes once per edge in the S8R order, the corner twin, every invariant refusal (clockwise, repeated node, out-of-range, duplicate coordinates, misplaced midside, order mismatch, bad set), nearest node and element.
- Model: nodal grips on whole tabs (319 nodes each, 280-690-280 elements), coupled grips with reference points and couplings, line grips, force control as consistent edge loads (corners half shares; 1/6, 2/3, 1/6 on eight-node edges) summing to the total, unbuilt kinds refused naming the planned chunk, the compression mesh.
- Writer: ten-digit numbers with decimal points; deterministic text; round trip through our reader with no error and no note, same coordinates and connectivity, same plies and strengths; nodal and coupled grips give the same displacements and reaction; a generated free-lateral-edge coupon reproduces the engine's mixed-solver strain and reaction to 1e-10; force control balances to 1e-6 N; order-2 decks are S8R with nine entries per element; committed decks match their specs.

## Not run

CalculiX, Gmsh, PrePoMax and ParaView: not installed (inventory 2026-10-15); their use starts in chunks A2 and B. The website suites and the manual build: unaffected. UNVERIFIED for this chunk.
