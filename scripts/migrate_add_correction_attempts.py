"""
Migration: add correction_attempts column to campaign_results.

Stores how many times the campaign was regenerated after a compliance rejection.
Default 0 (no corrections).

Run once:
  python scripts/migrate_add_correction_attempts.py
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
            ADD COLUMN IF NOT EXISTS correction_attempts INT DEFAULT 0
        """)
        print("[OK] campaign_results.correction_attempts column added (or already exists)")

    await close_pool()
    print("[OK] Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
