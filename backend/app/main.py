"""FastAPI application entry point.

Registers routers, middleware, and startup hooks. All route logic lives
in ``app/api/``. This file stays thin — its only job is wiring.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, event, geo, health, news, visualbranding, visuals, workflows
from app.config import get_settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure logging on startup. FastAPI lifespan replaces on_event."""
    settings = get_settings()
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(),
        ],
    )
    logger.info("backend_started", cors_origins=settings.BACKEND_CORS_ORIGINS)
    yield


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Separated from module-level instantiation so tests can call
    ``create_app()`` independently without importing side effects.
    """
    settings = get_settings()

    app = FastAPI(
        title="Celonis CI Backend",
        version="0.1.0",
        description="Multi-agent competitive intelligence platform.",
        lifespan=lifespan,
    )

    # --- Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(chat.router)
    app.include_router(workflows.router)
    app.include_router(geo.router)
    app.include_router(visuals.router)
    app.include_router(visuals.visuals_router)
    app.include_router(visualbranding.router)
    app.include_router(event.router)
    app.include_router(news.router)

    # --- Root info endpoint ---
    @app.get("/", tags=["meta"])
    async def root() -> dict[str, str]:
        """Return service identity. Used for quick sanity checks."""
        return {"status": "ok", "service": "celonis-ci-backend"}

    return app


app = create_app()
