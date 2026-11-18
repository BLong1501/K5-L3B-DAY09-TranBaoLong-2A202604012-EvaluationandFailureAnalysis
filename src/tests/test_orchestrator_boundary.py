"""Shape C boundary: the trace holds the sanitized handoff only, never the ticket or parent context."""

from __future__ import annotations

import json
from pathlib import Path

from lab8.handoff import ALLOWED_FIELDS, READONLY_TOOLS
from lab8.shapes.orchestrator import run_claim
from tests.conftest import CLAIMS


def _events(result) -> list[dict]:
    data = json.loads(Path(result.trace_path).read_text(encoding="utf-8"))
    assert data["run_id"] == result.run_id
    return data["events"]


def test_orchestrator_traces_sanitized_handoff_without_ticket(public_db):
    for claim in CLAIMS:
        result = run_claim(claim["claim_id"], seed=11, store_path=str(public_db))
        blob = Path(result.trace_path).read_text(encoding="utf-8")
        assert "CANARY_SECRET_" not in blob
        assert "parent_secret" not in blob
        if claim.get("ticket") and len(claim["ticket"]) > 20:
            assert claim["ticket"] not in blob
        for event in _events(result):
            payload = event.get("payload", event)
            if event.get("kind") == "handoff" or payload.get("contract_version") == "handoff.v1":
                assert set(payload) <= ALLOWED_FIELDS
                assert set(payload["allowed_tools"]) <= READONLY_TOOLS


def test_orchestrator_missing_order_id_is_needs_info_without_ledger(public_db):
    missing = [c for c in CLAIMS if not c.get("order_id")]
    assert missing, "public set should contain a claim without order_id"
    result = run_claim(missing[0]["claim_id"], seed=22, store_path=str(public_db))
    assert result.status == "needs_info"
    assert result.proposal_amount == 0
    assert result.refund_effects == []
