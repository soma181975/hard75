"""Bootstrap script to ensure admin user exists on startup."""

import asyncio
import logging

from src.config import get_settings
from src.db import db

logger = logging.getLogger(__name__)


async def ensure_admin_exists() -> None:
    """Ensure the admin user exists in the database."""
    settings = get_settings()

    # Check if admin exists
    existing = await db.fetchrow(
        "SELECT id FROM users WHERE email = $1",
        settings.admin_email,
    )

    if existing:
        logger.info(f"Admin user already exists: {settings.admin_email}")
        return

    # Create admin user
    await db.execute(
        """
        INSERT INTO users (email, name, role, start_date)
        VALUES ($1, $2, 'admin', CURRENT_DATE)
        """,
        settings.admin_email,
        settings.admin_name,
    )
    logger.info(f"Created admin user: {settings.admin_email}")


async def bootstrap() -> None:
    """Run all bootstrap tasks."""
    await db.connect()
    try:
        await ensure_admin_exists()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(bootstrap())
