# Component card: finite element layer | version 0.1 | updated 2026-10-15 (chunk 2)

## Purpose and intended use

Read the Abaqus input decks the team builds for coupon and laminate models, solve them with our own laminate membrane kernel on the engine's stiffness, and compare the two number for number (ADR-0029). Built so far: the reader (chunk 1) and the membrane kernel with its validation cases (chunk 2). Ply recovery, first-ply failure and the comparison harness follow.

## Out of scope / do not use for

Anything Abaqus can do that the reader refuses (see the table in [fea/README.md](../../fea/README.md)): three-dimensional elements, triangles, unsymmetric layups, rotated laminate axes, translated instances, nonlinear or multi-step analyses, pressure and distributed loads, out-of-plane loading. Bending, buckling, thermal strain, ply stresses and failure are not computed yet. Abaqus result files (`.odb`, `.dat`, `.rpt`) are not read. The kernel's full-integration bilinear element is not Abaqus's reduced-integration S4R; the two agree for uniform fields and differ at a level to be measured in the first comparison note (risk R-15).

## Inputs / outputs

Input: an Abaqus `.inp` file and the unit system it is written in (`mm-MPa` or `m-Pa`), stated by the caller. Output: a `Deck` in SI base units with parts, elements, node and element sets, composite shell sections (plies bottom-first, the `symmetric` flag applied), materials with `*Elastic` and `*Fail Stress`, instances, reference nodes, kinematic couplings, boundary conditions and the one static step; the skipped output keywords; the file's SHA-256; notes. `section_plies` turns a section into the engine's `Ply` list, and `is_symmetric_layup` says whether `B` vanishes. Unsupported content raises `DeckError` with the line number (ADR-0003). `solve_membrane(deck)` returns nodal displacements, reactions at prescribed dofs (the reference node's reaction is the sum over its coupled region), membrane strains at element centroids and Gauss points, and section forces `N = A eps`, all in SI; `cases.py` compares a solve with expected numbers in the deck's units. Theory: [fea/docs/theory.md](../../fea/docs/theory.md).

## Dependencies and versions

Python 3.12+, `anisotropy-engine` (editable path dependency), NumPy, SciPy (for the kernel in the next chunk), Pydantic 2 (`fea/uv.lock`). No Abaqus software is needed to read a deck.

## Evaluation

[Chunk 2 evaluation](../evaluations/fea/2026-10-15-membrane-kernel.md): the kernel reproduces the engine's midplane strain, section force and reaction to 1e-12 on one element, 2 by 2, 3 by 5 and 4 by 8 meshes under prescribed displacement and under edge load; isotropic closed forms; a coupled edge equals the same edge prescribed node by node; the gripped coupon in equilibrium and converging under refinement; the team's deck solved in equilibrium. [Chunk 1 evaluation](../evaluations/fea/2026-10-15-deck-reader.md): the reader.

## Known limitations

The Abaqus sign convention for compressive limits in `*Fail Stress` and the layer order semantics of `symmetric` are UNVERIFIED against Abaqus documentation; the reader stores values as written and consumers use magnitudes and bottom-first order (ADR-0004). Set and material names must match exactly as written (Abaqus itself is case-insensitive). Units are stated, not inferred; a wrong statement is caught only by the modulus plausibility warning.

## Failure modes seen

- 2026-10-15: the team's deck defines `*Nset, nset=s_Set-4` twice, once with `instance=` and once naming the assembly reference node of that very coupling. The reader unions the two and drops the reference node from the coupled nodes with a note.

## Owner and contact

Founder / engineering.
