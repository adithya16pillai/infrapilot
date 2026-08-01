"""InfraPilot API.

Thin orchestration layer: validation, persistence, and streaming. All graph
computation lives in `app.engine`, which is deliberately pure so it can run
here, in a pytest, or inside a Modal function without modification.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    CORS_ORIGIN_REGEX,
    CORS_ORIGINS,
    OSPREY_MODE,
    USE_MODAL,
    planner_mode,
)
from .db import connect, init_db
from .models import HealthResponse
from .routes import graph, recommendations, simulate


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="InfraPilot",
    description="AI resilience copilot for critical infrastructure",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

health_router = APIRouter(prefix="/api", tags=["health"])


@health_router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        with connect() as conn:
            conn.execute("SELECT COUNT(*) FROM assets").fetchone()
        database = "ok"
    except Exception as exc:  # noqa: BLE001
        database = f"error: {exc}"

    return HealthResponse(
        modal="ok" if USE_MODAL else "local (fallback engine)",
        database=database,
        overmind="fallback",
        osprey=OSPREY_MODE,
        planner=planner_mode(),
    )


app.include_router(health_router)
app.include_router(graph.router)
app.include_router(simulate.router)
app.include_router(recommendations.router)


@app.get("/")
def root() -> dict:
    return {"service": "InfraPilot", "docs": "/docs", "health": "/api/health"}
