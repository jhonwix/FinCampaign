"""
Migration: add human review columns to campaign_results.

Adds review_status, review_note, reviewed_at to support analyst
approval/rejection of REVIEW-verdict rows.

Run once:
  python scripts/migrate_add_review.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db.connection import get_pool, close_pool


async def migrate() -> None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            ALTER TABLE campaign_results
            ADD COLUMN IF NOT EXISTS review_status VARCHAR(20) DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS review_note   TEXT        DEFAULT NULL,
            ADD COLUMN IF NOT EXISTS reviewed_at   TIMESTAMP   DEFAULT NULL
        """)
        print("[OK] campaign_results review columns added (or already exist)")

    await close_pool()
    print("[OK] Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
