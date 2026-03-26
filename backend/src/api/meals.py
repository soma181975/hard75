"""API endpoints for meals and nutrition tracking."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.api.deps import CurrentUser
from src.db import db

router = APIRouter()


class FoodItem(BaseModel):
    """A single food item within a meal."""

    name: str
    quantity: Optional[str] = None
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None


class MealResponse(BaseModel):
    """Response model for a meal."""

    id: int
    date: date
    meal_type: str
    description: Optional[str] = None
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    fiber_g: Optional[int] = None
    sugar_g: Optional[int] = None
    food_items: Optional[list[dict]] = None


class MealCreate(BaseModel):
    """Request model for creating a meal."""

    date: date
    meal_type: str  # breakfast, lunch, dinner, snack, pre-workout, post-workout
    description: Optional[str] = None
    calories: Optional[int] = None
    protein_g: Optional[int] = None
    carbs_g: Optional[int] = None
    fat_g: Optional[int] = None
    fiber_g: Optional[int] = None
    sugar_g: Optional[int] = None
    food_items: Optional[list[FoodItem]] = None


class DailyNutritionResponse(BaseModel):
    """Response model for daily nutrition summary."""

    date: date
    total_calories: int
    total_protein_g: int
    total_carbs_g: int
    total_fat_g: int
    total_fiber_g: int
    meal_count: int


class MacroTrendPoint(BaseModel):
    """Data point for macro trends over time."""

    date: date
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int


@router.get("", response_model=list[MealResponse])
async def list_meals(
    current_user: CurrentUser,
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    meal_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """List meals for the current user."""
    query = """
        SELECT * FROM meals
        WHERE user_id = $1
    """
    params = [current_user.id]
    param_num = 2

    if meal_type:
        query += f" AND meal_type = ${param_num}"
        params.append(meal_type)
        param_num += 1

    if date_from:
        query += f" AND date >= ${param_num}"
        params.append(date_from)
        param_num += 1

    if date_to:
        query += f" AND date <= ${param_num}"
        params.append(date_to)
        param_num += 1

    query += f" ORDER BY date DESC, id DESC LIMIT ${param_num} OFFSET ${param_num + 1}"
    params.extend([limit, offset])

    rows = await db.fetch(query, *params)

    return [
        MealResponse(
            id=row["id"],
            date=row["date"],
            meal_type=row["meal_type"],
            description=row["description"],
            calories=row["calories"],
            protein_g=row["protein_g"],
            carbs_g=row["carbs_g"],
            fat_g=row["fat_g"],
            fiber_g=row["fiber_g"],
            sugar_g=row["sugar_g"],
            food_items=row["food_items"],
        )
        for row in rows
    ]


@router.get("/daily", response_model=list[DailyNutritionResponse])
async def get_daily_nutrition(
    current_user: CurrentUser,
    days: int = Query(default=30, le=90),
):
    """Get daily nutrition totals for charts."""
    rows = await db.fetch(
        """
        SELECT
            date,
            COALESCE(SUM(calories), 0) as total_calories,
            COALESCE(SUM(protein_g), 0) as total_protein_g,
            COALESCE(SUM(carbs_g), 0) as total_carbs_g,
            COALESCE(SUM(fat_g), 0) as total_fat_g,
            COALESCE(SUM(fiber_g), 0) as total_fiber_g,
            COUNT(*) as meal_count
        FROM meals
        WHERE user_id = $1
            AND date >= CURRENT_DATE - $2 * INTERVAL '1 day'
        GROUP BY date
        ORDER BY date
        """,
        current_user.id,
        days,
    )

    return [
        DailyNutritionResponse(
            date=row["date"],
            total_calories=row["total_calories"],
            total_protein_g=row["total_protein_g"],
            total_carbs_g=row["total_carbs_g"],
            total_fat_g=row["total_fat_g"],
            total_fiber_g=row["total_fiber_g"],
            meal_count=row["meal_count"],
        )
        for row in rows
    ]


@router.get("/trends", response_model=list[MacroTrendPoint])
async def get_macro_trends(
    current_user: CurrentUser,
    days: int = Query(default=30, le=90),
):
    """Get macro trends over time for charts."""
    rows = await db.fetch(
        """
        SELECT
            date,
            COALESCE(SUM(calories), 0) as calories,
            COALESCE(SUM(protein_g), 0) as protein_g,
            COALESCE(SUM(carbs_g), 0) as carbs_g,
            COALESCE(SUM(fat_g), 0) as fat_g
        FROM meals
        WHERE user_id = $1
            AND date >= CURRENT_DATE - $2 * INTERVAL '1 day'
        GROUP BY date
        ORDER BY date
        """,
        current_user.id,
        days,
    )

    return [
        MacroTrendPoint(
            date=row["date"],
            calories=row["calories"],
            protein_g=row["protein_g"],
            carbs_g=row["carbs_g"],
            fat_g=row["fat_g"],
        )
        for row in rows
    ]


@router.get("/today", response_model=DailyNutritionResponse)
async def get_today_nutrition(current_user: CurrentUser):
    """Get today's nutrition summary."""
    row = await db.fetchrow(
        """
        SELECT
            CURRENT_DATE as date,
            COALESCE(SUM(calories), 0) as total_calories,
            COALESCE(SUM(protein_g), 0) as total_protein_g,
            COALESCE(SUM(carbs_g), 0) as total_carbs_g,
            COALESCE(SUM(fat_g), 0) as total_fat_g,
            COALESCE(SUM(fiber_g), 0) as total_fiber_g,
            COUNT(*) as meal_count
        FROM meals
        WHERE user_id = $1 AND date = CURRENT_DATE
        """,
        current_user.id,
    )

    return DailyNutritionResponse(
        date=row["date"],
        total_calories=row["total_calories"],
        total_protein_g=row["total_protein_g"],
        total_carbs_g=row["total_carbs_g"],
        total_fat_g=row["total_fat_g"],
        total_fiber_g=row["total_fiber_g"],
        meal_count=row["meal_count"],
    )


@router.post("", response_model=MealResponse)
async def create_meal(current_user: CurrentUser, meal: MealCreate):
    """Create a new meal entry."""
    import json

    # Get the hard75_day_id if it exists
    day = await db.fetchrow(
        "SELECT id FROM hard75_days WHERE user_id = $1 AND date = $2",
        current_user.id,
        meal.date,
    )
    day_id = day["id"] if day else None

    # Convert food_items to JSON
    food_items_json = None
    if meal.food_items:
        food_items_json = json.dumps([item.model_dump() for item in meal.food_items])

    row = await db.fetchrow(
        """
        INSERT INTO meals (
            user_id, hard75_day_id, date, meal_type,
            description, calories, protein_g, carbs_g,
            fat_g, fiber_g, sugar_g, food_items
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        RETURNING *
        """,
        current_user.id,
        day_id,
        meal.date,
        meal.meal_type,
        meal.description,
        meal.calories,
        meal.protein_g,
        meal.carbs_g,
        meal.fat_g,
        meal.fiber_g,
        meal.sugar_g,
        food_items_json,
    )

    return MealResponse(
        id=row["id"],
        date=row["date"],
        meal_type=row["meal_type"],
        description=row["description"],
        calories=row["calories"],
        protein_g=row["protein_g"],
        carbs_g=row["carbs_g"],
        fat_g=row["fat_g"],
        fiber_g=row["fiber_g"],
        sugar_g=row["sugar_g"],
        food_items=row["food_items"],
    )


@router.delete("/{meal_id}")
async def delete_meal(current_user: CurrentUser, meal_id: int):
    """Delete a meal entry."""
    result = await db.execute(
        "DELETE FROM meals WHERE id = $1 AND user_id = $2",
        meal_id,
        current_user.id,
    )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Meal not found")

    return {"message": "Meal deleted"}
