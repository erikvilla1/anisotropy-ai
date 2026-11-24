# fea/checks/bond_cases

Two tests of fracture mechanics run in MOOSE, as an independent check of the bond that softens and lets go (ADR-0137; `fea/docs/theory.md`, Section 12). MOOSE is not a dependency: nothing that runs needs it. The files are kept so that the runs can be made again. Both were made with MOOSE's image `idaholab/moose`, version 2026.08.12-167ee97, on the models of `fea/tests/test_bond_solver.py`: two arms 100 by 1.98 mm of a unidirectional carbon ply in plane strain, 200 eight-node elements along the length and 8 through the two arms.

## The shear test (end-notched flexure)

The arms are bonded beyond a 35 mm crack, rest on supports 100 mm apart and are pressed down at mid-span. The bond's fracture energy is 1.0 N/mm and its strength 60 MPa, the same in peel and in shear.

- `shear-test.i`: the input file, run as `combined-opt -i shear-test.i NX=200 SIGMA=60 VISC=1e-6 OUT=shear-test`.
- `shear-test-moose.csv`: the curve that run gave. `time` is the movement of the load point in mm, `force` the force on it in N per mm of width, negative downward.

The largest load in the curve is 36.47 N per mm of width, 729.5 N on a width of 20 mm. With MOOSE's damping of the damage at 1e-4 and 1e-5 it was 731.0 and 730.0 N, so the number is the one the damping tends to. Our solver, which needs no damping, gives 729.5 N for the same model: `test_the_shear_tests_largest_load_is_mooses_and_nears_beam_theorys_as_the_strength_rises` holds it to that within 0.3 %.

After the largest load the two programs drift apart. In that MOOSE version a bond that is not opening ends its shear law at √2 times the stated slip; MOOSE's current source no longer has the factor. Only the largest load is compared.

## The peel test (double cantilever beam)

The arms are bonded beyond a 30 mm crack and pulled apart at their ends. The fracture energy is 0.352 N/mm and the strength 30 MPa.

- `peel-test.i`: the input file, run as `combined-opt -i peel-test.i NX=200 SIGMA=30 VISC=1e-4 OUT=peel-test`.
- `peel-test-moose.csv`: the curve that run gave. `time` is the opening of the arms' ends in mm (`tip_y` is half of it), `force` the force on one arm in N per mm of width.

While the crack grows, at openings from 2.0 to 5.3 mm, MOOSE's load is within 0.81 % of beam theory's with the root correction, and our solver's within 1.02 % (ADR-0137's trial). No test reads this curve: `test_the_peel_tests_load_follows_beam_theory_while_the_crack_grows` holds our solver to beam theory itself, within 2 %.
