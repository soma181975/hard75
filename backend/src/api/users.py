"""API endpoints for user management (admin only)."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.api.deps import AdminUser, CurrentUser
from src.db import db

router = APIRouter()


class UserResponse(BaseModel):
    """Response model for a user."""

    id: int
    email: str
    name: str
    role: str
    avatar_url: Optional[str] = None
    start_date: Optional[date] = None
    timezone: str = "America/New_York"
    current_streak: int = 0
    total_completed: int = 0


class UserCreate(BaseModel):
    """Request model for creating a user."""

    email: EmailStr
    name: str
    role: str = "user"
    start_date: Optional[date] = None
    timezone: str = "America/New_York"


class UserUpdate(BaseModel):
    """Request model for updating a user."""

    name: Optional[str] = None
    role: Optional[str] = None
    start_date: Optional[date] = None
    timezone: Optional[str] = None


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: CurrentUser):
    """Get the current authenticated user."""
    row = await db.fetchrow(
        """
        SELECT
            u.*,
            calculate_streak(u.id) as current_streak,
            (SELECT COUNT(*) FROM hard75_days WHERE user_id = u.id AND all_done = TRUE) as total_completed
        FROM users u
        WHERE u.id = $1
        """,
        user.id,
    )

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        avatar_url=row["avatar_url"],
        start_date=row["start_date"],
        timezone=row["timezone"] or "America/New_York",
        current_streak=row["current_streak"] or 0,
        total_completed=row["total_completed"] or 0,
    )


@router.get("", response_model=list[UserResponse])
async def list_users(admin: AdminUser):
    """List all users (admin only)."""
    rows = await db.fetch(
        """
        SELECT
            u.*,
            calculate_streak(u.id) as current_streak,
            (SELECT COUNT(*) FROM hard75_days WHERE user_id = u.id AND all_done = TRUE) as total_completed
        FROM users u
        ORDER BY u.created_at DESC
        """
    )

    return [
        UserResponse(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            role=row["role"],
            avatar_url=row["avatar_url"],
            start_date=row["start_date"],
            timezone=row["timezone"] or "America/New_York",
            current_streak=row["current_streak"] or 0,
            total_completed=row["total_completed"] or 0,
        )
        for row in rows
    ]


@router.post("", response_model=UserResponse)
async def create_user(admin: AdminUser, user: UserCreate):
    """Create a new user (admin only)."""
    # Check if email already exists
    existing = await db.fetchrow(
        "SELECT id FROM users WHERE email = $1",
        user.email,
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    row = await db.fetchrow(
        """
        INSERT INTO users (email, name, role, start_date, timezone)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING *
        """,
        user.email,
        user.name,
        user.role,
        user.start_date,
        user.timezone,
    )

    return UserResponse(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        avatar_url=row["avatar_url"],
        start_date=row["start_date"],
        timezone=row["timezone"] or "America/New_York",
        current_streak=0,
        total_completed=0,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(admin: AdminUser, user_id: int):
    """Get a specific user (admin only)."""
    row = await db.fetchrow(
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

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        avatar_url=row["avatar_url"],
        start_date=row["start_date"],
        timezone=row["timezone"] or "America/New_York",
        current_streak=row["current_streak"] or 0,
        total_completed=row["total_completed"] or 0,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(admin: AdminUser, user_id: int, update: UserUpdate):
    """Update a user (admin only)."""
    # Build dynamic update query
    updates = []
    values = []
    param_num = 2  # Start after user_id

    for field, value in update.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ${param_num}")
        values.append(value)
        param_num += 1

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    query = f"""
        UPDATE users
        SET {', '.join(updates)}
        WHERE id = $1
        RETURNING *
    """

    row = await db.fetchrow(query, user_id, *values)

    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    # Get streak info
    streak = await db.fetchval("SELECT calculate_streak($1)", user_id)
    total = await db.fetchval(
        "SELECT COUNT(*) FROM hard75_days WHERE user_id = $1 AND all_done = TRUE",
        user_id,
    )

    return UserResponse(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        role=row["role"],
        avatar_url=row["avatar_url"],
        start_date=row["start_date"],
        timezone=row["timezone"] or "America/New_York",
        current_streak=streak or 0,
        total_completed=total or 0,
    )


@router.delete("/{user_id}")
async def delete_user(admin: AdminUser, user_id: int):
    """Delete a user (admin only)."""
    # Don't allow deleting yourself
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(
        "DELETE FROM users WHERE id = $1",
        user_id,
    )

    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User deleted"}
