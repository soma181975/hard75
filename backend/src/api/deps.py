"""API dependencies for authentication and authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from src.auth.session import SessionUser, get_session_user


async def get_current_user(request: Request) -> SessionUser:
    """Get the current authenticated user."""
    user = get_session_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_admin(
    current_user: Annotated[SessionUser, Depends(get_current_user)],
) -> SessionUser:
    """Require the current user to be an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# Type aliases for dependency injection
CurrentUser = Annotated[SessionUser, Depends(get_current_user)]
AdminUser = Annotated[SessionUser, Depends(require_admin)]
