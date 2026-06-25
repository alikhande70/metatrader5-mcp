# Examples

Practical usage examples for the three permission tiers this server exposes.
Outputs below are **simplified** for readability — real responses include more
fields.

> **Planning is not execution.** Every example here only reads data, computes
> numbers, or builds an order *plan*. **No order is ever sent**, this server has
> no `order_send`, and **live trading is always blocked**. The
> `REQUIRES_APPROVAL` tools produce a plan for a human to review — they do not
> place, modify, or cancel anything.

For a runnable version of the calls below, see
[`examples/example_client.py`](../examples/example_client.py). For wiring an MCP
client (Claude Desktop / Claude Code), see
[`examples/claude_desktop_config.example.json`](../examples/claude_desktop_config.example.json)
and [`examples/claude_code_config.example.json`](../examples/claude_code_config.example.json),
plus the [Windows quickstart](QUICKSTART_WINDOWS.md).

---

## SAFE_READ

Read-only market/account data. Always allowed, logged, no approval required.
Nothing here changes any state.

### `get_account_info`

```text
call: get_account_info()
->
{
  "login": 5012345,
  "balance": 10000.0,
  "equity": 10000.0,
  "currency": "USD",
  "leverage": 100,
  "trade_mode": 0        # 0 = demo, 1 = contest, 2 = real
}
```

### `get_symbol_info` / `get_tick`

```text
call: get_symbol_info(symbol="EURUSD")
->
{ "name": "EURUSD", "digits": 5, "point": 0.00001, "trade_contract_size": 100000.0 }

call: get_tick(symbol="EURUSD")
->
{ "bid": 1.10000, "ask": 1.10020, "last": 1.10010, "time": 1700000000 }
```

### `get_rates`

```text
call: get_rates(symbol="EURUSD", timeframe="H1", count=3)
->
[
  { "time": 1700000000, "open": 1.1000, "high": 1.1015, "low": 1.0995, "close": 1.1008 },
  { "time": 1700003600, "open": 1.1008, "high": 1.1020, "low": 1.1002, "close": 1.1012 },
  ...
]
```

### `get_positions` / `get_orders` / `get_history_deals`

```text
call: get_positions()              -> []        # no open positions
call: get_orders()                 -> []        # no pending orders
call: get_history_deals(date_from="2024-01-01", date_to="2024-12-31")
->
[ { "ticket": 100, "symbol": "EURUSD", "volume": 0.1, "price": 1.10, "profit": 20.0 } ]
```

### `read_log` / `read_strategy_report`

```text
call: read_log(date="20240101", lines=3, kind="terminal")
->
{ "kind": "terminal", "date": "20240101", "returned_lines": 3, "lines": ["...", "...", "..."] }

call: read_strategy_report(path="ReportTester.html")
->
{ "summary": { "Total Net Profit": "2099.42", "Profit Factor": "1.57" }, "raw_rows": [ ... ] }
```

`read_strategy_report` only reads `.html`/`.htm` files inside the configured
reports directory (`MT5_MCP_REPORTS_DIR`, default `reports/`). Paths that escape
it are rejected.

---

## SAFE_ANALYSIS

Pure computation over data you already read. No MT5 connection required, no
approval needed, no state change.

### `calculate_profit_risk_basic`

```text
call: calculate_profit_risk_basic(entry_price=1.1000, stop_loss=1.0950, take_profit=1.1100)
->
{ "risk": 0.0050, "reward": 0.0100, "risk_reward_ratio": 2.0 }
```

### `summarize_positions` / `analyze_drawdown` / `analyze_trade_history`

```text
call: analyze_trade_history(deals=[ ... ])
->
{ "trades": 42, "win_rate": 0.57, "profit_factor": 1.4, "avg_win": 31.2, "avg_loss": -22.8 }
```

These never connect to a broker to place anything — they only crunch numbers on
data you pass in (or that was already read via a SAFE_READ tool).

---

## REQUIRES_APPROVAL (order *planning* only)

These are the closest thing to trading in this server, so they require a human
approval **and** a demo account with `MT5_MCP_ENABLE_DEMO_TRADING=true`. Even
then, **they only plan. They never send an order.** There is no `order_send`
anywhere in this server, and real/contest accounts are always blocked.

### `calculate_margin` / `calculate_profit`

```text
call: calculate_margin(order_type="BUY", symbol="EURUSD", volume=0.1, price=1.1000)
->
{ "margin": 110.0, "currency": "USD" }        # what the order WOULD require; not placed
```

### `check_order` / `prepare_order_plan`

```text
call: prepare_order_plan(order_type="BUY", symbol="EURUSD", volume=0.1, price=1.1000)
->
{
  "request":   { "action": "DEAL", "symbol": "EURUSD", "volume": 0.1, "price": 1.1000 },
  "margin":    110.0,
  "est_profit": 50.0,
  "order_check": { "retcode": 0, "comment": "Done" },
  "note": "PLAN ONLY - not sent. Live trading is blocked; no order_send is called."
}
```

The result is a **plan for review**. To act on it, a human would place the trade
themselves in the MetaTrader 5 terminal. This server will not do it for you.

---

## Recap

- **Planning is not execution.**
- **No order is sent** by any tool in this server.
- **Live trading is blocked** — unconditionally for real/contest accounts, and
  for demo accounts unless you explicitly opt in *and* approve each call.

If a call fails, see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
