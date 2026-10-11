# ADR-0019: The physics library presents every equation the engine implements, each naming its engine function and textbook location

- Status: Accepted
- Date: 2026-10-10
- Decided by: Erik Villa (founder) | Drafted by: Claude Code
- Related: `lib/physics.ts`, `lib/physics-foundations.ts`, `lib/physics-latex.ts`, `engine/docs/theory.md`, `tests/physics-reference.test.ts`, `docs/physics-library-completion-2026-10-10.md`

## Context

The website's physics library held 29 equation cards from the 2 October 2026 foundation work (classical laminate theory, ply failure, constituent estimates, thermal and moisture effects). Since then the engine gained prescribed curvature (ADR-0013), a temperature change (ADR-0014), mixed load and deformation conditions (ADR-0016) and failure with fixed and variable loads (ADR-0017), all documented in `engine/docs/theory.md` with textbook citations and validation cases. None of them had a card. A reader of the library could not see what the engine computes, and the two documents could drift apart.

## Options considered

1. Keep the physics library as a textbook-only equation reference and leave engine-specific operations in `theory.md`. Pro: no duplication. Con: the public page understates what the product computes, and nothing ties a card to a validated function.
2. Generate the physics cards from `theory.md` at build time. Pro: one source. Con: `theory.md` is written for the manual with LaTeX blocks and code markers; the cards need short plain-text equations, units and scope notes, and a generator would need its own review.
3. Hand-write a card for every operation `theory.md` documents, each naming the engine function it describes and the textbook or NASA location, and test that every card has a location, units and a typeset form. Pro: the page becomes a complete map of the engine's physics with checkable citations. Con: two places to update when the engine changes.

## Decision

Option 3. Every section of `engine/docs/theory.md` has a card. A card that describes an engine operation names the function in its detail text. Cards keep the textbook as the equation source where the book states the equation; the two operations the book does not state (prescribed curvature and mixed conditions) cite NASA RP-1351 for the constitutive relation and the engine theory for the rearrangement. Hashin–Rotem is presented only under that name and only as the textbook prints it; the later Hashin mode equations stay deferred.

## Why (evidence)

- `engine/docs/theory.md` sections 4 to 7 cite Daniel and Ishai Eqs. 7.27–7.28, 7.84, 8.16, 8.18, 8.20, 8.25, 8.33, 9.26–9.28 and NASA RP-1351 Eqs. 48–51; the engine reproduces 30 validation cases against printed answer keys.
- The textbook review (`docs/textbook-review-daniel-ishai-2006.md`) listed first-ply failure with fixed hygrothermal stress, Hashin–Rotem and the coupled compliance as candidate cards, with their printed pages.
- `tests/physics-reference.test.ts` checks that every card has a location, units and an https reference, and that every card name has a typeset equation.

## Consequences

Easier: a reader can go from a result in the calculator to the equation and its source in one place. Harder: an engine change now needs a card update and a theory update; the test count of cards pins the catalog so an accidental removal fails CI. We depend on the Daniel and Ishai page numbers staying those of the second edition.

## How we will know it was wrong

If a theory section is added without a card for two releases in a row, or if the cards and `theory.md` disagree on an equation, option 2 (generation from one source) should be revisited.
