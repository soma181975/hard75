"""Google OAuth authentication routes."""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth

from src.config import get_settings
from src.db import db
from src.auth.session import SessionUser, set_session_user, clear_session

router = APIRouter()
settings = get_settings()

# Configure OAuth
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/auth/login")
async def login(request: Request):
    """Initiate Google OAuth login."""
    if not settings.google_client_id:
        # Development mode: auto-login as test user
        if settings.is_development:
            user = await db.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                "test@example.com",
            )
            if user:
                set_session_user(
                    request,
                    SessionUser(
                        id=user["id"],
                        email=user["email"],
                        name=user["name"],
                        role=user["role"],
                        avatar_url=user["avatar_url"],
                    ),
                )
                return RedirectResponse(url="/dashboard", status_code=302)
        raise HTTPException(
            status_code=500,
            detail="Google OAuth not configured",
        )

    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback")
async def auth_callback(request: Request):
    """Handle Google OAuth callback."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to get user info")

    email = user_info.get("email")
    google_id = user_info.get("sub")
    name = user_info.get("name", email.split("@")[0])
    avatar_url = user_info.get("picture")

    # Check if user exists
    user = await db.fetchrow(
        "SELECT * FROM users WHERE email = $1 OR google_id = $2",
        email,
        google_id,
    )

    if not user:
        # Create new user
        user = await db.fetchrow(
            """
            INSERT INTO users (email, name, google_id, avatar_url, role)
            VALUES ($1, $2, $3, $4, 'user')
            RETURNING *
            """,
            email,
            name,
            google_id,
            avatar_url,
        )
    else:
        # Update existing user
        user = await db.fetchrow(
            """
            UPDATE users
            SET google_id = COALESCE(google_id, $2),
                avatar_url = COALESCE($3, avatar_url),
                name = COALESCE($4, name)
            WHERE id = $1
            RETURNING *
            """,
            user["id"],
            google_id,
            avatar_url,
            name,
        )

    # Set session
    set_session_user(
        request,
        SessionUser(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            avatar_url=user["avatar_url"],
        ),
    )

    # Redirect based on role
    if user["role"] == "admin":
        return RedirectResponse(url="/admin", status_code=302)
    return RedirectResponse(url="/dashboard", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    """Log out the current user."""
    clear_session(request)
    return RedirectResponse(url="/login", status_code=302)
