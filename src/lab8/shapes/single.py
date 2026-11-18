"""Shape B — one ReAct agent.

Vòng ReAct (lab8.runtime.run_react, tối đa 8 bước): `decide` chỉ được chọn tool ĐỌC.
Tiền do compute_compensation tính. Sau vòng lặp, code của shape (không phải model)
gọi durability.issue_refund với quote đầy đủ. Host là người ghi duy nhất.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.mock_llm import complete
from lab8.runtime import ToolRejected, run_react
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "single"
MAX_STEPS = 8


def run_claim(
    claim_id: str,
    *,
    seed: int,
    store_path: str,
    crash_at: str | None = None,
) -> RunResult:
    conn = connect(store_path)
    try:
        return _run(conn, claim_id, seed=seed, crash_at=crash_at)
    finally:
        conn.close()


def _run(conn: sqlite3.Connection, claim_id: str, *, seed: int, crash_at: str | None) -> RunResult:
    budget = Budget()
    trace = Trace(make_run_id(SHAPE, claim_id, seed))

    def done(status: str, amount: int, reason: str | None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": int(amount), "reason": reason})
        return finish(conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status,
                      proposal_amount=amount, budget=budget, trace=trace, error_reason=reason)

    # ---- Bước 1: đọc claim qua view đã lọc (không có parent_secret) ----
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim["found"]:
        return done("failed", 0, "unknown_claim")

    # ---- Bước 2: thiếu order_id -> needs_info (không đoán mã đơn từ ticket) ----
    if not claim["order_id"]:
        complete(budget, seed=seed, purpose="draft", prompt="needs_info")
        return done("needs_info", 0, "missing_order_id")

    # Model "đọc" ticket một lần (tính cost). Kết quả không được dùng để quyết tiền.
    complete(budget, seed=seed, purpose="think", prompt=claim["ticket"])

    # ---- Bước 3: vòng ReAct ----
    memory: dict[str, Any] = {}
    decide = _make_decide(claim, memory, budget, seed, trace)
    try:
        loop = run_react(
            conn,
            budget,
            observation={"claim": {"claim_id": claim_id}},
            decide=decide,
            max_steps=MAX_STEPS,
        )
    except ToolRejected as exc:
        return done("failed", 0, f"tool_rejected:{exc}")

    trace.add("react_stop", {"stopped": loop["stopped"]})
    if loop["stopped"] != "final":
        return done("failed", 0, "step_cap")

    final = loop["final"]

    # ---- Bước 4: code kiểm lại kết quả của vòng lặp ----
    if final.get("status") == "escalated":
        complete(budget, seed=seed, purpose="draft", prompt="escalated")
        return done("escalated", 0, final.get("reason"))

    quote = memory.get("quote")
    if quote is None:  # model dừng mà chưa có quote từ tool -> không tin, không trả tiền
        return done("failed", 0, "no_quote_from_tool")
    proposal = int(quote["amount_vnd"])  # lấy từ tool, KHÔNG từ final của model

    complete(budget, seed=seed, purpose="draft", prompt=f"proposal={proposal}")

    # ---- Bước 5: quote 0 -> denied, không gọi host ----
    if proposal <= 0:
        return done("denied", 0, quote.get("reason"))

    # ---- Bước 6: quote > 0 -> host quyết. Quote ĐẦY ĐỦ, truyền crash_at ----
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise  # không nuốt: T12 cần crash thật sự xảy ra
    trace.add("host", {"ok": outcome["ok"], "reason": outcome["reason"], "conflict": outcome["conflict"]})

    if not outcome["ok"]:
        return done("failed" if outcome["conflict"] else "denied", proposal, outcome["reason"])
    return done("resolved", proposal, None)


def _make_decide(claim: dict[str, Any], memory: dict[str, Any], budget: Budget, seed: int, trace: Trace):
    """Tạo hàm decide. Nó nhớ kết quả các bước trước trong `memory`
    vì run_react chỉ đưa lại kết quả của tool gần nhất."""
    who = {"order_id": claim["order_id"], "principal_id": claim["principal_id"]}

    def decide(seen: dict[str, Any]) -> dict[str, Any]:
        # 1) Ghi nhớ kết quả tool vừa chạy (nếu có)
        last_tool = seen.get("last_tool")
        result = seen.get("last_result")
        if last_tool == "lookup_order":
            memory["order_view"] = result
            trace.add("observe", {"tool": last_tool, "visible": result["visible"], "reason": result["reason"]})
        elif last_tool == "lookup_refund_history":
            memory["history"] = result
            trace.add("observe", {"tool": last_tool, "refunded_vnd": result.get("refunded_vnd")})
        elif last_tool == "compute_compensation":
            memory["quote"] = result
            trace.add("observe", {"tool": last_tool, "amount_vnd": result["amount_vnd"],
                                  "reason": result["reason"], "clause_ids": result["clause_ids"]})

        # 2) Chọn hành động tiếp theo (luật cố định, tin order row, không tin ticket)
        if "order_view" not in memory:
            action = {"tool": "lookup_order", "args": who}
        elif not memory["order_view"]["visible"]:
            action = {"final": {"status": "escalated", "reason": memory["order_view"]["reason"]}}
        elif "history" not in memory:
            action = {"tool": "lookup_refund_history", "args": who}
        elif "quote" not in memory:
            action = {"tool": "compute_compensation", "args": {"order": memory["order_view"]["order"]}}
        else:
            action = {"final": {"status": "quoted", "amount_vnd": memory["quote"]["amount_vnd"]}}

        # 3) Mỗi bước là một lần "model suy nghĩ" -> tính vào Budget
        step_name = action.get("tool") or "final"
        complete(budget, seed=seed, purpose="think", prompt=f"next={step_name}")
        trace.add("act", {"action": step_name})
        return action

    return decide
