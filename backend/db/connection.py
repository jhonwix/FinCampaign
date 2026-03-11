"""
PostgreSQL connection pool using asyncpg.
Pool is created once on startup and shared across all requests.
"""

import asyncpg

from config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return the shared connection pool, creating it if necessary."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            ssl=None,  # SSL disabled for local development
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    """Close the connection pool on application shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
