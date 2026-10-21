# fea/checks

The proofs that the finite element layer reads and solves what it claims (ADR-0029). None of these is a model we show the team; those are in [`../models/`](../models/README.md). Every location is defined once in `src/anisotropy_fea/paths.py` (ADR-0036).

| Folder or file | Holds |
| --- | --- |
| `cases/` | Validation cases: a deck, expected numbers, a source and a tolerance (ADR-0007 style). The format is at the top of `src/anisotropy_fea/cases.py`. |
| `decks/` | The tiny hand-made decks the cases and tests read. |
| `calculix-conventions.toml` | How CalculiX 2.22 reports composite results (layer order, integration points, axes, shear strain), detected by running it. Every CalculiX record names it. |
| `unnotched-im7-8552/`, `compression-im7-8552/`, `open-hole-im7-8552/` | The public IM7/8552 regression set, each in the shape of a model folder: specs at the root, `decks/`, `records/`. These are the earlier coupons on the public NCAMP material; the tests, the manual and CI use them, and their data may be published. Add an IM7/8552 model only when a problem needs that material. |
| `open-hole-isotropic-kirsch/` | The wide isotropic plate with a small hole, and its deck. Its validation case is `cases/open-hole-isotropic-kirsch.toml`. |

`tests/test_write_abaqus.py` checks that every committed deck is what its spec writes today, and `tests/test_records.py` checks that the kernel reproduces every record. Rewrite the decks with `tools/regenerate_decks.py` after changing a spec or a writer.

## The tiny decks

- `coupon-1x1-im7-8552.inp`: one element, 10 mm by 80 mm, IM7/8552 [0/45/-45/45/0]s, 1 % axial strain by edge displacement, lateral edges free. The uniform-strain patch test.
- `coupon-2x8-grips-im7-8552.inp`: the team's model structure (parts, instance, assembly sets, node surfaces, kinematic couplings to two reference nodes, displacement-controlled step, PRESELECT output) on a 2 by 8 mesh with the same public material. Edit by hand with care and keep the header comments true.
- `coupon-2x2-im7-8552.inp`: the one-element coupon meshed 2 by 2. `coupon-1x1-cload-im7-8552.inp`: the same under 1000 N of edge load.
- `plate-1x1-isotropic.inp`: a homogeneous shell section with an isotropic material and an `Instance.label` boundary target; nominal values, not a cited material. `plate-1x1-isotropic-shear.inp`: the same plate in simple shear.

The decks state the Tsai-Wu interaction term f* = 0 as the sixth `*Fail Stress` value, which is Abaqus's documented default made explicit (ADR-0021: the engine never assumes it). Their material numbers come from the library dataset `ncamp-im7-8552-2019-rtd-measured-v1` converted to MPa. `G13` and `G23` are nominal: Abaqus syntax requires them and this package does not use them.

## The cases

- `patch-1x1-im7-engine-equality`, `patch-2x2-im7-engine-equality`: prescribed 1 % axial strain with free lateral edges. The expected strain, section force, reactions and displacements come from the engine's mixed solver on the same plies, recomputed live in `tests/test_membrane_solve.py`.
- `patch-1x1-cload-im7-engine-equality`: a 1000 N edge load; the expected values come from the engine's forward solve.
- `isotropic-uniaxial-plane-stress`, `isotropic-simple-shear`: closed forms of isotropic plane stress (Timoshenko and Goodier, Chapter 2), by hand.
- `open-hole-isotropic-kirsch`: the plate in `open-hole-isotropic-kirsch/` under 100 MPa against Kirsch's closed form (Timoshenko and Goodier, Chapter 4) at the kernel's centroids, computed by `tools/kirsch_hole.py`. The 2 % tolerance comes from its convergence study; the small components are left out, with the reason in the case.
- The three IM7 cases also carry every ply's stress and strain in material axes and the first-ply-failure factor by maximum stress, Tsai-Hill and Tsai-Wu. Only the factor is checked there, because identical plies tie in a uniform state. The isotropic uniaxial case carries its one-ply stress, 700 MPa.
