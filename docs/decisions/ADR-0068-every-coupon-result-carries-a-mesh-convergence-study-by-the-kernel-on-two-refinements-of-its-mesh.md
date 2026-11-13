# ADR-0068: Every coupon result carries a mesh convergence study, by the kernel on two refinements of its mesh, so the reader sees which numbers settle and which grow

- Status: Proposed (the founder chose "mesh convergence section" over test-data validation and the remaining local re-runs on 2026-11-09; the record is drafted with it)
- Date: 2026-11-09
- Decided by: Founder, 2026-11-09 (direction: the decision card's "Mesh convergence section") | Drafted by: Claude Code
- Related: [ADR-0066](ADR-0066-solver-results-are-compared-as-one-set-of-quantities-in-the-ply-axes-at-stated-places-and-peaks-are-reported-apart.md) (the quantities and the peaks "that grow as the mesh is refined"), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md) amendment 3 (the open-hole convergence study in `tools/kirsch_hole.py`), [ADR-0064](ADR-0064-a-coupon-job-reports-its-result-before-it-draws-and-builds-the-package.md) (the run's steps), [ADR-0067](ADR-0067-we-build-on-open-source-solvers-our-kernel-stays-the-fast-path-for-flat-linear-laminates-and-new-physics-comes-from-calculix-under-our-composite-layer.md) (the kernel stays the fast path for flat linear laminates: the study is the kernel's); `fea/src/anisotropy_fea/convergence.py`, `fea/tools/convergence_study.py`, `fea/tools/run_coupon.py`, `fea/tests/test_convergence.py`
- Area: fea

## Context

On 2026-11-08 and 2026-11-09 the founder asked, three times in different words, how a number on the Summary can be trusted: how to verify a coupon he ran on the site, why PrePoMax shows another S11, why the Anisotropy and CalculiX columns differ. ADR-0066 answered the first two with the validation table and the peaks table, and its peaks table says the clamped-edge values "grow as the mesh is refined" without showing it. A reader has no way to see, on the page, that the gauge values are the ones a finer mesh would confirm.

The standard engineering answer is a mesh convergence study: the same model on a sequence of finer meshes, the quantities of interest beside each other, a value trusted where it stops moving. `tools/kirsch_hole.py` did one for the open-hole coupon by hand on 2026-10-19 (ADR-0030 amendment 3) and it set the case's tolerance; no coupon run does one, and nothing user-facing shows one. The founder's standing rule since 2026-11-08: anything user-facing is automatic, no manual drops or runs.

Measured on the public check coupon `unnotched-im7-8552-nodal` (IM7/8552 [45/0/-45/90]s, 25 by 250 mm, 1 mm pull; `fea/tests/test_convergence.py`, 2026-11-09, this container): the kernel solves its 10 by 125 mesh in 0.3 s, the 20 by 250 mesh in 1.1 s and the 40 by 500 mesh in 4.7 s; with the ply recovery and three failure criteria the whole study takes 20 s. The reaction reads 16211.75, 16208.51 and 16207.20 N (−0.02 % then −0.008 %); the 0° ply's σ₁ at the gauge-centre element 1180.75, 1180.52 and 1180.42 MPa; the 0° ply's largest |σ₁|, at the tab corner, 1295, 1467 and 1701 MPa (+12 % then +14 %); the Tsai-Wu first-ply-failure factor over the mesh 0.886, 0.778 and 0.668, and over the gauge section as ADR-0066 defines it (the `Gauge` set less the gripped row) 0.975, 0.884 and 0.772: the gauge-section factor is carried by the row of elements beside the gripped one, which sits on the same singular corner, and so it does not settle either. The 90° plies' largest |σ₁| (compression along their fibres, across the width) does settle: not every peak is singular.

## Options considered

1. Say in prose that the peaks grow with the mesh and the gauge values do not. Rejected: ADR-0066 did, and the founder read that prose and still asked; a sentence is not evidence a reader can check.
2. A study by hand per coupon, with a tool and a note, as the open-hole coupon has. Rejected: it is not automatic, so a user of the site never sees it, and a coupon's note goes stale when its spec changes.
3. Refine the element order (p-refinement, the S8R the CalculiX twin already uses) instead of the mesh. Rejected for now: the kernel's element is the bilinear membrane, and a study that changes the element and the mesh at once shows two things; the CalculiX twin is already the second element. Noted as a later step.
4. **The kernel solves every coupon on its own mesh and on two refinements that split each element along both axes, in every run, and the result carries the quantities of ADR-0066 on each mesh with the clamped-edge peaks and the failure factors, and flags which have settled.** Chosen (proposed here).

## Decision

### The study

- The meshes are the spec's own and its refinements by the factors 1, 2 and 4: a structured mesh's counts multiplied (or its seeds per segment, or its element size divided), so every tab line and partition line keeps its node row and the gauge-centre element shrinks around the same probe. A refinement past 40,000 elements is left out and the result says so (`left_out`); the cap keeps the study under about half a minute on the hosted solver.
- The quantities on each mesh are ADR-0066's validation set at the element nearest the `centre` probe (the record's gauge-centre element, by the model's own nearest-element rule): the reaction at the moving grip, the strain εx, εy, γxy, and every ply's σ₁, σ₂, τ₁₂ in its fibre axes; beside them, every ply's largest |σ₁| over the mesh with its element and whether it touches a gripped node (the clamped edge), and the first-ply-failure factor by each criterion over the mesh and over the gauge section. The element and node counts and the solve's seconds are recorded.
- A change is the step from the previous mesh as a fraction of the value on the finer mesh; for a triple, of the triple's largest component, so a component that is noise beside the others (ADR-0066's 4e-15 MPa shear) does not read as a change. A quantity has **settled** when its last step is under 1 %. The flags are per group: reaction, gauge strain, ply stresses, peaks, failure over the mesh, failure over the gauge. Settled is not an error bound: it says the next refinement is unlikely to move the number, nothing about the model's physics.
- The study is written by `fea/tools/convergence_study.py` as `<coupon>-convergence.json`, a run step after "our engine" (`run_coupon.py`, `STAGES`), and into the fields file's summary as `convergence`, the way CalculiX's numbers are (`beside`), so the page and the document read it from the one file. A coupon the study does not cover gets `studied: false` with the reason, never a stopped run: the study is a reading beside the result, not a condition of it. The tool prints the same table on the command line.
- Scope, for now: gripped in-plane coupons on the structured mesher (unnotched tension, compression, ±45° shear). The open-hole O-grid (Gmsh), the bending coupons and the plate are later steps, each named in the reason the result carries.

### What the reader sees

The Summary and the coupon PDF print the study under the validation table: one column per mesh (its counts and element count), one row per quantity, each cell the value and its change from the previous mesh, a mark where the quantity has settled, and one sentence per group saying so in words ("the gauge values change by less than 1 % between the two finest meshes; the clamped-edge peaks grow 12 % and 14 %, as a singular corner does"). The peaks row keeps ADR-0066's label, "not a validation value".

### The gauge-section failure factor

The study shows that the gauge-section factor of ADR-0066, which excludes only the gripped row, is set by the row beside it and does not settle. This record changes nothing about it: the table shows the number moving, which is the truth of that definition. A factor read at a stated distance from the tab line, or at the gauge centre alone, is a separate decision with its own record.

## Why (evidence)

- The numbers above, from `fea/tests/test_convergence.py` on the public coupon (the test asserts the reaction's change under 0.1 %, every ply's gauge stresses under 1 %, the 0° ply's peak growing by more than 10 % per refinement, the 90° ply's peak settled, and the flags `reaction`, `gauge_strain`, `plies` true and `peaks`, `fpf`, `fpf_gauge` false).
- Timings in this container (Linux, Python 3.13, the kernel's SciPy solver): 0.3, 1.1 and 4.7 s per solve at 1,250, 5,000 and 20,000 elements; 20 s for the whole study with the ply recovery and three criteria at every mesh. The hosted job already runs CalculiX and builds a PDF; the study adds less than the CalculiX step.
- The open-hole study of 2026-10-19 (`docs/evaluations/fea/2026-10-19-gmsh-open-hole.md`): the same method, by hand, is what set the Kirsch case's 2 % tolerance.

## Consequences

- Easier: a reader sees on the page which numbers a finer mesh confirms and which it does not, with the numbers rather than a sentence; a coupon whose gauge values do not settle at 4x shows that its mesh is too coarse.
- Harder: every run solves three times; a hosted job takes up to about half a minute longer on a large coupon, and the fields file grows by the study (the public coupon's by about 700 lines of JSON). The browser fixtures carry it.
- We now depend on the structured mesher's refinement keeping the tab lines on node rows (true by construction: the counts are multiplied) and on the kernel's nearest-element rule for the gauge element on every mesh.
- Open: the open-hole O-grid, the bending coupons and the plate; a gauge-section failure factor read away from the clamped edge; p-refinement as a second axis.

## How we will know it was wrong

- An engineer reads the table and still asks whether the number can be trusted: the presentation, not the study, needs another record.
- The study's time passes the CalculiX twin's on a hosted job, or a job times out because of it: lower the cap or move the study after the result (ADR-0064's document stages).
- A coupon's gauge values do not settle at 4x on a mesh the setup check accepted: the setup check's mesh rule needs the study's verdict, a separate decision.
