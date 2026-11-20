"""Queue a proposal. Approving it records the decision and does not run it."""

from __future__ import annotations

from dataclasses import asdict

from .governance import DelegatedProposal, evaluate
from .policy_store import book, store


def submit(state, proposal: DelegatedProposal) -> dict:
    current = book(state)
    decision = evaluate(state, current.policy(proposal.area), proposal)
    row = {
        "proposal": asdict(proposal),
        "decision": asdict(decision),
        "status": "pending" if decision.needs_human else "authorized",
    }
    current.approvals.append(row)
    current.approvals = current.approvals[-100:]
    store(state, current)
    return row


def resolve(state, proposal_id: str, approved: bool) -> dict | None:
    current = book(state)
    found = None
    for row in current.approvals:
        if row.get("proposal", {}).get("id") == proposal_id and row.get("status") in ("pending", "authorized"):
            row["status"] = "approved" if approved else "rejected"
            found = row
            break
    store(state, current)
    return found


def note_restocks(state) -> None:
    """Put empty warehouse lines on the queue. This does not place an order."""
    if state is None:
        return
    current = book(state)
    seen = {row.get("proposal", {}).get("id") for row in current.approvals}
    try:
        from open_late.ui.inventory_sheet import sheet
    except Exception:
        return
    holes = [row for row in sheet(state, place="warehouse")["rows"] if row["status"] in ("Out", "Low")]
    for row in holes[:4]:
        proposal_id = f"restock:{row['sku']}"
        if proposal_id in seen:
            continue
        product = state.products.get(row["sku"])
        if product is None:
            continue
        qty = max(int(product.case_size or 1), int(row.get("reorder") or 1))
        submit(state, DelegatedProposal(
            id=proposal_id,
            area="inventory",
            title=f"Restock {row['product']}",
            command_kind="place_order",
            payload={"supplier_id": product.supplier_id, "items": {product.id: qty}},
            confidence=0.55,
            expected_spend=int(product.cost) * qty,
            reason=f"{row['status']} at {row['location']}. {qty} would cover the hole.",
        ))
        seen.add(proposal_id)
