"""Ochrony HTTP przed routingiem: limit rozmiaru ciała i zgodność nagłówka Origin."""

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import Request, Response

from app.api.errors import problem

Handler = Callable[[Request], Awaitable[Response]]
Middleware = Callable[[Request, Handler], Awaitable[Response]]

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def limit_body(max_bytes: int) -> Middleware:
    """413 po samym nagłówku Content-Length, zanim ciało zostanie wczytane i sparsowane.

    Żądania bez Content-Length (chunked) zatrzymuje nginx (client_max_body_size) i limit
    znaków umowy w API.
    """

    async def middleware(request: Request, call_next: Handler) -> Response:
        length = request.headers.get("content-length")
        if length is not None and (not length.isdigit() or int(length) > max_bytes):
            return problem(request, 413, "za_duze", "Treść jest za długa.")
        return await call_next(request)

    return middleware


async def check_origin(request: Request, call_next: Handler) -> Response:
    """Obrona w głąb przed CSRF (obok SameSite=Strict): żądanie zmieniające stan z przeglądarki
    musi pochodzić z tego samego hosta. Brak nagłówka Origin (curl, skrypty) przepuszczamy.
    nginx przekazuje Host z portem ($http_host), więc porównanie obejmuje port.
    """
    origin = request.headers.get("origin")
    if request.method in UNSAFE_METHODS and origin is not None:
        if urlsplit(origin).netloc != request.headers.get("host", ""):
            return problem(request, 403, "obce_zrodlo", "Żądanie z innej witryny.")
    return await call_next(request)
