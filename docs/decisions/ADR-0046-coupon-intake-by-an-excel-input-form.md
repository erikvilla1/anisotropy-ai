# ADR-0046: A coupon enters as an Excel input form the team fills in, read into the spec by a tool

- Status: Proposed
- Date: 2026-10-25
- Decided by: Founder, 2026-10-25: an Excel input form like the audit form; the founder runs the engine and the team only fills in the form; solver inputs only for now; a library material by name or the team's own constants with their source, own constants never in the repository. | Drafted by: Claude Code
- Related: `fea/src/anisotropy_fea/intake.py`, `fea/src/anisotropy_fea/forms.py`, `fea/tools/coupon_form.py`, `fea/tools/coupon_from_form.py`, `fea/tests/test_intake.py`, [ADR-0018](ADR-0018-source-rights-classes.md), [ADR-0030](ADR-0030-models-from-a-spec-calculix-as-reference-solver.md), [ADR-0038](ADR-0038-coupon-identity-card-and-designation.md), [ADR-0039](ADR-0039-case-pages-attempt-history-and-one-index.md), [ADR-0043](ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md)

## Context

- **The founder's aim.** The team should produce data with our engine. An engineer states a coupon test, we build and solve it, and the package goes back. The team recreates the model in Abaqus/CAE and audits it. Later the coupon is fabricated and tested, so the engine can be validated against a physical test.
- **What existed.** A coupon was described only by the TOML spec that `spec.py` reads. The documented way to start one was "copy a neighbour's spec". Nothing told an engineer which inputs are needed, in which units, or what is refused. No template existed anywhere in the repository (checked 2026-10-25).
- **Found on the way:**
  - The library has no short material code. The codes in coupon names (X840PW) are chosen by hand.
  - Only four library records give G13 and G23, which every spec and every Abaqus LAMINA material needs.
  - The documented step `regenerate_decks.py <coupon> <coupon>-nodal --ccx` stopped at the coupling spec and never wrote the twin's CalculiX deck.
  - A file could set `si = true` and skip unit conversion.
  - An unknown unit system crashed a tool instead of being refused.
  - The case pages crashed for a coupon that has specs but no CalculiX record yet.
  - The record tool did not create `ours/verification/`.

## Options considered

1. **The team edits the TOML spec.** Rejected:
   - the team would need the tools and the spec's vocabulary;
   - errors would show only when the founder runs it;
   - there are no pick-lists.
2. **A web form.** Rejected for now. There is nothing to host and no accounts yet (ADR-0006, ADR-0027), and it is far more code for one team.
3. **An Excel input form and a reader.** Chosen:
   - the team already fills in the audit form;
   - openpyxl is already a dependency;
   - the founder runs the engine.

## Decision

Option 3.

- **The form.** `fea/tools/coupon_form.py` writes it on demand, so the material list and the versions are current; no binary is kept in the repository. Its sheets:
  - **Coupon:** one labelled row per input in ten blocks, each with its unit and a line of help. The team's cells are yellow, and the fixed words are lists.
  - **How to fill it in.**
  - **Library materials:** the records the engine can resolve, with their constants, strengths, ply thickness, source and rights class.
  - **Record:** hidden; the form version and the engine version.

  The house style is shared with the audit form through `forms.py`.
- **The reader.** `fea/tools/coupon_from_form.py <form>`, through `intake.convert`:
  - It checks the cells and names every problem by its row, all at once (ADR-0003).
  - It names the coupon by the rules the coupon tests enforce: a code means one thing, and one thing has one code. Blank codes are reused or, for a layup, proposed.
  - It renders the team's build and its CalculiX twin, and lets `parse_spec` judge the exact text it will write. A spec refusal is reported with the form rows it concerns.
  - It writes `ours/<coupon>.toml` and `ours/<coupon>-nodal.toml`. It files the form as received in `team/<date>/` with a README, and writes a case-page skeleton when there is none (status in progress; attempt 01 is the intake). Then it prints the next commands.
  - `--replace` rewrites the two specs and nothing else. `--dry-run` writes nothing.
- **Fixed by us**, stated in the specs' comments and on the form:
  - units mm, MPa and N; element order 1;
  - plane stress and transverse isotropy for CalculiX (ADR-0030 amendment 1);
  - probes from the geometry;
  - max stress and Tsai-Hill when the material has strengths, no Tsai-Wu;
  - every output request.
- **Asked of the team every time:** G13 and G23.
- **The mesh.** An element size is turned into seeds with a node row on each tab line. When the team already has an Abaqus model, it gives that model's elements across, partition lines and rows per segment instead, so the audit's B1 row can match node for node. A compression amount is typed as a magnitude.
- **Only the four in-plane tests are offered.** Bending is refused by the model builder today.
- **The team's own constants.**
  - `material.source` marks them, and the engine gives them the rights class `user-supplied` (ADR-0018).
  - The deck heading, the coupon card, the document's material section, the package's `3-material/<name>.csv` and audit row B6 state the source.
  - The team comparison sets each value beside the one in the team's deck.
  - A spec with them may exist only under `.local/` (a test enforces it). They never enter `lib/`.
- **The fixes found on the way.**
  - `regenerate_decks.py` skips a CalculiX deck it cannot write and says why.
  - `parse_spec` refuses the loader's fields in a file, and turns an unknown unit system into a refusal.
  - The case pages and indexes say "no record yet". `coupon.py --all` skips such a coupon.
  - `record_from_dat.py` creates the folder it writes to.

## Why (evidence)

- **Tests, 2026-10-25.**
  - `cd fea && uv run pytest`: 417 passed.
  - `tests/test_intake.py`: 32. The public IM7/8552 stand-in filled in gives a spec equal to the stand-in's. Writer and parser agree. An element size lands a node row on each tab line. 17 refusals each name their row, and several problems come in one message. The open-hole block meshes the hole. The designation rules hold. The filing writes five files, refuses a second reading without `--replace`, and writes nothing on a dry run.
  - `tests/test_coupon_document.py`: two builds with the team's own constants, one without and one with a team deck.
- **End to end on the founder's machine, 2026-10-25,** with the public stand-in filled in on a fresh blank form:
  - The layup code L1 was refused: "L1 already names another stacking sequence on this machine". With the code left blank, the coupon was named IM7-UNT-L2.
  - `regenerate_decks.py IM7-UNT-L2 IM7-UNT-L2-nodal --ccx` wrote three decks and skipped the coupling spec's CalculiX deck by name.
  - `new_attempt.py` made attempt 02.
  - Our engine gave a reaction of 16211.7 N; CalculiX 2.22 gave 16161.3 N on the twin.
  - The record: 57 of 57 values within 3 % (floor 2 %), reaction +0.31 %.
  - `case_pages.py --check` exited 0.
  - `coupon.py IM7-UNT-L2` wrote the package with its PDF, the audit form and `3-material/im7-8552.csv`.
  - The demonstration coupon was then removed from `.local/fea/`.
- **The own-constants path, in a scratch folder:** the coupon IM7OWN-UNT-L1, rights class user-supplied, its deck heading line "material IM7-Team: the team's own constants: the NCAMP IM7/8552 report, typed in by the team; rights class user-supplied".
- **The team's experience with the form:** no evidence yet.

## Consequences

- **Easier.** An engineer states a coupon without our tools or vocabulary. Every refusal names its row. Every coupon starts with the same files, case page and commands. The team's own material data can be used without being published.
- **Harder.** The form's rows and the spec's fields must stay in step: a new spec field needs a row, its key-to-row entry and a test. Spec rules still arrive one at a time, because `validate_spec` stops at the first broken rule.
- **We depend on** the team filling in the form as given, and on openpyxl.

## How we will know it was wrong

- A coupon needs more than two form round trips before it reads.
- The team asks for inputs the form does not offer: bending, m-Pa units, second-order elements, Tsai-Wu, fabrication or test-plan fields.
- The team sends coupons by other means than the form.
