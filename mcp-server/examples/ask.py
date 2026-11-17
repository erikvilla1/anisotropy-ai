"""Try the server as an MCP client does (ADR-0107): start it over stdin and stdout, solve the form's example coupon through the API on
this machine and ask about the result. Run it with the API up, from this folder:

    uv run python examples/ask.py

It prints what each tool answered, shortened. No model is involved: this is the plumbing a client such as Claude Desktop uses.
"""

import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

HERE = Path(__file__).resolve().parents[1]


async def main() -> int:
    server = StdioServerParameters(command="uv", args=["run", "--directory", str(HERE), "anisotropy-mcp"])
    async with Client(server) as client:
        async def ask(tool: str, **arguments):
            result = await client.call_tool(tool, arguments)
            text = result.content[0].text if result.content else ""
            if result.is_error:
                raise SystemExit(f"{tool}: {text}")
            return json.loads(text)

        print("tools:", ", ".join(tool.name for tool in (await client.list_tools()).tools))
        form = await ask("describe_coupon_form")
        values = {**form["example"], "filled_by": "examples/ask.py", "date": dt.date.today().isoformat(), "size_from": "the form's example"}
        solved = await ask("solve_coupon", values=values)
        if not solved["solved"]:
            raise SystemExit(f"not solved: {json.dumps(solved['setup']['not_passed'], indent=1)}")
        print("solved:", solved["coupon"]["title"])
        print("answer:", solved["sentences"][0])
        first = solved["answer"]["first_ply_failure"][solved["answer"]["verdict"]["earliest"]]
        element = int(first["label"].rsplit(".", 1)[1])
        at = await ask("result_values", result_id=solved["result_id"], element=element, plies=[first["ply"]], quantities=["S11", "S22", "S12"])
        print(f"ply {first['ply']} at element {element}:", at["rows"][0]["values"], at["units"]["S11"])
        shear = (await ask("result_extreme", result_id=solved["result_id"], quantities=["S12"]))["extremes"][0]
        print(f"largest |S12| in the gauge section: {shear['value']} {shear['unit']}, ply {shear['ply']} at element {shear['element']}; tied plies {shear['tied_plies']}")
        why = await ask("explain_result", result_id=solved["result_id"], question="why does this ply fail first?")
        print("why, from:", "; ".join(section["from"] for section in why["theory"]) or "no section found")
        working = await ask("show_working", result_id=solved["result_id"], criterion=solved["answer"]["verdict"]["earliest"])
        last = next(iter(working["criteria"].values()))["steps"][-1]
        print("working, last step:", last["title"], "|", last["equations"][-1]["substituted"] if last["equations"] else "")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
