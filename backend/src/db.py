"""Database client using asyncpg for async PostgreSQL operations."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import asyncpg

from src.config import get_settings


class Database:
    """Async PostgreSQL database client."""

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create connection pool."""
        settings = get_settings()
        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
        )

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool."""
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a connection from the pool."""
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get a connection with a transaction."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and return all rows."""
        async with self.connection() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        """Execute a query and return a single row."""
        async with self.connection() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single value."""
        async with self.connection() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query and return the status."""
        async with self.connection() as conn:
            return await conn.execute(query, *args)

    async def executemany(self, query: str, args: list[tuple]) -> None:
        """Execute a query with multiple sets of arguments."""
        async with self.connection() as conn:
            await conn.executemany(query, args)


# Global database instance
db = Database()


async def get_db() -> Database:
    """Dependency for getting database instance."""
    return db
