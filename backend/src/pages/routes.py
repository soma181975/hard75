"""Full page routes for the dashboard."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.auth.session import get_session_user
from src.db import db

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Redirect to appropriate page based on auth state."""
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if user.is_admin:
        return RedirectResponse(url="/admin", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Render the login page."""
    user = get_session_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request=request, name="pages/login.html")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the user dashboard."""
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    # Get user's days
    days = await db.fetch(
        """
        SELECT * FROM hard75_days
        WHERE user_id = $1
        ORDER BY day_number
        """,
        user.id,
    )

    # Get streak info
    streak = await db.fetchval("SELECT calculate_streak($1)", user.id)
    total_completed = await db.fetchval(
        "SELECT COUNT(*) FROM hard75_days WHERE user_id = $1 AND all_done = TRUE",
        user.id,
    )

    # Get recent workouts
    workouts = await db.fetch(
        """
        SELECT * FROM workout_sessions
        WHERE user_id = $1
        ORDER BY date DESC, workout_number
        LIMIT 10
        """,
        user.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/dashboard.html",
        context={
            "user": user,
            "days": [dict(d) for d in days],
            "streak": streak or 0,
            "total_completed": total_completed or 0,
            "workouts": [dict(w) for w in workouts],
        },
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Render the admin dashboard."""
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Get all users with their progress
    users = await db.fetch(
        """
        SELECT
            u.*,
            calculate_streak(u.id) as current_streak,
            (SELECT COUNT(*) FROM hard75_days WHERE user_id = u.id AND all_done = TRUE) as total_completed
        FROM users u
        ORDER BY u.created_at DESC
        """
    )

    # Get pending senders
    pending = await db.fetch(
        """
        SELECT * FROM pending_senders
        WHERE status = 'pending'
        ORDER BY last_message_at DESC
        """
    )

    return templates.TemplateResponse(
        request=request,
        name="pages/admin.html",
        context={
            "user": user,
            "users": [dict(u) for u in users],
            "pending_senders": [dict(p) for p in pending],
        },
    )


@router.get("/admin/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(request: Request, user_id: int):
    """View a specific user's progress as admin."""
    user = get_session_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not user.is_admin:
        return RedirectResponse(url="/dashboard", status_code=302)

    # Get the target user
    target_user = await db.fetchrow(
        """
        SELECT
            u.*,
            calculate_streak(u.id) as current_streak,
            (SELECT COUNT(*) FROM hard75_days WHERE user_id = u.id AND all_done = TRUE) as total_completed
        FROM users u
        WHERE u.id = $1
        """,
        user_id,
    )

    if not target_user:
        return RedirectResponse(url="/admin", status_code=302)

    # Get user's days
    days = await db.fetch(
        """
        SELECT * FROM hard75_days
        WHERE user_id = $1
        ORDER BY day_number
        """,
        user_id,
    )

    # Get recent workouts
    workouts = await db.fetch(
        """
        SELECT * FROM workout_sessions
        WHERE user_id = $1
        ORDER BY date DESC, workout_number
        LIMIT 20
        """,
        user_id,
    )

    # Get recent meals
    meals = await db.fetch(
        """
        SELECT * FROM meals
        WHERE user_id = $1
        ORDER BY date DESC, id DESC
        LIMIT 20
        """,
        user_id,
    )

    # Group meals by date for easy lookup
    meals_by_date = {}
    for meal in meals:
        meal_dict = dict(meal)
        # Use isoformat for consistent date string format
        date_str = meal_dict["date"].isoformat() if hasattr(meal_dict["date"], 'isoformat') else str(meal_dict["date"])
        # Convert datetime objects to strings for JSON serialization
        for key, value in meal_dict.items():
            if hasattr(value, 'isoformat'):
                meal_dict[key] = value.isoformat()
        if date_str not in meals_by_date:
            meals_by_date[date_str] = []
        meals_by_date[date_str].append(meal_dict)

    # Also convert day dates for template comparison
    days_list = []
    for d in days:
        day_dict = dict(d)
        # Store original date for display but also string version for lookup
        day_dict["date_str"] = day_dict["date"].isoformat() if hasattr(day_dict["date"], 'isoformat') else str(day_dict["date"])
        days_list.append(day_dict)

    return templates.TemplateResponse(
        request=request,
        name="pages/admin_user.html",
        context={
            "user": user,
            "target_user": dict(target_user),
            "days": days_list,
            "workouts": [dict(w) for w in workouts],
            "meals": [dict(m) for m in meals],
            "meals_by_date": meals_by_date,
        },
    )
