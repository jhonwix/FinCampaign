"""
In-memory lookup cache for parametric values.

Loaded once at FastAPI startup via load_lookup_cache().
Accessors are synchronous — safe to call from asyncpg executor threads.
"""
from __future__ import annotations

from db.connection import get_pool

# Module-level singleton: { category: [value, ...] }
# Written once at startup; read-only after that — no locking needed.
_cache: dict[str, list[str]] = {}


async def load_lookup_cache() -> None:
    """Load all active lookup values from PostgreSQL into the in-memory cache."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT category, value
            FROM   lookup_values
            WHERE  is_active = TRUE
            ORDER  BY category, sort_order, value
            """
        )
    new_cache: dict[str, list[str]] = {}
    for row in rows:
        new_cache.setdefault(row["category"], []).append(row["value"])

    _cache.clear()
    _cache.update(new_cache)


def get_valid_values(category: str) -> list[str]:
    """Return ordered list of valid values for a category. Sync — thread-safe."""
    return list(_cache.get(category, []))


def is_valid_value(category: str, value: str) -> bool:
    """Return True if value belongs to category. Sync — thread-safe."""
    return value in _cache.get(category, [])


def get_all_lookups() -> dict[str, list[str]]:
    """Return a shallow copy of the full cache — used by /api/lookups endpoint."""
    return {k: list(v) for k, v in _cache.items()}
