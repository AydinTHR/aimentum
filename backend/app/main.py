import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.auth import BearerAuthMiddleware
from app.core.config import settings
from app.routers import (
    app_settings,
    calendar,
    checkins,
    goals,
    health,
    progress,
    push,
    retros,
    tasks,
    tick,
    today,
)
from app.services.llm import LlmUnavailable

app = FastAPI(title=settings.app_name)
app.add_middleware(BearerAuthMiddleware)
# Added after the auth middleware on purpose: Starlette wraps in reverse
# order, so CORS ends up outermost and preflight OPTIONS requests (which
# carry no Authorization header) are answered before auth can reject them.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)
logger = logging.getLogger(__name__)


@app.exception_handler(LlmUnavailable)
def _llm_unavailable(request: Request, exc: LlmUnavailable) -> JSONResponse:
    """Answer with a reason instead of a stack trace.

    Planning is the first thing the owner touches, so "the agent could not
    be reached" has to arrive as readable copy on the screen rather than as
    an opaque 500.
    """
    logger.warning("llm unavailable on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "The agent could not be reached right now. Try again in a moment."},
    )


app.include_router(health.router)
app.include_router(goals.router)
app.include_router(progress.router)
app.include_router(today.router)
app.include_router(tasks.router)
app.include_router(app_settings.router)
app.include_router(checkins.router)
app.include_router(retros.router)
app.include_router(push.router)
app.include_router(tick.router)
app.include_router(calendar.router)
