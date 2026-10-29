# ADR-0055: The studio opens on a guided chat that fills the same form rows; the full form stays one click away

- Status: Proposed
- Date: 2026-10-29
- Decided by: Founder, 2026-10-29 (the studio "looks very html, the flow feels not smooth, wording can be confusing"; all interaction should happen in the chat interface; ship fast to get feedback from users) | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md), [ADR-0003](ADR-0003-reject-invalid-input.md), [ADR-0004](ADR-0004-sign-and-stacking-conventions.md), [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md), [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md), `lib/studio-chat.ts`, `components/studio/coupon-chat.tsx`, `tests/studio-chat.test.ts`, `tests/browser/studio.spec.ts`

## Context

- The studio (ADR-0051) shows the input form's sixty rows at once, grouped as the Excel sheet groups them. Engineers meet spreadsheet wording ("Value (mm or N)", "Solve") and the angle convention (0 degrees across the coupon, ADR-0004) only in a hint line.
- The site's chat (`/chat`) is a scripted preview: it never reaches the API and computes nothing.
- The API already judges every row (`POST /v1/coupon-jobs/check`) and the template already words every result (ADR-0052).

## Options considered

1. **A guided chat in the studio that asks one thing at a time and fills the same form rows; the full form stays as a tab.** One values object, one check, one solve; the chat is a new way to type the rows. Chosen.
2. **Replace `/chat` with the coupon assistant.** One chat on the site, but the scripted preview's other answers (comparison table, report outline, data checklist) and their tests would go in the same change.
3. **Restyle the form only.** Cheaper; the sixty rows stay in front of the engineer.
4. **A language model reads the engineer's messages.** Freer wording; needs the provider setting of ADR-0052 on every turn, and a model's reading of a number is not checkable the way a pattern is.

## Decision

- `/studio` opens on the guided chat. It asks for the test, the material, G13 and G23 when the library lacks them, the layup in laminate notation, the size, the load and the engineer's name, offering one-click answers. A typed message is read by fixed patterns (`readMessage`): test names and ASTM numbers, library materials, laminate notation such as `[45/0/-45/90]s`, `[0/90]2s`, `[±45]2`, `L x W mm`, tabs, a hole, a span, a ply thickness, a travel in mm or a force in N or kN. What it reads is echoed back before it is used; what it cannot read changes nothing.
- When nothing is missing the chat runs the setup check itself and shows blocking items with a Fix button that returns to the question owning the row. Ready setups get a Run analysis button; the results come back as a message (reaction, largest displacement, the earliest first-ply failure R, the template's first sentence, the CalculiX agreement) beside the existing 3D results.
- The rows carry between the chat and the full form, which keeps the plate, the Abaqus mesh and the Abaqus names.
- The chat states the angle convention when it asks for the layup; the convention itself is unchanged (ADR-0004).
- The browser computes no result (ADR-0001). It converts kN to N on entry and offers the tape estimate G13 = G12, G23 = E2/3 from the library's numbers as a choice the engineer clicks, noted on the coupon as the form's help asks; no row is filled without the engineer's click or words (ADR-0003).
- `/chat` stays the scripted preview for now (changed by amendment 1).

## Why (evidence)

- The browser test plays the API from the public fixtures: the clicked path and a typed change reach the same check and solve as the form, and one typed line fills the open-hole rows that then show in the full form (`tests/browser/studio.spec.ts`). The typed reading and the notation are unit-tested (`tests/studio-chat.test.ts`), including that the chat and the example send the same values.
- No user evidence yet: the change is for collecting it.

## Consequences

- Easier: a first coupon without reading the form; changes by one line ("make it [0/90]2s").
- Harder: a second way to fill rows to keep in step with the form definition; new rows need a question or stay in the full form.
- Two chats on the site until `/chat` is settled (option 2).

## How we will know it was wrong

- Engineers in the first feedback round open the full form for coupons the chat covers, or a typed message is read into a wrong row.

## Amendment 1 (2026-10-29): `/chat` is the coupon assistant

- Decided by: Founder, 2026-10-29, on the question "Should /chat become the new coupon assistant?": "Point /chat at the coupon chat" (option 2 above, taken after option 1 shipped).
- `/chat` renders the same guided chat and full-form tab as `/studio`, full screen under the chat header. The home page's message and a library material (`?material=` with a library id) start the conversation there; the home composer drops its response-format menu.
- The scripted preview's answers (scope brief, comparison table, data checklist, scope JSON, LaTeX outline, specification editor) are no longer reachable from `/chat`; their browser tests are replaced by the chat's. `components/workspace.tsx` keeps serving `/data`; its unused assistant code and `lib/demo.ts`'s scope helpers can go in a later cleanup.
- A typed load keeps its minus sign (`-20 kN` is read as -20000 N) so the setup check refuses it rather than the chat dropping the sign (ADR-0003).
