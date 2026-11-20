# ADR-0124: The workspace has three sections, FEA, CAD and Laminate; FEA opens blank and the chat sets it up for the work asked for

- Status: Proposed; its reader of a question in words also answers a question of meaning in a coupon's chat with no result, by [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md) amendment 5
- Date: 2026-11-20
- Decided by: Founder, 2026-11-19 (asked whether the assistant configures the one workspace to what the user asks for, "instead of having all mixed in one it is more like one workspace but will get configured to what the user wants"; chose "Ask only if work is open" on the card "Should the chat ask before switching to another mode?"; then corrected the mockup: "it should be only FEA, CAD, then Laminate for right now on the bottom 3, the chat on the top", "say one clicks on FEA, the chat assistant is still in the right, the workspace in the middle but the left is not configured to anything so maybe just a blank worktree, the user can talk with the AI inside FEA for any related FEA questions since they are in FEA and they can later say 'you know what I want to start a wing analysis' or 'I want to test some coupons' then the workspace gets configured to that"; "ok yes looks good" on mockup v3; chose "Build it now" on the card "Start building the FEA, CAD, Laminate workspace now?". The words read, the answer endpoint, `?for=coupon` and the CAD page's content are the drafter's) | Drafted by: Claude Code
- Related: [ADR-0062](ADR-0062-the-chat-becomes-a-workspace-product-a-solver-independent-project-three-columns-one-panel-per-step-the-assistant-beside-it.md) (one workspace per kind of work), [ADR-0091](ADR-0091-the-workspace-speaks-to-the-customer-in-the-products-own-words-mapped-in-the-page-and-guarded-by-a-test.md) amendment 2 (decision D5 removed the CAD tile; this record brings it back), [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md) (answers from our theory pages, with the number guard), [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md) (the model's proposals stay per product), `lib/workspaces.ts`, `lib/work-intent.ts`, `lib/project-store.ts`, `components/workspace/chooser.tsx`, `components/workspace/fea-start.tsx`, `components/workspace/cad-workspace.tsx`, `components/studio/coupon-chat.tsx`, `components/studio/laminate-chat.tsx`, `api/src/anisotropy_api/general_answers.py`, [ADR-0121](ADR-0121-the-assistant-is-held-to-question-banks-per-feature-checked-free-on-every-pull-request-and-by-a-real-model-before-a-feature-merges.md) (the question bank `tests/assistant-questions/sections.json`), the mockup the founder approved (a Design canvas artifact, v3)
- Area: website, api, assistant

## Context

- On main (b5f4f3f) `/workspace` showed one tile per kind of work, "Coupon FEA" and "Laminate response" (`lib/workspaces.ts`), each its own page on the shared shell. The coupon chat jumped to the laminate page on fixed words (`CHAT_TOOLS.laminate.words`) without asking, and the laminate chat came back only on a message starting "back" or "coupon". Nothing knew a wing; that lives on the wing branch (PR #244).
- The founder's next projects are a wing for a class and a step repair; FEA, CAD and laminate work will grow side by side. He asked that the one workspace be set up for the work the user asks for rather than show every kind at once.
- The CAD tile and `/workspace/cad` were removed on 2026-11-12 (ADR-0091 amendment 2, D5), when the page was an empty placeholder. Shapes and dimensions belong to a CAD section that does not exist yet.
- A question the FEA chat can answer without a model setup ("what is a mesh convergence study?") had no route: the why answers (ADR-0102) need a solved result's fact sheet.

## Options considered

1. One tile per kind of work (coupon, laminate, wing, ...), as on main: rejected by the founder ("only FEA, CAD, then Laminate").
2. Three sections, FEA, CAD and Laminate; FEA opens blank and is set up as a coupon (a wing later) from the chat or a pick: chosen by the founder.
3. Switching between sections: at once always (the coupon chat's way on main), always with a confirm, or a confirm only when the open project holds work. The founder chose the last.
4. Reading what the user asks for: fixed words only; a model for every message; fixed words first and a model only where they find nothing. Fixed words decide here; a question they place nowhere goes to the answer endpoint, whose model may name a kind of work to set up, offered as one tap and never applied on its own.
5. Where a blank FEA project's state lives: a new project kind (rejected: a project's kind never changes, `KindChanged` in `records.py`, so a blank project could not become a coupon); a field of the FEA project's content (chosen: `analysis`, "none" or "coupon", which the API keeps as part of the page's JSON).

## Decision

1. **Three sections.** `/workspace` opens on a box, "What do you want to work on?", and three tiles in this order: FEA, CAD, Laminate (`WORKSPACES`). A message in the box opens the section it names (`readIntent` in `lib/work-intent.ts`), with the message carried to that section's assistant; a message that names none is offered the three sections as buttons. The projects list says "FEA · Coupon test", "FEA" (not set up) or "Laminate".
2. **FEA opens blank.** The FEA tile starts a project with `analysis: "none"`: the model tree on the left is empty but for what can be set up ("Coupon test"; "Import a model" where it is offered), the middle is empty, and the FEA assistant on the right answers questions about FEA from our theory pages and sets the project up when asked. "I want to test some coupons", "coupon testing" or a coupon's own words set the same project up as a coupon in place; the coupon assistant then carries on, with the message when it states more than the kind of work. A wing answers that it is not here yet, until the wing branch merges. A project saved before this change is a coupon; `?for=coupon` and `?material=` open FEA set for a coupon.
3. **Questions in blank FEA.** `POST /v1/workspace/questions` answers a question asked before anything is set up: the sections of our theory pages the question finds (`find_theory`) go to the model with the question, in a fixed schema (the answer, the sections it rests on, whether they cover it, and a kind of work to set up from those offered, or none). The number guard of ADR-0102 keeps the answer only when every number in it is the question's; the page names the sections. With no model, the page names the sections found. A kind of work the model names is offered as a button; the page never sets the project up on the model's word alone.
4. **Switching asks only when work is open.** From the coupon chat, a request for Laminate or CAD switches at once when the coupon holds no rows of its own, and asks once with one tap when it does ("Your coupon is saved under Projects"). The laminate chat does the same for FEA. The project left stays in the list; the section switched to opens its newest project when that project is empty, else a new one, with the message carried.
5. **CAD** is a section again: the same three columns, an empty feature tree, and an assistant that says CAD is being built and takes the user to FEA or Laminate by the same words. This reverses decision D5 of ADR-0091 amendment 2 on the founder's word.

Not in this change: the wing as a kind of FEA work (after PR #244 merges, by the same `analysis` field); the MCP server's tools named by section and the theory search filtered by section; a model reading the start box.

## As built (2026-11-20)

- Sections: `lib/workspaces.ts` (`WORKSPACES` FEA, CAD, Laminate; `FEA_KINDS` coupon; `COUPON_HREF`). The start screen: `components/workspace/chooser.tsx` (box, the pick card, three tiles, "FEA · Coupon test" in the list).
- Reading a message: `lib/work-intent.ts` (`readIntent`, `saysMore`, `sectionOf`); the carried message: `lib/handoff.ts` (`setUp` heads the next chat, `prompt` is read by it); opening a section: `components/workspace/go-to.ts` (its newest project when that holds no work, else a new one).
- Blank FEA: `analysis` on the FEA project (`lib/project-store.ts`: `newFeaProject`, the `analysis` action, `hasWork`; written to the server only as `analysis: "none"`), `askedFor` in `components/studio/project-context.tsx` (`?for=coupon`, `?material=`), and `components/workspace/fea-start.tsx` (empty model tree, empty centre, the FEA assistant). "Use these inputs" of a past run sets a blank project up as a coupon.
- Questions: `POST /v1/workspace/questions` (`api/src/anisotropy_api/general_answers.py`, `GENERAL_SYSTEM` and `answer_general` in `assistant.py`), `answerGeneral` in `lib/studio-api.ts`.
- Switching: `components/workspace/switch-ask.tsx`, used by `coupon-chat.tsx` (header "FEA assistant" with a "Coupon test" tag) and `laminate-chat.tsx`, which now reads a carried message.
- CAD: `app/workspace/cad/page.tsx`, `components/workspace/cad-workspace.tsx`.
- The home page's coupon box (unused today), the "Describe a coupon" and "Coupon analysis" links open `COUPON_HREF`.
- Questions of this feature (ADR-0121): the coupon chat's route `laminate` became `section` in `lib/chat-route.ts` (Laminate or CAD where they can be opened, a wing anywhere), and the FEA assistant of a blank project answers by `routeStart` in `lib/work-intent.ts` (`set-up`, `not-here`, `open`, `general`). Their questions are the bank `tests/assistant-questions/sections.json` (17 questions, page `start` added to the harness); `/v1/workspace/questions` is reached by its `general` questions (`api/tests/test_assistant_questions.py`). "open the laminate calculator", a marked gap of criterion 10, is now opened.

## Why (evidence)

- The founder's choices and corrections, quoted above; the approved mockup (v3) and its five pictures (`/mnt/project-files/mode-switching/`, outside the repository).
- The coupon chat's jump to Laminate without a question: `components/studio/coupon-chat.tsx` on b5f4f3f, the line `if (onLaminate && toolNamed(text) === "laminate")`.
- The API keeps a project's content as the page's own JSON (`ProjectInput.content`, `api/src/anisotropy_api/schemas.py`), so the `analysis` field needs no migration.
- The tests that cover the change and their output are in the pull request.

## Consequences

- Every link that promised a coupon goes to `/workspace/fea?for=coupon`; `/workspace/fea` alone opens the newest FEA project, or a blank one.
- The browser specs of the coupon workspace open it with `?for=coupon`.
- A section's name is its one name everywhere ("FEA", "CAD", "Laminate"); the coupon assistant is the FEA assistant with a "Coupon test" tag.
- The answer endpoint is one more model call per question in blank FEA, billed per call under the feature `answer_question` (ADR-0120), the one feature for questions answered from the theory pages, so no migration of the table's check is needed; the run records tell the two routes apart.

## How we will know it was wrong

- People type a request into blank FEA that the fixed words miss and the model names no kind for: the questions recorded with no sections found and no kind named grow past a fifth of those asked in a month.
- People switch sections by mistake and come back within a minute, or the one-tap question is answered "Stay here" more often than not.
