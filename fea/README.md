# anisotropy-fea

The finite element layer (ADR-0029). It reads the Abaqus input decks the team builds for coupon models and solves them on the engine's laminate stiffness with its own membrane kernel, so the two can be compared number for number. The theory behind every number is in [docs/theory.md](docs/theory.md), with the function that computes each equation.

## Run

```powershell
cd fea
uv sync --locked
uv run pytest -q -ra tests ../engine/tests
uv run python examples/deck_summary.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
uv run python examples/solve_deck.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
uv run python examples/plot_deck.py checks/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa --out ../.local/fea/checks/plots
```

`export_vtk.py` writes the solved model as a `.vtu` file for ParaView (points: displacement, reaction; cells: strains, section forces, failure indices with the worst ply, every ply's material-axis stresses), so the result can be rotated, probed and coloured like in any finite element tool. `plot_deck.py` draws the mesh and deformed shape, the three strain fields, the axial section force and the first-ply-failure map as one PNG (matplotlib, a development dependency). Write the pictures of a team deck to `.local/`, never into the repository.

The team's own decks go in `.local/fea/<coupon>/from-team/<date>/` (git-ignored; their materials may be proprietary; layout in ADR-0036 and the `workspace-layout` skill). `tests/test_local_tension_deck.py` runs against the team's deck in `.local/fea/X840PW-UNT-L1/from-team/<date>/` (found by `paths.team_deck`) when it is there and is skipped, with the reason shown, when it is not.

## A coupon in one command

`tools/run_coupon.py` takes a coupon from its filled-in input form to its package (ADR-0049). It runs the steps of the case page's Rebuild section: the specs, the decks, the next attempt, our kernel, the CalculiX twin, the record (gauge probes only) and the package. Then it adds the attempt's row to the case page and lists the files to open in Abaqus/CAE, PrePoMax and ParaView. It needs CalculiX and refuses before writing anything without it. It also takes a values file, the form's rows as one JSON object as the workspace sends them (ADR-0046 amendment 3), runs the setup check of `anisotropy_fea.checks` first and refuses a blocked one, rewrites a progress file after every step (`--progress`), and keeps the checklist and the preview in the attempt's `run/studio/` (ADR-0051).

```powershell
uv run python tools/run_coupon.py <filled form>.xlsx --run-by "<role>"            # a new coupon
uv run python tools/run_coupon.py <filled form>.xlsx --run-by "<role>" --replace  # after changing the form
uv run python tools/run_coupon.py <coupon> --run-by "<role>"                      # again, on the specs as they are
uv run python tools/run_coupon.py <values>.json --run-by "<role>"                # the same rows as the workspace sends them
```

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
| `*Orientation` | any right-handed frame in the plate's plane: a unit `a` with `a_z = 0`, `b` = z cross `a`, an optional rotation `3, angle`; the angle from x to local 1 becomes the section's rotation (ADR-0065) | an `a` out of the plane or not of unit length, a `b` other than z cross `a`, a rotation about axis 1 or 2, `system=`, `definition=` |
| `*Shell Section` | `composite` with layer lines `t, nip, material, angle[, name]` and `symmetric`; or `material=` with `t[, nip]` | `offset`, `nodal thickness`, `*Shell General Section`, `*Membrane Section`, `*Solid Section` |
| `*Material` / `*Elastic` | `type=LAMINA` with `E1, E2, nu12, G12, G13, G23`; isotropic `E, nu` | other types, temperature or field dependence |
| `*Fail Stress` | one line `Xt, Xc, Yt, Yc, S[, f*[, sigma_biax]]`, stored as written | several lines |
| `*Assembly` / `*Instance` | one assembly; instances at the origin without rotation | translated or rotated instances |
| `*Surface` | `type=NODE` with weight 1; `type=ELEMENT` stored | other types, other weights |
| `*Coupling` + `*Kinematic` | dofs 1 and 2 coupled; the reference node's rotations fixed by a `*Boundary` | `*Distributing`, `*Structural`, `influence radius`, a free in-plane dof or reference rotation |
| `*Step` / `*Static` | one linear static step | `nlgeom=YES`, `perturbation`, a second step, other procedures, `*Static` parameters |
| `*Boundary` | `target, first[, last[, value]]`; `ENCASTRE`, `PINNED`, `XSYMM`, `YSYMM`, `ZSYMM`; targets are assembly sets, `Instance.label` or an assembly node label | `type=` other than displacement, `amplitude=`, `op=`, antisymmetry types, nonzero values on dofs 3 to 6 |
| `*Cload` | `target, dof, value` on dofs 1 to 5 (3 to 5 go to the flat shell, ADR-0053) | `amplitude=`, `follower`, dof 6 |
| `*Dload` | `element set or Instance.label, P, pressure` (a uniform pressure on the shell; the flat shell solves it) | other labels, `*Dsload` |

Two deck habits of Abaqus/CAE are handled on purpose: the same set name defined twice is unioned, and a reference node listed inside its own coupled node set is dropped from the coupled nodes with a note in `Deck.notes`, since Abaqus runs such a deck as written.

## The kernel

Four-node isoparametric plane-stress elements whose stiffness is the laminate membrane matrix `A` from the engine, 2 by 2 Gauss integration, sparse assembly, kinematic couplings as dof aliasing (every coupled node translates with its reference node, so the reference node's reaction is the sum over the region), prescribed displacements by partitioning, sparse LU solve, reactions as the residual, element strain at the centroid and the Gauss points, section forces `N = A eps`. The layups are symmetric (`B = 0`), the loading is in-plane and the plate is flat, so the bending problem has the trivial solution and the membrane problem is exact for these decks; the kernel refuses a layup whose `B` does not vanish, a singular system (a free rigid-body motion), a node in no element, and prescriptions that conflict through a coupling. A deck that bends, carries a pressure, prescribes or loads a degree of freedom out of the plane, or has an unsymmetric layup goes to the flat shell kernel instead (`shell.py`, ADR-0053): the same four-node element with five degrees of freedom per node, MITC4 transverse shear tying, the laminate's `A`, `B`, `D` and shear-corrected transverse stiffness, pressures as consistent nodal forces; `kernel.solve_deck` dispatches. Its cases (`bend-*`, `plate-*`, `strip-*`) come from `tools/plate_closed_forms.py`. Validation cases live in `checks/cases/` and are run by `tests/test_fe_validation_cases.py`; the format is documented at the top of `src/anisotropy_fea/cases.py`.

## Models from a spec

A coupon model is generated from one TOML file in its test folder, `checks/<test>/` or, for our models of the team's coupons, the local `../.local/fea/<coupon>/`, never committed (ADR-0030, ADR-0036, ADR-0042): kind (`unnotched_tension`, `open_hole_tension`, `compression`, `shear_pm45`, `three_point_bending`, `four_point_bending`, `plate`), dimensions, mesh controls, layup, material from the engine's cited library or explicit constants with stated out-of-plane constants, grips (`nodal` or `coupling`, on the end rows or the whole tabs), loading by displacement or force, probe points and output requests; a `plate` lists `[[supports]]`, `[[loads]]` and `[[regions]]` over named regions instead of grips and a loading (ADR-0054). Every key is required and every invalid combination is refused by name; the format is documented at the top of `src/anisotropy_fea/spec.py`.

```powershell
uv run python examples/build_model.py checks/unnotched-im7-8552/unnotched-im7-8552-coupling.toml --out ../.local/fea/checks/unnotched-im7-8552/runs/kernel
```

writes the complete deck (`<spec>-abaqus.inp`: part, elements, sets, composite section, material with citations in the header, reference nodes and couplings when asked, step, boundaries, loads, output requests), a model preview (`<spec>-model.png`), then reads the deck back with our own reader, solves it with the kernel, and writes the result figure, the `.vtu` and `summary.txt`. Built today: unnotched tension and compression coupons on the structured mesher, open-hole coupons on a Gmsh transfinite O-grid (`mesher.gmsh_open_hole_plate`, optional extra `mesh`: `uv sync --extra mesh`; ADR-0030, amendment 3), and three- and four-point bending coupons resting on two support lines, pinned in their plane at the centre node of each, pushed by their loading nose(s) (ADR-0053; `checks/three-point-im7-8552/`), and plates held and loaded on named regions, pressures included (ADR-0054; `checks/plate-pressure-isotropic/`). Shear coupons follow. Each spec's generated decks live in its test folder's `decks/` (rewrite them with `tools/regenerate_decks.py`); the tools are described in [docs/installation-fea-tools.md](../docs/installation-fea-tools.md).

The studio's questions to the package run as one command each (ADR-0051): `uv run python tools/studio_tool.py check <values>.json --out <dir>` writes the setup checklist and the preview; `coupons` lists every coupon on the machine; `values <coupon>` reads a coupon's spec back into its rows; `fixtures <values>.json --out <dir>` adds a kernel solve's fields and explanation for the browser tests. `uv run python tools/export_form_definition.py` writes the form's rows as `lib/coupon-form-definition.json` for the website (`--check` reports drift; a test does too).

The team states a coupon on the coupon input form instead (ADR-0046): `uv run python tools/coupon_form.py` writes the blank Excel form, and `uv run python tools/coupon_from_form.py <filled form>.xlsx` checks it, names every problem by its row, and writes the coupon's two specs, its `team/<date>/` folder and its case page under `../.local/fea/<coupon>/`.

## CalculiX, the independent solver

```powershell
uv run python examples/run_calculix.py checks/unnotched-im7-8552/unnotched-im7-8552-nodal.toml --out ../.local/fea/checks/unnotched-im7-8552/runs/calculix
```

writes the CalculiX deck (`write_calculix`: S8R composite shells, four-field layer lines, one `*ORIENTATION` per ply angle, ENGINEERING CONSTANTS with the spec's out-of-plane constants, numeric boundaries, `*NODE PRINT` totals and `*EL PRINT, GLOBAL=YES` with COORD), runs the solver found through `ANISOTROPY_CCX` or on PATH (`calculix.run_calculix`), parses the `.dat` (`calculix.parse_dat`) and prints the reactions, probe displacements and strains next to the kernel's on the order-1 twin mesh. The `.frd` opens in PrePoMax (File, Open results). CalculiX refuses what its manual says it cannot do: order-1 composite shells, a reaction at a coupled reference node, force control on nodal grips. `plane_stress = true` in `[material.transverse]` writes nu13 = nu23 = 0: CalculiX expands a composite S8R into a single brick, and nonzero through-thickness Poisson ratios then couple the plies' thickness contraction and raise the in-plane stresses, which neither Abaqus LAMINA nor our kernel does (ADR-0030, amendment 1). Use it whenever the reference is plane stress.

A deck our reader has read, such as the team's Abaqus coupon, converts to CalculiX too: `examples/convert_to_calculix.py <deck> --units mm-MPa --nu23 <value> --out <dir>` promotes the mesh to S8R, turns each coupling into direct constraints carrying the reference node's values, rewrites the material with the stated out-of-plane constants (`--plane-stress` for nu13 = nu23 = 0), runs the solver and prints the reactions and centre strain next to the kernel's. The converted deck opens laminated in PrePoMax.

How CalculiX reports composite results (layer order, integration points, axes, shear strain) was detected by running it and is recorded in `checks/calculix-conventions.toml`; the tests repeat the detection whenever the solver is present. `tools/record_from_dat.py` turns a run into a comparison record in the test's `records/` folder (numbers with provenance and both deck digests), and `tests/test_records.py` checks that the kernel reproduces every committed record within its tolerance and floor. The first record and its numbers: [the comparison note](../docs/evaluations/fea/2026-10-15-calculix-first-comparison.md).

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
models/<test>/        the models we show the team: spec(s), decks/, records/, README (models/README.md)
checks/              proofs that are not team models: cases/, decks/ (tiny fixtures), the IM7/8552 regression set, the Kirsch plate (checks/README.md)
examples/             deck_summary.py, solve_deck.py
```

## Abaqus field reports

The team exports results from Abaqus/CAE as CSV field reports (Report > Field Output). `abaqus_report.read_field_report` reads one quantity (S11, S22, S12 or Mises; one row per element and section point, repeated header blocks allowed, `IntPt` must be 1 so the value is the centroid's, the layer taken from the section-point text with layer 1 at the bottom), `report_quantities` maps several into the record tables (`nan` for a component not exported, which the comparison skips; Mises into `ply_mises`), and `tools/record_from_report.py` writes the record. Records of the team's decks stay under `.local/fea/<coupon>/comparison/` and are checked by `tests/test_local_tension_deck.py` when present. Format samples and the round-trip test: `tests/test_abaqus_report.py`.

The same reports come out of an ODB without the GUI (ADR-0045): `tools/abaqus_extract_fields.py`, run under `abaqus python`, writes one CSV per quantity in that layout (every section point the field holds, one per layer, rows sorted, LF line endings, SHA-256 printed), the reactions as `<job>-RF.csv` and the provenance as `<job>-extract.json`; it refuses what it would otherwise have to guess (several steps, instances or frames, several section points in a layer without `--layer-point`, a full-integration shell). `anisotropy_fea.abaqus` finds the command (`ANISOTROPY_ABAQUS`, then `abaqus` on PATH), runs a deck (`run_abaqus`) and the extraction (`extract_fields`); `tools/run_abaqus.py` solves a spec, exports its fields and writes the record against the kernel into an attempt's `run/abaqus/`. Every generated deck is valid Abaqus/Standard input as written (ADR-0045 amendment 2): one variable per `*El Print` table (Abaqus allows nine per table and refused the combined `SF, SE` and `S, E` of a composite shell) and no line over 256 bytes (Abaqus counts the bytes of the UTF-8 file, so a long heading comment is wrapped); the run tool's deck is the spec's deck in `decks/`, byte for byte. Tests: `tests/test_abaqus_extract.py` (the script's plain parts, no Abaqus needed) and `tests/test_abaqus.py` (the runner; the solve skips without Abaqus).

## A model sent from Abaqus

A model comes in as one zip, the exchange bundle (ADR-0094; `anisotropy_fea.bundle`, version 1): a `manifest.json` (the format's version, the deck system as stated, who wrote it and when, each file with its size and SHA-256), the deck Abaqus solved, every element and ply in `tools/abaqus_every_output.py`'s columns and, when there are any, the reactions, the model as built in Abaqus/CAE and its journal. `open_bundle` checks the whole bundle before anything is read from it and refuses it with every reason at once: a file the manifest does not list, a path that leaves the bundle, a size or digest that does not match, a key or role version 1 does not know. Nothing in a bundle is executed; a journal is text. The module uses the standard library only, so the connector can run it under Abaqus's own Python.

```
uv run python tools/abaqus_upload.py pack --deck <job>.inp --every-output <job>-every-output.csv --rf <job>-every-output-RF.csv --units mm-MPa --out <bundle>.zip
uv run python tools/abaqus_upload.py check <bundle>.zip
uv run python tools/abaqus_upload.py compare <bundle>.zip --ours <package>/4-results/ours-every-output.csv --our-deck <our deck>.inp --json <result>.json
```

`compare` puts a bundle beside a run of ours from that run's own files; nothing is solved. The model is compared item by item (`equivalence.deck_equivalence`), after a coupon drawn elsewhere is moved onto ours, and the results by the rules of `tools/compare_every_output.py`, ADR-0089's acceptance. A model on another mesh is compared without its mesh (`equivalence.equivalence_without_mesh`: the outline, the element type, the section, the layup, each ply's constants), each of its gauge elements beside ours nearest its centroid, and at the reaction; its free length is reported, not judged. Two material constants that are one number written to six significant digits count as the same, and the item says so: Abaqus/CAE writes an input file's material lines with six digits. A bundle in the other deck system is converted first. The exit code is the verdict (0 agrees, 1 differs or incomplete, 2 refused or out of scope), and `--json` holds what a page will show: beside the tables, a `summary` with how many places differ, the model's items counted, and for each zone the quantity with the largest difference, its place and both numbers, which the run's card reads as it is (ADR-0094, step 6). Four such results of the public D3039 check are kept in `tests/fixtures/abaqus/` for the page's tests and pinned by `tests/test_abaqus_upload.py`; after a change that is meant to move them, rewrite them with `ANISOTROPY_WRITE_FIXTURES=1 uv run pytest tests/test_abaqus_upload.py -k fixtures`. Tests: `tests/test_bundle.py`, `tests/test_abaqus_upload.py`.

The connector writes the bundle on the machine that has Abaqus (ADR-0094, step 2; `tools/anisotropy_connector.py`). It is four files kept in one folder, the standard library and Abaqus's own modules only; `connector` below writes them as one zip to hand over.

```
uv run python tools/abaqus_upload.py connector --out anisotropy-connector.zip
abaqus python anisotropy_connector.py <job>.odb --units mm-MPa
abaqus cae noGUI=anisotropy_connector.py -- <job>.odb --units mm-MPa --cae <model>.cae
```

The first Abaqus command reads the ODB (`abaqus_every_output.read`), takes `<job>.inp` from beside it and writes `<job>-anisotropy.zip`; it uses no seat of Abaqus/CAE. The second also reads the `.cae`, from a copy in a temporary folder because opening a `.cae` changes the file, and adds the model as built as `<job>-model.json` (the parts with their layups ply by ply, the materials, the sections, the assembly, the steps with what each boundary condition, load and output request is in them, the constraints; what could not be read is named under `not_read`) and the `.jnl` beside the `.cae`. Under Abaqus/CAE put the ODB first, and read the line the command prints: Abaqus/CAE ends with exit code 0 whatever happened. `--units` states the deck system, which an Abaqus model does not carry. Nothing is sent unless asked: the command writes one file. With `--send <the API's address>` (step 5) the bundle then goes to `POST /v1/connector/uploads` with the upload token from `--token-file` or `ANISOTROPY_UPLOAD_TOKEN`, never from the command line and never printed; the address is https or this machine, a redirect is not followed, and the command prints the upload's id and the verdict, or why it was not sent (the bundle still on the disk; the script ends with 1, which Abaqus's launcher on Windows turns into 0, so the line is the answer). Tests of the sending: `tests/test_connector_send.py`, over a socket on the same machine. From Abaqus 2025's own Python it was run on the founder's machine against a stand-in server, both commands (ADR-0094, the eighth run); over https it is UNVERIFIED. `check` counts what the model file holds; the comparison is made on the deck and never on that file. Tests: `tests/test_anisotropy_connector.py`, with the two readers that need Abaqus replaced. The two runs under Abaqus 2025, both routes, are in ADR-0094's evidence.

The way out is a build script (ADR-0094, step 3; `anisotropy_fea.write_cae_script`): from the same model the input deck is written from, a script that Abaqus/CAE runs to build the coupon as a native model to edit, with its sketch, partitions, material, composite layup, grips, step, seeds, structured mesh, output requests and a job.

```
uv run python tools/abaqus_build_script.py <coupon>.toml --out <coupon>-build.py
abaqus cae noGUI=<coupon>-build.py -- save=<coupon>.cae
```

In Abaqus/CAE itself it is File > Run Script, which adds the model and its job to the open session and saves nothing (this route is not yet checked by us; the terminal route is). The script adds one model and one job, stops when either name is taken and never saves over a file. It covers the unnotched tension coupon on a structured mesh, with nodal or coupled grips, and refuses anything else with the reason. The package of such a coupon carries it as `2-our-model/abaqus/<coupon>-build.py`, and a run reports it as the output `abaqus_build`, which the run's card offers as a download. Tests: `tests/test_write_cae_script.py`, against a stand-in for Abaqus/CAE. The round trip under Abaqus 2025 (built by the script, solved, sent back by the connector, compared: agrees with ours for both grips) is in ADR-0094's evidence.

The whole round trip is three tools on the machine that has Abaqus (ADR-0094, step 4; `tools/abaqus_tools.py`): `build` (Abaqus/CAE runs the build script and saves the model with its job's input file), `run` (the job, in the foreground) and `send` (the connector's bundle with the model as built, then the comparison with our own solve of the same spec). One coupon, one work folder.

```
uv run python tools/abaqus_tools.py state <coupon>.toml --folder <work>
uv run python tools/abaqus_tools.py plan  <coupon>.toml --folder <work> --tools build run send
uv run --project ../api python -m anisotropy_api.abaqus_round_trip "build this coupon in Abaqus and compare" --coupon <coupon>.toml --folder <work>
```

Each tool is one fixed command of Abaqus (ANISOTROPY_ABAQUS, or `abaqus` on PATH) whose names our code derives from the spec; no shell is used and no argument is free text. A tool whose output is already in the folder is refused, a chain with a gap is refused whole, and Abaqus/CAE's exit code is never taken for success: the files are. Every call goes to `<work>/abaqus-tools.json` with the command as run, the time and each file's SHA-256. Until uploads exist, `send` compares on the same machine and writes `<job>-comparison.json`; the exit code is the comparison's (0 agrees, 1 differs, 2 refused). The third line lets the assistant choose among the three from a sentence (it names tools and nothing else; with the assistant off, every step left runs). Tests: `tests/test_abaqus_tools.py`, with Abaqus replaced by a stand-in that leaves the files Abaqus leaves, and `api/tests/test_abaqus_round_trip.py`.

## Model comparison documents

Every comparison record gets its own typeset document, separate from the manual: `uv run --project fea python docs/models/build.py <record.toml>` from the repository root writes a self-contained LaTeX file and, with Tectonic, the PDF (ADR-0031). It holds the spec and deck headers, the kernel's solution figure, the engine's classical laminate theory hand check (`report.laminate_check`: the laminate as a uniaxial test with free lateral edges, from the deck's section and gripped node rows), the kernel theory with its code, the reference solver's provenance and conventions, the mapping and judging code, every compared number with its error (`report.comparison_rows`, `report.summarize`), and the reading note `<record>.md` written beside the record. Section 4 of each document is a step-by-step rebuild guide for Abaqus/CAE and PrePoMax generated from `report.model_facts` (the deck's extents, partition lines, seeds, sets, constraints, boundary conditions, ply stack with z positions and output requests), with an evidence tag on every value. Documents of committed records go to `docs/models/build/`; documents of local records stay in `report/` beside the record (ADR-0032). See [docs/models/README.md](../docs/models/README.md).

The component card is [docs/components/fea.md](../docs/components/fea.md); what the team must export for a comparison is in [docs/abaqus-export-recipe.md](../docs/abaqus-export-recipe.md).
