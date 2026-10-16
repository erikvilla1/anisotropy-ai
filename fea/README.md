# anisotropy-fea

The finite element layer (ADR-0029). It reads the Abaqus input decks the team builds for coupon models and, in the next chunk, solves them on the engine's laminate stiffness so the two can be compared number for number. Nothing here computes a result yet; this chunk is the reader.

## Run

```powershell
cd fea
uv sync --locked
uv run pytest -q -ra tests ../engine/tests
uv run python examples/deck_summary.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa
```

The team's own decks go in `.local/abaqus/` (git-ignored; their materials may be proprietary). `tests/test_local_tension_deck.py` runs against `.local/abaqus/Tension-test.inp` when it is there and is skipped, with the reason shown, when it is not.

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

## Why a membrane model is enough for these decks

The layups are symmetric (`B = 0`), the loading is in-plane through the couplings, the plate is flat and the reference nodes' out-of-plane dofs are fixed, so the bending problem has the trivial solution and the in-plane problem is plane stress with the laminate stiffness `A`. `G13` and `G23` play no part. The kernel (next chunk) refuses a layup whose `B` does not vanish.

## Layout

```
src/anisotropy_fea/   abaqus_reader.py (tokenize, parse_deck, read_deck), model.py (Deck and records, validate_deck, to_si), units.py
tests/                reader, units and local-deck tests
validation/decks/     committed fixture decks with public library materials (fea/validation/README.md)
examples/             deck_summary.py
```

The component card is [docs/components/fea.md](../docs/components/fea.md); what the team must export for a comparison is in [docs/abaqus-export-recipe.md](../docs/abaqus-export-recipe.md).
