"""HTMX partial routes for dynamic updates."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.auth.session import get_session_user
from src.db import db

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/checklist", response_class=HTMLResponse)
async def checklist_partial(request: Request):
    """Render the 75-day checklist grid."""
    user = get_session_user(request)
    if not user:
        return HTMLResponse(status_code=401)

    days = await db.fetch(
        """
        SELECT day_number, all_done FROM hard75_days
        WHERE user_id = $1
        ORDER BY day_number
        """,
        user.id,
    )

    # Create a dict for quick lookup
    days_map = {d["day_number"]: d["all_done"] for d in days}

    return templates.TemplateResponse(
        request=request,
        name="partials/checklist.html",
        context={"days_map": days_map},
    )


@router.get("/streak", response_class=HTMLResponse)
async def streak_partial(request: Request):
    """Render the streak counter."""
    user = get_session_user(request)
    if not user:
        return HTMLResponse(status_code=401)

    streak = await db.fetchval("SELECT calculate_streak($1)", user.id)
    total = await db.fetchval(
        "SELECT COUNT(*) FROM hard75_days WHERE user_id = $1 AND all_done = TRUE",
        user.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/streak.html",
        context={
            "streak": streak or 0,
            "total_completed": total or 0,
        },
    )


@router.get("/photos", response_class=HTMLResponse)
async def photo_gallery_partial(request: Request):
    """Render the photo gallery."""
    user = get_session_user(request)
    if not user:
        return HTMLResponse(status_code=401)

    days = await db.fetch(
        """
        SELECT day_number, date, photo_url FROM hard75_days
        WHERE user_id = $1 AND photo_url IS NOT NULL
        ORDER BY day_number DESC
        LIMIT 12
        """,
        user.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/photo_gallery.html",
        context={"photos": [dict(d) for d in days]},
    )


@router.get("/workouts", response_class=HTMLResponse)
async def workouts_partial(request: Request):
    """Render recent workout cards."""
    user = get_session_user(request)
    if not user:
        return HTMLResponse(status_code=401)

    workouts = await db.fetch(
        """
        SELECT ws.*,
            (SELECT COUNT(*) FROM workout_sets WHERE session_id = ws.id) as set_count
        FROM workout_sessions ws
        WHERE ws.user_id = $1
        ORDER BY ws.date DESC, ws.workout_number
        LIMIT 6
        """,
        user.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/workout_card.html",
        context={"workouts": [dict(w) for w in workouts]},
    )


@router.get("/nutrition", response_class=HTMLResponse)
async def nutrition_partial(request: Request):
    """Render today's nutrition summary."""
    user = get_session_user(request)
    if not user:
        return HTMLResponse(status_code=401)

    nutrition = await db.fetchrow(
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
        user.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/nutrition.html",
        context={"nutrition": dict(nutrition) if nutrition else {}},
    )


@router.get("/meals", response_class=HTMLResponse)
async def meals_partial(request: Request):
    """Render recent meals."""
    user = get_session_user(request)
    if not user:
        return HTMLResponse(status_code=401)

    meals = await db.fetch(
        """
        SELECT * FROM meals
        WHERE user_id = $1
        ORDER BY date DESC, id DESC
        LIMIT 9
        """,
        user.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="partials/meals.html",
        context={"meals": [dict(m) for m in meals]},
    )
