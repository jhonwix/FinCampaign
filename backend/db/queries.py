"""
PostgreSQL query functions for the FinCampaign backend.
"""

import json
from datetime import datetime

import asyncpg

from db.connection import get_pool


async def get_customer_by_id(customer_id: int) -> dict | None:
    """
    Fetch a customer record by ID.

    Returns:
        Dict with customer fields, or None if not found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, age, monthly_income, monthly_debt,
                   credit_score, late_payments, credit_utilization,
                   products_of_interest, created_at
            FROM customers
            WHERE id = $1
            """,
            customer_id,
        )
    if row is None:
        return None
    return dict(row)


async def list_customers(limit: int = 100, offset: int = 0) -> list[dict]:
    """
    List all customers with pagination.

    Returns:
        List of customer dicts.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, age, monthly_income, monthly_debt,
                   credit_score, late_payments, credit_utilization,
                   products_of_interest, created_at
            FROM customers
            ORDER BY id
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    return [dict(r) for r in rows]


async def save_campaign_result(
    customer_id: int,
    request_id: str,
    risk_assessment: dict,
    campaign: dict,
    compliance: dict,
    gcs_path: str,
    processing_ms: int,
    campaign_id: int | None = None,
) -> int:
    """
    Save the pipeline result to the campaign_results table.

    Returns:
        The new record ID.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO campaign_results (
                customer_id, request_id, segment, risk_level, dti,
                eligible_for_credit, recommended_products,
                product_name, campaign_message, rates, channel,
                compliance_verdict, human_review_required, warnings,
                gcs_path, processing_ms, processed_at, campaign_id
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7,
                $8, $9, $10, $11,
                $12, $13, $14,
                $15, $16, NOW(), $17
            )
            RETURNING id
            """,
            customer_id,
            request_id,
            risk_assessment.get("segment"),
            risk_assessment.get("risk_level"),
            float(risk_assessment.get("dti", 0)),
            risk_assessment.get("eligible_for_credit", False),
            json.dumps(risk_assessment.get("recommended_products", [])),
            campaign.get("product_name"),
            campaign.get("campaign_message"),
            campaign.get("rates"),
            campaign.get("channel"),
            compliance.get("overall_verdict"),
            compliance.get("human_review_required", False),
            json.dumps(compliance.get("warnings", [])),
            gcs_path,
            processing_ms,
            campaign_id,
        )
    return row["id"]


async def get_results_by_customer(customer_id: int) -> list[dict]:
    """List all campaign results for a given customer."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, request_id, segment, risk_level, dti,
                   eligible_for_credit, product_name, compliance_verdict,
                   human_review_required, gcs_path, processing_ms, processed_at
            FROM campaign_results
            WHERE customer_id = $1
            ORDER BY processed_at DESC
            """,
            customer_id,
        )
    return [dict(r) for r in rows]


# ── Campaign CRUD ───────────────────────────────────────────────────────────────

async def create_campaign(data: dict) -> int:
    """Insert a new campaign row and return its id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO campaigns (
                name, type, description, target_segments,
                min_credit_score, max_credit_score, min_monthly_income,
                max_dti, max_late_payments, max_credit_utilization,
                product_name, rate_min, rate_max, max_amount, term_months,
                channel, message_tone, cta_text
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7,
                $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17, $18
            )
            RETURNING id
            """,
            data["name"],
            data["type"],
            data.get("description", ""),
            json.dumps(data.get("target_segments", [])),
            data.get("min_credit_score", 300),
            data.get("max_credit_score", 850),
            float(data.get("min_monthly_income", 0)),
            float(data.get("max_dti", 100)),
            data.get("max_late_payments", 10),
            float(data.get("max_credit_utilization", 100)),
            data.get("product_name", ""),
            float(data.get("rate_min", 0)),
            float(data.get("rate_max", 100)),
            float(data.get("max_amount", 0)),
            data.get("term_months", 0),
            data.get("channel", "Email"),
            data.get("message_tone", "Amigable"),
            data.get("cta_text", ""),
        )
    return row["id"]


async def get_campaign_by_id(campaign_id: int) -> dict | None:
    """Fetch a single campaign by id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM campaigns WHERE id = $1",
            campaign_id,
        )
    if row is None:
        return None
    return dict(row)


async def list_campaigns(limit: int = 100, offset: int = 0) -> list[dict]:
    """Return campaigns ordered by created_at desc."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM campaigns
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    return [dict(r) for r in rows]


async def update_campaign_status(campaign_id: int, status: str) -> None:
    """Set campaign status (DRAFT, RUNNING, COMPLETED)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE campaigns SET status = $1 WHERE id = $2",
            status,
            campaign_id,
        )


async def update_campaign_stats(
    campaign_id: int,
    targeted: int,
    processed: int,
    approved: int,
    review: int,
) -> None:
    """Update post-run statistics and set last_run_at."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE campaigns
            SET total_targeted   = $1,
                total_processed  = $2,
                total_approved   = $3,
                total_review     = $4,
                last_run_at      = NOW()
            WHERE id = $5
            """,
            targeted,
            processed,
            approved,
            review,
            campaign_id,
        )


async def get_campaign_results(campaign_id: int) -> list[dict]:
    """Return all campaign_results rows linked to a campaign."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT cr.id, cr.request_id, cr.customer_id,
                   c.name AS customer_name,
                   cr.segment, cr.risk_level, cr.dti,
                   cr.eligible_for_credit, cr.product_name,
                   cr.compliance_verdict, cr.human_review_required,
                   cr.processing_ms, cr.processed_at
            FROM campaign_results cr
            JOIN customers c ON c.id = cr.customer_id
            WHERE cr.campaign_id = $1
            ORDER BY cr.processed_at DESC
            """,
            campaign_id,
        )
    return [dict(r) for r in rows]
