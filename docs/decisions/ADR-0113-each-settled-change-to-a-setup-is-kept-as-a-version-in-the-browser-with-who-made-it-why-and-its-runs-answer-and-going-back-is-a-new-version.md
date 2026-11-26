# ADR-0113: Each settled change to a setup is kept as a version in the browser, with who made it, why, and its run's answer, and going back is a new version

- Status: Proposed; the versions are kept by the server, the browser keeping a copy, by [ADR-0143](ADR-0143-a-models-setup-is-changed-through-typed-tools-in-the-api-that-the-page-the-mcp-server-and-the-workspaces-planner-share-and-the-server-keeps-its-versions.md)
- Date: 2026-11-18
- Decided by: Founder, 2026-11-17, on a review of the workspace he shared ("Model history, revisions, and traceability ... Every consequential change should be traceable and reversible"), choosing it among the gaps offered: "point 2 3 and 4 is good" | Drafted by: Claude Code
- Related: [ADR-0111](ADR-0111-the-fea-workspace-sets-a-model-up-in-a-model-tree-on-the-left-in-the-words-of-any-finite-element-program-and-the-chat-changes-the-same-tabs.md) (the model tree the History sits in), [ADR-0109](ADR-0109-a-persons-past-analyses-are-listed-from-their-own-jobs-each-with-the-answer-its-run-wrote-and-one-opens-again-as-it-was-solved-from-the-files-that-run-stored.md) (past runs, kept by the server), [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md) (changes made by talking), [ADR-0001](ADR-0001-deterministic-engine.md); `lib/model-versions.ts`, `components/studio/use-versions.ts`, `components/workspace/history-tab.tsx`
- Area: website

## Context

- The workspace keeps one copy of a project's setup: each edit, by the engineer or by the assistant from a message, replaces it. A run's values are kept by the server (ADR-0109), but not which edit led to it, and an edit cannot be undone except by typing the old value again.
- A review the founder shared on 2026-11-17 asks that every consequential change be traceable and reversible: who made it, the values before and after, why, and the run made from it; and that the only copy of an earlier state is never overwritten. Asked which gaps to build, the founder chose this one with two others.
- A typed value changes the rows once per key pressed; a change from the chat or a click changes them once.

## Options considered

1. *Keep each settled change as a version in this browser, per project; going back is itself a new version (chosen).* A change counts once it has been still for 1.2 s, so a value typed key by key is one version; a change the assistant makes is kept apart from typing still settling. Nothing on the server changes. The versions are lost with the browser's site data, and another browser does not see them.
2. Keep the versions in the project the server stores (ADR-0062 part 6). Rejected for now: each edit is sent to the server; fifty copies of the setup in every save is a larger request on every key, and the projects table would need a migration. A later step if the founder wants versions across devices.
3. Undo and redo only, with no list. Rejected: no record of who changed what, and no comparison of runs, which the review asks for.
4. A version per key pressed. Rejected: a number typed as "250" would be three versions.

## Decision

- **A version** holds the rows and a plate's lists, when, who ("you", or "the assistant" for a change applied from a message), why (the message, the chip clicked, "Start over", "Back to version 3"), and what changed from the version before, in the rows' own labels ("Element size (mm): 2 → 4"), the plies as one layup ("[45/0/-45/90]s → [0/90]s") and a plate's lists as their sentences. The date the page fills in is not a change.
- **When.** A change becomes a version once it has settled (1.2 s). A change the assistant is about to make first keeps any typing still settling as the engineer's own version. A run settles the setup at once and marks the version it was made from; once its results are read, their reaction, largest displacement and first-ply failure, printed from the package's values, are kept on that version.
- **Going back** to a version sets its rows and lists again and is kept as a new version ("Back to version 3"): nothing is overwritten. The check and the results shown are cleared, as for any change; the live solve answers the setup again.
- **History** is the last panel of the model tree: "Undo the last change", then each version newest first with a "Go back to this" button and a box to tick; two ticked show what differs between them and each run's answer side by side.
- **Where kept.** In this browser's storage, per project, the last 50 versions.

## As built (2026-11-18)

- `lib/model-versions.ts`: `withVersion`, `changesBetween`, `withRun`, `withResult`, `comparison`, `readVersions`, `writeVersions`, `MAX_VERSIONS` (50).
- `components/studio/use-versions.ts` (`useVersions`, `SETTLE_MS` 1200): in the project context as `versions` (`list`, `attribute`, `restore`). The chat calls `attribute` before it changes the rows: the assistant with the message for a typed change or an applied proposal, "you" with the chip's words for a click.
- `components/workspace/history-tab.tsx`, under the tree in `components/workspace/tension-screen.tsx`; styles in `app/workspace/workspace.css`.

## Why (evidence)

- `tests/model-versions.test.ts` (4): a settled change is a version with its changes in the rows' labels and no change adds none; going back is a new version and the oldest go past 50; a run marks its version and keeps its answer, and two versions compare; versions are kept per project and a blocked or odd store gives none.
- Browser, `tests/browser/studio.spec.ts` "the model tree": "use 4 mm elements" is kept as a version by the assistant with the message; the run's answer is on it; two versions compare; "Undo the last change" brings the element size back and is kept as "Back to version …".
- `npm test`: 426 tests, 425 pass, 1 skipped. `npm run typecheck`: clean. The whole studio browser suite: 55 passed (5.6 min).
- UNVERIFIED: not deployed; no engineer has used it.

## Consequences

- Every change is listed and any setup can be had again, in the browser it was made in.
- A run's answer is tied to the setup that made it, so two runs can be compared by what differed.
- Versions do not follow the engineer to another browser or device, and clearing site data loses them (option 2 is the step for that).

## How we will know it was wrong

- An engineer looks for a version on another device, or loses versions they relied on.
- A change is put down to the wrong author, or one edit shows as several versions.
- The History is not opened, or "Undo the last change" is asked for in the chat instead.
