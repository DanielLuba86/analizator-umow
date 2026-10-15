# 0001. Backend w Pythonie (FastAPI) i frontend w React

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Analizator umów wystawia REST API, uruchamia agenta opartego na Claude Agent SDK i prezentuje wyniki w przeglądarce. Agent SDK ma wsparcie dla Pythona, a rdzeń domeny (weryfikacja cytatów, reguły) ma być testowany bez frameworka. Interfejs ma obsługiwać logowanie, role i przegląd tez z cytatami.

## Decyzja

Backend: Python 3.12, FastAPI, SQLAlchemy i Alembic, zarządzany przez uv; kontrola jakości: ruff, mypy (`--strict`), pytest. Frontend: React + Vite + TypeScript (`strict: true`), testy vitest, ESLint. Komunikacja przez REST, sesja w ciasteczku httpOnly.

## Rozważane opcje

- Python (FastAPI) + React: natywne Claude Agent SDK, typowane API, dojrzały ekosystem testów. Dwa języki w repozytorium.
- Pełny stack w TypeScripcie: jeden język, ale agent musiałby korzystać z innego SDK lub procesu pomocniczego.
- Django z szablonami po stronie serwera: mniej kodu frontendu, słabsze wsparcie dla asynchronicznego agenta i bardziej interaktywnego UI.

## Konsekwencje

- Agent i domena działają w jednym procesie Pythona, bez warstwy pośredniej.
- Dwa łańcuchy narzędzi (uv i npm) wymagają dwóch jobów w CI (`backend`, `frontend`).
- Kontrakt API jest typowany po obu stronach; zmiany schematu wymagają aktualizacji obu części.
