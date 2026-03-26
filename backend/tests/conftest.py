"""Pytest configuration and fixtures."""

import asyncio
from datetime import date
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from src.main import app
from src.db import db, Database
from src.auth.session import SessionUser


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_db():
    """Create a mock database for testing."""
    mock = AsyncMock(spec=Database)
    mock.fetch = AsyncMock(return_value=[])
    mock.fetchrow = AsyncMock(return_value=None)
    mock.fetchval = AsyncMock(return_value=None)
    mock.execute = AsyncMock(return_value="OK")
    return mock


@pytest.fixture
def test_user() -> dict:
    """Create a test user dict."""
    return {
        "id": 1,
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
        "avatar_url": None,
        "start_date": date.today(),
    }


@pytest.fixture
def admin_user() -> dict:
    """Create an admin user dict."""
    return {
        "id": 2,
        "email": "admin@example.com",
        "name": "Admin User",
        "role": "admin",
        "avatar_url": None,
        "start_date": date.today(),
    }


@pytest.fixture
def session_user(test_user: dict) -> SessionUser:
    """Create a session user from test user."""
    return SessionUser(
        id=test_user["id"],
        email=test_user["email"],
        name=test_user["name"],
        role=test_user["role"],
        avatar_url=test_user["avatar_url"],
    )


@pytest.fixture
def admin_session_user(admin_user: dict) -> SessionUser:
    """Create an admin session user."""
    return SessionUser(
        id=admin_user["id"],
        email=admin_user["email"],
        name=admin_user["name"],
        role=admin_user["role"],
        avatar_url=admin_user["avatar_url"],
    )


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_day() -> dict:
    """Create a sample Hard 75 day."""
    return {
        "id": 1,
        "user_id": 1,
        "day_number": 1,
        "date": date.today(),
        "workout1_done": True,
        "workout2_done": True,
        "diet_done": True,
        "water_done": True,
        "reading_done": True,
        "photo_done": True,
        "all_done": True,
        "steps": 10000,
        "water_oz": 128,
        "reading_minutes": 30,
        "photo_url": None,
        "raw_notes": "Test day",
    }


@pytest.fixture
def sample_workout() -> dict:
    """Create a sample workout session."""
    return {
        "id": 1,
        "user_id": 1,
        "hard75_day_id": 1,
        "date": date.today(),
        "workout_number": 1,
        "workout_type": "strength",
        "duration_minutes": 45,
        "location": "gym",
        "is_outdoor": False,
        "notes": "Good workout",
        "screenshot_url": None,
    }


@pytest.fixture
def sample_email_body() -> str:
    """Sample email body for extraction testing."""
    return """
    Day 5 update!

    Workout 1: Morning gym session - 45 minutes
    - Bench Press: 135x10, 155x8, 175x6
    - Squat: 185x10, 205x8, 225x6
    - Deadlift: 225x8, 275x6, 315x4

    Workout 2: Evening outdoor run - 45 minutes at the park

    Diet: Stayed on track, no cheats
    Water: Finished my gallon
    Reading: 15 pages of Atomic Habits
    Photo: Taken!

    Steps today: 12,543
    """
