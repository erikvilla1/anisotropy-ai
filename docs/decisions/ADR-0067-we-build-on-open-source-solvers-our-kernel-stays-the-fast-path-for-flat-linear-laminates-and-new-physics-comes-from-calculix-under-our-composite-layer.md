# ADR-0067: We build on open-source solvers instead of replacing them: our kernel stays the fast path for flat linear laminates, new physics comes from CalculiX, and our composite layer reads either solver's results

- Status: Accepted
- Date: 2026-11-09
- Decided by: Founder, 2026-11-09 ("I thought using opensource models was the plan to grow our platform it is not somethin we are trying to replace but more build upon"; then, on the recommendation below, "yes please write it up") | Drafted by: Claude Code
- Related: ADR-0001 (the engine computes every number), ADR-0029 (our own membrane kernel; option 2 was CalculiX), ADR-0030 (CalculiX as the reference solver, amendment 5 on the SPOOLES bound), ADR-0053 (the flat MITC4 shell), ADR-0062 (a solver-independent project), ADR-0066 (results compared in the ply axes; amendment 1, no Abaqus column), risks R-17 and R-19

## Context

The founder asked what Anisotropy adds that CalculiX does not have. Read from the code, the answer is that our solver adds no physics CalculiX lacks; it is the narrower of the two:

- **Our kernel** (`fea/src/anisotropy_fea/membrane.py`, `shell.py`, `kernel.py`) solves one linear static step on a flat plate with four-node elements: the membrane on the laminate's `A` (ADR-0029), and the MITC4 shell on `A`, `B`, `D` and the transverse shear stiffness (ADR-0053). The deck reader refuses everything else by name (`fea/README.md`, "What is read, and what is refused").
- **CalculiX** has composite shells and solids, buckling and nonlinear analysis already (ADR-0029, option 2), and its manual also lists contact, frequency, dynamic and heat transfer procedures (none of these run here yet); for composites its shells are S8R only, which it expands into one brick per element (ADR-0030).

What Anisotropy adds sits around the solve, and it is composite-specific: every ply's strain and stress in its fibre axes (`recovery.py`), first-ply failure by maximum stress, Tsai-Hill, Tsai-Wu and maximum strain (`engine/src/anisotropy_engine/failure.py`), the classical laminate theory column of the validation table (ADR-0066), the engine's mesh-free analyses (ABD, thermal, micromechanics, plate buckling, the cited material library), the coupon kinds built from one spec or form (`spec.py`, ADR-0046), the setup check (`checks.py`), the coupon package and its document (ADR-0049), the workspace chat, hosted jobs and the viewer (ADR-0056, ADR-0062, ADR-0063).

Growth is already built on open source in places: CalculiX solves the twin (`write_calculix.py`, `calculix.py`), Gmsh meshes the open hole (`mesher.py`), SciPy factors the kernel's matrix, and the per-ply read of CalculiX's `.frd` in the fibre axes (`frd.py`, ADR-0066 step 1) is the first place our composite layer runs on another solver's results. The founder then stated the direction: open-source solvers are the foundation the platform grows on, not something it replaces. What is not yet written down is where new solver capability comes from.

## Options considered

1. **Grow our own kernel for each new physics** (solids, nonlinear geometry, buckling eigenvalues, contact, dynamics). Every equation would be in `fea/docs/theory.md` with a code marker, one code path. But each new element and procedure re-implements what CalculiX already has and needs its own validation ladder; years of work that does not reach the composite layer, and against the founder's direction.
2. **Keep the kernel for what it does today, and take every new physics from CalculiX, with our composite layer applied to CalculiX's results.** The kernel stays the fast path and the independent check where both solvers apply; new kinds reach users at the cost of writing a deck and reading results, not a solver.
3. **Retire the kernel and run everything through CalculiX.** One solver to maintain. But it loses the sub-second solve the chat relies on, loses the independent second answer (CalculiX would have no twin), loses the four-node composite shell CalculiX refuses, and every result would rest on a binary whose conventions we detect by running it (R-17).
4. **Build on a commercial solver (Abaqus).** Rejected: the only installation is the founder's teaching licence, not for company work (ADR-0030), and the founder ruled it out of the product (ADR-0066 amendment 1, "open source calculix is enough").

## Decision

Option 2.

1. **The kernel's scope stays where it is**: one linear static step on flat plates, the membrane and the MITC4 shell, for the coupon kinds it solves today. Bug fixes, validation cases, speed and new coupon kinds within that scope are welcome. A new element type, a nonlinearity or a new procedure in the kernel needs its own decision record saying why CalculiX, or another open-source solver, cannot provide it.
2. **New physics comes from an open-source solver we drive**, CalculiX first: we write its deck from the same spec, run it as a separate program, and read its `.dat` and `.frd`. ADR-0029 already planned three-dimensional stresses this way.
3. **The composite layer is solver-neutral.** Per-ply results in the fibre axes, failure criteria, the laminate theory check where it applies, the fields, the explanation and the document read one result shape, whichever solver filled it, and the page says which solver solved and which checked. A job looks like an Anisotropy job either way.
4. **Where only one solver applies, the page says there is no independent check**, and that kind's validation comes from closed forms or published results before it is offered, as the ladder of ADR-0029 did for the kernel.
5. **Other open-source tools join the same way**: as programs we drive or libraries we call (Gmsh, ParaView through `.vtu`, and any later one), with the composite layer on top. Which ones is decided case by case, not here.

The numbers of a CalculiX-solved kind are CalculiX's displacements and stresses, labelled as such, and our tested code's per-ply values and failure indices computed from them; ADR-0001 holds for the second, and the first is cited, as the twin's numbers already are.

## Why (evidence)

- The scope comparison above, from `fea/README.md`, the kernel's refusals in `abaqus_reader.py` and ADR-0029's options.
- Speed: the kernel read and solved `fea/checks/unnotched-im7-8552/decks/unnotched-im7-8552-nodal-abaqus.inp` in 0.35 to 0.42 s (three runs in a cloud container, 2026-11-09). A whole hosted-image coupon job, CalculiX twin included, reported its result at 6.4 to 6.7 s (ADR-0064). CalculiX's own solve time on that coupon: no measurement here.
- Agreement where both apply: the same quantity read the same way agrees within 0.3 % between the kernel and CalculiX (ADR-0066), which is what makes each a check of the other.
- The first piece of option 2 exists: `frd.py` reads CalculiX's per-ply state in the fibre axes and `calculix_summary.py` carries it into the fields. No failure index is computed from CalculiX's results yet.

## Consequences

- Easier: a new analysis (a buckling eigenvalue, a solid model, a nonlinear coupon) is a deck writer, a results reader and validation cases, not a new solver. The engine's closed-form plate buckling (ADR-0022) is a ready check for a first CalculiX buckling kind.
- Easier: the founder's question "how does our engine do" keeps a second answer on every kind both solvers solve.
- Harder: the composite layer has to be split from the kernel's result types into one solver-neutral shape before a CalculiX-only kind ships; that is the first piece of work under this record, in its own pull request.
- We depend more on CalculiX: its version and conventions (R-17), its SPOOLES size bound in the image until PaStiX is built in (ADR-0030 amendment 5), and its licence. CalculiX is distributed under the GPL; we run it as a separate program and read its files, and what shipping it inside a customer's installation requires is not yet asked of counsel (no evidence yet; Gmsh's case is R-19).
- Kinds solved only by CalculiX have no twin, and the page must say so.

## How we will know it was wrong

- A capability the product needs is missing from CalculiX and every other open-source solver we can drive (for example a composite element or a damage model), so the kernel has to grow anyway.
- CalculiX-solved kinds are too slow for the chat: a typical coupon of such a kind takes longer than the hosted tier's 12-minute job limit (ADR-0056), or users stop waiting for it.
- Counsel says that shipping CalculiX inside a customer's installation is not acceptable for the self-hosted tier.
