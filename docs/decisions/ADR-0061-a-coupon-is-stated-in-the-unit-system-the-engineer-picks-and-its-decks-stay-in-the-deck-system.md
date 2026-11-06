# ADR-0061: A coupon is stated in the unit system the engineer picks, its results and document come back in that system, and its decks stay in the deck system

- Status: Proposed
- Date: 2026-11-06
- Decided by: Founder, 2026-11-05 and 2026-11-06 ("i see the units are hard coded to only GPa, i want it to be flexible to U.S and other S.I units like MPa, mm, m etc freedom for the user to pick the units"; asked whether the solver and decks would show the units the user selected, and told that the decks stay in one system while the results, the PDF and the package's PDF read in the user's units: "yes, make no mistakes") | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0002](ADR-0002-si-units-inside-the-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (amendment 5), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0055](ADR-0055-the-studio-opens-on-a-guided-chat-that-fills-the-same-form-rows-and-the-full-form-stays-one-click-away.md), [ADR-0060](ADR-0060-the-chat-solves-laminate-problems-through-the-case-solver-with-every-value-in-its-own-unit.md); `fea/src/anisotropy_fea/units.py`, `fea/src/anisotropy_fea/intake.py`, `docs/models/coupon.py`, `lib/studio-chat.ts`, `fea/tests/test_deck_units.py`, `fea/tests/test_intake.py`, `fea/tests/test_checks.py`, `fea/tests/test_coupon_document.py`, `tests/studio-chat.test.ts`, `tests/browser/studio.spec.ts`

## Context

ADR-0060 made the chat's laminate problem free in its units and left the coupon flow in mm and MPa: every row of the coupon input form (ADR-0046) carried "(mm)", "(MPa)" or "(N)" in its label, the checklist, the preview, the document and the package read the coupon in those units, and `units.py` knew two systems, `mm-MPa` and `m-Pa`, both of them deck systems. An engineer with a coupon drawn in inches and a datasheet in psi had to convert every number by hand before typing it, and read the results back the same way. The founder asked for the same freedom the laminate flow has.

Three facts shape the choice. The engine works in SI inside and converts only at entry and exit (ADR-0002), and nothing in the browser may compute a number (ADR-0001), so the page cannot convert. An Abaqus or CalculiX deck carries no units: every deck we write, read back, compare with the team's and record is in one of the two metric deck systems, and the team's own decks are stated in one of them (`team.py`), so a deck in inches would have no twin to compare with and no reader. A coupon job takes about ninety seconds of finite elements; the laminate flow re-solves the problem in another system on a toggle because it solves in milliseconds, which a coupon job cannot.

## Options considered

1. Convert in the browser: a unit menu, the page multiplies by the factor and sends millimetres. Rejected as in ADR-0060: a number the page computes, a second factor table that can drift, and a run record of values the engineer never typed.
2. A separate `stated_units` field beside `CouponSpec.units`, the deck's system staying in `units`. Rejected: two unit fields on every spec, every reader of a spec choosing between them, and a coupon file that states its units twice.
3. `CouponSpec.units` is the system the coupon is stated and read in, one of four: `mm-MPa`, `m-Pa`, `in-psi`, `in-ksi`. Every deck we write, read, compare and record is in `deck_units_of(units)`: the stated system when a deck is written in it (`mm-MPa`, `m-Pa`), `mm-MPa` otherwise. The reader-facing outputs (the checklist, the preview, the fields, the explanation, the document's problem, results and cover chapters, the values a coupon reads back into) use the stated system; the decks, the deck chapters, the CalculiX record, the audit, the verification, the team comparison and the package's CSV files use the deck system, and every one of them says which (chosen).
4. Decks in the stated system too, inches included. Rejected: a deck in inches has no twin among the team's metric decks (`team.py`), the public checks and CalculiX records are all metric, and a deck carries no units for a reader to tell them apart by.

For the chat: a message that names another system while dimensioned rows are already stated is refused with the reason, and an explicit switch (the Units menu on the test question, or a message that asks for the switch) clears the dimensioned rows and says which, so no number is ever read in a system other than the one it was typed in. A value typed without a unit takes the stated system's unit; a value typed with a unit of another system is converted by nothing: the chat reads the number and leaves the check to refuse it. The decks are never re-solved in another system after the fact; a coupon stated in in-psi is solved once and read in in-psi.

## Decision

Option 3. `units.py` gains `in-psi` and `in-ksi` (from the engine's `INCH`, `LBF` and `PSI`, one set of constants for the repository), `DECK_UNIT_SYSTEMS`, `DECK_UNITS = "mm-MPa"`, `deck_unit_factors` (refuses a system a deck is not written in: "An Abaqus deck carries no units."), `deck_units_of`, `units_words` and the `UNIT_LABEL` table that every document, the studio and the case pages share. The deck reader (`model.to_si`), the deck writers, `femodel` (whose heading says "units of this deck: mm-MPa (the coupon is stated in in-psi)"), `compare`, `audit`, the plots, the CalculiX record and the examples take the deck system from `deck_units_of(spec.units)`.

The form (version 0.6, ADR-0046 amendment 5) gains a Units row, first in "The coupon", with the four systems as its words; every row with a unit has a label in each system (`Field.label_in`), the check names rows in the stated system ("Length (in)"), and `values_of_spec` reads a coupon back in its stated system. The checklist's units item says "every row in in, psi and lbf; the results come back in the same units; the Abaqus and CalculiX decks are written in mm, MPa and N, as every deck we solve is". The document states the problem and the results in the stated system, adds a note when it differs from the deck system, and the package's README says "Numbers in the files are in mm, MPa and N; the PDF states the coupon in in, psi and lbf, as the team did."

The page converts nothing: `fea/tools/export_form_definition.py` writes each row's label and default in every system, the systems' words and labels, the deck system, and each library material's E1, E2, G12 and ply thickness in every system into `lib/coupon-form-definition.json`, and the chat reads them from there. The chat's test question carries the Units menu; its widgets, chips, tape estimate, thickness note and summary take their labels and figures from the definition.

## Why (evidence)

- `cd fea && uv run pytest -q tests/test_deck_units.py tests/test_intake.py tests/test_values_input.py tests/test_checks.py tests/test_spec.py`: the four systems' factors and `deck_units_of`; the public IM7/8552 coupon restated in in-psi gives the same SI spec, a deck written in mm-MPa with the heading above, and a card in inches; own constants typed in psi are the same material; every refusal names its row in inches; the checklist of an inch coupon reads "9.84252 by 0.984252 in, 2.20472 in tabs" and warns "Msi typed as psi"; a coupon reads back in in-psi.
- `cd fea && uv run pytest -q tests/test_coupon_document.py`: the in-psi public coupon's document reads "lengths are in in, stresses in psi, forces in lbf" with the deck note, its deck heading names both systems, and its README says where each number's units are.
- `npm test` (`tests/studio-chat.test.ts`, `tests/studio-form.test.ts`): labels, summary, chips and library constants per system; "pulled 0.04 in" and "2000 lbf" read in in-psi; a message naming another system refused while rows are stated, an explicit switch clearing them; `blankForm("in-psi")` taking the engine's element size for inches.
- `tests/browser/studio.spec.ts`, "a coupon stated in inches and psi is read, labelled and sent in those units": the chat with in-psi picked shows "G13 = 680000, G23 = 433300 psi" and "Ply thickness 0.0072 in", sends `units: "in-psi"` with the lengths in inches and the force in lbf to `POST /v1/coupon-jobs/check`, refuses "pull it 1 mm, in millimetres", and the full form reads "Length (in)".
- The counts and the full outputs are in the pull request of this change.

## Consequences

Easier: an engineer states a coupon in the system of their drawing and datasheet and reads every result, the checklist and the PDF in it; the labels, defaults and library figures the page shows in each system are the engine's; the laminate and coupon flows follow one rule (the engine converts, the page converts nothing).

Harder: the deck chapters, the audit and the package's files read in the deck system while the PDF's problem and results read in the stated one, and a reader of an inch coupon's package must read the sentences that say so; a coupon's units are fixed once typed, and changing them in the chat clears the dimensioned rows; `in-ksi` and `in-psi` share labels but for the stress, which the checklist's "Msi typed as psi" warning watches.

We now depend on `UNIT_LABEL` in `units.py` as the one table of labels, on `deck_units_of` at every place a deck is written or read, and on the form definition JSON carrying the per-system figures, held equal to the package by `fea/tests/test_studio_tool.py`.

## How we will know it was wrong

- A team deck arrives in inches and we need to compare with it: the deck system stops being a function of the stated system, and option 4 returns with a reader for inch decks.
- Engineers ask to see a solved coupon's results in another system without solving again: a conversion of the results on exit, in the API, as the laminate flow's re-solve is today.
- A number on the page in one system differs from the engine's in that system: the definition JSON has drifted, and `test_studio_tool.py` must have missed it.
