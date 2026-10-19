# Reading: course reader problem 5.9, curing stresses in a cross-ply laminate

The reading of the two course reader 5.9 cases, AS4 and S-glass (the note's file name is a prefix of theirs).

## What the problem exercised

A [0/90]s laminate cooled from its cure temperature with no mechanical load: the thermal resultants, the mid-plane strain that results, and the residual stresses in the 0 and 90 degree plies (section 7 of the theory). Two materials, so the same steps run twice with different constants.

## What explains the differences

The key misprints two values: the thermal resultant N_T for AS4 and the mid-plane strain for S-glass. The cases record the values the engine and an independent hand calculation agree on, and say so in their source lines; `.local/homework/code/course-reader/cr59_reference.py` is that hand calculation, written with explicit cosine and sine formulas and without importing the engine.

## Verified, and not

- Verified by these cases: thermal resultants and residual ply stresses of a symmetric cross-ply laminate after cure, for two materials.
- Not covered: the key's misprinted values are not compared; what replaced them is the agreement of two independent calculations, not an outside source.
