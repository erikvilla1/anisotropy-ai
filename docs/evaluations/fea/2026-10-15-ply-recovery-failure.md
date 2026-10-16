# Evaluation: finite element chunk 3, ply stresses in material axes and first-ply failure (ADR-0029) | 2026-10-15

- Scope: `fea/recovery.py` pushes each element's membrane strain through its plies with the engine's `ply_surfaces` (zero curvature) and checks every ply with the engine's criterion dispatch; the smallest strength ratio over the mesh is the first-ply-failure factor with its element, ply and mode. The engine exposes `face_strength_ratio` and `check_criterion` (earlier private names kept as aliases). Cases gain per-ply stress and strain groups and an `fpf` group. Fixture decks state the Tsai-Wu interaction term f* = 0 explicitly.
- Environment: as chunk 2; `fea/uv.lock` unchanged.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests`

```text
106 passed in 1.48s
```

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` (the CI job)

```text
517 passed in 10.40s
```

From `engine/`: `uv run pytest -q`

```text
411 passed in 9.59s
```

From `fea/`: `uv run python examples/solve_deck.py validation/decks/coupon-2x8-grips-im7-8552.inp --units mm-MPa` (last lines)

```text
first-ply failure, max_stress: factor 0.726059 on the applied loading, element CFRP-Coupon-1.3, ply 1 (bottom = 1), mode transverse tension
first-ply failure, tsai_hill: factor 0.709915 on the applied loading, element CFRP-Coupon-1.3, ply 1 (bottom = 1), mode interactive
first-ply failure, tsai_wu: factor 0.678606 on the applied loading, element CFRP-Coupon-1.3, ply 1 (bottom = 1), mode interactive
first-ply failure, max_strain: not available (section 'CFRP-Coupon-1.CompositeLayup-1-1': Plies [0, ..., 9] have no strain limits; give them or state strain_limits = "from-strengths")
```

Reading: the gripped IM7/8552 [0/45/-45/45/0]s coupon at 0.8 mm of pull (1 % nominal) reaches first-ply failure at 0.73 of that, in a 0 degree ply by transverse tension, in the second element row from the bottom grip. The uniform one-element coupon at the same nominal strain gives 0.7706 (maximum stress), 0.7553 (Tsai-Hill) and 0.7239 (Tsai-Wu), the engine's own `first_ply_failure` values for the same state; transverse tension of a 0 degree ply at about 0.77 % axial strain is consistent with F2t / E2 for this dataset.

The team's deck has no `*Fail Stress`, so every criterion is refused by name ("Plies [...] have no strengths"; Tsai-Wu additionally needs f*). Nothing is assumed.

## What the tests cover (10 new in fea, 3 in the engine)

- Ply states equal the engine's `ply_surfaces` with zero curvature for all ten plies (stress and strain in material axes, stress in laminate axes, angles), bottom and top faces equal; the +45 and -45 plies differ because the state carries shear.
- First-ply failure equals the engine's `first_ply_failure` for maximum stress, Tsai-Hill and Tsai-Wu: factor to 1e-12, every ply's ratio to 1e-12, the governing ply is the bottom-most of the tied plies and its mode matches the engine's check for that ply. The factor halves when the imposed displacement doubles. Every element of the 2 by 2 mesh carries the same ratios. The isotropic homogeneous section gives sigma = E eps. The gripped coupon fails first within two element rows of a grip and the factor is the minimum over every ply of every element.
- Refusals by name: maximum strain without strain limits, an unknown criterion, Tsai-Wu without f*, a deck without `*Fail Stress`. `deck_f12_star` reads the sixth `*Fail Stress` value, returns None without it, and reads a changed value.
- Cases: the three IM7 cases now carry ten plies' stresses and strains and the three factors; the isotropic case its one-ply stress; the runner's self-tests still report a wrong value as exactly one disagreement.
- Engine: the public names are the earlier private objects; `face_strength_ratio` with nothing held equals the single-state ratio functions; `check_criterion` refuses an unknown criterion, Tsai-Wu without f*, maximum strain without limits, and plies without strengths.

## Not run

Website suites and the manual build: unaffected. UNVERIFIED for this chunk.

## Open against Abaqus

Abaqus writes failure measures MSTRS, TSAIH and TSAIW rather than a strength ratio; the comparison chunk converts (1/R, 1/R squared, and the Tsai-Wu quadratic form). The sign convention of the compressive limits in `*Fail Stress` and whether S11, S22, S12 at a layer's section point are in material axes remain UNVERIFIED until the team exports results.
