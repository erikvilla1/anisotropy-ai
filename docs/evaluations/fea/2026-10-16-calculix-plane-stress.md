# Evaluation: plane stress for the CalculiX material (ADR-0030, amendment 1) | 2026-10-16

- Scope: `fea/` gains the spec key `material.transverse.plane_stress` (required), `TransverseChoice(plane_stress=...)` in the converter and `convert_to_calculix.py --plane-stress`; with `true` the CalculiX ENGINEERING CONSTANTS line carries nu13 = nu23 = 0 and the deck header says so. The committed IM7/8552 specs state `plane_stress = false`; their generated decks changed only in the header's spec digest, and the record's two deck digests were updated (no number in the record changed).
- Why: our generated model of the team's fabric coupon ran 2.8 % stiffer in CalculiX than in our kernel. The cause, proposed in a note from the founder and confirmed in the `.dat`: CalculiX expands a composite S8R into one brick, and the through-thickness Poisson ratios of its three-dimensional law lock the plies' different thickness contractions together, producing a through-thickness stress of about a sixth of the axial stress at the gauge centre. Abaqus LAMINA and our kernel are plane stress.
- Environment: Windows 11; CalculiX 2.22 from the PrePoMax v2.6.0 bundle (`C:\Tools\PrePoMax v2.6.0\Solver\ccx_dynamic.exe`, `ANISOTROPY_CCX`); `fea/uv.lock` unchanged.

## Commands and captured output

From `fea/`: `uv run pytest -q -ra tests ../engine/tests` with CalculiX available

```text
596 passed in 40.89s
```

(591 before this change; the five new tests: `test_spec.py::test_plane_stress_writes_zero_through_thickness_poisson_ratios_and_refuses_the_given_ones`, `test_write_calculix.py::test_plane_stress_puts_zero_poisson_ratios_in_the_engineering_constants_and_says_so`, `test_convert_deck.py::test_plane_stress_in_the_converter`, `test_calculix.py::test_plane_stress_removes_the_through_thickness_coupling_of_calculix_composite_shells[nu23-given]` and `[plane-stress]`, the last two needing CalculiX.)

The regression test's own numbers, printed by the same code outside pytest (a made-up fabric-like material, E1 = E2 = 50 GPa, nu12 = 0.05, G12 = 5 GPa, [0/45]s of 0.125 mm plies, the small fixture coupon of 2 by 8 S8R elements, 1 mm pull; the constants are test inputs, not a material):

```text
coupled      ccx RF_y   4768.27  kernel   4724.01  rel 0.0094  max|szz|/max|syy| 0.1212  mean eyy ccx 0.02521 kernel 0.02552  warnings 0
   ENGINEERING CONSTANTS: 50000., 50000., 50000., 0.05, 0.05, 0.4, 5000., 4000.
plane_stress ccx RF_y   4686.17  kernel   4724.01  rel 0.0080  max|szz|/max|syy| 0.0006  mean eyy ccx 0.02514 kernel 0.02552  warnings 0
   ENGINEERING CONSTANTS: 50000., 50000., 50000., 0.05, 0., 0., 5000., 4000.
```

The through-thickness stress is the signature: 12 % of the axial stress with the constants given, 0.06 % with plane stress. The reaction force remains 0.8 % from the kernel on this coarse mesh with either setting; that is the S8R-against-Q4 difference already recorded in the first comparison note, to be tested by the eight-node element (chunk E).

The committed IM7/8552 fixture does not show the effect (its E2, and so E3, is small): the same four-variant check on `tests/fixtures/small-coupon-ccx.inp` gave through-thickness over axial stress 0.0008 as committed and 0.0018 even with E3 raised to E1, reaction force unchanged to 0.01 %. The committed record therefore keeps `plane_stress = false` and its numbers.

On the team's coupon (material not public; numbers in `.local/abaqus/notes/prepomax-tension-generated-2026-10-16.md`): the reaction force moved from +2.8 % to -0.10 % of the kernel, the centre 0-degree ply axial stress from +9 % above classical laminate theory to +0.9 % (the kernel's own value, the rigid tabs holding the lateral contraction), the through-thickness stress from a sixth of the axial stress to 1e-4 of it, and the near-grip shear strain, 20 % off before, now agrees within 3 %. Our generated CalculiX deck and the team's converted deck give identical totals to 7 digits.

Classical laminate theory for that layup from the engine (`abd_matrices`, `ply_surfaces`, N_x = N_xy = 0, eps_y = 10/50) reproduces the two numbers quoted in the founder's note (reaction 105.0 kN, 0-degree ply axial stress 15689 MPa) to the digit, so the note's reference values are the engine's.

## Not run, UNVERIFIED

- Abaqus itself: the team's maximum-stress figure in the founder's note is as reported to us; no Abaqus field output has been exported yet (`docs/abaqus-export-recipe.md`).
- CI with `calculix-ccx` from apt (still UNVERIFIED from chunk B).
- The manual build after the theory paragraph (prose only, no new code marker; the marker test passes).
