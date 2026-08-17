"""
PostgreSQL async connection pool manager for CrawlRAG.

Uses asyncpg for non-blocking database I/O that integrates cleanly
with FastAPI's async request lifecycle.

Usage
-----
    # In FastAPI lifespan:
    await db_pool.connect()
    ...
    await db_pool.disconnect()

    # In repository / service code:
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM cars")
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg

from app.core.config import settings
from app.core.logging import get_module_logger

logger = get_module_logger(__name__)


class DatabaseConnectionPool:
    """Manages a singleton asyncpg connection pool for the application.

    The pool is created once on startup and closed on shutdown.
    All database access goes through ``acquire()``, which borrows a
    connection from the pool and returns it automatically on exit.
    """

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Create the asyncpg connection pool.

        Called once during FastAPI startup.  Subsequent calls are no-ops
        if the pool is already open.
        """
        if self._pool is not None:
            logger.debug("PostgreSQL pool already open — skipping re-connect.")
            return

        dsn = settings.POSTGRES_DSN
        logger.info(
            "Opening PostgreSQL connection pool (min=%d, max=%d) to '%s' …",
            settings.POSTGRES_POOL_MIN_SIZE,
            settings.POSTGRES_POOL_MAX_SIZE,
            settings.POSTGRES_DB,
        )

        try:
            self._pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=settings.POSTGRES_POOL_MIN_SIZE,
                max_size=settings.POSTGRES_POOL_MAX_SIZE,
                command_timeout=settings.POSTGRES_COMMAND_TIMEOUT,
            )
            logger.info("PostgreSQL connection pool opened successfully.")
        except Exception as exc:
            logger.error(
                "Failed to open PostgreSQL connection pool: %s",
                exc,
                exc_info=True,
            )
            self._pool = None
            raise

    async def disconnect(self) -> None:
        """Close the connection pool gracefully.

        Called once during FastAPI shutdown.  Safe to call even if the
        pool was never opened (e.g. because the DB was unavailable).
        """
        if self._pool is None:
            return

        logger.info("Closing PostgreSQL connection pool …")
        await self._pool.close()
        self._pool = None
        logger.info("PostgreSQL connection pool closed.")

    # ------------------------------------------------------------------
    # Connection acquisition
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Borrow a connection from the pool as an async context manager.

        Auto-connects if the pool has not been explicitly opened yet.
        """
        if self._pool is None:
            logger.info("PostgreSQL pool not open yet — auto-connecting...")
            await self.connect()

        if self._pool is None:
            raise RuntimeError("PostgreSQL pool could not be initialized.")

        async with self._pool.acquire() as connection:
            yield connection


    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        """Return True if the pool is open and has at least one connection."""
        return self._pool is not None

    def get_pool_stats(self) -> dict:
        """Return current pool statistics for health-check endpoints."""
        if self._pool is None:
            return {"status": "disconnected"}
        return {
            "status": "connected",
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
            "size": self._pool.get_size(),
            "idle_connections": self._pool.get_idle_size(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere.
# ---------------------------------------------------------------------------
db_pool = DatabaseConnectionPool()
