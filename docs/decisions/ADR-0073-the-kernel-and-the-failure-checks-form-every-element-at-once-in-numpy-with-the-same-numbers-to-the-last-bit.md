# ADR-0073: The kernel and the failure checks form every element at once in NumPy, with the same numbers to the last bit, instead of one Python call per element and ply

- Status: Proposed (the founder chose "Speed up the kernel first" on 2026-11-09; the record is drafted with it)
- Date: 2026-11-09
- Decided by: Founder, 2026-11-09 (direction: the decision card's "Speed up the kernel first") | Drafted by: Claude Code
- Related: [ADR-0068](ADR-0068-every-coupon-result-carries-a-mesh-convergence-study-by-the-kernel-on-two-refinements-of-its-mesh.md) (the study this speeds up), [ADR-0064](ADR-0064-a-coupon-job-reports-its-result-before-it-draws-and-builds-the-package.md) (the result before the package), [ADR-0001](ADR-0001-deterministic-engine.md) (the engine computes every number), [ADR-0029](ADR-0029-finite-elements-own-membrane-kernel-validated-against-abaqus.md) (the membrane kernel), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md) (the kernel stays the fast path); `engine/src/anisotropy_engine/failure.py`, `engine/src/anisotropy_engine/response.py`, `fea/src/anisotropy_fea/membrane.py`, `fea/src/anisotropy_fea/recovery.py`, `fea/src/anisotropy_fea/mesh.py`, `engine/tests/test_failure_arrays.py`, `fea/tests/test_kernel_arrays.py`

## Context

Since ADR-0068 every coupon run solves the kernel on its mesh and on two refinements (1,250, 5,000 and 20,000 elements for the public unnotched coupon) and checks every ply of every element by the four criteria. The study runs before CalculiX and before the run reports its result (`fea/tools/run_coupon.py`, stage "the convergence study"), so it delays the result ADR-0064 brought to 6.4 to 6.7 s.

Measured in a cloud container on 2026-11-09 (Linux, Python 3.13, the public unnotched IM7/8552 spec): `tools/convergence_study.py` took 24.0 and 25.7 s. A profile of the study put most of it in Python loops that call small NumPy or engine functions once per element or ply: the strength ratios (630,000 calls of the engine's `face_strength_ratio`), the ply states (26,250 calls of `ply_surfaces`), the kernel's assembly and strain recovery (236,250 calls of `strain_displacement`) and a gauge-set lookup by `tuple.index`. At 20,000 elements the sparse LU itself took 0.26 s of a 6.7 s solve.

## Options considered

1. **Keep the loops.** Nothing changes; every coupon result comes about 25 s later than before ADR-0068, and each job holds a solver container that much longer.
2. **Move the study after the result**, as the drawings and the PDF are. The result is fast again, but the study still costs about 25 s of container time per job, and the Summary's study table arrives later.
3. **Form every element at once in NumPy.** The kernel builds every element's stiffness and strains as stacked arrays; the engine gains array forms of `ply_surfaces` and of `face_strength_ratio` with nothing held, written beside the per-ply functions with the same operations in the same order, so the numbers are the same to the last bit. Chosen.
4. **A compiled extension (Rust through PyO3, or Numba).** A new toolchain and build for a gain NumPy already gives; the research of 2026-11-09 found the loops, not the arithmetic, to be the cost.
5. **Array forms inside the fea package only.** Faster too, but the failure criteria would then exist twice outside the engine, against ADR-0001.

## Decision

Option 3. `anisotropy_engine.response.ply_surface_arrays` is `ply_surfaces` for n mid-plane states, and `anisotropy_engine.failure.scaled_strength_ratios` is `face_strength_ratio` with nothing held for n ply states of one material; the per-ply functions stay and stay the reference. In the fea package, `membrane.assemble`, `element_strains` and `section_forces` form every element at once (`strain_displacement_all` refuses the first clockwise or degenerate element by name, as before), `recovery.element_ply_states` and `strength_ratios` call the engine once per section and ply, and `Mesh.element` looks a key up in an index built once. The shell (MITC4) assembly and its element states keep their loops: bending coupons and plates are outside the study, and a later change can treat them the same way.

## Why (evidence)

- Same numbers: a snapshot of every displacement, reaction, strain, section force, ply state, strength ratio and mode, first-ply-failure factor, element and ply, and gauge set, for the 7 check specs (unnotched nodal and coupling, compression, open-hole IM7/8552 and Kirsch by Gmsh, three-point bending, plate under pressure) and the 11 check decks in `fea/checks/decks/`, plus the whole convergence study, before and after the change: every array equal bit for bit; the only differences are the study's own timings.
- `engine/tests/test_failure_arrays.py`: the four criteria on 3,000 random states over twelve decades, with zero components, unloaded rows, a negative zero and limits that overflow, give the per-ply ratio and mode for every row; `ply_surface_arrays` equals `ply_surfaces` on 200 membrane and bending states. `fea/tests/test_kernel_arrays.py`: on a coupon mesh with every node moved, the assembled stiffness equals the per-element sum entry for entry, the strains and section forces equal the per-element products, every ply ratio and mode equals the engine's per-ply answer, and a clockwise element is named in the error.
- Speed, same container: `convergence_study` 23.5 to 24.0 s before, 1.9 s after; per mesh (1,250, 5,000, 20,000 elements) 1.13, 4.14 and 18.69 s before, 0.12, 0.30 and 1.49 s after.
- A whole coupon job, `tools/run_coupon.py` on the studio's public coupon values (`tests/fixtures/studio/values.json`) without the PDF, two runs each in the same container: at its 5 mm elements the result came at 8.2 s before and 3.2 to 3.6 s after, the job ended at 18.0 to 18.1 s before and 7.8 to 8.3 s after; at 2 mm elements (1,250, as the check spec) the result came at 36.0 to 37.4 s before and 8.8 s after, the job ended at 75.4 to 77.2 s before and 17.1 to 17.3 s after. Before, the study alone took 4.7 s of the 5 mm job and 27 s of the 2 mm one. The hosted image's times: not measured.
- `cd fea && uv run --extra mesh pytest -q -ra tests ../engine/tests`: 1,134 passed and 9 skipped before (5 min 41 s), 1,148 passed and the same 9 skipped after (2 min 4 s); the 9 need Abaqus, Tectonic or the team's local coupons.

## Consequences

The study no longer delays the result by more than a couple of seconds, and a solver container is free sooner. The engine carries two forms of the same equations, the per-ply functions and their array forms; a change to a criterion has to change both, and `test_failure_arrays.py` fails when they part. Bit-for-bit equality was measured on this machine's NumPy; another BLAS could differ in the last bit, which the tests that compare with a tolerance would accept and the bit-for-bit tests would report.

## How we will know it was wrong

Revisit if the bit-for-bit tests fail on CI or on the solver image (then compare with a tolerance of 1e-12 and say so), if a criterion is changed in one form and not the other, or if the shell solve becomes the slow step of a run (then give it the same treatment).
