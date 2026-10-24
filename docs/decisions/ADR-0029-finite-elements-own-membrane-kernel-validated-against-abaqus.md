# ADR-0029: Finite element analysis starts with our own two-dimensional laminate membrane kernel, Gmsh meshes, an Abaqus input writer from the same mesh, and a comparison harness against the team's Abaqus runs

- Status: Proposed
- Date: 2026-10-14
- Decided by: Founder (pending review) | Drafted by: Claude Code
- Related: ADR-0001 (the engine computes every number), ADR-0007 (validation cases store numbers and a source), ADR-0011 (separate package for a new layer), ADR-0019 (physics library mirrors the theory), ADR-0022 (plate buckling), ADR-0026 (run records), ADR-0027 (order of work), [system overview](../00_system_overview.md), [engine theory, "Not modeled yet"](../../engine/docs/theory.md)

## Context

The engine analyzes flat laminates by classical laminate theory and stops at holes and any geometry (theory.md, "Not modeled yet"). The founder decided on 2026-10-14 that finite element analysis is the next phase, before the assistant: build models, mesh them, solve them, and compare against Abaqus models the team makes at coupon and laminate level, to see whether the two match. Open-hole coupons are the first geometry named in the system overview. Facts that constrain the choice:

- The engine is Python with NumPy, Pydantic and openpyxl only (`engine/pyproject.toml`); SciPy is not a dependency yet.
- The team has Abaqus and will build the comparison models. Abaqus input decks are plain text; results leave Abaqus as reports or files the team exports. Whether a given Abaqus licence allows sharing exported numbers in this repository: no evidence yet.
- The founder works on Windows 11; the engine, API and database already run there.
- Every number in a result must be computed by tested code and traceable to its theory and sources (ADR-0001, ADR-0019). A solver whose element formulation we cannot document in `theory.md` breaks that chain.

## Options considered

Who solves:

1. **Our own two-dimensional finite element kernel in Python**: plane-stress quadrilateral elements whose stiffness is the laminate's membrane matrix `A` from the engine, assembled sparse with SciPy, with ply stresses recovered at each element through the engine's existing transformation and failure functions. Fully documented in `theory.md`, exactly consistent with the engine for an unnotched coupon, a few hundred lines, limited to in-plane problems of flat symmetric laminates at first (bending through `D`, and buckling, are later additions to the same kernel). No three-dimensional stresses.
2. **Drive CalculiX**: write its input deck, run `ccx`, parse the results. Composite shells and solids, buckling and nonlinear analysis exist already. The composite shell section is restricted to S8R (and S6 in some versions) elements per the manual; the element formulation is CalculiX's and would be cited, not documented as ours; one more binary to install and version on every machine, including the customer's.
3. **Drive code_aster**: layered DKT shells with `DEFI_COMPOSITE`. Linux-native, usually run inside Salome-Meca; a heavy dependency for a Windows founder and for self-hosted customers.
4. **FEniCSx**: we would write the element formulation anyway, with a Linux or conda toolchain under it.
5. **No solver of ours: only export Abaqus input decks** from the laminate definition. Nothing to validate, but then the product cannot answer without the customer's Abaqus licence, and the founder's question ("how does our engine do") goes unanswered.

Who meshes:

1. **Gmsh through its Python package**: installed by `pip install gmsh`, Windows wheel included; parametric geometry with OpenCASCADE, structured quadrilateral meshes by transfinite curves and recombination; the same mesh is written to our solver and to an Abaqus input deck.
2. **A hand-written structured mesher** for rectangles with a hole: no dependency, but every new geometry is new code.

How Abaqus results are compared:

1. **Numbers only, with a source reference** (ADR-0007): the team exports probe values (displacements, strains, stress concentration at the hole edge) from a run on the identical mesh we generated; the file records who ran it, the Abaqus version, element type, date and the input deck's digest. Committed when the material is from the public library; kept in `.local/` when it is not.
2. **Parse Abaqus output databases.** Proprietary binary format; needs an Abaqus installation to read.

## Decision

Options 1, 1 and 1: our own membrane kernel, Gmsh, numbers-only comparison records. A new package `fea/` with its own lockfile depends on the engine (as `api/` does, ADR-0011) and holds the mesher, the kernel, the Abaqus input writer and the comparison harness; the engine stays free of SciPy and Gmsh. The kernel's element theory, assembly, boundary conditions and ply stress recovery are documented in `theory.md` with code markers, as every other computation is, and the physics library gets cards for them (ADR-0019).

Validation ladder, each step a case in `fea/validation/` before the next is started:

1. Unnotched rectangular symmetric laminate under uniform edge load: the finite element midplane strains must equal the engine's `A^-1 N` to solver tolerance. This ties the kernel to the engine.
2. Isotropic plate with a central hole: the stress concentration approaches the Kirsch value of 3 at the hole edge as the plate widens and the mesh refines; the finite-width trend is checked against a printed table (source to be named when the case is written).
3. Orthotropic laminate with a central hole: Lekhnitskii's closed form for the infinite anisotropic plate, with the laminate's effective constants, and a finite-width correction (Tan). The printed equations are cited when the case is written, never from memory.
4. The team's Abaqus runs on the identical mesh, for the same three geometries, recorded as comparison files. Agreement targets are set in the first comparison note, not here.

Chunks, in order: (1) `fea/` package, Gmsh mesher for a rectangular coupon with an optional hole, our mesh format, node sets for edges and the hole, the Abaqus input writer, tests on counts and set membership; (2) the membrane kernel and validation case 1; (3) ply stress recovery and first-ply failure per element through the engine's failure functions, validation cases 2 and 3; (4) the comparison harness and the first Abaqus records from the team; (5) finite element runs through the API with run records. Bending (`D`), finite element buckling, and three-dimensional stresses through option 2 are later decisions.

## Amendment 2026-10-15 (founder, planning session)

The team already produces Abaqus input decks (`.inp`) for coupon models and will produce result exports; nothing can be compared until those exports exist. So the first chunk reads the team's deck and solves on their mesh, instead of meshing with Gmsh and writing a deck for them. The validation ladder keeps its four steps; step 4 is reached by reading their mesh. Gmsh and our deck writer move after the comparison harness. Chunks become: (1) `fea/` package with an Abaqus deck reader for the subset the team's decks use (S4-family shells, composite shell section with `symmetric`, LAMINA elastic, kinematic couplings to reference nodes with rotations fixed, displacement and concentrated-load boundary conditions, one linear static step; everything else refused by line number), units stated by the caller (`mm-MPa` or `m-Pa`, ADR-0003); (2) the membrane kernel and the engine-equality, isotropic and grip-constrained cases; (3) ply recovery and first-ply failure; (4) comparison records and the first Abaqus run; (5) Gmsh, our deck writer, open-hole cases; (6) runs through the API.

Fixtures policy: decks and comparison records whose materials come from the public library are committed under `fea/validation/`; the team's decks and any record naming a material that is not public stay in `.local/abaqus/`. A reference node listed inside its own coupled node set (found in the team's deck) is dropped from the set with a recorded note, since Abaqus runs the deck as written. An export recipe for the team (print requests or field reports) is written in chunk 1; its Abaqus keyword semantics are UNVERIFIED until the team runs it.

## Amendment 2026-10-15, second (founder, review of this record)

Two additions:

1. **The mathematics and physics behind every model are documented the way the engine's are, in the same manual.** `fea/docs/theory.md` states each equation the kernel implements (element shape functions, strain-displacement matrix, element stiffness from the laminate `A` matrix, assembly, constraint handling, reactions, strain and ply stress recovery, failure) with a `<!-- code: name -->` marker per function, and the LaTeX manual build (`docs/manual/build.py`, ADR-0008) is extended to read the `fea` package: its theory, tests, validation cases and evaluation. The theory document is part of chunk 2; extending the manual build is its own small chunk right after, since the build is engine-only today and the physics cards on the website (ADR-0019) need a separate decision on whether they mirror finite element theory too.
2. **Published finite element models of composite coupons join the validation ladder.** After the engine-equality, closed-form and Abaqus steps, the kernel reproduces finite element models of coupons and laminates published in textbooks or research papers (open-access sources preferred; a licensed source is cited by table and figure only, ADR-0018). A literature search for suitable published models comes first and is recorded as a research note in `docs/`, with each candidate's geometry, material, element type, reported results and rights class. No candidate identified yet: no evidence.

## Amendment 2026-10-15, third (founder, after the reader, kernel, ply recovery and manual chunks)

No usable Abaqus exists (the founder's `C:\SIMULIA` is an academic teaching licence, probably expired) and the team has exported nothing, so the independent solver of validation step 4 is **CalculiX now and Abaqus when exports exist**, and the models to compare are **generated from a parametric spec by us** rather than only read from the team's decks (ADR-0030). The remaining chunks are renumbered: A1 spec, structured mesher, model and Abaqus writer with preview and solve; A2 Gmsh open-hole mesh and the Kirsch case; B CalculiX writer, runner, parser, conventions detection and the first comparison records; C compression and shear; D bending in CalculiX only; E the eight-node element so one S8R deck serves both solvers; then the Abaqus records when the team exports, and runs through the API. The team's decks remain inputs that our reader takes, and the export recipe stands.

## Why (evidence)

- Gmsh ships a Windows wheel and the Python API through pip: [PyPI gmsh 4.15.1](https://pypi.org/project/gmsh/4.15.1/). Quadrilateral recombination options are shown in a [seamsh tutorial](https://jlambrechts.git-page.immc.ucl.ac.be/seamsh/examples/4-advanced-gmsh.html); a perforated-plate structured quad mesh built on Gmsh is in [EasyFEA's Mesh9 example](https://easyfea.readthedocs.io/en/v3.1.0/examples/Meshes/Mesh9.html). Our own open-hole mesh script: not written yet.
- CalculiX composite shell sections are limited to S8R elements: [CalculiX manual, *SHELL SECTION](https://web.mit.edu/calculix_v2.7/CalculiX/ccx_2.7/doc/ccx/node238.html) (version 2.7 page; a user report names S8R or S6 in a later version, [forum](https://calculix.discourse.group/t/layer-by-layer-simulation-implementation-in-calculix/1967)). Abaqus input syntax is close to CalculiX's: [forum thread](https://calculix.discourse.group/t/editing-abaqus-inp-file-format-to-use-in-calculix/2849). Current manual page: not checked.
- code_aster layered shells use `DEFI_COMPOSITE` with DKT elements: [validation case V3.03.113](https://www-mdp.eng.cam.ac.uk/web/CD/engapps/aster_docs/VDocs-HTML/V303113a/V303113a.pdf.html) (old version; current syntax not checked).
- Abaqus composite layups and per-ply output: [Understanding composite layups and orientations](https://abaqus-docs.mit.edu/2017/English/SIMACAECAERefMap/simacae-c-advlayupsorientations.htm), [Requesting output from a composite layup](https://ceae-server.colorado.edu/v2016/books/usi/pt04ch23s05.html), [*SHELL SECTION keyword](https://abaqus-docs.mit.edu/2017/English/SIMACAEKEYRefMap/simakey-r-shellsection.htm).
- The engine's `A` matrix, transformations and failure functions are tested (engine suite, 408 tests on 2026-10-11) and documented in `theory.md`; the kernel reuses them rather than re-deriving them.
- Cost of writing the kernel, accuracy against Abaqus, and the team's Abaqus version and licence terms for sharing exported numbers: no evidence yet. The first comparison note supplies the accuracy evidence.
- A team coupon deck (Abaqus/CAE 2026, read 2026-10-15, kept in `.local/`): S4R elements, a composite shell section with `symmetric`, LAMINA elastic, two kinematic couplings, displacement-controlled linear static step, no print requests, so its `.dat` holds no results. This fixes the reader's first keyword subset and shows why the export recipe comes first.

## Consequences

Easier: an open-hole coupon prediction that is traceable to documented theory and to the engine's own numbers; the same mesh runs in our solver and in the team's Abaqus, so differences are the solvers', not the models'; the comparison records are the first evidence of how we do against a commercial code. Harder: a second Python package and lockfile; two new dependencies (SciPy, Gmsh) in the product, with Gmsh a large binary wheel to package for self-hosted customers; in-plane only until bending is added; finite element results are large, so a run record holds a summary and a digest while fields go elsewhere, a question for a later record (ADR-0026 names the trigger). The assistant moves after this phase (ADR-0027 amended).

## How we will know it was wrong

If validation case 1 cannot match the engine to tolerance, the kernel is wrong and is fixed before anything else. If the Abaqus comparisons disagree beyond the targets set in the first comparison note and the cause is the element formulation rather than a model difference, revisit option 2 for the solver. If a customer's first real need is three-dimensional (interlaminar stress, thick sections, joints), skip to option 2 rather than extending the kernel. If Gmsh proves unpackageable for a self-hosted customer, revisit the mesher.
