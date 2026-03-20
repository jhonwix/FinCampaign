#!/usr/bin/env python3
"""
Migration: add id_number (cédula) column to customers table.

Usage:
    python scripts/migrate_add_id_number.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import asyncpg
from config import settings


async def main():
    print("Migration: add id_number to customers")
    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )
    try:
        await conn.execute(
            """
            ALTER TABLE customers
            ADD COLUMN IF NOT EXISTS id_number VARCHAR(20) DEFAULT NULL;
            """
        )
        print("  Column id_number added (or already existed).")

        await conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_customers_id_number
                ON customers(id_number)
                WHERE id_number IS NOT NULL;
            """
        )
        print("  Unique partial index on id_number created (or already existed).")
        print("Migration complete.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
