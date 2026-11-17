# ADR-0107: An MCP client reaches Anisotropy through a local server over stdio that calls the API; it solves a preview and starts no full run, and the client's model writes the words

- Status: Proposed
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
