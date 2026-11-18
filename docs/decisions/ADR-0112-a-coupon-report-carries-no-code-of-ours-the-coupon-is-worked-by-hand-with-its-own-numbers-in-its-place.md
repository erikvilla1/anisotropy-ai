# ADR-0112: A coupon report carries no code of ours; the coupon is worked by hand with its own numbers in its place

- Status: Proposed
- Date: 2026-11-18
- Decided by: Founder, 2026-11-18 ("i don't want any code attached becasue the user shouldn't have that, instead have detailed physics, hand calculations solved instead of code. Code is propreitary from our end and shuoldnt be made public"; on the coupon report PDF); Founder, 2026-11-18 ("Keep the Abaqus scripts", on whether the downloaded package also drops our scripts and spec files) | Drafted by: Claude Code
- Related: [ADR-0041](ADR-0041-one-document-per-coupon-in-chapters.md), [ADR-0043](ADR-0043-coupon-audit-scored-by-a-fixed-rubric-delivered-as-one-package-folder.md), [ADR-0094](ADR-0094-models-move-to-and-from-abaqus-through-a-connector-under-the-users-own-abaqus-and-one-versioned-bundle-compared-privately.md), [ADR-0103](ADR-0103-the-working-behind-an-answer-is-written-by-the-fea-package-when-it-solves-and-shown-by-the-page-when-asked-no-model-writes-a-formula-or-a-number.md), `fea/src/anisotropy_fea/hand_calculation.py`, `docs/models/coupon.py`, `docs/models/build.py`, `docs/models/team.py`, `fea/tests/test_hand_calculation.py`, `fea/tests/test_coupon_document.py`
- Area: fea, docs

## Context

The coupon report (ADR-0041) printed our source code: Chapter 2 printed the engine's and the kernel's theory, each equation followed by the function that computes it with its line numbers; Chapter 3 printed the coupon's spec, the CalculiX twin's spec and the deck header; the verification chapter printed the CalculiX conventions file and the deck's header; Appendix A printed the comparison code and our record tools; Appendix B printed our record of the CalculiX run; a last appendix gave the commands of our repository that made the files. The package (ADR-0043) carried both specs. The title page and the README named our build script. A hosted run hands the PDF and the package to whoever ran it, and after PR #232 it keeps the report's LaTeX as `document_source` too. The founder asked on 2026-11-18 that no code reach the user and that detailed physics and hand calculations, solved, stand in its place.

## Options considered

1. Keep the theory and drop only the code listings: the equations stay, but nothing shows how they reach this coupon's numbers, and an engineer cannot check them. Rejected: the founder asked for hand calculations solved.
2. A hand calculation computed again in the document: a second implementation of laminate theory, whose numbers could differ from the engine's. Rejected by ADR-0001.
3. A hand calculation written by the fea package from the engine's own values (the pattern of ADR-0103), every formula evaluated again from the values put in and refused when it does not give the engine's value; the finite element model's physics in equations; our files described as tables of their values. Chosen.
4. For the package: drop the Abaqus build script and the verify scripts as well as the specs. Rejected by the founder ("Keep the Abaqus scripts"): the engineer runs them in Abaqus on their own job, and they are part of the two-click loop (ADR-0094).

## Decision

- Chapter 2 is the hand calculation of the coupon: the ply's stiffness, each ply angle's stiffness in the coupon's axes, the laminate's membrane stiffness, its compliance and engineering constants, the force and strain the loading gives with free edges, every ply's strain and stress in its fibre axes, each criterion's strength ratio (maximum stress, Tsai-Hill, Tsai-Wu, as the coupon names them) and the loading at first-ply failure. Each step gives its formula, the formula with this coupon's values put in to six significant figures, and the result, with the textbook equations it follows (Daniel and Ishai). `anisotropy_fea.hand_calculation` writes it; every result is the engine's value, and a formula that does not give it to 1e-9 raises `HandCalculationError`. The laminate-theory check against the model and CalculiX follows, then the first ply to fail by hand beside the model's, then the finite element model's physics in equations (the element, its stiffness, equilibrium, the reading of every ply). A coupon of several laminates gets a sentence; a bending coupon gets the stiffness steps.
- No listing of code and no file of ours is printed: Chapter 3 gives the model's inputs as a table and where the CalculiX twin differs; the conventions and the record are tables of what they hold; Appendix A gives the comparison rule in words and equations; the appendix of commands goes. The title page, README and audit form name the product and its version, not our scripts. The comments of the LaTeX preamble go.
- The package drops our two specs and keeps the Abaqus deck, the build script, the CalculiX decks, the material, our results and the three verify scripts.
- The Abaqus keyword boxes of Chapter 4 stay: they are the deck the user already holds, written in Abaqus's own syntax.
- `our_code_named` finds a listing, a path of our repository or the name of a file or package of ours in the LaTeX or README; the build prints a warning when a hand-written reading note or card puts one in, and the tests hold the generated text to none.

## Why (evidence)

- On the public IM7/8552 [45/0/-45/90]s coupon every step closes against the engine: A11 = A22 = 98842.3 N/mm, Ey = 60848.5 MPa, the coupon carries 16127.5 N at 1 mm, and the 90-degree plies 4 and 5 fail first by transverse tension at R = 1.0892 (maximum stress), 1.05937 (Tsai-Hill) and 1.00429 (Tsai-Wu); `fea/tests/test_hand_calculation.py` checks the order of the steps, the engine's values and the refusal of a value 0.1 % off.
- `fea/tests/test_coupon_document.py::test_the_reader_gets_hand_calculations_and_no_code_of_ours` builds the public tension package with the build and verify scripts and finds no listing, repository path or file of ours in the LaTeX, the README or the audit form, and no .toml or .md in the package.

## Consequences

- The report is longer in Chapter 2 and shorter elsewhere; a reader can repeat every step of laminate theory with a calculator.
- Our files stay with us: the specs, the record and the conventions are summarised, not printed. A reader who wants a value of the record finds it in the comparison tables of Chapter 6.
- The decks' first comment still names our generator and the spec's file name: changing it rewrites every committed deck and the digest every record holds, so it is left for a later change.
- A reading note printed in a report must name no file of ours; the public notes were reworded, and a local note that names one is reported by the build.

## How we will know it was wrong

- An engineer cannot follow a step of the hand calculation to its result with the printed values, or a printed result differs from the engine's.
- Any code of ours, a spec, a record or a path of our repository is found in a PDF, its LaTeX or a package a user downloads.
