"""
Migration: add pipeline_route column to campaign_results.

Tracks which orchestrator route processed each customer:
  STANDARD      — PRIME / NEAR-PRIME / SUBPRIME eligible (full pipeline)
  PREMIUM_FAST  — SUPER-PRIME (no self-correction loop)
  CONDITIONAL   — SUBPRIME ineligible (conditional improvement offer)
  EDUCATIONAL   — DEEP-SUBPRIME (financial education plan, no credit offer)

Run once:
  python scripts/migrate_add_pipeline_route.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db.connection import get_pool, close_pool


async def migrate() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:

        # Add column only if it does not exist
        await conn.execute("""
            ALTER TABLE campaign_results
            ADD COLUMN IF NOT EXISTS pipeline_route VARCHAR(20) NOT NULL DEFAULT 'STANDARD'
        """)
        print("[OK] campaign_results.pipeline_route column added (or already exists)")

        # Back-fill existing rows based on segment + eligible_for_credit
        result = await conn.execute("""
            UPDATE campaign_results
            SET pipeline_route = CASE
                WHEN segment = 'DEEP-SUBPRIME'                              THEN 'EDUCATIONAL'
                WHEN segment = 'SUPER-PRIME'                                THEN 'PREMIUM_FAST'
                WHEN segment = 'SUBPRIME' AND eligible_for_credit = FALSE   THEN 'CONDITIONAL'
                ELSE 'STANDARD'
            END
            WHERE pipeline_route = 'STANDARD'
        """)
        print(f"[OK] Back-filled existing rows: {result}")

    await close_pool()
    print("[OK] Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
