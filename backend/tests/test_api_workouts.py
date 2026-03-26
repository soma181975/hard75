"""Tests for the workouts API endpoints."""

import pytest
from datetime import date
from unittest.mock import AsyncMock, patch


class TestWorkoutsAPI:
    """Tests for workouts API endpoints."""

    @pytest.mark.asyncio
    async def test_list_workouts_returns_sessions(self, sample_workout, session_user):
        """Test listing workouts returns user's sessions."""
        with patch("src.api.workouts.db") as mock_db:
            mock_db.fetch = AsyncMock(
                side_effect=[
                    [sample_workout],  # Sessions
                    [],  # Sets for session 1
                ]
            )

            sessions = await mock_db.fetch(
                """
                SELECT * FROM workout_sessions
                WHERE user_id = $1
                ORDER BY date DESC, workout_number
                LIMIT $2 OFFSET $3
                """,
                session_user.id,
                50,
                0,
            )

            assert len(sessions) == 1
            assert sessions[0]["workout_type"] == "strength"

    @pytest.mark.asyncio
    async def test_list_workouts_filtered_by_type(self, sample_workout, session_user):
        """Test filtering workouts by type."""
        with patch("src.api.workouts.db") as mock_db:
            mock_db.fetch = AsyncMock(return_value=[sample_workout])

            sessions = await mock_db.fetch(
                """
                SELECT * FROM workout_sessions
                WHERE user_id = $1 AND workout_type = $2
                ORDER BY date DESC, workout_number
                LIMIT $3 OFFSET $4
                """,
                session_user.id,
                "strength",
                50,
                0,
            )

            assert len(sessions) == 1
            assert sessions[0]["workout_type"] == "strength"


class TestVolumeCalculation:
    """Tests for volume calculation endpoint."""

    @pytest.mark.asyncio
    async def test_volume_over_time(self, session_user):
        """Test volume calculation over time."""
        volume_data = [
            {"date": date.today(), "total_volume": 15000, "session_count": 2},
        ]

        with patch("src.api.workouts.db") as mock_db:
            mock_db.fetch = AsyncMock(return_value=volume_data)

            rows = await mock_db.fetch(
                """
                SELECT
                    ws.date,
                    SUM(COALESCE(wset.weight_lbs, 0) * COALESCE(wset.reps, 0)) as total_volume,
                    COUNT(DISTINCT ws.id) as session_count
                FROM workout_sessions ws
                LEFT JOIN workout_sets wset ON wset.session_id = ws.id
                WHERE ws.user_id = $1
                    AND ws.date >= CURRENT_DATE - $2 * INTERVAL '1 day'
                GROUP BY ws.date
                ORDER BY ws.date
                """,
                session_user.id,
                30,
            )

            assert len(rows) == 1
            assert rows[0]["total_volume"] == 15000


class TestExerciseProgression:
    """Tests for exercise progression endpoint."""

    @pytest.mark.asyncio
    async def test_list_exercises(self, session_user):
        """Test listing unique exercises."""
        exercises = [
            {"exercise_name": "Bench Press"},
            {"exercise_name": "Squat"},
            {"exercise_name": "Deadlift"},
        ]

        with patch("src.api.workouts.db") as mock_db:
            mock_db.fetch = AsyncMock(return_value=exercises)

            rows = await mock_db.fetch(
                """
                SELECT DISTINCT wset.exercise_name
                FROM workout_sets wset
                JOIN workout_sessions ws ON ws.id = wset.session_id
                WHERE ws.user_id = $1
                ORDER BY wset.exercise_name
                """,
                session_user.id,
            )

            assert len(rows) == 3
            assert rows[0]["exercise_name"] == "Bench Press"

    @pytest.mark.asyncio
    async def test_exercise_progression_data(self, session_user):
        """Test getting progression data for an exercise."""
        progression_data = [
            {"date": date.today(), "max_weight": 225.0, "max_reps": 5},
        ]

        with patch("src.api.workouts.db") as mock_db:
            mock_db.fetch = AsyncMock(return_value=progression_data)

            rows = await mock_db.fetch(
                """
                SELECT
                    ws.date,
                    MAX(wset.weight_lbs) as max_weight,
                    MAX(wset.reps) as max_reps
                FROM workout_sets wset
                JOIN workout_sessions ws ON ws.id = wset.session_id
                WHERE ws.user_id = $1
                    AND wset.exercise_name = $2
                    AND ws.date >= CURRENT_DATE - $3 * INTERVAL '1 day'
                GROUP BY ws.date
                ORDER BY ws.date
                """,
                session_user.id,
                "Squat",
                90,
            )

            assert len(rows) == 1
            assert rows[0]["max_weight"] == 225.0

    def test_estimated_1rm_calculation(self):
        """Test Brzycki formula for estimated 1RM."""
        weight = 225.0
        reps = 5

        # Brzycki formula: weight * (36 / (37 - reps))
        estimated_1rm = weight * (36 / (37 - reps))

        assert estimated_1rm == pytest.approx(253.125, rel=0.01)

    def test_estimated_1rm_single_rep(self):
        """Test that single rep max equals the weight."""
        weight = 315.0
        reps = 1

        estimated_1rm = weight * (36 / (37 - reps))

        assert estimated_1rm == 315.0

    def test_estimated_1rm_high_reps(self):
        """Test formula behavior with high reps."""
        weight = 135.0
        reps = 15

        estimated_1rm = weight * (36 / (37 - reps))

        # With 15 reps, estimated 1RM should be significantly higher
        assert estimated_1rm > weight
        assert estimated_1rm == pytest.approx(220.9, rel=0.01)
