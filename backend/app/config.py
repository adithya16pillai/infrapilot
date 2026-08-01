"""Runtime configuration. Every external dependency is optional by design."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "infrapilot.db"))

# F3: when false the identical engine module runs in-process. The demo never
# depends on Modal being reachable.
USE_MODAL = _flag("USE_MODAL")
MODAL_FUNCTION = os.getenv("MODAL_FUNCTION", "infrapilot/simulate_cascade")

# F4: without a key the deterministic router plans the investigation instead.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "claude-sonnet-5")

# F6: mock adapter returns realistic findings in the same shape as the live API.
OSPREY_MODE = os.getenv("OSPREY_MODE", "mock").strip().lower()

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]

# Any localhost port is allowed so a demo that lands on :3001 (or the prod
# server on a different port) does not fail on CORS with no visible cause.
CORS_ORIGIN_REGEX = os.getenv(
    "CORS_ORIGIN_REGEX", r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
)


def planner_mode() -> str:
    """Which planner will actually run -- surfaced on /api/health."""
    return "llm" if ANTHROPIC_API_KEY else "fallback"
