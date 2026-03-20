"""
PostgreSQL query functions for the FinCampaign backend.
"""

import json
from datetime import datetime

import asyncpg

from db.connection import get_pool
from typing import Any


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
            SELECT id, id_number, name, age, monthly_income, monthly_debt,
                   credit_score, late_payments, credit_utilization,
                   products_of_interest, existing_products, created_at
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
            SELECT id, id_number, name, age, monthly_income, monthly_debt,
                   credit_score, late_payments, credit_utilization,
                   products_of_interest, existing_products, created_at
            FROM customers
            ORDER BY id
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )
    return [dict(r) for r in rows]


async def count_customers() -> int:
    """Return the total number of customers in the DB."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM customers")


async def save_campaign_result(
    customer_id: int,
    request_id: str,
    risk_assessment: dict,
    campaign: dict,
    compliance: dict,
    gcs_path: str,
    processing_ms: int,
    campaign_id: int | None = None,
    pipeline_route: str = "STANDARD",
    pipeline_confidence: float | None = None,
    correction_attempts: int = 0,
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
                gcs_path, processing_ms, processed_at, campaign_id,
                pipeline_route, pipeline_confidence, correction_attempts
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7,
                $8, $9, $10, $11,
                $12, $13, $14,
                $15, $16, NOW(), $17,
                $18, $19, $20
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
            pipeline_route,
            pipeline_confidence,
            correction_attempts,
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
                channel, message_tone, cta_text, campaign_intent
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7,
                $8, $9, $10,
                $11, $12, $13, $14, $15,
                $16, $17, $18, $19
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
            data.get("campaign_intent", "NEW"),
        )
    return row["id"]


async def get_campaign_by_id(campaign_id: int) -> dict | None:
    """Fetch a single campaign by id."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, type, description, target_segments,
                   min_credit_score, max_credit_score, min_monthly_income,
                   max_dti, max_late_payments, max_credit_utilization,
                   product_name, rate_min, rate_max, max_amount, term_months,
                   channel, message_tone, cta_text, campaign_intent,
                   status, total_targeted, total_processed, total_approved, total_review,
                   created_at, last_run_at
            FROM campaigns
            WHERE id = $1
            """,
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


async def bulk_insert_customers(customers: list[dict]) -> dict:
    """
    Insert multiple customers, skipping duplicates by id_number.
    Returns: { inserted, duplicates, errors }
    """
    pool = await get_pool()
    inserted = 0
    duplicates = 0
    errors: list[dict] = []

    async with pool.acquire() as conn:
        # Fetch all existing id_numbers once
        existing = {
            r["id_number"]
            for r in await conn.fetch("SELECT id_number FROM customers")
            if r["id_number"]
        }

        for c in customers:
            id_number = c.get("id_number", "")
            if id_number in existing:
                duplicates += 1
                continue
            try:
                await conn.execute(
                    """
                    INSERT INTO customers (
                        id_number, name, age, monthly_income, monthly_debt,
                        credit_score, late_payments, credit_utilization,
                        products_of_interest, existing_products
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    """,
                    id_number, c["name"], c["age"],
                    float(c["monthly_income"]), float(c["monthly_debt"]),
                    int(c["credit_score"]), int(c["late_payments"]),
                    float(c["credit_utilization"]), c["products_of_interest"],
                    c.get("existing_products", ""),
                )
                existing.add(id_number)
                inserted += 1
            except Exception as exc:
                errors.append({"name": c.get("name", "?"), "error": str(exc)})

    return {"inserted": inserted, "duplicates": duplicates, "errors": errors}


# ── Customer Memory (Phase 3) ────────────────────────────────────────────────

async def save_customer_interaction(
    customer_id: int,
    request_id: str,
    segment: str,
    eligible: bool,
    dti: float,
    product_offered: str,
    verdict: str,
    channel: str,
    pipeline_route: str = "STANDARD",
    confidence: float | None = None,
    campaign_id: int | None = None,
) -> None:
    """Insert one row into customer_interactions."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO customer_interactions (
                customer_id, campaign_id, request_id,
                pipeline_route, segment, eligible,
                dti, product_offered, verdict,
                channel, confidence
            ) VALUES (
                $1, $2, $3,
                $4, $5, $6,
                $7, $8, $9,
                $10, $11
            )
            """,
            customer_id,
            campaign_id,
            request_id,
            pipeline_route,
            segment,
            eligible,
            float(dti) if dti is not None else None,
            product_offered,
            verdict,
            channel,
            float(confidence) if confidence is not None else None,
        )


async def get_customer_interactions(customer_id: int) -> list[dict]:
    """Return all interaction rows for a customer, ordered newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, customer_id, campaign_id, request_id,
                   pipeline_route, segment, eligible, dti,
                   product_offered, verdict, channel, confidence, processed_at
            FROM customer_interactions
            WHERE customer_id = $1
            ORDER BY processed_at DESC
            """,
            customer_id,
        )
    return [dict(r) for r in rows]


async def upsert_customer_memory(customer_id: int, memory: dict) -> None:
    """Insert or update the customer_memory row for a customer."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO customer_memory (
                customer_id, total_interactions, first_seen_at, last_seen_at,
                last_segment, last_verdict, products_offered, verdict_counts,
                avg_dti, dti_trend, memory_card, updated_at
            ) VALUES (
                $1, $2, $3, $4,
                $5, $6, $7, $8,
                $9, $10, $11, NOW()
            )
            ON CONFLICT (customer_id) DO UPDATE SET
                total_interactions = EXCLUDED.total_interactions,
                first_seen_at      = EXCLUDED.first_seen_at,
                last_seen_at       = EXCLUDED.last_seen_at,
                last_segment       = EXCLUDED.last_segment,
                last_verdict       = EXCLUDED.last_verdict,
                products_offered   = EXCLUDED.products_offered,
                verdict_counts     = EXCLUDED.verdict_counts,
                avg_dti            = EXCLUDED.avg_dti,
                dti_trend          = EXCLUDED.dti_trend,
                memory_card        = EXCLUDED.memory_card,
                updated_at         = NOW()
            """,
            customer_id,
            memory["total_interactions"],
            memory.get("first_seen_at"),
            memory.get("last_seen_at"),
            memory.get("last_segment"),
            memory.get("last_verdict"),
            json.dumps(memory.get("products_offered", [])),
            json.dumps(memory.get("verdict_counts", {})),
            float(memory["avg_dti"]) if memory.get("avg_dti") is not None else None,
            memory.get("dti_trend"),
            memory.get("memory_card"),
        )


async def delete_campaign_results(campaign_id: int) -> int:
    """Delete all campaign_results rows for a campaign. Returns number of deleted rows."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM campaign_results WHERE campaign_id = $1",
            campaign_id,
        )
    # asyncpg returns "DELETE N" as a string
    return int(result.split()[-1])


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
                   cr.pipeline_route, cr.pipeline_confidence,
                   cr.correction_attempts,
                   cr.processing_ms, cr.processed_at,
                   cr.review_status, cr.review_note, cr.reviewed_at
            FROM campaign_results cr
            JOIN customers c ON c.id = cr.customer_id
            WHERE cr.campaign_id = $1
            ORDER BY cr.processed_at DESC
            """,
            campaign_id,
        )
    return [dict(r) for r in rows]


async def update_result_review(
    result_id: int,
    review_status: str,
    review_note: str,
) -> dict | None:
    """
    Set review_status, review_note, reviewed_at on a campaign_results row.

    Returns:
        Updated row dict (id, review_status, review_note, reviewed_at),
        or None if result_id not found.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE campaign_results
            SET review_status = $1,
                review_note   = $2,
                reviewed_at   = NOW()
            WHERE id = $3
            RETURNING id, review_status, review_note, reviewed_at
            """,
            review_status,
            review_note,
            result_id,
        )
    if row is None:
        return None
    result = dict(row)
    if result.get("reviewed_at"):
        result["reviewed_at"] = result["reviewed_at"].isoformat()
    return result
