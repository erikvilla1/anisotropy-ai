# ADR-0090: A tension coupon is built from its material and layup; the standard and the software choose the rest, and say so

- Status: Proposed
- Date: 2026-11-11
- Decided by: Founder, 2026-11-11 (on the first plan: "another confusing non user friendly is the inputting for abaqus for abaqus deck it doesn't make sense why the user has to do all of that, it shouldn't be there, all we need is more simpler input for the user ... what we are trying to do is recreate the model with our AI/software gives us the output files boom"; then, asked: the screen is "Two choices + chat", and what may be changed is "Own material constants, Pull or force, Coupon size and tabs, Mesh size") | Drafted by: Claude Code
- Related: [ADR-0089](ADR-0089-only-unnotched-tension-under-d3039-or-no-standard-is-offered-until-its-abaqus-comparison-is-validated.md) (one test first), [ADR-0046](ADR-0046-coupon-intake-by-an-excel-input-form.md) (the form's rows), [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (the workspace's panels), [ADR-0072](ADR-0072-a-coupons-test-standard-is-a-profile-of-clause-tagged-requirements-the-specimen-is-checked-against-and-a-deviation-is-reported-never-refused.md) (D3039's Table 2), [ADR-0003](ADR-0003-reject-invalid-input.md) (no silent defaults); `fea/src/anisotropy_fea/tension_input.py`, `lib/tension-screen.ts`, `components/workspace/tension-screen.tsx`, `fea/checks/d3039-im7-8552/`

## Context

The coupon workspace asked for a tension coupon in nine steps over about ninety rows: the test and the standard, the project, the geometry with its tabs and strain measurement, the layup and the material with G13 and G23, the loads and the grip kind and region, the mesh with "Your Abaqus mesh" (elements across, partition lines, rows per segment), a validate step, the run with the name of who runs it, and an Advanced panel with the Abaqus names of the part, the instance, the material, the layup and the section set. Most of those rows have one right answer for a D3039 coupon, or are already derived by the package when left blank (`intake.mesh_data` computes the partitions and seeds from an element size; D3039's Table 2 gives the size by the laminate's class). The founder found the input confusing and asked for the software to recreate the model from a simple input and hand back the files.

## Options considered

1. **Keep the panels and hide the advanced rows.** Rejected: most of what confused (G13, G23, the grips, the mesh, the strain measurement, the name) is not on the advanced panel, and the steps would still be nine.
2. **Fill the rows on the page with D3039's values.** Rejected: the page computes nothing (ADR-0051); the rules would live in two places.
3. **A preset the engineer loads, then edits.** Rejected: it leaves every row on the screen, which is what confused.
4. **The engineer gives the material and the layup; the package chooses every other row, each with its reason, and the page shows the list (chosen).** Four things stay changeable, as the founder named them.

## Decision

**The screen.** With the switch of ADR-0089 off, the coupon workspace is one screen: the standard (ASTM D3039, or no standard and the engineer's own size), the **material** (from the library, or the engineer's own constants), the **layup** (a notation, `[45/0/-45/90]s`), and **Build**. Folded under "Change a choice": the pull or force, the coupon's size and tabs, the element size; the own material's constants open when "My own material" is picked. The chat beside it fills the same choices from a sentence ("D3039 tension, IM7/8552, [45/0/-45/90]s") and asks only for what is missing. The check and the live preview run by themselves; Build runs the check and, when it is ready, the full analysis. The files (our Abaqus deck, the CalculiX deck and results, the document, the package) appear under Files. No Abaqus row is on the screen.

**The choices.** The page sends its own rows with `"input": "tension"`; `anisotropy_fea.tension_input.complete_tension` chooses every row the engineer left, before the setup check reads them, and never changes a row the engineer gave:

| Row | Chosen | Why |
|---|---|---|
| Test, units, standard | unnotched tension, mm-MPa, D3039 | the one test offered (ADR-0089); the decks' units; the test's standard |
| Width, length, tab length | D3039 Table 2 by the layup's class: 15 x 250 mm with 56 mm tabs for 0° unidirectional, 25 x 175 mm with 25 mm tabs for 90°, 25 x 250 mm for balanced and symmetric with our 56 mm grip length (Table 2 gives none) | the standard's size |
| Strain | an extensometer, 25 mm, at mid-length | D3039 §7.3; §7.3.2 allows 10 to 50 mm |
| Grips | nodal, on the whole tabs | the D3039 check and its CalculiX twin |
| Loading | a 1 mm pull | the model is linear: the loading at first-ply failure does not depend on it |
| Element size | 2 mm, structured, node rows at the tab lines and the extensometer's ends | the check's mesh; the full run adds a mesh study |
| G13, G23 | G13 = G12; for a tape G23 = E2 / 3, otherwise G23 = G12; to 0.01 MPa | the form's own estimates (its Definitions); only CalculiX's brick and the Abaqus shell's transverse shear read them, and a pull in the plane does not load them |
| Criterion | all; none when an own material gives not all five strengths | |
| Filled in by, date | the remembered name or "studio"; today | |

A layup in no Table 2 class, or a coupon under no standard, gets no size: the check asks for the length, width and tab length by row. Each choice is listed with its reason in the checklist (`built`), on the screen under "How we built it", and in the coupon's document (a section of the problem chapter, read again from the values file the job filed).

**The reference is the default path.** IM7/8552 with [45/0/-45/90]s under D3039 builds the public check `fea/checks/d3039-im7-8552` node for node, set for set and card for card. The check's spec takes the two rows that differed: G23 = E2 / 3 = 2987.73 MPa in place of a nominal 3000 MPa, and the studio's second element probe beside the bottom tab.

The full panels stay, unchanged, for the hidden tests in development (`ANISOTROPY_ALL_TESTS=on`). The Excel form keeps its rows for the team (ADR-0046).

## As built (2026-11-11)

- `fea/src/anisotropy_fea/tension_input.py` (`complete_tension`, `d3039_class`, `Built`); `intake.read_values` completes a values file that says `"input": "tension"` and refuses any other input word; `FormInput.built` and `Checklist.built` carry the list to the check's answer.
- `fea/checks/d3039-im7-8552`: G23 and the near-grip probe; both decks regenerated; the CalculiX record re-pinned on a new CalculiX 2.22 run (every value moved in its fifth significant figure or later; the reading says so).
- `docs/models/coupon.py`: `tension_choices`, `built_section`, in the problem chapter.
- Page: `lib/tension-screen.ts` (`tensionValues`, `tensionMissing`, `builtLines`), `components/workspace/tension-screen.tsx`; the workspace shows it with the switch off; the live solve sends its rows; the chat's steps are the material, the layup and, under no standard, the size (`nextStep(form, simple)`), and it waits for the API's switch before its first question.
- Tests: `fea/tests/test_tension_input.py` (each class, a layup in no class, given rows kept, the transverse moduli, the input word, and the reference pick against the check's model and deck); `fea/tests/test_coupon_document.py` (the section); `tests/tension-screen.test.ts`; the browser scenario of the screen in `tests/browser/studio.spec.ts`; the stand-in API's switch is on by default, so the other scenarios keep testing the full panels.

## Why (evidence)

- `intake.mesh_data` already derives the check's mesh from a 2 mm element size, nodal grips and a 25 mm extensometer (nx 12, seeds 28, 28, 12, 28, 28); `fea/tests/test_tension_input.py` builds the check's model from the two inputs.
- The tests and their output are in the pull request.

## Consequences

- Building a D3039 tension coupon takes two inputs. Every value the software chose is visible, with its reason, on the screen and in the document.
- The full panels are a development view until the other tests return; each will need its own short screen and its own choices when it is enabled.
- The G13/G23 estimate for a fabric is a placeholder (taken equal to G12); a membrane pull does not load it, a bending test would.

## How we will know it was wrong

- An engineer cannot state a coupon they need with the two inputs and the four changes (for example a tabbed coupon of a fabric under D3039 that falls in no class, or a coupon that needs coupling grips).
- A choice listed under How we built it differs from what the deck holds (a test of the reference pick fails).
