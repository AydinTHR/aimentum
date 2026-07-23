from fastapi import FastAPI

from app.core.auth import BearerAuthMiddleware
from app.core.config import settings
from app.routers import health

app = FastAPI(title=settings.app_name)
app.add_middleware(BearerAuthMiddleware)
app.include_router(health.router)
