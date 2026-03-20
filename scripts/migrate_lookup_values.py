"""
Migration: create and seed the lookup_values parametric table.
Safe to run multiple times — uses IF NOT EXISTS and ON CONFLICT DO NOTHING.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from db.connection import get_pool, close_pool

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS lookup_values (
    id          SERIAL       PRIMARY KEY,
    category    VARCHAR(60)  NOT NULL,
    value       VARCHAR(100) NOT NULL,
    label       VARCHAR(100) NOT NULL,
    sort_order  SMALLINT     NOT NULL DEFAULT 0,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_lookup_category_value UNIQUE (category, value)
);

CREATE INDEX IF NOT EXISTS idx_lookup_category
    ON lookup_values (category)
    WHERE is_active = TRUE;
"""

SEED_SQL = [
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('compliance_overall_verdict', 'APPROVED',               'Aprobado',                  1),
        ('compliance_overall_verdict', 'APPROVED_WITH_WARNINGS', 'Aprobado con advertencias', 2),
        ('compliance_overall_verdict', 'REVIEW',                 'En revision',               3),
        ('compliance_overall_verdict', 'REJECTED',               'Rechazado',                 4)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('compliance_check_result', 'PASS',   'Aprobado',    1),
        ('compliance_check_result', 'REVIEW', 'En revision', 2),
        ('compliance_check_result', 'FAIL',   'Fallido',     3)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('campaign_type', 'HIPOTECARIO', 'Credito Hipotecario', 1),
        ('campaign_type', 'VEHICULOS',   'Credito Vehiculo',    2),
        ('campaign_type', 'CDT',         'CDT',                 3),
        ('campaign_type', 'PERSONAL',    'Credito Personal',    4),
        ('campaign_type', 'TARJETA',     'Tarjeta de Credito',  5)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('campaign_intent', 'NEW',     'Adquisicion', 1),
        ('campaign_intent', 'RENEWAL', 'Renovacion',  2),
        ('campaign_intent', 'CROSS',   'Cross-sell',  3)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('credit_segment', 'SUPER-PRIME',   'Super Prime',   1),
        ('credit_segment', 'PRIME',         'Prime',         2),
        ('credit_segment', 'NEAR-PRIME',    'Near Prime',    3),
        ('credit_segment', 'SUBPRIME',      'Subprime',      4),
        ('credit_segment', 'DEEP-SUBPRIME', 'Deep Subprime', 5)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('campaign_status', 'DRAFT',     'Borrador',       1),
        ('campaign_status', 'RUNNING',   'En ejecucion',   2),
        ('campaign_status', 'COMPLETED', 'Completada',     3)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('campaign_channel', 'Email',    'Email',    1),
        ('campaign_channel', 'SMS',      'SMS',      2),
        ('campaign_channel', 'Push',     'Push',     3),
        ('campaign_channel', 'WhatsApp', 'WhatsApp', 4)
    ON CONFLICT (category, value) DO NOTHING;
    """,
    """
    INSERT INTO lookup_values (category, value, label, sort_order) VALUES
        ('message_tone', 'Amigable',    'Amigable',    1),
        ('message_tone', 'Profesional', 'Profesional', 2),
        ('message_tone', 'Urgente',     'Urgente',     3),
        ('message_tone', 'Premium',     'Premium',     4),
        ('message_tone', 'Empatico',    'Empatico',    5)
    ON CONFLICT (category, value) DO NOTHING;
    """,
]


async def migrate():
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            print("Creating lookup_values table...")
            await conn.execute(CREATE_TABLE)
            print("[OK] Table created.")
            for sql in SEED_SQL:
                await conn.execute(sql)
            print("[OK] Seed data inserted.")

            # Verify counts
            rows = await conn.fetch(
                "SELECT category, COUNT(*) as n FROM lookup_values GROUP BY category ORDER BY category"
            )
            print("\nLookup values by category:")
            for r in rows:
                print(f"  {r['category']}: {r['n']} values")

    await close_pool()
    print("\nMigracion completada.")


if __name__ == "__main__":
    asyncio.run(migrate())
