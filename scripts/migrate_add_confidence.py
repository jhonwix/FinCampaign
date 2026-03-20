"""
Migration: add pipeline_confidence column to campaign_results.

Stores the aggregated confidence score (0.0–1.0) computed by the orchestrator.
Values below 0.65 trigger automatic human review escalation.

Run once:
  python scripts/migrate_add_confidence.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db.connection import get_pool, close_pool


async def migrate() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:

        await conn.execute("""
            ALTER TABLE campaign_results
            ADD COLUMN IF NOT EXISTS pipeline_confidence FLOAT DEFAULT NULL
        """)
        print("[OK] campaign_results.pipeline_confidence column added (or already exists)")

    await close_pool()
    print("[OK] Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
