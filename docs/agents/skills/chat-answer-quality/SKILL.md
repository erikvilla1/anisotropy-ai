---
name: chat-answer-quality
description: How to judge whether an answer of the Anisotropy workspace chat to an engineer's question is a good one, how to review a set of questions asked on the live site, and how to write a feature's questions into the question banks and run the assistant's checks (ADR-0121). Load before reviewing chat answers, before a live test of the assistant, before changing how the chat reads a question or what a card says (lib/chat-route.ts, lib/result-question.ts, lib/result-failure.ts, components/studio/coupon-chat.tsx, the API's workspace routes, the MCP server's tools), and before calling a feature's pull request ready. Holds the eleven criteria, the review procedure, how to check the numbers independently, worked examples from the founder's own questions, and the question banks.
version: 0.2.0
---

# Chat answer quality

## When to use

Whenever the workspace chat's answers are reviewed, tested live, or changed. Read `project-rules` first. The founder's standing words for the chat: "simple and fast to the point", "more trustworthy", "less AI generated" (2026-11-16 and 2026-11-17). The decision records behind the chat are ADR-0085 (the answer), ADR-0091 (customer words), ADR-0099 and ADR-0100 (questions about a result), ADR-0102 (why), ADR-0103 (the working).

A right number is not a good answer. On 2026-11-17 every number the chat gave was correct and four answers of ten still failed, each for a reason in the list below.

## The criteria

An answer is good when all of these hold. A review names the criterion an answer fails by its number.

1. **It answers the question that was asked.** The kind of question sets the shape of the answer:

   | Kind | Example | A good answer |
   | --- | --- | --- |
   | Yes or no | "does it mean that at 1 mm it carries 22740 N, but first ply failure is at 23450 N" | Starts with "Yes" or "No", then the one relation that makes it so |
   | A value | "what is the stress at ply 7" | The value as the heading, with its place |
   | Which or where | "which ply fails first", "where is the shear stress highest" | Names the ply or the place first |
   | What is it | "what does element 376 represent" | Says what the thing is and where it sits; never a question about quantities |
   | Why | "why is ply 4 in compression" | One to three sentences from the result's facts |
   | A change | "change the width to 35 mm" | A proposal the engineer ticks, then the new result |

2. **It does not ask what the page already knows.** A missing place is the gauge centre, the element the Verification table reads; a missing quantity is σ₁, σ₂ and τ₁₂; a missing region is the gauge section. The answer says in one line which default it took and how to ask for another. It asks back only when two readings would give different numbers and neither is the page's own, once, with the choices named.
3. **It keeps the thread.** A fragment ("now in ply 5", "sigma 1", "and at element 400") takes its ply, place and quantity from the message before it. An answer to the chat's own question completes that question; nothing asked for is dropped on the way.
4. **Every number is the engine's.** Read from the stored result, in the digits the page prints. No model types a number (ADR-0001, ADR-0051). The chat and the page give the same verdict, factor, ply, criterion and basis.
5. **It states its basis in one line.** The place (element, gauge section or whole model), the ply with its angle, the criterion, the units, and whether it is a preview or a full run.
6. **The numbers hang together, and the answer shows how.** The applied state and the failure state stand side by side (1 mm and 22,740 N applied; 1.031 times that, 1.031 mm and 23,450 N, at first ply failure). What must scale does (force with width); what must not does not (stress, modulus, the failure factor).
7. **It says what a number is not.** Von Mises, Tresca and the principal stresses are not failure measures for a composite ply. First ply failure is not the ultimate strength. A value at a grip's clamped edge grows with the mesh and is reported apart from the answer (ADR-0066, ADR-0108).
8. **It is short and plain.** The answer is the heading, one line of labels follows, the rest is folded under "Details". A symbol comes with its words ("the transverse tensile strength", not "F2t" alone). No tool, vendor, model or person is named in the customer's view (ADR-0091). The same result is worded the same way each time it is shown.
9. **It matches what is on the page.** Never "Ready to run" beside finished results, never a live "Run analysis" beside a past run, and after a reload the chat says what is shown.
10. **It reads loose typing.** "whcih ply fails first" and "von misses" are read. A message that cannot be read says what can be asked, with two or three examples.
11. **It fails honestly.** What it cannot answer it says it cannot, with what to ask instead. The same question back twice in a row is a failure, whatever the question.

## Procedure: reviewing questions asked on the live site

1. **Gather the questions.** Read the chat itself when the founder's browser is connected. Otherwise, signed in as the founder, `GET /api/v1/runs` lists their run records, and `GET /api/v1/runs/<id>` holds each message and how it was read: the endpoints `workspace/result-questions` (the typed request, or the question asked back), `workspace/proposals`, `workspace/result-answers` and `coupon-jobs/<id>/explain`. A question the page's own patterns read leaves no record, so ask for a screenshot of anything missing.
2. **Classify each question** by the table in criterion 1, and note who read it: the page's patterns or the model.
3. **Judge each answer** against the eleven criteria: holds, weak, or fails, with the criterion's number.
4. **Check the numbers without the engine** (see below). One independent check per kind of number is enough.
5. **Report with the verdict first**: what holds, then what does not, numbered, each in one or two sentences. Say what could not be seen.
6. **Fix on a branch.** A change to the chat's words or reading needs its tests (`tests/result-question.test.ts`, `tests/result-failure.test.ts`, `tests/studio-chat.test.ts`, the browser suite) and an amendment to the record that owns it (load `decision-records`).

## Checking the numbers independently

- **Laminate theory**: from the library values of the material (`engine/src/anisotropy_engine/data/material-library.json`), build Q, rotate it per ply, sum A, solve for the strains under Ny = reaction / width, and recover each ply's σ₁, σ₂, τ₁₂. Write the few lines of NumPy fresh; do not call the engine, since the engine is what is being checked. The Verification table must agree to its printed digits.
- **Modulus and stress**: reaction / (width × thickness) is the gross stress; divided by the gauge strain it is the modulus.
- **Failure factor**: for maximum stress, the strength divided by the governing stress in the gauge section; for Tsai-Hill, one over the square root of the index sum. The failure index is one over the factor.
- **Scaling**: the model is linear, so the failure state is the applied state times the factor, in displacement and in force alike.
- A number from Abaqus or any other solver is evidence for a record, never an expected value in a test.

## Worked examples (the founder's questions, 2026-11-17)

IM7/8552 [45/0/-45/90]s unnotched tension, 1 mm applied.

| Question | What the chat did | Verdict |
| --- | --- | --- |
| "whcih ply fails first" | Ply 4 (90°), tied with ply 5, Tsai-Hill, 1.031 × the applied load | Holds |
| "change the width to 35 mm" | Proposed width 35, ran again: 16,210 N became 22,740 N, stress and modulus unchanged | Holds |
| "show me ply 4" | σ₁, σ₂, τ₁₂ of ply 4 at the clicked element | Holds |
| "now in ply 5", then "sigma 1" | Asked which result, then gave σ₁ for every ply | Fails 3 |
| "what does element 376 represent", twice | "Which result would you like?" both times | Fails 1 and 11 |
| "what is the stress at ply 7" | "Which element?" with the gauge centre on the page | Fails 2 |
| "von misses" | The ply's von Mises, with no caution | Weak, 7 |
| "does it mean that once it reaches 1 mm it got 22740 N, but for the first ply failure its 23450 N" | The "which ply fails first" card again | Fails 1 and 6: the answer is "yes" |

## Procedure: a feature's questions (ADR-0121)

Every feature that changes what the assistant reads or answers brings the questions a user would ask of it. The banks are `tests/assistant-questions/<feature>.json`; `harness.ts` beside them describes every field.

1. **Find the bank** whose `watches` names the files you changed, or start one: `feature`, `title`, `records` (the ADRs), `watches` (the files whose change means the bank must change) and `questions`. A bank written before its feature is built gets `waiting` with the reason, and each question a `live` saying what a good answer holds.
2. **Ask the way users ask.** Ten questions at least, of two kinds or more and three styles or more, one with a typo. Mix: a value, which or where, yes or no, what is it, why, a change, a command, and an honest decline; then fragments that lean on the message before (`after`), loose words, units, and another program's words (Abaqus, Ansys). Put the founder's own words in when he asked it (`source`).
3. **Say what a good answer holds**, by the criteria above: `route` (who answers with a model, as on the hosted site) and `offline` when no model reads it; `answer` (kind, heading, how it opens, words it says and never says, rows, plies, quantities, element) for the page's answer; `sections` for a why question; `mcp` (tool, arguments, words its answer holds, `context`) for an MCP client; `live` (`request`, `proposals`, `plate`, `covered`, `judge`) for what a model should make of it. Write what is right, not what the page says today.
4. **Mark a known gap** where the answer falls short: `gap` with the criterion's number and what goes wrong (`search:` for the theory search's, `mcp:` for the MCP server's). The check expects the fault and fails once it is fixed; take the mark off with the fix.
5. **Run check 1**: `npx tsx --test tests/assistant-questions.test.ts`, `cd api && uv run pytest tests/test_assistant_questions.py`, `cd mcp-server && uv run pytest tests/test_questions.py`. A new route of the chat, of `/v1/workspace/` or a new MCP tool fails until a question takes it.
6. **Before calling the pull request ready**, start the "Assistant check" workflow (check 2) for the feature's banks and read its report: `uv run --project api python scripts/assistant-live.py --features <feature> --dry-run` first says what it would send. It spends the founder's key: run it within its budget, once per feature, not per push; a run of answers already stored costs nothing. A pull request that changes the assistant and needs no questions says so in its description: "Assistant questions: none needed — <reason>" (check 3).

## Pitfalls

- A message sent through the model on the hosted site uses the founder's key. Read the records freely; ask before sending questions of your own.
- Only the browser tab an agent opened is visible to it, not the founder's own tab. Say so in the report.
- Before saying a change to an answer is live, read the `git_commit` of a fresh run record. On 2026-11-17 the hosted API answered with the code of before a deploy for half an hour (ADR-0056 amendment 10 restarts it at the first request after a deploy).
- A screenshot shows one scroll position. On 2026-11-17 "Ready to run" beside finished results was reported as a failure of criterion 9; the chat was scrolled up to messages from the page's load. Read the whole chat, or the records' times, before reporting what the chat says now.
- Do not judge an answer by its length or polish. Judge whether the engineer could act on it without asking again.
- A bank's expectation copied from what the page answers today encodes the fault. Write the good answer and mark the gap.
- The harness draws the page's answer with the page's functions but repeats how the component puts them together (`pageAnswer`, `modelAnswer` in `harness.ts`). When the component's order or wording changes, change the harness with it.

## Verification

- Every question in the review has a kind, a reader and a verdict with a criterion number.
- At least one number of each kind was recomputed outside the engine, and the working is shown in the report.
- The report leads with the verdict and says what was not seen.
- A feature's pull request changed a bank, or says why none was needed, and its real-model run's report is linked in the pull request.
