# anisotropy-fea

The finite element layer (ADR-0029). It reads the Abaqus input decks the team builds for coupon models and solves them on the engine's laminate stiffness with its own membrane kernel, so the two can be compared number for number. The theory behind every number is in [docs/theory.md](docs/theory.md), with the function that computes each equation.

## Run

```powershell
cd fea
uv sync --locked
uv run pytest -q -ra tests ../engine/tests
uv run python examples/deck_summary.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
uv run python examples/solve_deck.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
uv run python examples/plot_deck.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa --out ../.local/fea/scratch/plots
```

`export_vtk.py` writes the solved model as a `.vtu` file for ParaView (points: displacement, reaction; cells: strains, section forces, failure indices with the worst ply, every ply's material-axis stresses), so the result can be rotated, probed and coloured like in any finite element tool. `plot_deck.py` draws the mesh and deformed shape, the three strain fields, the axial section force and the first-ply-failure map as one PNG (matplotlib, a development dependency). Write the pictures of a team deck to `.local/`, never into the repository.

The team's own decks go in `.local/fea/abaqus/<test>/team/` (git-ignored; their materials may be proprietary; layout in ADR-0032 and the `workspace-layout` skill). `tests/test_local_tension_deck.py` runs against `.local/fea/abaqus/tension-coupon/team/Tension-test.inp` when it is there and is skipped, with the reason shown, when it is not.

## Units

An Abaqus deck carries no units. `read_deck(path, units)` requires `units` to be `"mm-MPa"` or `"m-Pa"` and converts coordinates, thicknesses, moduli, strengths, prescribed displacements and loads to SI base units on entry (ADR-0002). A missing or unknown statement is refused (ADR-0003). When a converted modulus falls outside 1 GPa to 1000 GPa the reader warns that the statement is probably wrong.

## What is read, and what is refused

The subset is exactly what the team's Abaqus/CAE coupon decks use. Anything else raises `DeckError` with the line number; nothing is skipped silently. Output requests (`*Preprint`, `*Restart`, `*Output`, `*Node Print`, `*El Print`, `*Node Output`, `*Element Output` and their relatives) cannot change the solution, so they are skipped and listed in `Deck.ignored_keywords`.

| Keyword | Read | Refused |
| --- | --- | --- |
| `*Heading`, `*Part` / `*End Part` | stored; one or more parts | nested parts |
| `*Node` | `label, x, y[, z]` in a part or in the assembly (reference points) | `nset=`, non-rectangular `system=`; any `z != 0` (the membrane is flat) |
| `*Element, type=` | `S4`, `S4R`, `S4R5`; `label, n1, n2, n3, n4`; `elset=` | every other type |
| `*Nset`, `*Elset` | `instance=`, `internal`, `generate`; multi-line lists; a repeated name is one set | `unsorted` |
| `*Orientation` | the global axes `1,0,0, 0,1,0` with rotation `3, 0.` or none | any other axes, rotation, `system=`, `definition=` |
| `*Shell Section` | `composite` with layer lines `t, nip, material, angle[, name]` and `symmetric`; or `material=` with `t[, nip]` | `offset`, `nodal thickness`, `*Shell General Section`, `*Membrane Section`, `*Solid Section` |
| `*Material` / `*Elastic` | `type=LAMINA` with `E1, E2, nu12, G12, G13, G23`; isotropic `E, nu` | other types, temperature or field dependence |
| `*Fail Stress` | one line `Xt, Xc, Yt, Yc, S[, f*[, sigma_biax]]`, stored as written | several lines |
| `*Assembly` / `*Instance` | one assembly; instances at the origin without rotation | translated or rotated instances |
| `*Surface` | `type=NODE` with weight 1; `type=ELEMENT` stored | other types, other weights |
| `*Coupling` + `*Kinematic` | dofs 1 and 2 coupled; the reference node's rotations fixed by a `*Boundary` | `*Distributing`, `*Structural`, `influence radius`, a free in-plane dof or reference rotation |
| `*Step` / `*Static` | one linear static step | `nlgeom=YES`, `perturbation`, a second step, other procedures, `*Static` parameters |
| `*Boundary` | `target, first[, last[, value]]`; `ENCASTRE`, `PINNED`, `XSYMM`, `YSYMM`, `ZSYMM`; targets are assembly sets, `Instance.label` or an assembly node label | `type=` other than displacement, `amplitude=`, `op=`, antisymmetry types, nonzero values on dofs 3 to 6 |
| `*Cload` | `target, dof, value` on dofs 1 or 2 | `amplitude=`, `follower`, dofs 3 to 6, `*Dload`, `*Dsload` |

Two deck habits of Abaqus/CAE are handled on purpose: the same set name defined twice is unioned, and a reference node listed inside its own coupled node set is dropped from the coupled nodes with a note in `Deck.notes`, since Abaqus runs such a deck as written.

## The kernel

Four-node isoparametric plane-stress elements whose stiffness is the laminate membrane matrix `A` from the engine, 2 by 2 Gauss integration, sparse assembly, kinematic couplings as dof aliasing (every coupled node translates with its reference node, so the reference node's reaction is the sum over the region), prescribed displacements by partitioning, sparse LU solve, reactions as the residual, element strain at the centroid and the Gauss points, section forces `N = A eps`. The layups are symmetric (`B = 0`), the loading is in-plane and the plate is flat, so the bending problem has the trivial solution and the membrane problem is exact for these decks; the kernel refuses a layup whose `B` does not vanish, a singular system (a free rigid-body motion), a node in no element, and prescriptions that conflict through a coupling. Validation cases live in `validation/cases/` and are run by `tests/test_fe_validation_cases.py`; the format is documented at the top of `src/anisotropy_fea/cases.py`.

## Models from a spec

A coupon model is generated from one TOML file under `validation/specs/` (ADR-0030): kind (`unnotched_tension`, `open_hole_tension`, `compression`, `shear_pm45`, `three_point_bending`, `four_point_bending`), dimensions, mesh controls, layup, material from the engine's cited library or explicit constants with stated out-of-plane constants, grips (`nodal` or `coupling`, on the end rows or the whole tabs), loading by displacement or force, probe points and output requests. Every key is required and every invalid combination is refused by name; the format is documented at the top of `src/anisotropy_fea/spec.py`.

```powershell
uv run python examples/build_model.py validation/specs/tension-coupon-x840-coupling.toml --out ../.local/fea/abaqus/tension-coupon/ours
```

writes the complete deck (`<spec>-abaqus.inp`: part, elements, sets, composite section, material with citations in the header, reference nodes and couplings when asked, step, boundaries, loads, output requests), a model preview (`<spec>-model.png`), then reads the deck back with our own reader, solves it with the kernel, and writes the result figure, the `.vtu` and `summary.txt`. Built today: unnotched tension and compression coupons on the structured mesher, and open-hole coupons on a Gmsh transfinite O-grid (`mesher.gmsh_open_hole_plate`, optional extra `mesh`: `uv sync --extra mesh`; ADR-0030, amendment 3). Shear and bending follow chunk by chunk. The generated decks for the committed specs live in `validation/decks/generated/`; the tools are described in [docs/installation-fea-tools.md](../docs/installation-fea-tools.md).

## CalculiX, the independent solver

```powershell
uv run python examples/run_calculix.py validation/specs/tension-coupon-x840-nodal.toml --out ../.local/fea/calculix-prepomax/tension-coupon/ours
```

writes the CalculiX deck (`write_calculix`: S8R composite shells, four-field layer lines, one `*ORIENTATION` per ply angle, ENGINEERING CONSTANTS with the spec's out-of-plane constants, numeric boundaries, `*NODE PRINT` totals and `*EL PRINT, GLOBAL=YES` with COORD), runs the solver found through `ANISOTROPY_CCX` or on PATH (`calculix.run_calculix`), parses the `.dat` (`calculix.parse_dat`) and prints the reactions, probe displacements and strains next to the kernel's on the order-1 twin mesh. The `.frd` opens in PrePoMax (File, Open results). CalculiX refuses what its manual says it cannot do: order-1 composite shells, a reaction at a coupled reference node, force control on nodal grips. `plane_stress = true` in `[material.transverse]` writes nu13 = nu23 = 0: CalculiX expands a composite S8R into a single brick, and nonzero through-thickness Poisson ratios then couple the plies' thickness contraction and raise the in-plane stresses, which neither Abaqus LAMINA nor our kernel does (ADR-0030, amendment 1). Use it whenever the reference is plane stress.

A deck our reader has read, such as the team's Abaqus coupon, converts to CalculiX too: `examples/convert_to_calculix.py <deck> --units mm-MPa --nu23 <value> --out <dir>` promotes the mesh to S8R, turns each coupling into direct constraints carrying the reference node's values, rewrites the material with the stated out-of-plane constants (`--plane-stress` for nu13 = nu23 = 0), runs the solver and prints the reactions and centre strain next to the kernel's. The converted deck opens laminated in PrePoMax.

How CalculiX reports composite results (layer order, integration points, axes, shear strain) was detected by running it and is recorded in `validation/records/_calculix-conventions.toml`; the tests repeat the detection whenever the solver is present. `tools/record_from_dat.py` turns a run into a comparison record under `validation/records/` (numbers with provenance and both deck digests), and `tests/test_records.py` checks that the kernel reproduces every committed record within its tolerance and floor. The first record and its numbers: [the comparison note](../docs/evaluations/fea/2026-10-15-calculix-first-comparison.md).

## Ply stresses and first-ply failure

`recovery.py` pushes each element's strain through its plies with the engine's `ply_surfaces` (zero curvature), giving every ply's strain and stress in laminate and material axes, and checks each ply with the engine's criterion dispatch (`face_strength_ratio`): maximum stress, Tsai-Hill, Tsai-Wu (the deck's `*Fail Stress` sixth value is the interaction term; refused without it) and maximum strain (refused: a deck carries no strain limits). The smallest ratio over the mesh is the first-ply-failure factor on the applied displacement or load; ties between identical plies resolve to the first element in deck order and the bottom-most ply. A deck without `*Fail Stress` is refused by name.

## Layout

```
src/anisotropy_fea/   abaqus_reader.py (tokenize, parse_deck, read_deck), model.py (Deck and records, validate_deck, to_si), units.py,
                      mesh.py (mesh_from_deck, section_stiffness), membrane.py (the kernel: element, constraint_map, assemble, solve_membrane),
                      results.py (MembraneSolution), recovery.py (element_ply_states, strength_ratios, deck_f12_star),
                      cases.py (validation case format, compare, disagreements)
docs/theory.md        every equation and the function that computes it, with code markers
tests/                reader, units, element, solve, recovery, validation-case, theory-marker and local-deck tests
validation/decks/     committed fixture decks with public library materials; validation/cases/ the cases (fea/validation/README.md)
examples/             deck_summary.py, solve_deck.py
```

## Abaqus field reports

The team exports results from Abaqus/CAE as CSV field reports (Report > Field Output). `abaqus_report.read_field_report` reads one quantity (S11, S22, S12 or Mises; one row per element and section point, repeated header blocks allowed, `IntPt` must be 1 so the value is the centroid's, the layer taken from the section-point text with layer 1 at the bottom), `report_quantities` maps several into the record tables (`nan` for a component not exported, which the comparison skips; Mises into `ply_mises`), and `tools/record_from_report.py` writes the record. Records of the team's decks stay under `.local/fea/abaqus/<test>/comparison/` and are checked by `tests/test_local_tension_deck.py` when present. Format samples and the round-trip test: `tests/test_abaqus_report.py`.

## Model comparison documents

Every comparison record gets its own typeset document, separate from the manual: `uv run --project fea python docs/models/build.py <record.toml>` from the repository root writes a self-contained LaTeX file and, with Tectonic, the PDF (ADR-0031). It holds the spec and deck headers, the kernel's solution figure, the engine's classical laminate theory hand check (`report.laminate_check`: the laminate as a uniaxial test with free lateral edges, from the deck's section and gripped node rows), the kernel theory with its code, the reference solver's provenance and conventions, the mapping and judging code, every compared number with its error (`report.comparison_rows`, `report.summarize`), and the reading note `<record>.md` written beside the record. Section 4 of each document is a step-by-step rebuild guide for Abaqus/CAE and PrePoMax generated from `report.model_facts` (the deck's extents, partition lines, seeds, sets, constraints, boundary conditions, ply stack with z positions and output requests), with an evidence tag on every value. Documents of committed records go to `docs/models/build/`; documents of local records stay in `report/` beside the record (ADR-0032). See [docs/models/README.md](../docs/models/README.md).

The component card is [docs/components/fea.md](../docs/components/fea.md); what the team must export for a comparison is in [docs/abaqus-export-recipe.md](../docs/abaqus-export-recipe.md).
