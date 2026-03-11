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
                gcs_path, processing_ms, processed_at
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7,
                $8, $9, $10, $11,
                $12, $13, $14,
                $15, $16, NOW()
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
