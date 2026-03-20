"""
Customer History Tool

Fetches a customer's previous campaign results from PostgreSQL and formats
them as structured context for the Campaign Generator agent.

This is a "tool" in the agentic sense: the orchestrator explicitly calls it
before invoking the Campaign Generator, giving the agent memory of what this
customer has previously received. The agent then uses this context to avoid
repeating offers, acknowledge returning customers, and adjust strategy.

Production value:
  - Prevents campaign fatigue (same product offered 3 times in 90 days)
  - Enables loyalty messaging ("As a valued customer who recently qualified...")
  - Informs channel choice (previous REVIEW via Email → try WhatsApp)
  - Enables intelligent cross-sell ("Already APPROVED for Personal → offer Card")
  - Generates better personalization than any static rule system can
"""

from datetime import datetime, timedelta

from db.queries import get_results_by_customer

_HISTORY_WINDOW_DAYS = 180   # look back 6 months
_MAX_ENTRIES = 5             # max history items injected into prompt


async def get_customer_history_context(customer_id: int | None) -> str:
    """
    Fetch and format the recent campaign history for a customer.

    Args:
        customer_id: DB customer id. None means no history lookup (anonymous profile).

    Returns:
        A formatted string for injection into the Campaign Generator prompt,
        or an empty string if no history exists or lookup fails.
    """
    if not customer_id:
        return ""

    try:
        all_results = await get_results_by_customer(customer_id)
    except Exception as exc:
        # History is enrichment, never critical path — fail gracefully
        print(f"[HistoryTool] Failed to fetch history for customer {customer_id}: {exc}")
        return ""

    if not all_results:
        return ""

    # Filter to window
    cutoff = datetime.utcnow() - timedelta(days=_HISTORY_WINDOW_DAYS)
    recent = []
    for r in all_results[:20]:
        processed_at = r.get("processed_at")
        if isinstance(processed_at, str):
            try:
                processed_at = datetime.fromisoformat(processed_at.replace("Z", "+00:00"))
                processed_at = processed_at.replace(tzinfo=None)
            except Exception:
                pass
        if isinstance(processed_at, datetime) and processed_at < cutoff:
            continue
        recent.append(r)

    if not recent:
        return ""

    lines = [
        f"=== CUSTOMER HISTORY — last {_HISTORY_WINDOW_DAYS} days ({len(recent)} interaction(s)) ===",
    ]
    for r in recent[:_MAX_ENTRIES]:
        date_str = r.get("processed_at", "")
        if isinstance(date_str, datetime):
            date_str = date_str.strftime("%Y-%m-%d")
        elif isinstance(date_str, str) and "T" in date_str:
            date_str = date_str[:10]

        eligible_str = "eligible" if r.get("eligible_for_credit") else "NOT eligible"
        review_str = " [HUMAN REVIEW REQUIRED]" if r.get("human_review_required") else ""
        lines.append(
            f"  [{date_str}] product={r.get('product_name', 'N/A')} | "
            f"verdict={r.get('compliance_verdict', '?')} | "
            f"segment={r.get('segment', '?')} | {eligible_str}{review_str}"
        )

    lines.append(
        "IMPORTANT: Use this history to avoid repeating the exact same offer, "
        "acknowledge the customer's relationship, and build on previous interactions."
    )
    return "\n".join(lines)


def summarize_history_for_log(history_ctx: str) -> str:
    """Return a short one-liner for orchestrator logging."""
    if not history_ctx:
        return "no history"
    count = history_ctx.count("[20")   # rough count of date entries
    return f"{count} previous interaction(s)"
