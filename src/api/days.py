"""API endpoints for Hard 75 days tracking."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import CurrentUser
from src.db import db

router = APIRouter()


class DayResponse(BaseModel):
    """Response model for a Hard 75 day."""

    id: int
    day_number: int
    date: date
    workout1_done: bool
    workout2_done: bool
    diet_done: bool
    water_done: bool
    reading_done: bool
    photo_done: bool
    all_done: bool
    steps: Optional[int] = None
    water_oz: Optional[int] = None
    reading_minutes: Optional[int] = None
    # Nutrition totals
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    fiber_g: Optional[int] = None
    photo_url: Optional[str] = None
    raw_notes: Optional[str] = None


class DayUpdate(BaseModel):
    """Request model for updating a day."""

    workout1_done: Optional[bool] = None
    workout2_done: Optional[bool] = None
    diet_done: Optional[bool] = None
    water_done: Optional[bool] = None
    reading_done: Optional[bool] = None
    photo_done: Optional[bool] = None
    steps: Optional[int] = None
    water_oz: Optional[int] = None
    reading_minutes: Optional[int] = None
    # Nutrition totals
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    fiber_g: Optional[int] = None
    raw_notes: Optional[str] = None


class StreakResponse(BaseModel):
    """Response model for streak info."""

    current_streak: int
    total_completed: int
    days_remaining: int


@router.get("", response_model=list[DayResponse])
async def list_days(
    current_user: CurrentUser,
    limit: int = Query(default=75, le=75),
    offset: int = Query(default=0, ge=0),
):
    """List all Hard 75 days for the current user."""
    rows = await db.fetch(
        """
        SELECT * FROM hard75_days
        WHERE user_id = $1
        ORDER BY day_number DESC
        LIMIT $2 OFFSET $3
        """,
        current_user.id,
        limit,
        offset,
    )
    return [DayResponse(**dict(row)) for row in rows]


@router.get("/streak", response_model=StreakResponse)
async def get_streak(current_user: CurrentUser):
    """Get the current streak and progress info."""
    # Get streak using the database function
    streak = await db.fetchval(
        "SELECT calculate_streak($1)",
        current_user.id,
    )

    # Get total completed days
    total = await db.fetchval(
        """
        SELECT COUNT(*) FROM hard75_days
        WHERE user_id = $1 AND all_done = TRUE
        """,
        current_user.id,
    )

    return StreakResponse(
        current_streak=streak or 0,
        total_completed=total or 0,
        days_remaining=75 - (total or 0),
    )


@router.get("/{day_number}", response_model=DayResponse)
async def get_day(current_user: CurrentUser, day_number: int):
    """Get a specific day's details."""
    if day_number < 1 or day_number > 75:
        raise HTTPException(status_code=400, detail="Day number must be between 1 and 75")

    row = await db.fetchrow(
        """
        SELECT * FROM hard75_days
        WHERE user_id = $1 AND day_number = $2
        """,
        current_user.id,
        day_number,
    )

    if not row:
        raise HTTPException(status_code=404, detail="Day not found")

    return DayResponse(**dict(row))


@router.patch("/{day_number}", response_model=DayResponse)
async def update_day(
    current_user: CurrentUser,
    day_number: int,
    update: DayUpdate,
):
    """Update a specific day's progress."""
    if day_number < 1 or day_number > 75:
        raise HTTPException(status_code=400, detail="Day number must be between 1 and 75")

    # Build dynamic update query
    updates = []
    values = []
    param_num = 3  # Start after user_id and day_number

    for field, value in update.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ${param_num}")
        values.append(value)
        param_num += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    query = f"""
        UPDATE hard75_days
        SET {', '.join(updates)}
        WHERE user_id = $1 AND day_number = $2
        RETURNING *
    """

    row = await db.fetchrow(query, current_user.id, day_number, *values)

    if not row:
        raise HTTPException(status_code=404, detail="Day not found")

    return DayResponse(**dict(row))


@router.post("/{day_number}", response_model=DayResponse)
async def create_or_update_day(
    current_user: CurrentUser,
    day_number: int,
    update: DayUpdate,
):
    """Create or update a day's progress (upsert)."""
    if day_number < 1 or day_number > 75:
        raise HTTPException(status_code=400, detail="Day number must be between 1 and 75")

    # Get user's start date to calculate the correct date
    user = await db.fetchrow(
        "SELECT start_date FROM users WHERE id = $1",
        current_user.id,
    )

    if not user or not user["start_date"]:
        raise HTTPException(
            status_code=400,
            detail="User start date not set. Please set your start date first.",
        )

    from datetime import timedelta

    day_date = user["start_date"] + timedelta(days=day_number - 1)

    # Build upsert query
    data = update.model_dump(exclude_unset=True)

    row = await db.fetchrow(
        """
        INSERT INTO hard75_days (
            user_id, day_number, date,
            workout1_done, workout2_done, diet_done,
            water_done, reading_done, photo_done,
            steps, water_oz, reading_minutes,
            calories, protein_g, carbs_g, fat_g, fiber_g,
            raw_notes
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
        ON CONFLICT (user_id, day_number)
        DO UPDATE SET
            workout1_done = COALESCE(EXCLUDED.workout1_done, hard75_days.workout1_done),
            workout2_done = COALESCE(EXCLUDED.workout2_done, hard75_days.workout2_done),
            diet_done = COALESCE(EXCLUDED.diet_done, hard75_days.diet_done),
            water_done = COALESCE(EXCLUDED.water_done, hard75_days.water_done),
            reading_done = COALESCE(EXCLUDED.reading_done, hard75_days.reading_done),
            photo_done = COALESCE(EXCLUDED.photo_done, hard75_days.photo_done),
            steps = COALESCE(EXCLUDED.steps, hard75_days.steps),
            water_oz = COALESCE(EXCLUDED.water_oz, hard75_days.water_oz),
            reading_minutes = COALESCE(EXCLUDED.reading_minutes, hard75_days.reading_minutes),
            calories = COALESCE(EXCLUDED.calories, hard75_days.calories),
            protein_g = COALESCE(EXCLUDED.protein_g, hard75_days.protein_g),
            carbs_g = COALESCE(EXCLUDED.carbs_g, hard75_days.carbs_g),
            fat_g = COALESCE(EXCLUDED.fat_g, hard75_days.fat_g),
            fiber_g = COALESCE(EXCLUDED.fiber_g, hard75_days.fiber_g),
            raw_notes = CASE
                WHEN EXCLUDED.raw_notes IS NOT NULL
                THEN COALESCE(hard75_days.raw_notes || E'\\n\\n', '') || EXCLUDED.raw_notes
                ELSE hard75_days.raw_notes
            END
        RETURNING *
        """,
        current_user.id,
        day_number,
        day_date,
        data.get("workout1_done", False),
        data.get("workout2_done", False),
        data.get("diet_done", False),
        data.get("water_done", False),
        data.get("reading_done", False),
        data.get("photo_done", False),
        data.get("steps"),
        data.get("water_oz"),
        data.get("reading_minutes"),
        data.get("calories"),
        data.get("protein_g"),
        data.get("carbs_g"),
        data.get("fat_g"),
        data.get("fiber_g"),
        data.get("raw_notes"),
    )

    return DayResponse(**dict(row))
