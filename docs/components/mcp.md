# Component card: MCP server | version 0.1 | updated 2026-11-17

## Purpose and intended use

Let an engineer ask Anisotropy from an MCP client they already use, such as Claude Desktop or Claude Code (ADR-0107). The client starts `mcp-server/` on the engineer's machine and calls its tools; each tool asks the API on the same machine, so the engine and the fea package compute every number. Steps to start and connect it: [mcp-server/README.md](../../mcp-server/README.md).

## What it does and does not compute

It computes nothing about a result. It passes on what the API answers (the materials, the setup check, the kernel's live solve of ADR-0086 with the answer of ADR-0085, the theory sections a question finds) and picks stored values out of the result it holds: the value at an element and a ply, and the element where a quantity is largest, by the page's rules (ADR-0099, ADR-0100). Nothing is converted, averaged or rounded. The words the engineer reads are written by the client's model, and no guard of ours runs on them.

## Inputs / outputs

In: tool calls over stdin and stdout. A setup is the coupon form's rows by key (`lib/coupon-form-definition.json`), with `angles` as a list in place of the sixteen ply rows; the server adds the form's version and nothing else.

Out, per tool, as compact JSON text:

| Tool | Returns |
| --- | --- |
| `list_materials` | The library's datasets, each marked with whether a coupon setup can name it |
| `material_values` | The SI values the engine would use for a material, each with its page |
| `describe_coupon_form` | The form's rows (key, meaning, required, choices, default), what this API offers, and an example marked as an example |
| `check_setup` | The check: what each passed item read, the items that did not pass with the rows to change, and which of them stop a solve |
| `solve_coupon` | The check and, when nothing blocks, the answer (verdict, first ply to fail per criterion, loading, reaction), the package's sentences, what can be asked, and a `result_id`. Never the fields |
| `result_values` | One element's stresses and strains ply by ply in fibre axes, and each criterion's strength ratio, index and mode there |
| `result_extreme` | Where a quantity is largest over the gauge section (the elements the package read, `mesh.gauge_elements`, ADR-0108), the whole model or a named region: the value, ply, element, tied plies, and each ply's own extreme |
| `explain_result` | The result's fact sheet, the package's sentences and the theory sections the question's words find, with their text |
| `show_working` | The working of ADR-0103: each formula, the formula with the numbers put in, and its result; one step alone with `step` (ADR-0107 amendment 4) |

The server also sends the client's model its rules (`INSTRUCTIONS` in `server.py`): the answer first in one line and at most three lines of basis; only what was asked; no tool, program, vendor, path or model named to the engineer; numbers only from tool results, as written, with units, to four significant figures at most; every missing row asked for in one message; say when a value was the example's; say once that the solve is a preview; the gauge section's answer, with a criterion reached first at a gripped edge said apart; answer a why in one to three sentences from the facts and sections only (ADR-0107 amendment 1). What a tool returns names none of this machine's programs or paths: the full run's own setup items are left out and the package's aside about another program's viewer is cut.

## Dependencies and connections

- The API on the same machine, at `ANISOTROPY_API_URL` (default `http://127.0.0.1:8000`), with the actor `assistant` (ADR-0026): `GET /v1/materials`, `GET /v1/materials/{id}`, `GET /v1/coupon-tests`, `POST /v1/coupon-jobs/check`, `POST /v1/coupon-jobs/live`, `POST /v1/workspace/theory-sections`.
- `lib/coupon-form-definition.json` in the checkout, for the form's rows.
- The `mcp` Python SDK (2.3 or later, below 3) and `httpx`; `uv` to run it.
- No port, no file written, no sign-in. The last 8 solves are held in memory until the client closes the server.

## Evaluation

`cd mcp-server && uv run pytest` (38 tests, 2026-11-17): the tools through an in-process client against a stand-in for the API that answers with `tests/fixtures/studio/`; the extremes held to the fea package's own in the same result. `uv run python examples/ask.py` tries the server over stdin and stdout against a running API. Evidence and what is unverified: [ADR-0107](../decisions/ADR-0107-an-mcp-client-reaches-anisotropy-through-a-local-server-over-stdio-that-calls-the-api-it-solves-a-preview-and-starts-no-full-run-and-the-clients-model-writes-the-words.md).

## Out of scope and limits

- Not connected to Claude Desktop or Claude Code yet (UNVERIFIED); tried through the SDK's own client only.
- A preview only: no mesh convergence study, no CalculiX cross-check, no document, no full run, nothing written to a coupon's folder.
- A local API only. The hosted site's sign-in is not carried.
- The client's model can still state a number no tool returned; the rules ask it not to and nothing checks.
- The lookup rules are a second copy of the page's (`lib/result-question.ts`); a change to one must be made in the other.
- The working is written for the first ply to fail by maximum stress and Tsai-Hill (ADR-0103); a model brought in as an Abaqus file (ADR-0105) and a plate's supports and loads (ADR-0101) are not reachable through the tools.

## Owner

Founder / engineering.
