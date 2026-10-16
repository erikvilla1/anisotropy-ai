# ADR-0030: Coupon models are generated from a parametric spec, and CalculiX is the independent reference solver

- Status: Proposed
- Date: 2026-10-15
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: ADR-0029 (finite element phase; amendment 3 below), ADR-0001, ADR-0003, ADR-0007, ADR-0018, ADR-0021, `fea/src/anisotropy_fea/{spec,mesher,femodel,write_abaqus}.py`, `fea/validation/specs/`, [installation of the tools](../installation-fea-tools.md), risks R-15 to R-18

## Context

The founder wants finite element models created by us, with everything a model includes: mesh, sets, layup, materials, grips, loads, step and output requests, and wants to see them. ADR-0029 planned to compare our kernel with the team's Abaqus runs, but no Abaqus is available: the `C:\SIMULIA` installation on the founder's machine is a UC San Diego academic teaching licence, probably expired and in any case not for company work (inventory 2026-10-15), and the team has exported no results. CalculiX is a free solver that reads an Abaqus-style deck. The founder's choices on 2026-10-15: CalculiX is the independent reference solver beside our kernel; models come from a parametric spec in code; the first models are unnotched tension, open-hole tension, compression or in-plane shear, and three- or four-point bending. CalculiX itself creates no models; a mesher and a writer do.

Facts from the CalculiX manual that bind the design (read 2026-10-15, version 2.7 and 2.18 pages of the same manual):

- `*SHELL SECTION, COMPOSITE` is for S8R (and S6) elements only; a layer line is `thickness, <unused>, material[, orientation]`; the layer order (first line bottom or top) is not stated ([*SHELL SECTION](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node238.html)).
- An S8R is expanded into one C3D20R brick; a composite shell has two integration points per layer through the thickness; each layer's local x axis is the projection of its `*ORIENTATION` first axis onto the shell; a drilling rotation or moment is removed with a warning; reaction forces cannot be written to the `.frd` for composites ([S8 and S8R](https://www.feacluster.com/CalculiX/ccx_2.18/doc/ccx/node41.html)).
- `*KINEMATIC` constrains dofs 1 to 3 only, a `*COUPLING` surface must be face-based, and "Selecting RF on *NODE PRINT does not work for the reference node"; `*NODE PRINT` does not calculate forces induced by multiple point constraints (manual pages `*COUPLING`, `*KINEMATIC`, `*NODE PRINT`, read by the planning agent; page addresses in the plan file).
- `*ELASTIC` types are ISO, ORTHO, ENGINEERING CONSTANTS and ANISO; there is no LAMINA; ENGINEERING CONSTANTS takes `E1, E2, E3, nu12, nu13, nu23, G12, G13` and `G23, temperature` (manual page `*ELASTIC`).
- `*EL PRINT` prints in the orientation's local system by default and globally with `GLOBAL=YES`; `COORD` prints the integration point coordinates (manual page `*EL PRINT`).
- Ubuntu 24.04 packages `calculix-ccx` 2.21; PyPI `gmsh` 4.15 ships Windows and manylinux wheels; PrePoMax ships a portable Windows zip bundling CalculiX with a GUI ([PrePoMax](https://prepomax.fs.um.si/)).

## Options considered

How models are made:

1. **By hand in a GUI** (PrePoMax or Abaqus/CAE), exported as decks our tools read. Flexible; every model a manual, unversioned artefact; the structure of each deck differs.
2. **From a parametric spec in code** that generates the complete deck: reproducible, digest-stable, versioned, tested, the same mesh to every solver; costs a spec format and writers.
3. **Only the team's decks** (status quo): nothing to compare until the team exports.

The reference solver:

1. **Abaqus**: unavailable.
2. **CalculiX**: free, Abaqus-like deck, composite shells, installable in CI; S8R only for composites; grips cannot be reference-node couplings if the reaction is wanted.
3. **None**: the kernel checked only against the engine and closed forms; no independent finite element check.

Element strategy for one mesh in two solvers:

1. **Twin decks from the same corner nodes**: S4R for our kernel and Abaqus, S8R for CalculiX; the bilinear-against-quadratic difference stays in every comparison.
2. **An eight-node element in the kernel**, so one S8R deck runs everywhere; one element routine, a reader extension.

Grips in the CalculiX deck:

1. **Direct nodal constraints** on the grip node sets, reactions by `*NODE PRINT, TOTALS=YES` on those sets; our kernel already proves this equals a coupling whose reference rotations are fixed.
2. `*COUPLING`/`*KINEMATIC` to a reference node: the manual says the reference node's reaction cannot be printed.
3. `*RIGID BODY`: the manual says its reaction "will not be correct".

Out-of-plane constants, which CalculiX's three-dimensional law needs and Abaqus's LAMINA partly needs:

1. **Stated in the spec** (G13, G23, nu23, and either a declared transverse-isotropy rule or explicit E3 and nu13).
2. Silently E3 = E2, nu13 = nu12: excluded by ADR-0003.

## Decision

Option 2 for model creation, option 2 for the reference solver, option 1 now and option 2 later for the element strategy, option 1 for grips, option 1 for the out-of-plane constants. A spec (`fea/validation/specs/*.toml`, format in `fea/src/anisotropy_fea/spec.py`) names the kind, dimensions, mesh controls, layup, material (the engine's cited library or explicit constants) with its out-of-plane constants, grips (nodal or coupling; on the end rows or on the whole tabs), loading (displacement or force), probes and output requests; everything is required and every invalid combination is refused by name. `femodel.build_model` makes the solver-neutral model in SI; `write_abaqus` writes the deck our reader and Abaqus take, and the CalculiX writer, runner and `.dat` parser follow in the next chunk. Meshes come from our structured mesher now and from Gmsh for the open hole next. Committed specs use public library materials; a spec with a licensed material would be refused for committing by the tests (R-16). Chunks, in order: A1 spec, mesher, model, Abaqus writer, preview and solve (this record); A2 Gmsh open hole and the Kirsch case; B CalculiX writer, runner, parser, the conventions detection run (layer order, integration-point order, orientation, shear-strain convention) before any composite comparison, and the first comparison records; C compression and shear records; D bending in CalculiX only; E the eight-node element; later the Abaqus records when the team exports.

## Why (evidence)

- The manual pages listed in the context: they set S8R-only composites, the reaction-force limitation of couplings, the missing LAMINA type and the per-layer orientation rule.
- `fea/tests/test_write_abaqus.py`: a generated deck round-trips through our reader with no error and no note, the nodal and coupled grip models give the same displacements and reaction, a free-lateral-edge generated coupon reproduces the engine's mixed-solver strain to 1e-10, force control balances the reaction to 1e-6 N; `fea/tests/test_spec.py`: twenty-one invalid specs refused by name; results in the chunk A1 evaluation note.
- No comparison with CalculiX yet: no evidence. Agreement targets are set in the first comparison note (chunk B).
- Installation of CalculiX, Gmsh and ParaView on the founder's machine and in CI: not done yet; every step in `docs/installation-fea-tools.md` is UNVERIFIED until run.

## Consequences

Easier: every comparison model is reproducible from a short file and its SHA-256; one mesh goes to every solver; the founder opens the generated deck in PrePoMax or Abaqus/CAE and the results in ParaView; the team's decks remain inputs we read. Harder: two optional external tools (CalculiX, Gmsh) with version drift; a conventions file per CalculiX major version before any composite comparison; the reader must learn S8R before one deck serves both solvers; bending exists in CalculiX only until the kernel has bending. The team's grip idiom (couplings to reference nodes) is kept in the Abaqus deck but has no CalculiX counterpart with a readable reaction.

## How we will know it was wrong

If the conventions detection run gives different layer or point orders across CalculiX versions, the mapping is not stable and composite comparisons need the `.frd` route instead. If the reaction at shell constraint nodes in CalculiX does not balance (the manual's multiple-point-constraint caveat), switch to `*SECTION PRINT`. If a needed geometry cannot be built as a transfinite O-grid, add the OpenCASCADE route. If a customer's first real need is three-dimensional, the kernel stays as is and CalculiX carries it.
