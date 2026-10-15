"""Błędy API jako application/problem+json (RFC 9457) z request_id.

Odpowiedzi błędów nigdy nie zawierają `detail` ani wartości wejściowych — treść umowy
nie może wrócić w błędzie. Błędy walidacji podają tylko położenie pola i typ błędu.
"""

import re
import uuid
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"
REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

log = structlog.get_logger(__name__)

_GENERIC_TITLES: dict[int, tuple[str, str]] = {
    400: ("zle_zadanie", "Nieprawidłowe żądanie."),
    401: ("brak_logowania", "Wymagane zalogowanie."),
    403: ("brak_uprawnien", "Brak uprawnień."),
    404: ("nie_znaleziono", "Nie znaleziono."),
    405: ("metoda_niedozwolona", "Metoda niedozwolona."),
    409: ("konflikt", "Konflikt ze stanem zasobu."),
    413: ("za_duze", "Treść jest za długa."),
    422: ("bledne_dane", "Nieprawidłowe dane wejściowe."),
    500: ("blad_serwera", "Wewnętrzny błąd serwera."),
}


class ApiError(Exception):
    """Błąd domenowy API; `title` jest stałym tekstem, nigdy treścią z żądania."""

    def __init__(self, status: int, slug: str, title: str) -> None:
        super().__init__(slug)
        self.status = status
        self.slug = slug
        self.title = title


def new_request_id(incoming: str | None) -> str:
    if incoming and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def request_id_of(request: Request) -> str:
    rid = getattr(request.state, "request_id", None)
    if not isinstance(rid, str):
        rid = new_request_id(None)
        request.state.request_id = rid
    return rid


def problem(
    request: Request,
    status: int,
    slug: str,
    title: str,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    rid = request_id_of(request)
    body: dict[str, Any] = {
        "type": f"/problems/{slug}",
        "title": title,
        "status": status,
        "request_id": rid,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(
        body, status_code=status, media_type=PROBLEM_JSON, headers={REQUEST_ID_HEADER: rid}
    )


def _generic(request: Request, status: int) -> JSONResponse:
    slug, title = _GENERIC_TITLES.get(status, ("blad", "Błąd."))
    return problem(request, status, slug, title)


async def _api_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, ApiError):
        raise exc
    return problem(request, exc.status, exc.slug, exc.title)


async def _http_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    return _generic(request, exc.status_code)


async def _validation_error(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    errors = [
        {
            "loc": [p for p in e.get("loc", ()) if isinstance(p, str | int)],
            "type": str(e.get("type")),
        }
        for e in exc.errors()
    ]
    slug, title = _GENERIC_TITLES[422]
    return problem(request, 422, slug, title, errors)


async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error", error=type(exc).__name__, path=request.url.path)
    return _generic(request, 500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled)
