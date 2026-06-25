# Tool reference

All parameters are JSON-serializable; all responses are plain dicts/lists.

## SAFE_READ

| Tool | Parameters | Returns |
|---|---|---|
| `get_account_info` | - | Account dict: balance, equity, margin, leverage, currency, `trade_mode` (0=demo, 1=contest, 2=real), etc. |
| `get_terminal_info` | - | Terminal dict: connected, trade_allowed, data_path, build, etc. |
| `get_symbol_info` | `symbol: str` | Symbol spec dict: point, digits, spread, volume_min/max/step, contract size, etc. |
| `get_tick` | `symbol: str` | Latest tick dict: time, bid, ask, last, volume. |
| `get_rates` | `symbol: str`, `timeframe: str` (e.g. `M1`, `M15`, `H1`, `H4`, `D1`), `count: int = 100`, `start_pos: int = 0` | List of OHLCV bar dicts, most recent `count` bars starting `start_pos` back. |
| `get_positions` | `symbol: str | None`, `ticket: int | None` | List of open position dicts. |
| `get_orders` | `symbol: str | None`, `ticket: int | None` | List of active pending order dicts. |
| `get_history_deals` | `date_from`, `date_to` (ISO date strings), or `ticket`, or `position`, optional `group` | List of historical deal dicts. |
| `read_log` | `date: str | None` (YYYYMMDD, default today), `lines: int = 200`, `kind: "terminal" | "experts"` | Tail of the MT5 log file for that date. |
| `read_strategy_report` | `path: str` | Parsed Strategy Tester HTML report: `summary` dict + `raw_rows`. |

## SAFE_ANALYSIS

| Tool | Parameters | Returns |
|---|---|---|
| `summarize_positions` | `positions: list[dict] | None` (fetched live if omitted) | Totals + breakdown by symbol and by side. |
| `analyze_drawdown` | `deals: list[dict] | None`, `starting_balance: float = 0.0`, `include_curve: bool = False`, or `date_from`/`date_to` to fetch live deals | Peak-to-trough drawdown stats. |
| `analyze_trade_history` | `deals: list[dict] | None`, or `date_from`/`date_to` | Win rate, profit factor, gross/net profit, average win/loss. |
| `calculate_profit_risk_basic` | `entry_price`, `stop_loss`, `take_profit`, `volume: float = 1.0`, `value_per_point: float | None` | Risk/reward distances and ratio; estimated money amounts if `value_per_point` given. Pure math - no MT5 connection. |

## REQUIRES_APPROVAL (order planning - never sends an order)

A human must approve every call (see `docs/SAFETY.md`), and the risk guard
requires a demo account with `MT5_MCP_ENABLE_DEMO_TRADING=true`.

| Tool | Parameters | Returns |
|---|---|---|
| `calculate_margin` | `order_type` (`BUY`/`SELL`/...), `symbol`, `volume`, `price` | `{required_margin, ...}` from MT5's `order_calc_margin`. |
| `calculate_profit` | `order_type`, `symbol`, `volume`, `price_open`, `price_close` | `{estimated_profit, ...}` from MT5's `order_calc_profit`. |
| `check_order` | `order_type`, `symbol`, `volume`, `price`, `sl`, `tp`, `deviation`, `magic`, `comment` | `{request, check_result, sent: false}` - server-side dry-run validation via MT5's `order_check`. |
| `prepare_order_plan` | same as `check_order` | A full plan dict: `plan_id`, `status: "PLANNED_NOT_SENT"`, `request`, `required_margin`, `estimated_profit_at_tp`, `estimated_loss_at_sl`, `order_check_result`. |

`order_type` accepts MT5's order type names: `BUY`, `SELL`, `BUY_LIMIT`,
`SELL_LIMIT`, `BUY_STOP`, `SELL_STOP`.

## BLOCKED / not implemented

No tool by these names exists: `send_order`, `place_order`, `modify_order`,
`cancel_order`, `delete_order`, `close_position`, `close_order`,
`execute_trade`, `live_trade`. They're listed in `permissions.py` purely so
`action_router.dispatch()` refuses them by name if anything ever tries to
call them.
