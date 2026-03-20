#!/usr/bin/env python3
"""
Create PostgreSQL tables and seed with test customers.

Usage:
    python scripts/setup_db.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import asyncpg
from config import settings

CREATE_CUSTOMERS = """
CREATE TABLE IF NOT EXISTS customers (
    id                  SERIAL PRIMARY KEY,
    id_number           VARCHAR(20)     UNIQUE,
    name                VARCHAR(100)    NOT NULL,
    age                 INTEGER         NOT NULL CHECK (age BETWEEN 18 AND 100),
    monthly_income      NUMERIC(12, 2)  NOT NULL CHECK (monthly_income > 0),
    monthly_debt        NUMERIC(12, 2)  NOT NULL DEFAULT 0 CHECK (monthly_debt >= 0),
    credit_score        INTEGER         NOT NULL CHECK (credit_score BETWEEN 300 AND 850),
    late_payments       INTEGER         NOT NULL DEFAULT 0 CHECK (late_payments >= 0),
    credit_utilization  NUMERIC(5, 2)   NOT NULL DEFAULT 0 CHECK (credit_utilization BETWEEN 0 AND 100),
    products_of_interest TEXT           NOT NULL,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);
"""

CREATE_CAMPAIGN_RESULTS = """
CREATE TABLE IF NOT EXISTS campaign_results (
    id                      SERIAL PRIMARY KEY,
    customer_id             INTEGER         NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    request_id              VARCHAR(50)     NOT NULL UNIQUE,
    segment                 VARCHAR(30),
    risk_level              VARCHAR(20),
    dti                     NUMERIC(6, 2),
    eligible_for_credit     BOOLEAN,
    recommended_products    JSONB,
    product_name            VARCHAR(100),
    campaign_message        TEXT,
    rates                   VARCHAR(100),
    channel                 VARCHAR(50),
    compliance_verdict      VARCHAR(30),
    human_review_required   BOOLEAN,
    warnings                JSONB,
    gcs_path                TEXT,
    processing_ms           INTEGER,
    processed_at            TIMESTAMP       NOT NULL DEFAULT NOW()
);
"""

SEED_CUSTOMERS = [
    # id_number, name, age, monthly_income, monthly_debt, credit_score, late_payments, credit_utilization, products_of_interest
    # SUPER-PRIME
    ("1000000001", "Andrea Torres",      28, 7200.00,  900.00, 760, 0, 15.0, "auto loan"),
    ("1000000002", "Sofia Ramirez",      35, 9500.00,  800.00, 810, 0, 10.0, "mortgage refinance"),
    # PRIME
    ("1000000003", "Laura Gomez",        31, 5500.00,  800.00, 720, 0, 22.0, "credit card"),
    ("1000000004", "Roberto Vargas",     42, 6800.00, 1500.00, 710, 1, 28.0, "personal loan"),
    # NEAR-PRIME
    ("1000000005", "Carlos Mendoza",     34, 4500.00, 1200.00, 680, 2, 45.0, "personal loan or credit card"),
    ("1000000006", "Diana Morales",      29, 3800.00,  950.00, 665, 2, 38.0, "credit card"),
    ("1000000007", "Javier Castillo",    38, 5200.00, 1800.00, 655, 3, 49.0, "personal loan"),
    # SUBPRIME
    ("1000000008", "Pedro Ruiz",         52, 3200.00, 1400.00, 630, 4, 60.0, "personal loan"),
    ("1000000009", "Lucia Herrera",      45, 2900.00, 1300.00, 615, 5, 68.0, "secured credit card"),
    # DEEP-SUBPRIME
    ("1000000010", "Miguel Angel Reyes", 45, 2800.00, 1900.00, 580, 6, 82.0, "personal loan"),
]


async def main():
    print("=" * 60)
    print("FinCampaign — PostgreSQL Setup")
    print("=" * 60)
    print(f"Host:     {settings.postgres_host}:{settings.postgres_port}")
    print(f"Database: {settings.postgres_db}")
    print(f"User:     {settings.postgres_user}")
    print()

    conn = await asyncpg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
    )

    try:
        # Create tables
        await conn.execute(CREATE_CUSTOMERS)
        print("Table 'customers' ready.")

        await conn.execute(CREATE_CAMPAIGN_RESULTS)
        print("Table 'campaign_results' ready.")

        # Check existing rows
        existing = await conn.fetchval("SELECT COUNT(*) FROM customers")
        if existing > 0:
            print(f"\n{existing} customers already exist — skipping seed.")
        else:
            # Insert seed data
            await conn.executemany(
                """
                INSERT INTO customers
                    (id_number, name, age, monthly_income, monthly_debt, credit_score,
                     late_payments, credit_utilization, products_of_interest)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                SEED_CUSTOMERS,
            )
            count = await conn.fetchval("SELECT COUNT(*) FROM customers")
            print(f"\n{count} test customers inserted.")

        # Show summary
        print()
        rows = await conn.fetch(
            "SELECT id, name, credit_score FROM customers ORDER BY credit_score DESC"
        )
        print(f"{'ID':<4} {'Name':<25} {'Score':<6}")
        print("-" * 37)
        for r in rows:
            print(f"{r['id']:<4} {r['name']:<25} {r['credit_score']:<6}")

        print()
        print("Setup complete.")
        print("New endpoint available: POST /api/analyze/db/{customer_id}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
