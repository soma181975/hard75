"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src.config import get_settings
from src.db import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    await db.connect()
    yield
    # Shutdown
    await db.disconnect()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Hard 75 Tracker",
        description="Track your Hard 75 challenge progress",
        version="1.0.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # Add CORS middleware for React UI
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add session middleware
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="hard75_session",
        max_age=86400 * 7,  # 7 days
    )

    # Mount static files
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Import and include routers
    from src.auth.oauth import router as auth_router
    from src.api.days import router as days_router
    from src.api.workouts import router as workouts_router
    from src.api.meals import router as meals_router
    from src.api.users import router as users_router
    from src.api.pending import router as pending_router
    from src.pages.routes import router as pages_router
    from src.partials.routes import router as partials_router

    # API routes
    app.include_router(auth_router, tags=["auth"])
    app.include_router(days_router, prefix="/api/days", tags=["days"])
    app.include_router(workouts_router, prefix="/api/workouts", tags=["workouts"])
    app.include_router(meals_router, prefix="/api/meals", tags=["meals"])
    app.include_router(users_router, prefix="/api/users", tags=["users"])
    app.include_router(pending_router, prefix="/api/pending", tags=["pending"])

    # Page routes
    app.include_router(pages_router, tags=["pages"])
    app.include_router(partials_router, prefix="/partials", tags=["partials"])

    return app


app = create_app()
