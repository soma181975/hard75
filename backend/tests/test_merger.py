"""Tests for the merger module."""

import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from src.agent.merger import Merger
from src.agent.extractor import ExtractionResult, ExtractedDay, ExtractedWorkout


class TestMerger:
    """Tests for the Merger class."""

    @pytest.fixture
    def merger(self):
        """Create a merger instance."""
        return Merger()

    @pytest.fixture
    def extraction_result(self):
        """Create a sample extraction result."""
        return ExtractionResult(
            day=ExtractedDay(
                day_number=5,
                date=date.today(),
                workout1_done=True,
                workout2_done=True,
                diet_done=True,
                water_done=True,
                reading_done=True,
                photo_done=True,
                steps=10000,
                water_oz=128,
                reading_minutes=30,
                raw_notes="Day 5 complete!",
            ),
            workouts=[
                ExtractedWorkout(
                    workout_number=1,
                    workout_type="strength",
                    duration_minutes=45,
                    is_outdoor=False,
                    location="gym",
                    exercises=[
                        {
                            "name": "Bench Press",
                            "sets": [
                                {"set_number": 1, "weight_lbs": 135, "reps": 10},
                                {"set_number": 2, "weight_lbs": 155, "reps": 8},
                            ],
                        }
                    ],
                ),
                ExtractedWorkout(
                    workout_number=2,
                    workout_type="cardio",
                    duration_minutes=45,
                    is_outdoor=True,
                    location="park",
                    exercises=[],
                ),
            ],
            confidence=0.9,
            raw_response="{}",
        )

    @pytest.mark.asyncio
    async def test_merge_no_start_date(self, merger, extraction_result):
        """Test merge fails gracefully when user has no start date."""
        with patch("src.agent.merger.db") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value={"start_date": None})

            result = await merger.merge(
                user_id=1,
                extraction=extraction_result,
            )

            assert result["day_created"] is False
            assert result["workouts_created"] == 0

    @pytest.mark.asyncio
    async def test_merge_invalid_day_number(self, merger):
        """Test merge rejects invalid day numbers."""
        extraction = ExtractionResult(
            day=ExtractedDay(day_number=100),  # Invalid: > 75
            workouts=[],
            confidence=0.5,
            raw_response="{}",
        )

        with patch("src.agent.merger.db") as mock_db:
            mock_db.fetchrow = AsyncMock(return_value={"start_date": date.today()})

            result = await merger.merge(user_id=1, extraction=extraction)

            assert result["day_created"] is False

    @pytest.mark.asyncio
    async def test_merge_calculates_day_from_date(self, merger):
        """Test that day number is calculated from date."""
        start_date = date.today() - timedelta(days=4)
        check_date = date.today()  # Should be day 5

        extraction = ExtractionResult(
            day=ExtractedDay(
                day_number=None,
                date=check_date,
                workout1_done=True,
            ),
            workouts=[],
            confidence=0.8,
            raw_response="{}",
        )

        with patch("src.agent.merger.db") as mock_db:
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    {"start_date": start_date},  # User lookup
                    {"id": 1},  # Day upsert
                ]
            )

            result = await merger.merge(user_id=1, extraction=extraction)

            # Verify the day was created
            assert mock_db.fetchrow.call_count == 2

    @pytest.mark.asyncio
    async def test_merge_full_extraction(self, merger, extraction_result):
        """Test merging a full extraction result."""
        start_date = date.today() - timedelta(days=4)

        with patch("src.agent.merger.db") as mock_db:
            mock_db.fetchrow = AsyncMock(
                side_effect=[
                    {"start_date": start_date},  # User lookup
                    {"id": 1},  # Day upsert
                    {"id": 1},  # Workout 1 created
                    {"id": 2},  # Workout 2 created
                ]
            )
            mock_db.execute = AsyncMock()

            result = await merger.merge(
                user_id=1,
                extraction=extraction_result,
                photo_urls=["http://example.com/photo.jpg"],
            )

            assert result["day_created"] is True
            assert result["workouts_created"] == 2
            assert result["sets_created"] == 2  # 2 sets from first workout


class TestMergerSetCreation:
    """Tests for workout set creation."""

    @pytest.fixture
    def merger(self):
        return Merger()

    @pytest.mark.asyncio
    async def test_merge_sets_creates_records(self, merger):
        """Test that sets are properly created."""
        workout = ExtractedWorkout(
            workout_number=1,
            workout_type="strength",
            exercises=[
                {
                    "name": "Squat",
                    "sets": [
                        {"set_number": 1, "weight_lbs": 225, "reps": 5},
                        {"set_number": 2, "weight_lbs": 245, "reps": 4},
                        {"set_number": 3, "weight_lbs": 265, "reps": 3},
                    ],
                },
                {
                    "name": "Leg Press",
                    "sets": [
                        {"set_number": 1, "weight_lbs": 400, "reps": 10},
                    ],
                },
            ],
        )

        with patch("src.agent.merger.db") as mock_db:
            mock_db.execute = AsyncMock()

            sets_created = await merger._merge_sets(session_id=1, workout=workout)

            assert sets_created == 4
            assert mock_db.execute.call_count == 4
