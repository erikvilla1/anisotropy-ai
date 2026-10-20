# Evaluation: the team's X840-Z60 tension coupon joins the committed validation set (ADR-0030, amendment 4) | 2026-10-20

- Scope: `fea/tests/test_spec.py` admits a `licensed-reference` library material in a committed spec (the three citable classes of ADR-0018; `user-supplied` and explicit constants still refused). New committed specs `tension-coupon-x840-nodal.toml` and `tension-coupon-x840-coupling.toml` (the team's 10 mm by 80 mm coupon, [0/45/-45/45/0]s of 0.1 mm plies, 15 mm tabs, 10 mm pull, library material `x840-z60-pw`, plane stress, first-ply failure by maximum stress and Tsai-Hill), their generated decks under `validation/decks/generated/` (checked against the specs by `test_write_abaqus.py`), the CalculiX record `tension-coupon-x840-nodal-calculix.toml` with its reading note, `validation/README.md` updated. The X840-Z60 rights evidence in `lib/curated-materials.ts` now records the founder's confirmation of 2026-10-20 and the cofounder's university access; the engine library JSON is re-exported. The founder's decision: the engine is proved on the material of the problem at hand, not on IM7/8552 unless a problem calls for it.
- Branch: `feat/validation-x840-coupon`, from `feat/micromechanics` with `feat/library-x840-z60` (PR #56) merged in, so the library record is present.
- Environment: Windows 11, uv 0.13, Python 3.12; CalculiX 2.22 from the PrePoMax v2.6.0 bundle through `ANISOTROPY_CCX`; Tectonic for the document; Node for the website tests.

## Commands and captured output

From `fea/`: `uv run python examples/run_calculix.py validation/specs/tension-coupon-x840-nodal.toml --out ../.local/fea/calculix-prepomax/tension-coupon/ours`

```text
written ..\.local\fea\calculix-prepomax\tension-coupon\ours\tension-coupon-x840-nodal-ccx.inp (2581 nodes, 800 S8R elements)
CalculiX 2.22: 3.2 s, 0 warnings; results in ..\.local\fea\calculix-prepomax\tension-coupon\ours (.dat, .frd)
Grip-Top: CalculiX total force [0.0410689, 105884] N; kernel [-1.7244e-09, 105993] N
Grip-Bottom: CalculiX total force [-0.0410686, -105884] N; kernel [1.64164e-10, -105993] N
probe node centre (node 446): CalculiX U [-3.19307e-11, 5]; kernel [-5.93358e-14, 5]
probe element centre (element 395): CalculiX mean strain [-0.07728, 0.2018, gamma 1.229e-06]; kernel centroid [-0.07731, 0.2019, 1.06e-06]
probe element near_grip (element 155): CalculiX mean strain [-0.009961, 0.1637, gamma 0.009662]; kernel centroid [-0.009692, 0.1635, 0.009414]
equilibrium (kernel): sum of reactions [-0.  0.] N
```

The CalculiX deck that ran is byte-identical to the committed `validation/decks/generated/tension-coupon-x840-nodal-ccx.inp` (`diff -q`), and the `-kernel.inp` the runner wrote is identical to the committed `-abaqus.inp`.

`uv run python examples/build_model.py validation/specs/tension-coupon-x840-coupling.toml --out <scratch>` (kernel solve of the coupled twin):

```text
kernel solve: reaction at RF-Top = [-1.68278e-09, 105993] N; equilibrium residual 1.44e-07 N; largest free-dof residual 7.42e-10 N
first-ply failure, max_stress: factor 0.0381923 on the applied loading, element Coupon-1.225, ply 2, in-plane shear
first-ply failure, tsai_hill: factor 0.0371133 on the applied loading, element Coupon-1.215, ply 2, interactive
```

`uv run python tools/record_from_dat.py validation/specs/tension-coupon-x840-nodal.toml <.dat> --deck-reference ... --deck-kernel ... --version 2.22 --tolerance 0.03 --floor 0.02 --element-probes centre --out validation/records/tension-coupon-x840-nodal-calculix.toml`:

```text
written validation\records\tension-coupon-x840-nodal-calculix.toml {'rf': 2, 'u': 1, 'strain': 1, 'ply_stress_local': 1, 'ply_strain_local': 1}
```

From `fea/`: `uv run pytest -q`

```text
242 passed in 55.08s
```

From `engine/`: `uv run pytest -q`

```text
437 passed in 40.60s
```

From the root: `npm run export:library`, `npm test`, `npm run typecheck`

```text
wrote 29 datasets for 26 materials to C:\Users\erikv\Documents\Composite_AI\engine\src\anisotropy_engine\data\material-library.json
ℹ tests 71
ℹ pass 71
ℹ fail 0
> tsc --noEmit
```

From the root: `uv run --project fea python docs/models/build.py fea/validation/records/tension-coupon-x840-nodal-calculix.toml`

```text
Characters without a LaTeX mapping (check how they render): §
69 numbers compared, 69 agree; LaTeX written to ...\docs\models\build\tension-coupon-x840-nodal-calculix\tension-coupon-x840-nodal-calculix.tex
Document written to ...\docs\models\build\tension-coupon-x840-nodal-calculix\tension-coupon-x840-nodal-calculix.pdf
```

The document's rebuild section prints the material as `library x840-z60-pw / chen-2015-x840-z60-pw-v1 (record 2026-10-18.1; Experimental and Numerical Investigation of Wide Area Blunt Impact Damage to Composite Aircraft Structures · Tables 3.1 and 3.2, §3.2.1 · University of California, San Diego · PhD dissertation ...); rights class licensed-reference`, followed by one citation row per value with its page (`.tex` line 386 onward). The deck header carries the same lines.

## What the numbers show

- CalculiX against the kernel on the team's coupon with the cited material: reaction 105884 N against 105993 N (0.10 %), centre strain within 0.05 %, all 69 recorded numbers (reactions, centre displacement, strain, ten plies' stresses and strains in material axes) within the 3 % tolerance. Reading note beside the record.
- The constants are the same as the team typed into CAE, so the kernel's reaction is the one the local comparisons of 2026-10-16 to 18 already showed; what the committed record adds is a citable material in a committed, reproducible model.

## Not run, UNVERIFIED

- The rendering of `§` in the PDF (the manual module reports it has no LaTeX mapping; the middle dot and degree sign were already reported on earlier documents). Open the PDF to check the citation row.
- The website in a browser (the library page's rights evidence text) and the Playwright suite.
- Any Abaqus run of the committed `tension-coupon-x840-*` decks; the team's own Abaqus run is compared locally in `.local/fea/abaqus/tension-coupon/comparison/`.
- The full CI command `uv run pytest -q -ra tests ../engine/tests` from `fea/` on Linux.
