from fastapi import FastAPI

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

app = FastAPI(title=settings.app_name)
app.add_middleware(BearerAuthMiddleware)
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
