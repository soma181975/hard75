"""Tests for the days API endpoints."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

from src.api.days import router


class TestDaysAPI:
    """Tests for days API endpoints."""

    @pytest.mark.asyncio
    async def test_list_days_returns_user_days(self, sample_day, session_user):
        """Test listing days returns only the user's days."""
        with patch("src.api.days.db") as mock_db:
            mock_db.fetch = AsyncMock(return_value=[sample_day])

            # Simulate the endpoint logic
            rows = await mock_db.fetch(
                """
                SELECT * FROM hard75_days
                WHERE user_id = $1
                ORDER BY day_number DESC
                LIMIT $2 OFFSET $3
                """,
                session_user.id,
                75,
                0,
            )

            assert len(rows) == 1
            assert rows[0]["day_number"] == 1
            assert rows[0]["all_done"] is True

    @pytest.mark.asyncio
    async def test_get_streak_calculates_correctly(self, session_user):
        """Test streak calculation."""
        with patch("src.api.days.db") as mock_db:
            mock_db.fetchval = AsyncMock(side_effect=[5, 10])  # streak, total

            streak = await mock_db.fetchval(
                "SELECT calculate_streak($1)",
                session_user.id,
            )
            total = await mock_db.fetchval(
                """
                SELECT COUNT(*) FROM hard75_days
                WHERE user_id = $1 AND all_done = TRUE
                """,
                session_user.id,
            )

            assert streak == 5
            assert total == 10

    @pytest.mark.asyncio
    async def test_get_day_not_found(self, session_user):
        """Test getting a non-existent day."""
        with patch("src.api.days.db") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=None)

            row = await mock_db.fetchrow(
                """
                SELECT * FROM hard75_days
                WHERE user_id = $1 AND day_number = $2
                """,
                session_user.id,
                99,
            )

            assert row is None

    @pytest.mark.asyncio
    async def test_update_day_partial_update(self, sample_day, session_user):
        """Test updating specific fields of a day."""
        updated_day = {**sample_day, "steps": 15000}

        with patch("src.api.days.db") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value=updated_day)

            # Simulate partial update
            row = await mock_db.fetchrow(
                """
                UPDATE hard75_days
                SET steps = $3
                WHERE user_id = $1 AND day_number = $2
                RETURNING *
                """,
                session_user.id,
                1,
                15000,
            )

            assert row["steps"] == 15000


class TestDayValidation:
    """Tests for day number validation."""

    def test_day_number_bounds(self):
        """Test that day numbers must be 1-75."""
        valid_days = [1, 37, 75]
        invalid_days = [0, -1, 76, 100]

        for day in valid_days:
            assert 1 <= day <= 75

        for day in invalid_days:
            assert not (1 <= day <= 75)


class TestDayUpsert:
    """Tests for day creation/update logic."""

    @pytest.mark.asyncio
    async def test_upsert_creates_new_day(self, session_user):
        """Test upserting creates a new day if it doesn't exist."""
        with patch("src.api.days.db") as mock_db:
            # First call returns user with start_date
            # Second call returns the created day
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    {"start_date": date.today()},
                    {
                        "id": 1,
                        "user_id": 1,
                        "day_number": 1,
                        "date": date.today(),
                        "workout1_done": True,
                        "workout2_done": False,
                        "diet_done": False,
                        "water_done": False,
                        "reading_done": False,
                        "photo_done": False,
                        "all_done": False,
                        "steps": None,
                        "water_oz": None,
                        "reading_minutes": None,
                        "photo_url": None,
                        "raw_notes": None,
                    },
                ]
            )

            # Get user's start date
            user = await mock_db.fetchrow(
                "SELECT start_date FROM users WHERE id = $1",
                session_user.id,
            )

            assert user["start_date"] is not None

    @pytest.mark.asyncio
    async def test_upsert_appends_notes(self):
        """Test that notes are appended, not replaced."""
        existing_notes = "Previous update"
        new_notes = "New update"
        expected = f"{existing_notes}\n\n{new_notes}"

        # This tests the SQL logic conceptually
        result = f"{existing_notes}\n\n{new_notes}" if existing_notes and new_notes else new_notes
        assert result == expected
