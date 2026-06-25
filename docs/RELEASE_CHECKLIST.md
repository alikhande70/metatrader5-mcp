# Release checklist — v0.1.1-beta

This is the manual checklist a maintainer runs before tagging and publishing
`v0.1.1-beta`. It does not replace CI; it confirms CI is green and adds the
manual / safety checks CI cannot do on its own (Windows hardware, grep-based
safety invariants, the smoke-test table).

> **Reminder.** v0.1.1-beta still has **no order execution**. It is read /
> analysis / planning software, not live-trading software. Nothing in this
> checklist changes that — the checklist exists to confirm it stays true.

## 1. Pre-merge checks (per PR, before merging into `main`)

- [ ] PR is scoped as described in its description (tests/docs-only PRs do not
      touch `src/` unless explicitly called out and approved).
- [ ] No new `@mcp.tool()` was added or removed unless the PR explicitly says so.
- [ ] No change to `risk_guard.py`, `action_router.py`, `permissions.py`, or
      `approval_gate.py` behavior unless the PR explicitly says so.
- [ ] CI is green on the PR's head commit before merge.
- [ ] Squash merge used (one clean commit per PR on `main`).

## 2. CI checks

- [ ] `.github/workflows/tests.yml` passed on both matrix legs (Python 3.10
      and 3.11) on the commit being released.
- [ ] No CI matrix changes were made for this release unless strictly
      necessary (and if so, called out explicitly in the release PR).

## 3. Local test run

Run the full suite locally on the commit being tagged:

```bash
pip install -e ".[dev]"
pytest
```

- [ ] All tests pass, 0 failures, 0 errors.
- [ ] Record the test count from the `pytest` summary line in the release
      notes (see template below).

## 4. MCP tool count check

The server must register **exactly 18** tools (10 `SAFE_READ` + 4
`SAFE_ANALYSIS` + 4 `REQUIRES_APPROVAL`). This is asserted by
`tests/test_safety_invariants.py::test_mcp_tool_count_is_exactly_18` and
`tests/test_server.py::test_all_expected_tools_are_registered`, but confirm it
directly too:

```bash
grep -c "@mcp.tool()" src/mt5_mcp/server.py
```

- [ ] Output is `18`.

## 5. Grep checks: no execution code path exists

```bash
grep -rn "order_send(" src/
grep -rn "def order_send\|def send_order\|def place_order\|def modify_order\|def cancel_order\|def delete_order\|def close_position\|def close_order" src/
```

- [ ] Both commands return no matches.
- [ ] `tests/test_safety_invariants.py` (`test_no_order_send_call_exists_in_src`,
      `test_no_execution_function_defined_in_src`) passes, confirming this in
      CI as well as locally.

## 6. Windows smoke test

The automated suite runs against a fake in-memory MT5 module on Linux CI; it
does not prove the server works against a real Windows terminal. Before
claiming Windows validation for this release:

- [ ] Complete the **Windows smoke-test checklist** in
      [`docs/QUICKSTART_WINDOWS.md`](QUICKSTART_WINDOWS.md#windows-smoke-test-checklist)
      end-to-end on a real Windows machine with a running MT5 **demo** terminal.
- [ ] Paste the completed table (with Result/Notes filled in for every row)
      into the release notes.
- [ ] **Until that table is completed and attached, this release is NOT
      considered Windows-validated**, regardless of how green CI is — CI only
      covers the fake-MT5 path.

## 7. Tag the release

Once sections 1–6 are all checked:

```bash
git checkout main
git pull origin main
git tag -a v0.1.1-beta -m "v0.1.1-beta"
git push origin v0.1.1-beta
```

- [ ] Tag points at the exact `main` commit that passed sections 1–6.
- [ ] **Pushing the tag and creating the GitHub Release both require
      maintainer credentials** — an agent or contributor without push/release
      access cannot complete this step and must hand it off to a maintainer.

## 8. Release notes template

```markdown
## v0.1.1-beta

Phase 2: usability and safety-regression hardening. No order execution in
this release — read / analysis / planning only, same as Phase 1.

### Changed
- <bullet list of PRs merged since the last tag>

### Tests
- `pytest`: <N> passed, 0 failed (Python 3.10 and 3.11 in CI)
- MCP tool count: 18 (10 SAFE_READ, 4 SAFE_ANALYSIS, 4 REQUIRES_APPROVAL)
- No `order_send` call and no execution-named tool exist anywhere in `src/`

### Windows smoke test
<paste the completed table from docs/QUICKSTART_WINDOWS.md here>

### Safety reminder
This release still has no order execution, no modify/cancel/close/delete
order tools, no live trading, no VPS/remote mode, and no auto-approval mode.
It is not live-trading software.
```

## 9. Post-release

- [ ] Confirm the GitHub Release is published and linked to the `v0.1.1-beta` tag.
- [ ] Confirm the release notes include the completed Windows smoke-test table.
- [ ] Confirm no follow-up work was silently bundled into this tag (every
      change should trace back to a merged, reviewed PR).
