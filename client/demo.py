"""Repeatable MCP demo showing multiple tools and failure recovery.

Run from the project root:
    python -m client.demo
"""
import asyncio
import sys
from pathlib import Path

from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

from client.agent import result_text

ROOT = Path(__file__).resolve().parent.parent


async def run_demo() -> None:
    """Call two tracker tools, recover from an invalid update, and continue."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.main"],
        cwd=str(ROOT),
    )
    async with Client(params) as session:
        print("1. Listing saved opportunities:")
        saved = await session.call_tool(
            "list_saved_opportunities", {"status": "saved", "limit": 3}
        )
        print(result_text(saved) or "(none saved)")

        print("\n2. Demonstrating recovery from a failed tracker call:")
        failed = await session.call_tool(
            "update_status", {"opportunity_id": 999999, "status": "applied"}
        )
        if failed.is_error:
            print("Expected tool error:", result_text(failed))
        else:
            print("Unexpectedly updated an opportunity:", result_text(failed))

        print("\n3. Continuing after the error with pipeline stats:")
        stats = await session.call_tool("pipeline_stats", {})
        print(result_text(stats) or "(no tracker statistics)")


if __name__ == "__main__":
    asyncio.run(run_demo())
