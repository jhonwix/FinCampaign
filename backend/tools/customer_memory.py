"""
Customer Memory Tool — Phase 3

Builds and maintains a persistent, structured memory card per customer.
The memory card is rebuilt deterministically from all customer_interactions
records after each pipeline run. No extra LLM calls required.

The memory card string is injected into the Campaign Generator prompt,
replacing the raw history window used in Phase 2.
"""

import json
from collections import Counter

from db.connection import get_pool
from db.queries import get_customer_interactions, upsert_customer_memory

_SEGMENT_ORDER = ["DEEP-SUBPRIME", "SUBPRIME", "NEAR-PRIME", "PRIME", "SUPER-PRIME"]


def _calc_dti_trend(dtis: list[float]) -> str:
    """Determine DTI direction from a list of values ordered newest-first."""
    if len(dtis) < 2:
        return "N/A"
    # dtis[0] = most recent, dtis[-1] = oldest
    if dtis[0] < dtis[-1]:
        return "IMPROVING"
    if dtis[0] > dtis[-1]:
        return "WORSENING"
    return "STABLE"


def _build_memory_card(interactions: list[dict], customer_name: str) -> str:
    """Build a deterministic memory card string from interaction records.

    Args:
        interactions: List of interaction dicts ordered by processed_at DESC.
        customer_name: Customer's full name (used in card header).

    Returns:
        Formatted multi-line string ready for prompt injection.
    """
    if not interactions:
        return ""

    total = len(interactions)
    last = interactions[0]  # most recent

    # Segment trend (show up to last 3 in chronological order)
    segments = [i["segment"] for i in interactions if i.get("segment")]
    seg_trend = " → ".join(segments[:3][::-1]) if len(segments) > 1 else (segments[0] if segments else "N/A")

    # Unique products offered (preserving order, most recent first)
    seen: set = set()
    products: list[str] = []
    for i in interactions:
        p = i.get("product_offered")
        if p and p not in seen:
            seen.add(p)
            products.append(p)

    # Verdict counts
    vcounts = dict(Counter(i["verdict"] for i in interactions if i.get("verdict")))
    verdicts_str = " | ".join(f"{v}={c}" for v, c in vcounts.items())

    # DTI trend
    dtis = [float(i["dti"]) for i in interactions if i.get("dti") is not None]
    avg_dti = sum(dtis) / len(dtis) if dtis else 0.0
    dti_trend = _calc_dti_trend(dtis)

    last_date = str(last.get("processed_at", ""))[:10]

    return "\n".join([
        f"=== CUSTOMER MEMORY — {customer_name} ===",
        f"Interactions: {total} | Last: {last_date}",
        f"Segment trend: {seg_trend}",
        f"Products offered previously: {', '.join(products) if products else 'none'}",
        f"Outcomes: {verdicts_str if verdicts_str else 'none'}",
        f"Avg DTI: {avg_dti:.1f}% (trend: {dti_trend})",
        f"Last campaign: {last.get('product_offered', 'N/A')} via {last.get('channel', 'N/A')} → {last.get('verdict', 'N/A')}",
        "CONTEXT: Use this to avoid repeating identical offers, acknowledge the customer relationship,",
        "and adjust strategy based on previous outcomes.",
        "=== END MEMORY ===",
    ])


async def refresh_customer_memory(customer_id: int, customer_name: str) -> None:
    """Rebuild and persist the memory card for a customer.

    Fetches all interactions, computes aggregates, builds the card string,
    and upserts the customer_memory row.

    Args:
        customer_id: DB customer id.
        customer_name: Customer's full name (used in card header).
    """
    interactions = await get_customer_interactions(customer_id)
    if not interactions:
        return

    card = _build_memory_card(interactions, customer_name)
    total = len(interactions)

    verdicts = dict(Counter(i["verdict"] for i in interactions if i.get("verdict")))
    dtis = [float(i["dti"]) for i in interactions if i.get("dti") is not None]
    avg_dti = sum(dtis) / len(dtis) if dtis else None
    dti_trend = _calc_dti_trend(dtis)

    seen: set = set()
    products: list[str] = []
    for i in interactions:
        p = i.get("product_offered")
        if p and p not in seen:
            seen.add(p)
            products.append(p)

    await upsert_customer_memory(customer_id, {
        "total_interactions": total,
        "first_seen_at": interactions[-1]["processed_at"],
        "last_seen_at": interactions[0]["processed_at"],
        "last_segment": interactions[0].get("segment"),
        "last_verdict": interactions[0].get("verdict"),
        "products_offered": products,
        "verdict_counts": verdicts,
        "avg_dti": avg_dti,
        "dti_trend": dti_trend,
        "memory_card": card,
    })


async def get_customer_memory_card(customer_id: int | None) -> str:
    """Return the stored memory card string for a customer.

    Args:
        customer_id: DB customer id. None → returns "" immediately.

    Returns:
        Memory card string, or "" if no memory exists or lookup fails.
    """
    if not customer_id:
        return ""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT memory_card FROM customer_memory WHERE customer_id = $1",
                customer_id,
            )
        return (row["memory_card"] or "") if row else ""
    except Exception:
        return ""
