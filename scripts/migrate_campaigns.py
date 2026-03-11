"""
Migration: Add campaigns table and campaign_id column to campaign_results.

Run with:
    python scripts/migrate_campaigns.py
"""

import asyncio
import sys
import os

# Add backend/ to sys.path so that `config`, `db`, etc. resolve correctly
# (connection.py does `from config import settings` which needs backend/ in path)
_backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, os.path.abspath(_backend_dir))

from db.connection import get_pool, close_pool


CREATE_CAMPAIGNS = """
CREATE TABLE IF NOT EXISTS campaigns (
    id                     SERIAL PRIMARY KEY,
    name                   VARCHAR(100)  NOT NULL,
    type                   VARCHAR(50)   NOT NULL,
    description            TEXT          NOT NULL DEFAULT '',
    status                 VARCHAR(20)   NOT NULL DEFAULT 'DRAFT',
    target_segments        JSONB         NOT NULL DEFAULT '[]',
    min_credit_score       INTEGER       NOT NULL DEFAULT 300,
    max_credit_score       INTEGER       NOT NULL DEFAULT 850,
    min_monthly_income     NUMERIC(12,2) NOT NULL DEFAULT 0,
    max_dti                NUMERIC(5,2)  NOT NULL DEFAULT 100,
    max_late_payments      INTEGER       NOT NULL DEFAULT 10,
    max_credit_utilization NUMERIC(5,2)  NOT NULL DEFAULT 100,
    product_name           VARCHAR(100)  NOT NULL DEFAULT '',
    rate_min               NUMERIC(5,2)  NOT NULL DEFAULT 0,
    rate_max               NUMERIC(5,2)  NOT NULL DEFAULT 100,
    max_amount             NUMERIC(14,2) NOT NULL DEFAULT 0,
    term_months            INTEGER       NOT NULL DEFAULT 0,
    channel                VARCHAR(50)   NOT NULL DEFAULT 'Email',
    message_tone           VARCHAR(50)   NOT NULL DEFAULT 'Amigable',
    cta_text               VARCHAR(200)  NOT NULL DEFAULT '',
    total_targeted         INTEGER       NOT NULL DEFAULT 0,
    total_processed        INTEGER       NOT NULL DEFAULT 0,
    total_approved         INTEGER       NOT NULL DEFAULT 0,
    total_review           INTEGER       NOT NULL DEFAULT 0,
    created_at             TIMESTAMP     NOT NULL DEFAULT NOW(),
    last_run_at            TIMESTAMP
);
"""

ALTER_CAMPAIGN_RESULTS = """
ALTER TABLE campaign_results
    ADD COLUMN IF NOT EXISTS campaign_id INTEGER REFERENCES campaigns(id);
"""


async def run():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Creating campaigns table...")
        await conn.execute(CREATE_CAMPAIGNS)
        print("  OK — campaigns table created (or already exists).")

        print("Adding campaign_id column to campaign_results...")
        await conn.execute(ALTER_CAMPAIGN_RESULTS)
        print("  OK — campaign_id column added (or already exists).")

    await close_pool()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run())
