from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response

from app.api import actions, analyses, auth, contracts
from app.api.errors import REQUEST_ID_HEADER, install_error_handlers, new_request_id
from app.config import get_settings
from app.security.logging import configure_logging


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    engine = getattr(app.state, "engine", None)
    if engine is not None:
        engine.dispose()


async def _request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    rid = new_request_id(request.headers.get(REQUEST_ID_HEADER))
    request.state.request_id = rid
    structlog.contextvars.bind_contextvars(request_id=rid)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.unbind_contextvars("request_id")
    response.headers[REQUEST_ID_HEADER] = rid
    return response


def create_app() -> FastAPI:
    configure_logging(get_settings().log_level)
    app = FastAPI(title="Analizator umów", lifespan=_lifespan)
    app.middleware("http")(_request_id)
    install_error_handlers(app)
    app.include_router(auth.router)
    app.include_router(contracts.router)
    app.include_router(analyses.router)
    app.include_router(actions.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
