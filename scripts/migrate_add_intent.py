"""
Migration: add existing_products to customers + campaign_intent to campaigns.
Safe to run multiple times (uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db.connection import get_pool, close_pool


async def migrate():
    pool = await get_pool()
    async with pool.acquire() as conn:

        # 1. customers.existing_products
        await conn.execute("""
            ALTER TABLE customers
            ADD COLUMN IF NOT EXISTS existing_products TEXT NOT NULL DEFAULT ''
        """)
        print("[OK] customers.existing_products")

        # 2. campaigns.campaign_intent
        await conn.execute("""
            ALTER TABLE campaigns
            ADD COLUMN IF NOT EXISTS campaign_intent VARCHAR(10) NOT NULL DEFAULT 'NEW'
        """)
        print("[OK] campaigns.campaign_intent")

    await close_pool()
    print("Migracion completada.")


if __name__ == "__main__":
    asyncio.run(migrate())
