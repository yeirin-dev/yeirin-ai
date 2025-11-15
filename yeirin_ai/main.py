"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from yeirin_ai.api.routes import health, recommendations
from yeirin_ai.core.config.settings import settings
from yeirin_ai.infrastructure.database.connection import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Args:
        app: FastAPI application
    """
    # Startup: test database connection
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    print("✅ Database connection established")

    yield

    # Shutdown: cleanup
    await engine.dispose()
    print("👋 Database connection closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Yeirin AI Recommendation Service - RAG-based counseling center matching",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(recommendations.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
