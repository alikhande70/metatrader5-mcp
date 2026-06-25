"""Minimal standalone MCP client demonstrating metatrader5-mcp Phase 1 tools.

Run from the project root (after `pip install -e .`):

    python examples/example_client.py

This starts the server as a subprocess over stdio, lists its tools, and
calls a SAFE_READ tool, a SAFE_ANALYSIS tool, and a REQUIRES_APPROVAL tool
(which will prompt for console approval if MT5_MCP_APPROVAL_MODE=console).
Without a real MT5 terminal, the MT5-touching calls will return a clear
"MetaTrader5 package not available" error - that's expected on non-Windows
machines or when no terminal is running.
"""

from __future__ import annotations

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(command="python", args=["-m", "mt5_mcp.server"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:", sorted(t.name for t in tools.tools))

            print("\n--- SAFE_READ: get_account_info ---")
            result = await session.call_tool("get_account_info", {})
            print(result)

            print("\n--- SAFE_ANALYSIS: calculate_profit_risk_basic (pure math, no MT5 needed) ---")
            result = await session.call_tool(
                "calculate_profit_risk_basic",
                {"entry_price": 1.1000, "stop_loss": 1.0950, "take_profit": 1.1100},
            )
            print(result)

            print("\n--- REQUIRES_APPROVAL: check_order (will prompt for approval) ---")
            result = await session.call_tool(
                "check_order",
                {"order_type": "BUY", "symbol": "EURUSD", "volume": 0.1, "price": 1.1000},
            )
            print(result)


if __name__ == "__main__":
    asyncio.run(main())
