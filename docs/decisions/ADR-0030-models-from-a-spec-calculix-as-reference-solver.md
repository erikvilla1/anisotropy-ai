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
- CalculiX 2.22 (PrePoMax v2.6.0 bundle) ran the generated unnotched coupon with no warnings; the conventions were detected by running it (`fea/validation/records/_calculix-conventions.toml`: first layer line is the bottom ply, two integration points per layer, points numbered by z level, global axes with per-ply orientation honoured, tensor shear strain); the first comparison record passes with the largest difference 0.3 % (reaction 16162 against 16212 N), ply stresses at the centre within 0.1 %; beside the grip the element types differ by up to 20 % on small components, reported in the note and excluded from the record ([comparison note](../evaluations/fea/2026-10-15-calculix-first-comparison.md)).
- Installation on the founder's machine done ([tools](../installation-fea-tools.md)); CI's apt step and Gmsh: UNVERIFIED until run.

## Consequences

Easier: every comparison model is reproducible from a short file and its SHA-256; one mesh goes to every solver; the founder opens the generated deck in PrePoMax or Abaqus/CAE and the results in ParaView; the team's decks remain inputs we read. Harder: two optional external tools (CalculiX, Gmsh) with version drift; a conventions file per CalculiX major version before any composite comparison; the reader must learn S8R before one deck serves both solvers; bending exists in CalculiX only until the kernel has bending. The team's grip idiom (couplings to reference nodes) is kept in the Abaqus deck but has no CalculiX counterpart with a readable reaction.

## How we will know it was wrong

If the conventions detection run gives different layer or point orders across CalculiX versions, the mapping is not stable and composite comparisons need the `.frd` route instead. If the reaction at shell constraint nodes in CalculiX does not balance (the manual's multiple-point-constraint caveat), switch to `*SECTION PRINT`. If a needed geometry cannot be built as a transfinite O-grid, add the OpenCASCADE route. If a customer's first real need is three-dimensional, the kernel stays as is and CalculiX carries it.

## Amendment 1, 2026-10-16 (plane stress for the CalculiX material)

**Context.** Our generated model of the team's fabric coupon ran in CalculiX 2.8 % stiffer than our kernel (reaction force), with the centre strains agreeing to 0.1 %; the first comparison note attributed such gaps to the bilinear-against-quadratic element difference. A note from the founder reported the team's Abaqus model at a lower maximum stress than our CalculiX run (Abaqus number as reported to us, UNVERIFIED) and proposed the cause: CalculiX expands a composite S8R into one twenty-node brick, and the through-thickness Poisson ratios of its three-dimensional law (nu13, nu23, which Abaqus LAMINA does not have) lock the plies' different thickness contractions together. Checked in the `.dat`: at the gauge centre every ply carried a through-thickness stress of about a sixth of the axial stress, positive in the 0-degree plies and negative in the 45-degree plies, and the 0-degree ply's axial stress was 9 % above classical laminate theory. The same deck rerun with nu13 = nu23 = 0 put the through-thickness stress at 1e-4 of the axial stress and the reaction force 0.10 % below the kernel (numbers for that coupon in `.local/abaqus/notes/prepomax-tension-generated-2026-10-16.md`, material not public).

**Options.** (1) A required spec key `material.transverse.plane_stress`: `true` writes nu13 = nu23 = 0 and forbids giving nu23 or nu13; `false` keeps the stated values. (2) Always write zeros: rejected, a three-dimensional comparison (chunk D bending, a future solid model) needs the real constants. (3) Silently zero them when the reference is plane stress: rejected by ADR-0003. (4) Keep the constants and loosen the agreement target: rejected, the gap is a modelling difference the spec can state, not solver noise.

**Decision.** Option 1, in the spec (`spec.py`), the converter (`TransverseChoice(plane_stress=True)`, `convert_to_calculix.py --plane-stress`) and the deck headers, which say when zeros were written. The committed IM7/8552 specs state `plane_stress = false` and keep their record (its E2 and therefore E3 are small, so the coupling barely shows: 0.3 % there). A spec compared with our kernel or with an Abaqus LAMINA model states `plane_stress = true`.

**Evidence.** `fea/tests/test_calculix.py::test_plane_stress_removes_the_through_thickness_coupling_of_calculix_composite_shells` on a made-up fabric-like material (E1 = E2 = 50 GPa, nu12 = 0.05, nu23 = 0.4, [0/45]s, the small fixture mesh): through-thickness over axial stress 0.12 with the constants given, 0.0006 with plane stress; reaction force 4768 N and 4686 N against the kernel's 4724 N (the remaining 0.8 % is the coarse-mesh element difference). The paragraph in `fea/docs/theory.md`, section 1, states the mechanism. Agreement with Abaqus itself remains UNVERIFIED until the team exports numbers.

## Amendment 2, 2026-10-18 (Abaqus field reports as a record source)

**Context.** The team exported their coupon's results from Abaqus/CAE as CSV field reports (Report > Field Output: S11, S22 and Mises at the element centroids, outer section points only) rather than the `.dat` tables or the `odbreport` text the export recipe asked for. These are the first Abaqus numbers for any coupon.

**Options.** (1) Read the CAE CSV report as a third record source (`source = "csv"`): one row per element and section point, repeated header blocks, `IntPt` must be 1, the layer read from the section-point text; a component the team did not export written as `nan` and skipped by the comparison; Mises added as a per-ply group computed by `ply_mises`. (2) Insist on the `.dat` or `.rep` routes: rejected, the team's workflow produces reports and the numbers are the same. (3) Average multi-point reports to a centroid value: rejected, refused instead until a report of that kind exists (ADR-0003).

**Decision.** Option 1: `abaqus_report.py` (`read_field_report`, `report_quantities`), `tools/record_from_report.py`, the record grammar's `nan` and `ply_mises`. A record of the team's deck stays under `.local/abaqus/comparisons/` (material not public, R-16) and is checked by `tests/test_local_tension_deck.py` when present; a committed round-trip test feeds the kernel's own numbers through the CAE format.

**Evidence.** The 2026-10-18 comparison (`.local/abaqus/notes/abaqus-csv-vs-kernel-2026-10-18.md`, numbers not public): at the gauge centre S11, S22 and Mises of the outer plies agree with the kernel to 0.07 %; over the gauge (20 to 60 mm of 80) S22 and Mises within 0.4 % and S11 within 2.2 % of its maximum; in the one element row beside each tab line, a singular corner, S11 differs by up to 24 % of its maximum and Mises by 7 % (Abaqus's peak sits at that corner, the kernel's two elements away). The reports also settle three items the export recipe had marked UNVERIFIED: values at the centroid (`IntPt` 1), `Layer = 1` is the bottom ply (`SNEG`), and the outer-ply S11, S22 are in the ply's material axes. `fea/tests/test_abaqus_report.py`: the reader, ten refusals by line, the nan mapping, and the round trip to zero disagreements at 1e-9.

## Amendment 3, 2026-10-19 (the Gmsh O-grid for open-hole coupons, chunk A2)

**Context.** Chunk A1 built rectangles with the structured mesher; the open-hole coupon (ASTM D5766 proportions) needs a mesh around a hole. The design above chose a transfinite butterfly O-grid in Gmsh over OCC plus recombination for reproducibility.

**Options.** (1) Gmsh builds the corner nodes of the O-grid blocks (four annular blocks around an inner square of `ring_ratio` hole radii, the rectangular blocks around it, split at the tab lines) and our code adds the midside nodes and finds the named sets from coordinates, the same code as the structured mesher. (2) Let Gmsh make the order-2 mesh and the physical groups: rejected, its midside nodes on the arcs would not be at the chord midpoints that `Mesh2D` checks and our S8R twin deck assumes, and the sets would depend on Gmsh's group bookkeeping. (3) Write the O-grid in NumPy without Gmsh: rejected for this chunk, Gmsh is the route for the shapes to come (notched, tapered, bonded coupons) and the plan named it.

**Decision.** Option 1: `mesher.gmsh_open_hole_plate` (`gmsh` is the optional extra `mesh`, `uv sync --extra mesh`, 4.15.2 on the founder's machine and in CI). Gmsh coordinates are rounded to 1 pm and nodes and elements are renumbered by position, so a generated deck's text does not depend on Gmsh's internal numbering or on the platform; the committed decks are checked against their specs by `tests/test_open_hole.py` whenever Gmsh is installed. The spec refuses `nx`, `ny` and tabs that would reach the inner square by name. Two specs: `open-hole-im7-8552` (the D5766 coupon, 3168 elements, with its CalculiX record) and `open-hole-isotropic-kirsch` (a wide plate, d/w = 0.05, under a force, 7056 elements, for the Kirsch validation case).

**Evidence.** `fea/tools/kirsch_hole.py` against the Kirsch closed form (Timoshenko and Goodier, chapter 4) at the kernel's centroids, far-field stress 100 MPa: the hoop stress beside the hole is 8.6 % of the far-field stress below the closed form on a coarse mesh (1484 elements), 3.5 % at 5760, 1.8 % at the committed 7056 (first layer 0.15 mm), 1.0 % at 13416, so the bilinear element converges to it; two radii out and in the far field every component is within 0.44 % of the far-field stress. The case tolerance is 2 % relative, with the three small components (a few percent of the far-field stress) left out and the reason written in the case. The CalculiX record `open-hole-im7-8552-calculix` passes at 3 % (floor 2 %) on reactions, displacements and the gauge probe; beside the hole the two formulations differ in the small strain components (reading note), which stays UNVERIFIED until chunk E.

## Amendment 4, 2026-10-20 (committed specs may cite a licensed reference; the team's coupon material is the material we prove the engine on)

**Context.** The decision above said "committed specs use public library materials" and `fea/tests/test_spec.py` admitted only `open-publisher` and `public-domain`. The team's coupon material, X840-Z60, entered the library on 2026-10-18 from Z. M. Chen's 2015 UC San Diego dissertation (Tables 3.1 and 3.2), rights class `licensed-reference`: the copy was read through the cofounder's university access and no public copy was confirmed. Until this amendment the committed tension, compression and open-hole specs used IM7/8552 as a public stand-in, and our twins of the team's coupon stayed under `.local/`.

**Options.** (1) Keep the public-only rule and the IM7/8552 stand-ins; the team's coupon never leaves `.local/`. (2) Admit any library record whose values may be cited publicly under ADR-0018, so `licensed-reference` joins the two public classes: the spec names the record, the deck header and the generated document cite it by table and page, and nothing from the source is copied. (3) Admit every library material including `user-supplied`: rejected, a customer's or a supplier's confidential data has no public citation.

**Decision.** Option 2, decided by the founder on 2026-10-20: the engine is proved on the material of the problem at hand, the team's X840-Z60 coupon, and IM7/8552 is used only when a problem calls for it. `test_spec.py` admits the three citable classes; the specs `tension-coupon-x840-nodal` and `tension-coupon-x840-coupling` (the team's 10 mm by 80 mm coupon, [0/45/-45/45/0]s of 0.1 mm plies, 15 mm tabs, 10 mm pull), their generated decks and the CalculiX record `tension-coupon-x840-nodal-calculix` with its reading note move from `.local/fea/*/tension-coupon/` into `fea/validation/`. The committed name keeps the local test name `tension-coupon` (ADR-0032). The team's own deck, results and exports remain theirs and local. The IM7/8552 specs and records already committed stay as evidence of the public ladder; no new IM7/8552 case is added unless a problem needs that material.

**Evidence.** The deck header and the document's rebuild section print the library record, its rights class and every value's table and page (`femodel.py`, `docs/models/rebuild.py`); ADR-0018's policy table allows individual recorded values with table and page for a licensed reference; the dissertation PDF is under git-ignored `References/`. Evaluation note: `docs/evaluations/fea/2026-10-20-x840-coupon-committed.md`.
