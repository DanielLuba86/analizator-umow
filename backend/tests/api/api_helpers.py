"""Stałe i pomocnicze funkcje testów API (importowane przez conftest i testy)."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.config import Settings

PASSWORD = "haslo-testowe-123"  # noqa: S105 - tylko testy

ApiClientFactory = Callable[[str], TestClient]


def make_settings(**kw: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "cookie_secure": False,  # TestClient działa po http — ciasteczko Secure nie wróciłoby
        "max_contract_chars": 2000,
    }
    base.update(kw)
    return Settings(**base)  # type: ignore[arg-type]
