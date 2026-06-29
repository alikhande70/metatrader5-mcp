"""MQL5 code drafting and review (Level 0/1 - never mutates a real source file).

`generate_*` return ready-to-review MQL5 source as a draft string (the caller can then
persist it with mql5_file_write_draft and apply it with the approval-gated file tools).
`code_review` runs lightweight static heuristics. `fix_compile_error` turns parsed
compiler errors into a structured, human-reviewable fix plan - it does not edit code.
"""

from __future__ import annotations

import re
from typing import Any

from . import mql5_files

_EA_TEMPLATE = """//+------------------------------------------------------------------+
//| {name}.mq5                                                       |
//| Generated draft - review before compiling.                      |
//+------------------------------------------------------------------+
#property copyright "{author}"
#property version   "1.00"
#property strict

input long   InpMagic       = {magic};   // Magic number
input double InpLots        = 0.01;       // Fixed lot size
input int    InpStopLoss    = 200;        // Stop loss (points)
input int    InpTakeProfit  = 400;        // Take profit (points)

int OnInit()
  {{
   // TODO: validate inputs and initialise indicators/handles here.
   return(INIT_SUCCEEDED);
  }}

void OnDeinit(const int reason)
  {{
   // TODO: release handles/resources here.
  }}

void OnTick()
  {{
   // TODO: implement strategy logic. This draft does NOT place any orders.
  }}
//+------------------------------------------------------------------+
"""

_INDICATOR_TEMPLATE = """//+------------------------------------------------------------------+
//| {name}.mq5 (indicator)                                           |
//| Generated draft - review before compiling.                      |
//+------------------------------------------------------------------+
#property copyright "{author}"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1

double Buffer[];

int OnInit()
  {{
   SetIndexBuffer(0, Buffer, INDICATOR_DATA);
   return(INIT_SUCCEEDED);
  }}

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {{
   // TODO: fill Buffer[] with indicator values.
   return(rates_total);
  }}
//+------------------------------------------------------------------+
"""

_SCRIPT_TEMPLATE = """//+------------------------------------------------------------------+
//| {name}.mq5 (script)                                              |
//| Generated draft - review before compiling.                      |
//+------------------------------------------------------------------+
#property copyright "{author}"
#property version   "1.00"
#property script_show_inputs

void OnStart()
  {{
   // TODO: implement one-shot script logic. This draft does NOT place any orders.
   Print("{name} script ran.");
  }}
//+------------------------------------------------------------------+
"""


def generate_ea(name: str, magic: int = 0, author: str = "mt5-mcp") -> dict[str, Any]:
    code = _EA_TEMPLATE.format(name=name, author=author, magic=magic)
    return {"kind": "expert", "name": name, "suggested_path": f"Experts/{name}.mq5", "code": code}


def generate_indicator(name: str, author: str = "mt5-mcp") -> dict[str, Any]:
    code = _INDICATOR_TEMPLATE.format(name=name, author=author)
    return {"kind": "indicator", "name": name, "suggested_path": f"Indicators/{name}.mq5", "code": code}


def generate_script(name: str, author: str = "mt5-mcp") -> dict[str, Any]:
    code = _SCRIPT_TEMPLATE.format(name=name, author=author)
    return {"kind": "script", "name": name, "suggested_path": f"Scripts/{name}.mq5", "code": code}


_RISK_PATTERNS = {
    "uses_OrderSend": re.compile(r"\bOrderSend\b|\bCTrade\b|trade\.(Buy|Sell)\(", re.IGNORECASE),
    "defines_magic": re.compile(r"magic", re.IGNORECASE),
    "defines_stoploss": re.compile(r"stop\s*loss|\bSL\b|InpStopLoss", re.IGNORECASE),
    "defines_lots": re.compile(r"\blot|\bvolume\b", re.IGNORECASE),
}


def code_review(path: str) -> dict[str, Any]:
    """Lightweight static review of a workspace MQL5 file. Read-only; returns findings."""
    info = mql5_files.read(path)
    code = info["content"]
    findings: list[str] = []

    has_oninit = "OnInit" in code
    has_ontick = "OnTick" in code
    has_onstart = "OnStart" in code
    has_oncalc = "OnCalculate" in code

    if not (has_ontick or has_onstart or has_oncalc):
        findings.append("No OnTick/OnStart/OnCalculate entry point found - is this a complete program?")
    if "OnInit" in code and "INIT_SUCCEEDED" not in code:
        findings.append("OnInit present but never returns INIT_SUCCEEDED.")
    flags = {key: bool(pat.search(code)) for key, pat in _RISK_PATTERNS.items()}
    if flags["uses_OrderSend"]:
        findings.append("Code contains trade-execution calls (OrderSend/CTrade) - confirm risk controls and magic number are set.")
        if not flags["defines_stoploss"]:
            findings.append("Trade execution detected but no obvious stop-loss handling found.")
        if not flags["defines_magic"]:
            findings.append("Trade execution detected but no magic number found - orders may collide with other EAs.")

    return {
        "path": path,
        "lines": info["lines"],
        "entry_points": {"OnInit": has_oninit, "OnTick": has_ontick, "OnStart": has_onstart, "OnCalculate": has_oncalc},
        "flags": flags,
        "findings": findings or ["No obvious issues found by the basic heuristics."],
    }


def fix_compile_error(errors: list[dict[str, Any]], source_path: str | None = None) -> dict[str, Any]:
    """Turn parsed compiler errors into a structured, human-reviewable fix plan (no code change)."""
    steps: list[dict[str, Any]] = []
    for err in errors:
        message = str(err.get("message", "")).lower()
        suggestion = "Inspect the reported line and surrounding context."
        if "undeclared identifier" in message:
            suggestion = "Declare the identifier, fix a typo, or add the missing #include."
        elif "is not defined" in message or "cannot open" in message:
            suggestion = "Add the missing #include or ensure the dependency file exists in the workspace."
        elif "wrong parameters count" in message or "no one of the overloads" in message:
            suggestion = "Adjust the call to match the function signature."
        elif "semicolon" in message or "';'" in message:
            suggestion = "Add the missing semicolon at the end of the statement."
        steps.append(
            {
                "file": err.get("file"),
                "line": err.get("line"),
                "column": err.get("column"),
                "error": err.get("message"),
                "suggested_fix": suggestion,
            }
        )
    return {
        "source_path": source_path,
        "error_count": len(steps),
        "fix_plan": steps,
        "note": "Review each step, then apply changes with mql5_file_apply_patch/update (approval required). No code was changed.",
    }
