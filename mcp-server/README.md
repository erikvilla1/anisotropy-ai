# Anisotropy MCP server

A small program that lets an MCP client, such as Claude Desktop or Claude Code, use Anisotropy as tools (ADR-0107). The client starts it on your own machine and talks to it over stdin and stdout. Each tool asks the Anisotropy API running on the same machine, so the engine and the fea package compute every number. No port is opened and nothing is written to disk.

What you can ask for through it: the library's materials, a check of a coupon setup, a solve of the coupon by our kernel (a preview: no mesh study, no CalculiX cross-check, no document), the stress or strain at an element and a ply, where a quantity is largest, the facts and theory sections behind a "why", and the working behind the first ply to fail. It starts no full run and changes nothing.

## 1. Start the API

The server needs the API on this machine. From the repository root:

```
cd api
ANISOTROPY_RUN_RECORDS=off uv run uvicorn anisotropy_api.main:app --port 8000
```

In PowerShell, run `$env:ANISOTROPY_RUN_RECORDS = "off"` first, then the `uv run` command without the prefix. Leave it running. `ANISOTROPY_RUN_RECORDS=off` starts the API without its run-records database; with the database ([api/README.md](../api/README.md)) every tool call that reaches the engine is recorded with the actor `assistant`.

## 2. Try it without a client

```
cd mcp-server
uv run python examples/ask.py
```

It starts the server the way a client does, solves the form's example coupon and prints what each tool answered. If this works, the server works; what is left is telling your client where it is.

## 3. Connect a client

Both clients need the full path of this folder. The steps below follow the clients' own documentation as read on 2026-11-17; they were not tried in either client from here (UNVERIFIED).

**Claude Desktop.** Settings, Developer, Edit Config opens `claude_desktop_config.json` (on Windows `%APPDATA%\Claude\claude_desktop_config.json`, on macOS `~/Library/Application Support/Claude/claude_desktop_config.json`). Add the server under `mcpServers`, with your own path, then quit and reopen Claude Desktop:

```json
{
  "mcpServers": {
    "anisotropy": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\anisotropy-ai\\mcp-server", "anisotropy-mcp"]
    }
  }
}
```

A path on Windows needs each backslash doubled inside the JSON. If the tools do not appear, the server's own messages are in `mcp-server-anisotropy.log` in Claude Desktop's `logs` folder.

**Claude Code.** In a terminal:

```
claude mcp add anisotropy -- uv run --directory /path/to/anisotropy-ai/mcp-server anisotropy-mcp
```

Then `/mcp` inside Claude Code lists it.

Then ask, for example: "Run a [45/0/-45/90]s IM7/8552 tension coupon, 250 by 25 mm with 56 mm tabs, pulled 1 mm, and tell me which ply fails first."

## Settings

| Variable | Meaning | Default |
| --- | --- | --- |
| `ANISOTROPY_API_URL` | Where the API is. Plain `http` is taken only for this machine (`127.0.0.1`, `localhost`, `::1`); no user, password or query may be in it. | `http://127.0.0.1:8000` |

The hosted site sits behind a sign-in, which this server does not carry: it reaches an API that needs none, the one on your machine.

## Tools

| Tool | What it returns | Asks the API |
| --- | --- | --- |
| `list_materials` | The library's materials and whether a coupon setup can name each | `GET /v1/materials` |
| `material_values` | The SI values the engine would use for a material, each with its page | `GET /v1/materials/{id}` |
| `describe_coupon_form` | The rows a setup is made of, what this API offers, and an example | `GET /v1/coupon-tests`; the rows are `lib/coupon-form-definition.json` |
| `check_setup` | The setup check, item by item, with the rows to change | `POST /v1/coupon-jobs/check` |
| `solve_coupon` | The check and our kernel's answer, the package's sentences, and a `result_id` | `POST /v1/coupon-jobs/live` |
| `result_values` | Stresses and strains of one element, ply by ply, and what each criterion says there | nothing: read from the result the server holds |
| `result_extreme` | Where a quantity is largest, per ply and overall, with the plies tied | nothing |
| `explain_result` | The result's fact sheet, the package's sentences and the theory sections a question finds | `POST /v1/workspace/theory-sections` (the question alone) |
| `show_working` | The formulas with the numbers put in, for the first ply to fail; one step alone with `step` (strain, stress, criterion, loading) | nothing |

The server keeps the last 8 solves of a session in memory and forgets them when the client closes it.

## Tests

```
uv run pytest
```

The tests call the tools through an in-process MCP client against a stand-in for the API that answers with the result files the browser tests use (`tests/fixtures/studio/`).
