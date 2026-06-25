"""Minimal standalone MCP client for metatrader5-mcp (Phase 1 tools).

Run from the project root (after `pip install -e .`):

    python examples/example_client.py

This starts the server as a subprocess over stdio, lists its tools, and makes
exactly three illustrative calls, one per permission tier:

  1. SAFE_READ      - get_account_info        (no approval, reads only)
  2. SAFE_ANALYSIS  - calculate_profit_risk_basic (pure math, no MT5 needed)
  3. REQUIRES_APPROVAL - prepare_order_plan    (PLANNING ONLY - never sent)

IMPORTANT - this client never trades:
  - It does not send orders. It never calls order_send.
  - It does not modify, cancel, close, or delete any order.
  - The REQUIRES_APPROVAL call below only builds an order *plan* (margin /
    estimated P/L / MT5's own dry-run validation). It is NOT execution, and the
    server's risk guard still blocks it unless you are on a demo account with
    MT5_MCP_ENABLE_DEMO_TRADING=true and you approve it interactively.

Without a real MT5 terminal, the MT5-touching calls return a clear
"MetaTrader5 package not available" error - that is expected on non-Windows
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

            print("\n--- SAFE_READ: get_account_info (reads only, no approval) ---")
            result = await session.call_tool("get_account_info", {})
            print(result)

            print("\n--- SAFE_ANALYSIS: calculate_profit_risk_basic (pure math, no MT5 needed) ---")
            result = await session.call_tool(
                "calculate_profit_risk_basic",
                {"entry_price": 1.1000, "stop_loss": 1.0950, "take_profit": 1.1100},
            )
            print(result)

            print("\n--- REQUIRES_APPROVAL: prepare_order_plan (PLANNING ONLY - NOT SENT) ---")
            print("NOTE: this only builds an order plan (margin / estimated P/L / dry-run check).")
            print("      It does NOT place an order. No order_send is called. Live trading is blocked.")
            print("      It needs a demo account + MT5_MCP_ENABLE_DEMO_TRADING=true + your approval.")
            result = await session.call_tool(
                "prepare_order_plan",
                {"order_type": "BUY", "symbol": "EURUSD", "volume": 0.1, "price": 1.1000},
            )
            print(result)
            print("\nReminder: the output above is a PLAN, not an executed trade. Nothing was sent.")


if __name__ == "__main__":
    asyncio.run(main())
