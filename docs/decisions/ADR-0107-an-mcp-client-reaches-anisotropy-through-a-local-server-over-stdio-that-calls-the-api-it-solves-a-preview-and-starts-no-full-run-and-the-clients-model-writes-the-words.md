# ADR-0107: An MCP client reaches Anisotropy through a local server over stdio that calls the API; it solves a preview and starts no full run, and the client's model writes the words

- Status: Proposed; short answers with nothing of the machine named since amendment 1; the page's defaults taken since amendment 2; missing rows asked for in words with their defaults since amendment 3; one step of the working when one quantity is named since amendment 4; every element by its own number, and the failure index the results show, since amendment 5; six wing tools that read and preview a wing file, applying nothing, by [ADR-0128](ADR-0128-a-wings-chat-reads-a-change-of-plies-into-the-engines-form-and-previews-it-on-a-copy-answers-from-the-wings-report-and-the-reference-pages-and-the-wing-changes-only-on-the-engineers-apply.md)
- Date: 2026-11-17
- Decided by: Founder, 2026-11-16 ("ok do step 1 and step 2, just make a branch until we get the full plan that we discussed done", on the plan whose step 2 read "a local MCP server: a small program on your machine that lets Claude Desktop or Claude Code use Anisotropy as tools: list materials, check a setup, run a coupon, read a result value, ask why, show the working. Each tool calls the API we already have, so the engine still computes every number. Nothing new is exposed on the internet"; then "do MCP last"); which tools there are, that "run a coupon" is the kernel's preview and not the full run, where a result is held, the actor and the new route are the draft's proposals and not yet confirmed | Drafted by: Claude Code
- Related: [ADR-0001](ADR-0001-deterministic-engine.md); [ADR-0003](ADR-0003-reject-invalid-input.md); [ADR-0026](ADR-0026-run-record-contents-and-startup-policy.md); [ADR-0051](ADR-0051-the-coupon-studio-a-browser-page-through-the-api-with-the-fea-package-computing-every-number.md); [ADR-0052](ADR-0052-the-assistant-explains-from-a-fact-sheet-through-one-provider-interface-with-a-number-guard.md); [ADR-0085](ADR-0085-a-coupons-answer-is-given-per-criterion-in-its-gauge-section-fails-or-holds-the-loading-at-first-ply-failure-and-where-with-the-clamped-edge-reported-apart.md); [ADR-0086](ADR-0086-every-edit-is-answered-by-our-kernel-as-a-labelled-preview-from-warm-workers-and-calculix-the-mesh-study-and-the-package-stay-on-the-full-run.md); [ADR-0088](ADR-0088-the-model-proposes-rows-from-the-engineers-words-a-source-guard-keeps-what-the-message-writes-and-the-engineer-ticks-what-enters.md); [ADR-0099](ADR-0099-the-assistant-answers-a-question-about-a-result-by-reading-its-place-with-fixed-patterns-and-looking-the-value-up-in-the-results-the-page-shows.md); [ADR-0100](ADR-0100-a-model-reads-a-loose-question-about-a-result-into-a-fixed-request-and-the-page-looks-the-values-up-the-model-is-shown-no-result-and-writes-none.md); [ADR-0102](ADR-0102-a-question-of-why-about-a-result-is-answered-in-words-from-the-results-fact-sheet-and-the-matching-sections-of-our-own-theory-pages-named-under-the-answer.md); [ADR-0103](ADR-0103-the-working-behind-an-answer-is-written-by-the-fea-package-when-it-solves-and-shown-by-the-page-when-asked-no-model-writes-a-formula-or-a-number.md); `mcp-server/`; `api/src/anisotropy_api/main.py` (`find_theory_sections`); [component card](../components/mcp.md)
- Area: assistant, api

## Context

- The assistant so far lives on the workspace page: the page holds the result, a model named in the API's settings reads a message into a fixed request or writes an answer, and a guard of ours keeps only what the engineer's words or the engine's numbers hold (ADR-0052, ADR-0088, ADR-0100, ADR-0102).
- The Model Context Protocol (MCP) lets a client that has its own model, such as Claude Desktop or Claude Code, call tools a server offers. The client's model decides which tool to call and writes the words the engineer reads. No code of ours runs between that model and the engineer.
- The API already has what the tools need: the materials, the setup check, the kernel's live solve with its answer, fields and explanation, and the theory finder (ADR-0051, ADR-0086, ADR-0102). A live solve's fields are megabytes and are kept by whoever asked: the page keeps them in the browser, the API keeps none.
- Every route that reaches the engine requires the actor header, one of a fixed list held by a database constraint (ADR-0026). `assistant` has been on the list since ADR-0026 and nothing has used it.
- The hosted site sits behind Cloudflare Access; the local API has no sign-in.
- The official Python SDK `mcp` is at 2.3.0 on PyPI (read 2026-11-16): its high-level server is `MCPServer`, and its `Client` can talk to a server in the same process, which a test can use.

## Options considered

Where the server runs:

1. A program on the engineer's machine, started by the client, speaking over stdin and stdout, that calls the API on the same machine. No port is opened and no sign-in is involved.
2. A hosted MCP endpoint beside the API, behind the sign-in. Any client anywhere could use it; it is a new public surface that needs the protocol's sign-in flow for clients, per-person limits and the private folders of ADR-0106 behind every tool. Not now: the plan said nothing new on the internet.
3. A local program that imports the engine and the fea package and calls no API. Fewer parts to start, but a second way into the engine with no actor, no run record, no warm workers and its own copy of what the API's check does.

How it is written:

4. The official `mcp` Python SDK. The same language and tooling as the API (`uv`), and an in-process client for tests.
5. The official TypeScript SDK, beside the website's code, which could call the page's own lookups (`lib/result-question.ts`) with no second copy. It would need Node and a build on the engineer's machine, and those modules are written for the page's types.
6. The protocol by hand over stdin and stdout. No dependency; every message of the protocol to keep right ourselves.

What the tools may do:

7. Read and preview only: materials, the form, the setup check, the kernel's live solve, lookups in that result, the facts and theory behind a why, the working. Nothing is written to a coupon's folder and no job is started.
8. Also the full run: start a coupon job, follow it, hand back its files. A model would then start runs that take minutes, write a coupon's folder and claim its name. Left for a record of its own, once the preview has been used.
9. Also change a project's rows on the page. A second writer to what the engineer is editing; not considered further.

Where a result is held between questions:

10. In the server's memory under a short id, the last 8 solves, gone when the client closes the server.
11. Returned whole to the client. Megabytes of arrays in a model's context.
12. Kept by the API under an id. New state on the API, with the ownership rules of ADR-0104 to apply to it.
13. Solved again for every question from the setup the client resends. Stateless, but every question pays a solve and trusts the client's model to resend the same rows.

How a value is read from a result:

14. The page's rules (ADR-0099, ADR-0100) written again in Python in the server, and a test that holds the extremes it finds to the ones the fea package wrote in the same result's summary.
15. A route on the API that takes the fields and a request. The megabytes go up again with every question.
16. One lookup in the fea package for the page and the server alike. The page reads in the browser with no round trip (ADR-0099); moving it is a larger change than this record.

How a why is answered:

17. The tool hands the client's model the result's fact sheet, the package's sentences and the text of the theory sections the question's words find, from a new route that returns the sections with their text. No second model is called, and it works when the API has no model.
18. The tool calls `result-answers`, the API's own model with the number guard (ADR-0102), and passes on its prose. Guarded, but it needs the API's model and a second model call for every question, and the client's model rewords the prose after the guard has run.
19. The server reads the theory files from the checkout and ranks them itself. A second finder to keep level with `theory.py`.

Which actor the calls carry:

20. `assistant`, which the list has held unused since ADR-0026.
21. A new actor `mcp`, added by a migration to the constraint.

## Decision

Options 1, 4, 7, 10, 14, 17 and 20.

- `mcp-server/` is a project of its own (`anisotropy-mcp`, Python, the `mcp` SDK and `httpx`). A client starts it with `uv run --directory <path>/mcp-server anisotropy-mcp` and speaks to it over stdin and stdout.
- It calls the API at `ANISOTROPY_API_URL`, `http://127.0.0.1:8000` when unset, with `X-Anisotropy-Actor: assistant`. Plain `http` is taken only for this machine, and an address with a user, a password or a query is refused. What the API refuses, the tool refuses in the API's words.
- Nine tools. `list_materials`, `material_values`, `describe_coupon_form`, `check_setup` and `solve_coupon` pass on what the API answers. `solve_coupon` is the kernel's live solve (ADR-0086): it returns the setup as read, the answer of ADR-0085 as the package wrote it, the package's sentences, what can be asked, and a `result_id`; it says it is a preview. `result_values` and `result_extreme` read the result the server holds; `explain_result` returns the fact sheet, the sentences and the theory sections with their text; `show_working` returns the working of ADR-0103.
- A setup is the form's rows as the client gives them. The server adds only the form's version, and defaults nothing: a missing row comes back from the check as a row to change (ADR-0003).
- The server tells the client's model its rules in the protocol's `instructions`: every number comes from a tool result with its unit, to four significant figures; ask for a missing row; say which values were chosen when the engineer asked for an example; say the solve is a preview; answer a why only from the facts and sections and name the section; show the working as written.
- The API gains `POST /v1/workspace/theory-sections`: a question (and a limit of 1 to 5, 3 when unset) answered with the sections `theory.find` finds, each with its text as a reader is handed it. It is recorded with its actor as the question and the ids found, not the text.

## As built (2026-11-17)

- `mcp-server/src/anisotropy_mcp/api.py` (`Api`, `api_url`, `ApiRefused`), `results.py` (`values_at`, `extremes`, `gauge_section`, `offer`), `server.py` (`build`, `INSTRUCTIONS`, `Results`, `main`); `mcp-server/examples/ask.py` tries the server as a client does; `mcp-server/README.md` has the steps to connect Claude Desktop and Claude Code.
- A tool answers in compact JSON text and returns no structured content, so a result costs the client's model fewer tokens.
- `result_values` also returns what each criterion says of the ply at that element (the strength ratio, the failure index and the mode, as the fields hold them), which the page's probe table does not show.
- The form's rows are read from `lib/coupon-form-definition.json` in the checkout, the file the page is built from; the API does not serve it.
- `api/src/anisotropy_api/main.py` (`find_theory_sections`), `schemas.py` (`TheorySectionsRequest`, `TheorySection`, `TheorySectionsResponse`).
- CI runs the server's tests as the job `mcp` (`.github/workflows/tests.yml`).
- Not built: the full run (option 8), any hosted endpoint (option 2), a sign-in for the hosted API.

## Why (evidence)

- The server's tests: `cd mcp-server && uv run pytest -q` gave `38 passed in 0.86s` (2026-11-17). They call the tools through the SDK's in-process client against a stand-in for the API that answers with `tests/fixtures/studio/`, the files the fea package wrote. `tests/test_results.py` holds each ply's extreme in the gauge section to `summary.ply_extremes` of the same file, to a relative 1e-8. Seven changes that break a rule on purpose (the ply's index, the gauge section, the magnitude rule, the tie between elements, the form's version, the facts sent with the question, a missing row not blocking) each failed at least one test.
- The API's tests with a database: `cd api && TEST_DATABASE_URL=... uv run pytest -q` gave `662 passed, 1 skipped in 77.11s` (2026-11-17), seven of them new, for the route (`tests/test_result_answers.py`).
- A real try over stdin and stdout against a local API in the cloud container (`uv run python examples/ask.py`, 2026-11-17): the form's example, IM7/8552 [45/0/-45/90]s, 250 by 25 mm, 56 mm tabs, 1 mm pull, 2 mm elements, came back as "By the Tsai-Hill criterion the laminate holds at the applied loading, in the gauge section: the first ply to fail would be ply 4 (90 degrees), tied with ply 5, at element 1142 ... at 1.022 times the applied loading". The factor the tool returned, 1.0216921379399788, and the stresses of ply 4 at element 1142, -226.257014, 61.5629344 and -10.1845292 MPa, are the ones `POST /v1/coupon-jobs/live` returns for the same rows when called directly.
- The same try showed a setup with a missing row (no G13, no G23) and one with a layup that is not symmetric come back unsolved with the row to change, in the check's words.
- UNVERIFIED: the server has not been connected to Claude Desktop or to Claude Code, on Windows or elsewhere. The steps in `mcp-server/README.md` follow those clients' documentation as read on 2026-11-17.
- No evidence yet that a client's model follows the rules in `instructions`: no conversation through a real client has been read.
- No evidence yet on the hosted API: the server was tried against a local API only.

## Consequences

- An engineer can ask Anisotropy from a client they already use, in their own words, and get the engine's answer with its place and unit.
- The guards of ADR-0052, ADR-0088 and ADR-0102 do not run on what the client's model writes. The server can hand it numbers with units, the package's own sentences, the section a reason rests on and the rules; it cannot check the words. A wrong number in the client's answer would be the client's model's, and nothing of ours would catch it.
- The lookup rules now exist twice, in the page and in the server. A change to one has to be made in the other; the test against the package's extremes catches a drift in the gauge section and the picking, not in the wording.
- Calls through the server are recorded with the actor `assistant` when the API keeps records, so the questions asked of the theory pages, and the ones that found no section, can be read back. That is the evidence the plan asked for before a search by meaning is built.
- The theory sections' text now leaves the API to a caller. The pages are ours and are printed in the manual; `engine/docs/reasons.md` is a draft the founder has not reviewed, and a client's model will now quote it.
- We depend on the `mcp` SDK, whose version 2 renamed its server class; the version is held below 3.
- The server needs a checkout of the repository and `uv` on the engineer's machine, and the API started by hand. That is right for the founder and the team and too much for a customer.

## How we will know it was wrong

- The founder connects it to Claude Desktop, asks for a [45/0/-45/90]s IM7 tension coupon and which ply fails first, and does not get the answer the page gives for the same rows.
- A conversation through a client states a number about a result that no tool returned, or a reason that no section returned holds, without saying so. One such conversation is a reason to move the wording behind a guard (option 18) or to return finished sentences only.
- A question answered one way on the page and another way through the server for the same result: the two copies of the lookup have drifted (option 16 then).
- The records show questions through `assistant` that find no section, or the wrong one, often enough to matter: the finder by words is not enough here.
- Someone needs the full run, a customer's machine without a checkout, or the hosted site from a client: options 8 and 2, each a record of its own.

## Amendment 1, 2026-11-20 (short answers, nothing of the machine named)

**Context.** The first real-model run of the question banks (ADR-0121, run 44654876004, 2026-11-20) put fourteen questions to a model acting as an engineer's own assistant on these tools. Of twelve graded, none held: four failed and four were weak for one cause, the answers' length and their words. "which ply fails first" ran to a page that called the gauge section's factor the answer while giving the lower factor at a gripped edge beside it; "S22 in ply 4 at element 183" added both criteria's factors; most named CalculiX, "our kernel" or the tools themselves. The instructions asked for that: rule 3 said "solve_coupon is a preview by our kernel: no mesh convergence study, no CalculiX cross-check ... Say so", and `solve_coupon` returned this machine's solver and typesetter with their paths among the setup items. Four more failed on the check itself: arguments left at the tool's default, a question of why passed in the model's own words, and an element the mesh has not answered without a call, each correctly.

**Options.** (1) Leave the words to the client's model, as decided: it follows the instructions it is given, and those named the machinery. Rejected. (2) Return finished sentences only (option 18 of this record): the questions a tool answers are more than the sentences a package writes. Rejected for now. (3) Rewrite the instructions in the words of the `chat-answer-quality` skill's criteria (the answer first in one line and at most three lines of basis, only what was asked, no tool, program, vendor, path or model named, numbers as the tool wrote them, every missing row asked for at once, the gauge section's answer with a gripped edge said apart, a why in one to three sentences), and stop the tools handing the machinery over: the preview's text says "no check by a second solver and no report", the full run's own setup items (the solver and the typesetter, with their paths) are left out of a setup, the `solver` field goes, and the package's aside about another program's viewer is cut from its sentences as the page cuts it (ADR-0091). Chosen.

**Decision.** Option 3: `INSTRUCTIONS`, `PREVIEW`, `setup_of`, `sentences_of` in `mcp-server/src/anisotropy_mcp/server.py`. In the check (ADR-0121 amendment 3), the judge is shown what each tool returned, and an argument is matched against the tool's default when left out.

**Evidence.** `cd mcp-server && uv run pytest -q`: 54 passed (2026-11-20); a test holds that the instructions and every tool's description name no CalculiX, PrePoMax, Abaqus or kernel, and that a solve's answer names none of them, nor a path. How a real model answers after the change: UNVERIFIED until the next real run.

## Amendment 2, 2026-11-20 (the page's defaults)

**Context.** In the third real-model run (ADR-0121 amendment 5), asked "stress at element 9999", the client's model said the range, 1 to 250, and asked which element, which ply and which stress; asked for the Tsai-Wu working, which the result does not have, it asked which criterion to show. The page answers both without asking (criterion 2 of the `chat-answer-quality` skill).

**Decision.** Rule 11 of `INSTRUCTIONS`: a question that leaves out the ply or the quantity means every ply and the stresses along the fibres, across them and in shear; ask back only for what has no default, once, with the choices named; an element not in the model gets its range and the values at the element where first ply failure is read; a working the result does not have is said in one line, with the working of the criterion that fails first.

**Evidence.** `cd mcp-server && uv run pytest -q` 54 passed, the rule held by the test of the instructions (2026-11-20). How a real model answers: UNVERIFIED until the next run.

## Amendment 3, 2026-11-20 (missing rows asked for in words)

**Context.** In the fourth real-model run (ADR-0121 amendment 6), told "run a 250 x 25 IM7/8552 [45/0/-45/90]s coupon at 1 mm", the client's model listed the missing rows by their keys ("filled_by, date, size_from, tab_length, G13, G23") and then as a numbered list, where one short question would do. The answers of amendment 2's rule 11 held: asked about element 9999 it gave the range and the values where first ply failure is read, and asked for the Tsai-Wu working it said the result has maximum stress and Tsai-Hill and showed the Tsai-Hill working.

**Decision.** Rule 5 of `INSTRUCTIONS`: a missing row is asked for in words, never by its key, with the form's default or example beside each row that has one, so the engineer can answer yes.

**Evidence.** `cd mcp-server && uv run pytest -q` 54 passed, the rule held by the test of the instructions (2026-11-20). How a real model asks: UNVERIFIED until the next run.

## Amendment 4, 2026-11-20 (one step of the working when one quantity is named)

**Context.** The founder asked the website's chat "equation for stress" and got the whole Tsai-Hill working, strain step first: "didnt really answer my question". The page now shows the one step asked for (ADR-0103 amendment 1, PR #252). Through an MCP client the same question still reached `show_working`, which had no way to give one step, and rule 8 said to show its formulas as written, all four steps.

**Decision.** `show_working` takes `step` (`strain`, `stress`, `criterion`, `loading`, the fea package's step ids). With it, the tool returns that step alone, of the criterion named or, when none is, of the criterion that fails first by the page's rule (the verdict's earliest, else the basis's earliest, else the first written), with a note naming it and that the whole working is the same tool without `step`. Rule 8 of `INSTRUCTIONS`: when the engineer names one quantity and no criterion, pass it as `step` and show that step alone, saying in a few words that the whole working is there if wanted. A criterion named, or no quantity, still gets the whole working, as on the page.

**Evidence.** `cd mcp-server && uv run pytest -q` 74 passed (2026-11-20): the new test asks for the stress step with no criterion (Tsai-Hill's, the criterion that fails first in the fixture) and the failure index of maximum stress by name. The working bank's "equation for stress", "how was the strain calculated?", "formula for the failure index" and "equation for the max stress check" now say which call an MCP client makes. The first real-model run of the working bank on this change (run 44813140922, $0.29, 2026-11-20): the client passed the step asked for in all three questions that name one, and showed that step alone; 3 hold, 4 weak, 3 fail. The weak answers left out where the working is read and for which criterion; one failed for rounding the working's six-figure strains to four, as rule 4 then asked against rule 8; one headed the maximum stress working "Max stress governs at R = 1.057" where Tsai-Hill fails first at 1.032. So `show_working` also returns `fails_first` and a `basis_line` written by the server (the criterion and its factor, the ply and the element, the section and that it is a preview, and which criterion fails first when it is another), rule 8 says to give it as written after the answer's first line, and rule 4 lets a formula keep the numbers `show_working` wrote. Two findings are left: the Tsai-Hill working names its sum FI, which a reader takes for the failure index the results show (1/R), and the working's element (183) can differ from the verdict's (182) where elements tie. The second run (44815395148, $0.29): 4 hold, 6 weak, 0 fail; each basis line was given as written, maximum stress no longer said to govern, and the strains kept their six figures. The weak answers led with the basis line where rule 1 asks for the answer first ("equation for stress" opened with the Tsai-Hill factor) and used symbols such as Q₁₁ and F₆ without their words, so rule 8 now says to lead with what was asked, then the basis line, and to say each symbol's meaning the first time, from the tool's `what` and step titles. The third run (44816209462, $0.30): 4 hold, 6 weak, 0 fail. "equation for stress" now opens with the stress step and the basis line follows it; the symbols come with their words. Five of the six weak marks cite criterion 8, details not folded away: an MCP client shows the answer as plain text with no fold, so that part is the client's to judge. Beyond it, "tsai-wu working" did not set the applied state beside the failure state (criterion 6), "how was the strain calculated?" and "equation for the max stress check" were judged thin on the place and basis (criteria 2, 5, 7) though each gave the basis line, and "formula for the failure index" gives the Tsai-Hill sum 0.9388 but not the failure index the results show (0.9689, its square root), the first of the two findings above. These are left for a later amendment.

## Amendment 5, 2026-11-24 (every element by its own number; the failure index is 1/R)

**Context.** Amendment 4 left two findings. The first: `solve_coupon` gave the first ply to fail at element 182 while the working, `result_values` and the page name element 183. It is one element: the package's `element` in `fpf`, `fpf_gauge` and the verdict's `outside_earlier` is the element's place in the mesh's list, counted from 0, beside its `label` ("Strip-1.183"); `answer_of` passed the entries on unchanged, so a client read the place as the number. The second: asked for the failure index, the client gave the Tsai-Hill sum, 0.9388, not the 0.9689 the results show.

**Decision.** `answer_of` gives each first ply to fail, and the verdict's `outside_earlier`, its element by its own number, taken from its label as `result_values` does (`by_number`); an entry with no label leaves the element out rather than give the place. The working now ends its criterion step on the failure index the results show (ADR-0103 amendment 2), and rule 8 says the Tsai-Hill working's FI is its sum, that the failure index is the working's last line, 1/R, and to give 1/R when asked for the failure index.

**Evidence.** `cd mcp-server && uv run pytest -q` 88 passed (2026-11-24): the solve's answer names element 183 for both criteria, as the working does, and element 56 outside the gauge section, with no 182 anywhere in it. The bank `which-ply-fails.json` expects element 183 from `solve_coupon`. The real-model run of the working bank on this change (run 45474040907, $0.38, 2026-11-24): 3 hold, 6 weak, 1 fail. "formula for the failure index" now opens "Failure index = 1/R = √FI = 0.9689" and says FI is the Tsai-Hill sum; every answer names element 183. Five of the six weak marks cite criterion 8 (details not folded) or a step's thinness, as in amendment 4. The one fail, "show the working for max stress" (held in the run before), was marked for rewriting the engine's numbers: the answer's 17,150 N is the working's own load at first-ply failure, 1.057 times the 16,222 N reaction at the applied 1 mm, and 16,742 N is Tsai-Hill's, so the judge's reason does not hold; its other reasons are criterion 8 and the step's text "sigma_2 reaching F2t", which the page writes as σ₂ and the server passes as written.
