"""
Migration: create customer_interactions and customer_memory tables.

customer_interactions — permanent interaction log (one row per pipeline run per customer)
customer_memory       — aggregated memory card per customer (upserted after each run)

Run once:
  python scripts/migrate_add_memory.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db.connection import get_pool, close_pool


async def migrate() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:

        # ── customer_interactions ────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_interactions (
                id              SERIAL PRIMARY KEY,
                customer_id     INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
                campaign_id     INTEGER REFERENCES campaigns(id) ON DELETE SET NULL,
                request_id      VARCHAR(50),
                pipeline_route  VARCHAR(20),
                segment         VARCHAR(30),
                eligible        BOOLEAN,
                dti             NUMERIC(6,2),
                product_offered VARCHAR(100),
                verdict         VARCHAR(30),
                channel         VARCHAR(50),
                confidence      NUMERIC(4,2),
                processed_at    TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        print("[OK] customer_interactions table created (or already exists)")

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_ci_customer_date
                ON customer_interactions(customer_id, processed_at DESC)
        """)
        print("[OK] idx_ci_customer_date index created (or already exists)")

        # ── customer_memory ──────────────────────────────────────────────────────
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS customer_memory (
                customer_id         INTEGER PRIMARY KEY REFERENCES customers(id) ON DELETE CASCADE,
                total_interactions  INTEGER NOT NULL DEFAULT 0,
                first_seen_at       TIMESTAMP,
                last_seen_at        TIMESTAMP,
                last_segment        VARCHAR(30),
                last_verdict        VARCHAR(30),
                products_offered    JSONB DEFAULT '[]',
                verdict_counts      JSONB DEFAULT '{}',
                avg_dti             NUMERIC(6,2),
                dti_trend           VARCHAR(20),
                memory_card         TEXT,
                updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        print("[OK] customer_memory table created (or already exists)")

    await close_pool()
    print("[OK] Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
