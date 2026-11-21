# ADR-0134: The FEA workspace is the model across the window, with the chat full height on the right and a results card under the model

- Status: Proposed
- Date: 2026-11-21
- Decided by: Founder, 2026-11-20 and 2026-11-21 (on agent-made mockups of the workspace: "less clustered, more minimal"; "give me more canvas looking setups, also is there a way to make the FEA look more like FEA, like how the images look like"; "showcase card looking good but the AI chat is kind of hidden"; "or maybe chat on the right and the other card middle underneath"; then layout D, "Chat right", picked on a card, and, on the build plan, "laminate and cad after, and yes continue") | Drafted by: Claude Code
- Related: [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (the three columns, which stay for Laminate and CAD, amendment 3), [ADR-0111](ADR-0111-the-fea-workspace-sets-a-model-up-in-a-model-tree-on-the-left-in-the-words-of-any-finite-element-program-and-the-chat-changes-the-same-tabs.md) (the model tree, now a flyout, amendment 3), [ADR-0063](ADR-0063-the-viewer-colours-fields-on-the-graphics-card-from-the-packages-values-and-ranges-unlit-for-results-and-lights-the-model-for-presentation-without-external-assets.md) (the FEA look, amendment 1), [ADR-0098](ADR-0098-the-home-pages-demo-shows-an-example-wing-whole-apart-analysed-and-whole-again-from-one-recorded-solve-of-the-mesh-it-draws.md) (the rainbow, amendment 12), [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md) (short answers), [ADR-0124](ADR-0124-the-workspace-has-three-sections-fea-cad-and-laminate-fea-opens-blank-and-the-chat-sets-it-up-for-the-work-asked-for.md) (the FEA section); `components/workspace/canvas-shell.tsx`, `components/workspace/canvas-slots.tsx`, `components/workspace/fea-workspace.tsx`, `components/workspace/wing-workspace.tsx`, `components/studio/results-view.tsx`, `app/workspace/canvas.css`
- Area: website

## Context

Since ADR-0062 a workspace page is three columns under a toolbar: the setup panels (the model tree of ADR-0111 in the FEA section) on the left, the model and everything about the result in the centre, the assistant on the right. In the centre the model is one panel of 520 px among the field controls, the answer, the readout, the summary tables and the explanation, so the page scrolls and the model is a small part of it. On 2026-11-20 the founder asked for agent-made iterations of the workspace, "less clustered, more minimal", then "more canvas looking setups" with the FEA drawn "more like FEA". Three rounds of live mockups followed, the last two drawing two real records of the repository (`tests/fixtures/studio/fields.json` and `lib/demo-wing.json`). He chose a showcase card under the model, said the chat was "kind of hidden" in it, and on 2026-11-21 picked layout D of four chat-forward variants: the chat full height on the right, a results card under the model. He then agreed the build plan, with Laminate and CAD keeping today's columns until FEA is done.

What binds the design: every number is written by the fea package (ADR-0051), the model tree keeps its tabs and words (ADR-0111), the chat keeps its answers and Apply (ADR-0099, ADR-0128), the founder sees what a customer sees (ADR-0089 amendment 6), and no detail of the verification is shown to a customer (ADR-0111 amendment 2).

## Options considered

1. **Two cards**: the answer card and a chat card side by side under the model. Rejected by the founder: the chat stays small and low.
2. **Ask bar**: one line to ask in, under the model, the conversation opening over it. Rejected: the conversation is hidden until asked.
3. **Chat card**: the conversation in the showcase card itself. Rejected: the answer and the conversation fight for one card.
4. **Chat right (D)**: the model across the window, the chat full height on the right, the results card centred under the model, the tree folded to an icon rail on the left. Chosen by the founder.
5. **Keep the three columns and trim the centre.** Not offered again: the founder asked for less clutter and a larger model, which a column of the page cannot give.

## Decision

Option 4, for the FEA section: the coupon (set up, imported, a past analysis opened again, the fibre tow), the blank start and the wing. Laminate and CAD keep ADR-0062's columns until the founder moves them.

- **The window.** Under the site's workspace header (the logo top left), one screen that does not scroll: an icon rail on the left, the model in the middle, the chat on the right. The model's area is a full-size 3D view; its view buttons stay at its top right and the boundary conditions and loads it lists (ADR-0110) sit over its top left.
- **The tree.** The icon rail holds one button per tab of the model tree. A button opens the tree as a flyout beside the rail, scrolled to that tab and with it open; the model gives it the room. The flyout holds the same tabs, rows and words as before, Run analysis at its top. It is open while a project is being set up and closes once when a run's results first show; after that, the engineer's own opening or closing stands. T opens and closes it; Esc closes it.
- **The chat.** Full height on the right, 384 to 420 px wide, the same chat as before; its fold button hides it and a button at the window's right edge brings it back. / puts the cursor in its box.
- **The results card.** Under the model, centred, at most 980 px wide, in three columns: the project (its name, which can be changed in place, its kind, the way back to all projects, the run's stages or the next step, the model's download and the results in a new window), the legend and the view (field and ply, then a View menu with what is shown, the contours, the colours, the deformation, the mesh lines and the lighting), and the answer in its short form (ADR-0099): the verdict, R and where, with Details. Details opens the full answer, its tables, the summary, the explanation, the comparison with the engineer's own Abaqus run (ADR-0094) and the files, over the model. Before a run the card has the project and the next step and no legend. With the tree open, or the model's area narrower than 780 px, the card folds to two columns, the answer under the legend.
- **The readout.** A clicked element's values are a small card over the model, beside where it was clicked, with its ply table; the background clicked or Esc puts it away.
- **Narrow screens.** Below 900 px the model takes the screen and the card and the chat are one sheet at its foot, which opens to the chat; the tree opens over the page from its button.
- **The wing.** Its drawing in the model's area, its steps in the flyout, its chat on the right, its answer in the card.

## As built (2026-11-21)

- **Where.** `components/workspace/canvas-shell.tsx` (the rail, the flyout, the card, the chat, the phone's sheet, the keys), `components/workspace/canvas-slots.tsx` (the card's places: project, view, answer, details, over the model), `app/workspace/canvas.css`. The coupon fills the places from `components/studio/coupon-studio.tsx` and `results-view.tsx`; the wing from `components/workspace/wing-stage.tsx` and `wing-workspace.tsx`. The look is ADR-0063 amendment 1 and ADR-0071 amendment 2 (`lib/rainbow.ts`, `lib/studio-colors.ts`, `components/studio/scene-canvas.tsx`).
- **Differences from the plan.**
  - Narrow screens: the sheet has two buttons, Project (Results once there are results) and Assistant. It opens on the chat and turns to the card once when the first results show; on a phone the tree also closes then, even if the engineer opened it, because it covers the page. On a project not set up yet the tree opens over the page, since its first question (what is analysed) is there, and closes once a kind is picked. The page is built with the tree open and a narrow screen closes it before the first paint, so the built page and the browser's first drawing agree.
  - The wing: its tree stays open on a wide screen when its answer first shows, since it is worked again on every change. The margin chart's key sits under the chart, so only the planform's colours are in the card. Its assistant keeps the answer in words above the chat, as before, and the box to type in stays at the column's foot.
  - The wing's page now has the workspace header, as the coupon's has (`lib/site-nav.ts`); it had the site's header and footer.
  - The legend's numbers sit under the bar at their own places, in two staggered rows.
  - The View menu is a popover that closes on a press outside it or on Esc.
  - The model's download is one menu in the project column, the same before and after a run.
- **Checked.** In a local browser at 1440 by 900 after a run, the model's area is 985 by 543 px with the tree closed and the card 300 px tall. The browser specs that read the old columns were changed (`tests/browser/studio.spec.ts`, `workspace.spec.ts`, `import.spec.ts`, `wing.spec.ts`): `wing.spec.ts` 15 passed; the studio scenarios that failed on the first run passed when run again with fewer workers at once. The colour tests (`tests/studio-colors.test.ts`) 10 pass. The full browser suite runs on the pull request.

## Why (evidence)

The founder's choice on the mockups: the gallery of the three rounds (`/mnt/project-files/workspace-design/canvas/`, live at https://claude.ai/artifact/2dQDDZtrPjLFSr26q7u44f), layout D at `c1-chat-forward.html#chat-right`, with screenshots at 1440 by 900 after a run, on a proposal and on the wing. The build plan he agreed: https://claude.ai/artifact/XEq1V7oTcgyDGL84aQk5MQ. The room the model gets: at 1440 by 900 about 890 by 560 px with the tree closed against 520 by 520 px in today's centre column; at 1280 by 720 about 790 by 400 px with the tree closed and 440 by 400 px with it open (measured on the mockup). No measurement yet of whether engineers find their way faster.

## Consequences

- The model is the largest thing on the page, and the page no longer scrolls on a desktop. The summary tables and the explanation are one click further away, under Details.
- Two layouts live in the product until Laminate and CAD move.
- The results view places its parts through slots the shell provides (`canvas-slots.tsx`); without the shell, as on `/workspace/fea/view`, it draws them in one column as before.
- Browser specs that read the old columns change with it.

## How we will know it was wrong

- The founder or a first user cannot find a result or a setting that the three columns showed, or asks for the columns back.
- At 1280 by 720 with the tree open the model is too small to pick an element on (an element of the 5 mm coupon mesh smaller than about 6 px).
- The chat on the right is folded away in most sessions, which would say it takes room it does not earn.
