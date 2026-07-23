import secrets

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from app.core.config import settings

PUBLIC_PATHS = {"/health"}
PUBLIC_PREFIXES = ("/tick",)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Require the shared bearer token on everything except the public paths.

    /tick is excluded here because it authenticates with its own secret
    header, checked in its handler. An unset APP_TOKEN fails closed.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        token_ok = (
            bool(settings.app_token)
            and scheme.lower() == "bearer"
            and secrets.compare_digest(token, settings.app_token)
        )
        if not token_ok:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)
