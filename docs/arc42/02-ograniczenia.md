# 2. Ograniczenia

## Ograniczenia techniczne

| Ograniczenie | Uzasadnienie |
|---|---|
| Backend Python 3.12, FastAPI, SQLAlchemy 2, Alembic | wymaganie projektu; Claude Agent SDK ma pierwszorzędne wsparcie dla Pythona ([ADR 0001](../adr/0001-python-fastapi-i-react.md)) |
| Agent na Claude Agent SDK wyłącznie z własnymi narzędziami MCP in-process | wymaganie projektu i zasada najmniejszych uprawnień ([ADR 0002](../adr/0002-claude-agent-sdk-z-wlasnymi-narzedziami.md)) |
| Frontend React 18 + Vite + TypeScript (`strict`) | wymaganie projektu |
| PostgreSQL 16 w docker-compose | trwałe dane, transakcje i blokady wierszy ([ADR 0006](../adr/0006-postgresql-w-docker-compose.md)) |
| Model agenta `AGENT_MODEL` (domyślnie `claude-opus-5-5`), klasyfikatora `CLASSIFIER_MODEL` (domyślnie `claude-haiku-5-5`) | konfiguracja przez zmienne środowiskowe |
| Wejście: tekst lub Markdown | PDF/DOCX poza zakresem |
| Bez kolejki zadań; analizy w `BackgroundTasks` jednego procesu backendu | prostota wdrożenia ([ADR 0007](../adr/0007-zadania-w-tle-bez-kolejki.md)) |

## Ograniczenia organizacyjne

- Wszystkie dane (umowy, osoby, firmy) są syntetyczne; aplikacja nie udziela porad prawnych.
- Zero sekretów w repozytorium: konfiguracja przez zmienne środowiskowe, w repo tylko
  `.env.example`; gitleaks w CI.
- Każda faza to osobna gałąź i pull request do `main`; merge tylko przy zielonym CI.
- Komunikaty commitów po polsku.
- Logika domenowa powstaje test-first.
- Testy w CI nie korzystają z Claude API (fałszywy model i fałszywy klasyfikator).
- Jakość kodu: mypy `--strict` dla `backend/app`, ruff, ESLint, `tsc --noEmit`.

## Konwencje

- Kod i identyfikatory po angielsku, wartości domenowe po polsku (`najem`, `oczekuje`,
  `wstrzyknięcie`), zgodnie ze słownikiem w [sekcji 12](12-slownik.md).
- Błędy API w formacie `application/problem+json` z `request_id`.
- Decyzje architektoniczne jako krótkie ADR w formacie MADR ([indeks](../adr/README.md)).
