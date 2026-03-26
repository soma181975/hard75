"""API endpoints for workout sessions and sets."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import CurrentUser
from src.db import db

router = APIRouter()


class WorkoutSetResponse(BaseModel):
    """Response model for a workout set."""

    id: int
    exercise_name: str
    set_number: Optional[int] = None
    weight_lbs: Optional[float] = None
    reps: Optional[int] = None
    duration_seconds: Optional[int] = None
    distance_miles: Optional[float] = None
    rpe: Optional[float] = None
    notes: Optional[str] = None


class WorkoutSessionResponse(BaseModel):
    """Response model for a workout session."""

    id: int
    date: date
    workout_number: Optional[int] = None
    workout_type: Optional[str] = None
    duration_minutes: Optional[int] = None
    location: Optional[str] = None
    is_outdoor: bool
    notes: Optional[str] = None
    screenshot_url: Optional[str] = None
    sets: list[WorkoutSetResponse] = []


class VolumeDataPoint(BaseModel):
    """Data point for volume over time."""

    date: date
    total_volume: float
    session_count: int


class ExerciseProgressionPoint(BaseModel):
    """Data point for exercise progression."""

    date: date
    max_weight: float
    max_reps: int
    estimated_1rm: float


@router.get("", response_model=list[WorkoutSessionResponse])
async def list_workouts(
    current_user: CurrentUser,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    workout_type: Optional[str] = None,
):
    """List workout sessions for the current user."""
    if workout_type:
        rows = await db.fetch(
            """
            SELECT * FROM workout_sessions
            WHERE user_id = $1 AND workout_type = $2
            ORDER BY date DESC, workout_number
            LIMIT $3 OFFSET $4
            """,
            current_user.id,
            workout_type,
            limit,
            offset,
        )
    else:
        rows = await db.fetch(
            """
            SELECT * FROM workout_sessions
            WHERE user_id = $1
            ORDER BY date DESC, workout_number
            LIMIT $2 OFFSET $3
            """,
            current_user.id,
            limit,
            offset,
        )

    sessions = []
    for row in rows:
        session = WorkoutSessionResponse(**dict(row), sets=[])

        # Get sets for this session
        sets = await db.fetch(
            """
            SELECT * FROM workout_sets
            WHERE session_id = $1
            ORDER BY exercise_name, set_number
            """,
            row["id"],
        )
        session.sets = [WorkoutSetResponse(**dict(s)) for s in sets]
        sessions.append(session)

    return sessions


@router.get("/volume", response_model=list[VolumeDataPoint])
async def get_volume_over_time(
    current_user: CurrentUser,
    days: int = Query(default=30, le=90),
):
    """Get volume (weight * reps) over time for charts."""
    rows = await db.fetch(
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
        current_user.id,
        days,
    )

    return [
        VolumeDataPoint(
            date=row["date"],
            total_volume=float(row["total_volume"] or 0),
            session_count=row["session_count"],
        )
        for row in rows
    ]


@router.get("/exercises", response_model=list[str])
async def list_exercises(current_user: CurrentUser):
    """List all unique exercise names for the current user."""
    rows = await db.fetch(
        """
        SELECT DISTINCT wset.exercise_name
        FROM workout_sets wset
        JOIN workout_sessions ws ON ws.id = wset.session_id
        WHERE ws.user_id = $1
        ORDER BY wset.exercise_name
        """,
        current_user.id,
    )
    return [row["exercise_name"] for row in rows]


@router.get("/exercises/{exercise_name}/progression", response_model=list[ExerciseProgressionPoint])
async def get_exercise_progression(
    current_user: CurrentUser,
    exercise_name: str,
    days: int = Query(default=90, le=365),
):
    """Get progression data for a specific exercise."""
    rows = await db.fetch(
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
        current_user.id,
        exercise_name,
        days,
    )

    result = []
    for row in rows:
        weight = float(row["max_weight"] or 0)
        reps = row["max_reps"] or 0
        # Brzycki formula for estimated 1RM
        estimated_1rm = weight * (36 / (37 - reps)) if reps > 0 and reps < 37 else weight

        result.append(
            ExerciseProgressionPoint(
                date=row["date"],
                max_weight=weight,
                max_reps=reps,
                estimated_1rm=round(estimated_1rm, 1),
            )
        )

    return result


@router.get("/{session_id}", response_model=WorkoutSessionResponse)
async def get_workout(current_user: CurrentUser, session_id: int):
    """Get a specific workout session."""
    row = await db.fetchrow(
        """
        SELECT * FROM workout_sessions
        WHERE id = $1 AND user_id = $2
        """,
        session_id,
        current_user.id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Workout session not found")

    session = WorkoutSessionResponse(**dict(row), sets=[])

    # Get sets
    sets = await db.fetch(
        """
        SELECT * FROM workout_sets
        WHERE session_id = $1
        ORDER BY exercise_name, set_number
        """,
        session_id,
    )
    session.sets = [WorkoutSetResponse(**dict(s)) for s in sets]

    return session
