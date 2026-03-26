"""Session management for user authentication."""

from typing import Optional
from dataclasses import dataclass

from starlette.requests import Request


@dataclass
class SessionUser:
    """User data stored in session."""

    id: int
    email: str
    name: str
    role: str
    avatar_url: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def get_session_user(request: Request) -> Optional[SessionUser]:
    """Get the current user from session."""
    user_data = request.session.get("user")
    if not user_data:
        return None
    return SessionUser(**user_data)


def set_session_user(request: Request, user: SessionUser) -> None:
    """Set the current user in session."""
    request.session["user"] = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "avatar_url": user.avatar_url,
    }


def clear_session(request: Request) -> None:
    """Clear the session."""
    request.session.clear()
