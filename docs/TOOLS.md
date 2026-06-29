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
| `read_strategy_report` | `path: str` (a `.html`/`.htm` file inside the reports directory) | Parsed Strategy Tester HTML report: `summary` dict + `raw_rows`. Confined to `MT5_MCP_REPORTS_DIR` (default `reports/`); absolute paths and `..` traversal that escape it are rejected. |

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

## Bridge: introspection & audit (Level 0)

| Tool | Parameters | Returns |
|---|---|---|
| `list_tool_policies` | - | Every tool with its level, risk, and gating flags. |
| `get_tool_policy` | `name: str` | The full `ToolPolicy` for one tool (all capability fields). |
| `read_audit_log` | `lines: int = 100` | Tail of `logs/actions.log` as parsed JSON events. |

## Bridge: MQL5 workspace (Level 0; restore is Level 2)

All paths are confined to `MT5_MCP_WORKSPACE_DIR` (default `workspace/`).

| Tool | Parameters | Returns |
|---|---|---|
| `workspace_show_status` | - | Root, existence, and source counts per kind. |
| `workspace_detect_data_folder` | - | Configured workspace root (auto-detect needs Windows + MT5). |
| `workspace_list_experts` / `_indicators` / `_scripts` / `_includes` | - | Relative source paths. |
| `workspace_snapshot` | `label: str | None` | Zip snapshot under the backups dir (safe; no source change). |
| `workspace_restore_snapshot` | `archive: str`, `overwrite: bool = True` | Restores a snapshot zip. **Approval required.** |

## Bridge: MQL5 code — read / draft (Level 0/1, no source mutation)

| Tool | Parameters | Returns |
|---|---|---|
| `mql5_file_read` | `path: str` | File content + sha256 + line count. |
| `mql5_file_diff` | `path: str`, `new_content: str` | Unified diff vs the current file (no write). |
| `mql5_file_write_draft` | `path: str`, `content: str` | Writes to the drafts dir + diff vs source. |
| `mql5_file_backup` | `path: str` | Copies the source into the backups dir. |
| `mql5_code_review` | `path: str` | Static heuristics: entry points, risk flags, findings. |
| `mql5_code_generate_ea` | `name`, `magic: int = 0`, `author` | EA draft code + suggested path. |
| `mql5_code_generate_indicator` / `_script` | `name`, `author` | Indicator/script draft code. |
| `mql5_code_fix_compile_error` | `errors: list[dict]`, `source_path: str | None` | A human-reviewable fix plan (no code change). |

## Bridge: MQL5 file mutations (Level 2 — approval + backup + diff + rollback)

Each returns a diff, a `backup_path`, and a `rollback_id` (undo via
`mql5_file_revert_patch`). **A human must approve every call.**

| Tool | Parameters |
|---|---|
| `mql5_file_create` | `path`, `content` |
| `mql5_file_update` | `path`, `content` |
| `mql5_file_apply_patch` | `path`, `find`, `replace`, `count: int = 0` |
| `mql5_file_rename` | `path`, `new_path` |
| `mql5_file_delete` | `path` |
| `mql5_file_restore` | `path`, `backup_path` |
| `mql5_file_revert_patch` | `rollback_id` |

## Bridge: MetaEditor adapters (Level 0/1; `run_compile` Level 3)

| Tool | Parameters | Returns |
|---|---|---|
| `metaeditor_detect_path` | - | Locates `metaeditor64.exe` (Windows only). |
| `metaeditor_prepare_compile` | `source_path`, `include_path: str | None` | The `/compile` command line (no execution). |
| `metaeditor_run_compile` | `source_path`, `include_path`, `timeout_s: int = 120` | Compiles (Windows only; else `UNSUPPORTED_IN_THIS_ENVIRONMENT`). **Approval required.** |
| `metaeditor_read_compile_log` | `path` | Reads a `.log` from the workspace. |
| `metaeditor_parse_errors` / `_warnings` | `log_text: str` | Parsed `{file, line, column, code, message}` entries. |
| `metaeditor_generate_fix_plan` | `log_text`, `source_path` | Fix plan from parsed errors. |

## Bridge: Strategy Tester adapters (Level 0/1; `run_backtest` Level 3)

| Tool | Parameters | Returns |
|---|---|---|
| `tester_prepare_signal_only_test` | `expert`, `symbol`, `timeframe`, `date_from`, `date_to`, `deposit`, `model` | A tester `.ini` config draft (no execution). |
| `tester_run_backtest_if_supported` | `config_ini: str | None` | Gated; off-Windows returns `UNSUPPORTED_IN_THIS_ENVIRONMENT`. **Approval required.** |
| `tester_import_csv` | `path` (`.csv` in the reports dir) | Header + parsed rows + delimiter. |
| `tester_review_results` | `summary: dict` | Normalised metrics + red-flag list. |
| `tester_compare_runs` | `runs: list[dict]` | Best run by profit factor / net profit / drawdown. |
| `tester_generate_backtest_report` | `review: dict`, `title` | Markdown report string. |

## Declared but disabled (Level 4/5 — not registered as tools)

`mt5_chart_*`, `mt5_ea_*`, and `mt5_live_*` are declared in `policy.py` so the
capability model documents them and `dispatch()` fails closed, but they are
**disabled by default and not exposed as MCP tools** in this phase. Operational
chart/EA-runtime and live-account control are out of scope here.

## BLOCKED / not implemented

No tool by these names exists: `send_order`, `place_order`, `modify_order`,
`cancel_order`, `delete_order`, `close_position`, `close_order`,
`execute_trade`, `live_trade`. They're listed in `permissions.py` purely so
`action_router.dispatch()` refuses them by name if anything ever tries to
call them.
