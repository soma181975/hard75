"""API endpoints for pending sender management (admin only)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.api.deps import AdminUser
from src.db import db

router = APIRouter()


class PendingSenderResponse(BaseModel):
    """Response model for a pending sender."""

    id: int
    email: str
    first_seen_at: datetime
    message_count: int
    last_message_at: datetime
    status: str
    approved_user_id: Optional[int] = None
    approved_user_name: Optional[str] = None


class ApproveRequest(BaseModel):
    """Request model for approving a sender."""

    user_id: Optional[int] = None  # Link to existing user
    create_user: bool = False  # Create new user with this email
    user_name: Optional[str] = None  # Name for new user


@router.get("", response_model=list[PendingSenderResponse])
async def list_pending_senders(admin: AdminUser, status: str = "pending"):
    """List pending senders (admin only)."""
    rows = await db.fetch(
        """
        SELECT
            ps.*,
            u.name as approved_user_name
        FROM pending_senders ps
        LEFT JOIN users u ON u.id = ps.approved_user_id
        WHERE ps.status = $1
        ORDER BY ps.last_message_at DESC
        """,
        status,
    )

    return [
        PendingSenderResponse(
            id=row["id"],
            email=row["email"],
            first_seen_at=row["first_seen_at"],
            message_count=row["message_count"],
            last_message_at=row["last_message_at"],
            status=row["status"],
            approved_user_id=row["approved_user_id"],
            approved_user_name=row["approved_user_name"],
        )
        for row in rows
    ]


@router.post("/{sender_id}/approve", response_model=PendingSenderResponse)
async def approve_sender(
    admin: AdminUser,
    sender_id: int,
    request: ApproveRequest,
):
    """Approve a pending sender (admin only)."""
    # Get the sender
    sender = await db.fetchrow(
        "SELECT * FROM pending_senders WHERE id = $1",
        sender_id,
    )

    if not sender:
        raise HTTPException(status_code=404, detail="Sender not found")

    if sender["status"] != "pending":
        raise HTTPException(status_code=400, detail="Sender already processed")

    user_id = request.user_id

    # Create new user if requested
    if request.create_user:
        name = request.user_name or sender["email"].split("@")[0]
        user = await db.fetchrow(
            """
            INSERT INTO users (email, name, role, start_date)
            VALUES ($1, $2, 'user', CURRENT_DATE)
            RETURNING *
            """,
            sender["email"],
            name,
        )
        user_id = user["id"]
    elif not user_id:
        raise HTTPException(
            status_code=400,
            detail="Must provide user_id or set create_user=true",
        )

    # Update sender status
    row = await db.fetchrow(
        """
        UPDATE pending_senders
        SET status = 'approved', approved_user_id = $2
        WHERE id = $1
        RETURNING *
        """,
        sender_id,
        user_id,
    )

    # Get user name
    user = await db.fetchrow("SELECT name FROM users WHERE id = $1", user_id)

    return PendingSenderResponse(
        id=row["id"],
        email=row["email"],
        first_seen_at=row["first_seen_at"],
        message_count=row["message_count"],
        last_message_at=row["last_message_at"],
        status=row["status"],
        approved_user_id=row["approved_user_id"],
        approved_user_name=user["name"] if user else None,
    )


@router.post("/{sender_id}/reject")
async def reject_sender(admin: AdminUser, sender_id: int):
    """Reject a pending sender (admin only)."""
    result = await db.execute(
        """
        UPDATE pending_senders
        SET status = 'rejected'
        WHERE id = $1 AND status = 'pending'
        """,
        sender_id,
    )

    if result == "UPDATE 0":
        raise HTTPException(
            status_code=404,
            detail="Sender not found or already processed",
        )

    return {"message": "Sender rejected"}
