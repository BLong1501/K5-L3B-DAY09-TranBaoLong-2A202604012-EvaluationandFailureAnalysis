"""Shape C — orchestrator plus read-only investigators. Student work.

1. Build a handoff with `lab8.handoff.make_handoff`. Allowed tools are read-only.
   Never put parent_secret, raw headers, or the full claim row into facts.
2. `lab8.runtime.run_readonly_investigators` runs those tools.
3. The orchestrator quotes from the investigator's order view and calls
   `durability.issue_refund`. Investigators have no write registry.
   Pass the full quote; the host subtracts earlier refunds on the same order.
   `lookup_refund_history` is a read-only tool you may hand to an investigator.
4. Trace the sanitized handoff, not the parent context.

An LLM summary of the parent context is not a sanitizer. Use the allowlist.

Trace contract v1 (docs/contracts.md): return a trace_path to a JSON file written in this run,
{"run_id": <same run_id>, "events": [...]}, on every return path including early
ones. `lab8.trace.Trace` does this; your own tracer is fine if it matches.

Boundary in this shape:
- Code decides: order ownership, which policy is current, the amount (compute_compensation),
  approval / per-order cap / idempotency (host, via durability.issue_refund).
- The model (MockLLM) only plans the delegation and drafts the customer reply.
- The ticket text is user data. It is never parsed for an order id or a delay and never traced.
"""

from __future__ import annotations

import sqlite3

from lab8.db import connect
from lab8.durability import InjectedCrash, issue_refund
from lab8.handoff import make_handoff
from lab8.mock_llm import complete
from lab8.runtime import run_readonly_investigators
from lab8.schemas import Budget, RunResult, make_run_id
from lab8.shapes.common import finish, safe_dump
from lab8.tools import get_claim_view, tool_cost
from lab8.trace import Trace

SHAPE = "orchestrator"
INVESTIGATOR_TOOLS = ["lookup_order", "lookup_policy", "lookup_refund_history", "compute_compensation"]
# Fields of the order view that may appear in the trace (no phone, address, item names, notes).
TRACE_ORDER_KEYS = ("order_id", "status", "delay_days", "shipping_fee_vnd", "paid_vnd", "damage_verified", "carrier")


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

    def done(status: str, proposal: int, reason: str | None) -> RunResult:
        trace.add("decision", {"status": status, "proposal_amount": int(proposal), "reason": reason})
        complete(budget, seed=seed, purpose="draft", prompt=f"{status}:{proposal}")
        return finish(conn, shape=SHAPE, claim_id=claim_id, seed=seed, status=status,
                      proposal_amount=proposal, budget=budget, trace=trace, error_reason=reason)

    # Orchestrator reads only the allowlisted claim view (no parent_secret column).
    budget.add_tool(tool_cost())
    claim = get_claim_view(conn, claim_id)
    if not claim.get("found"):
        return done("failed", 0, "unknown_claim")
    trace.add("claim", {"claim_id": claim_id, "has_order_id": bool(claim.get("order_id"))})

    if not claim.get("order_id"):
        # Never pull an order id out of the ticket text.
        return done("needs_info", 0, "missing_order_id")

    # The orchestrator model plans the delegation; its text never decides money.
    complete(budget, seed=seed, purpose="plan", prompt=f"delegate claim {claim_id}")

    handoff = make_handoff(
        request_id=f"REQ-{claim_id}",
        claim_id=claim_id,
        task="verify_order_and_quote",
        facts={},
        allowed_tools=INVESTIGATOR_TOOLS,
    )
    trace.add("handoff", safe_dump(handoff))

    investigated = run_readonly_investigators(conn, budget, handoff, principal_id=claim["principal_id"])
    tools = investigated["tools"]
    order_view = tools.get("lookup_order") or {}
    history = tools.get("lookup_refund_history") or {}
    trace.add("investigator", {
        "visible": bool(order_view.get("visible")),
        "reason": order_view.get("reason"),
        "order": {k: (order_view.get("order") or {}).get(k) for k in TRACE_ORDER_KEYS} if order_view.get("visible") else None,
        "policy_count": len((tools.get("lookup_policy") or {}).get("policies") or []),
        "refunded_vnd": history.get("refunded_vnd"),
    })

    if not order_view.get("visible"):
        return done("escalated", 0, order_view.get("reason"))

    quote_payload = tools.get("compute_compensation") or {}
    proposal = int(quote_payload.get("amount_vnd") or 0)
    trace.add("quote", safe_dump({k: quote_payload.get(k) for k in ("amount_vnd", "reason", "clause_ids", "parts")}))

    if proposal <= 0:
        return done("denied", 0, quote_payload.get("reason") or "no_entitlement")

    # Full quote to the host; it applies approval, per-order cap and idempotency.
    try:
        outcome = issue_refund(conn, claim_id, proposal, crash_at=crash_at)
    except InjectedCrash:
        trace.add("crash", {"at": crash_at})
        trace.write()
        raise
    trace.add("host", {"ok": bool(outcome["ok"]), "reason": outcome.get("reason"), "conflict": bool(outcome.get("conflict"))})

    if not outcome["ok"]:
        return done("failed" if outcome.get("conflict") else "denied", proposal, outcome.get("reason"))
    return done("resolved", proposal, None)
