# Analizator umów

Aplikacja dla fikcyjnej kancelarii, w której agent Claude analizuje umowy najmu, dostawy
i zlecenia. Agent wskazuje strony, terminy, kary i ryzykowne zapisy. **Każda teza agenta jest
przyjmowana tylko z dosłownym cytatem z umowy, sprawdzanym automatycznie przez serwer.** Umowy od
kontrahentów są traktowane jako dane nieufne: ukryte instrukcje dla AI (prompt injection) kierują
analizę do kwarantanny. Akcje wysokiego ryzyka zatwierdza prawnik.

Stack:

- backend: FastAPI, Claude Agent SDK, SQLAlchemy, Alembic;
- frontend: React, Vite, TypeScript;
- baza: PostgreSQL;
- uruchomienie: docker compose.

Wszystkie umowy, osoby i firmy w repozytorium są syntetyczne. Aplikacja nie udziela porad
prawnych.

## Wymagania

- Docker z Docker Compose v2.
- Klucz API Anthropic (`ANTHROPIC_API_KEY`). Bez klucza aplikacja działa, ale analiza kończy się
  kwarantanną (klasyfikator niedostępny) albo błędem agenta.
- Do testów lokalnych (opcjonalnie):
  - [uv](https://docs.astral.sh/uv/) z Pythonem 3.12;
  - Node.js 22.

## Uruchomienie od zera

```bash
git clone https://github.com/DanielLuba86/analizator-umow.git
cd analizator-umow
cp .env.example .env
```

Uzupełnij w `.env`:

- `ANTHROPIC_API_KEY` — klucz API;
- `SEED_ASSISTANT_PASSWORD` i `SEED_LAWYER_PASSWORD` — hasła kont demo; puste hasło oznacza,
  że konto nie zostanie utworzone;
- `POSTGRES_PASSWORD` — zmień, i zmień tak samo w `DATABASE_URL`.

Następnie:

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head      # schemat bazy
docker compose exec backend python -m app.repo.seed   # wzorce klauzul i konta demo
```

Aplikacja działa pod adresem **http://localhost:8080**. API jest też bezpośrednio pod
http://localhost:8000; `curl localhost:8080/api/health` zwraca `{"status":"ok"}`.

### Konta demo

| Login | Rola | Hasło | Co może |
|---|---|---|---|
| `asystent` | asystent | `SEED_ASSISTANT_PASSWORD` | wgrywać umowy i wersje, uruchamiać analizy, porównywać wersje, składać wnioski o eksport i opinię |
| `prawnik` | prawnik | `SEED_LAWYER_PASSWORD` | to samo oraz zatwierdzać i odrzucać wnioski (kolejka „Wnioski do zatwierdzenia”) |

### Przykładowy przebieg

1. Zaloguj się jako `asystent`. Dodaj umowę z pliku, np.
   [`data/umowy/umowa_najmu.md`](data/umowy/umowa_najmu.md), i kliknij „Uruchom analizę”.
2. Raport pojawi się po chwili, a cytaty tez są podświetlone w tekście umowy.
3. Wgraj [`data/umowy_z_wstrzyknieciem/jawne_polecenie.md`](data/umowy_z_wstrzyknieciem/jawne_polecenie.md).
   Analiza trafi do kwarantanny, a raport będzie ukryty.
4. Zaloguj się jako `prawnik` i zatwierdź wniosek `kwarantanna`. Raport stanie się widoczny.

## Testy i sprawdzenia lokalne

Backend potrzebuje PostgreSQL. Najprościej uruchomić tymczasowy kontener:

```bash
docker run -d --rm --name analizator-testdb -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:16
cd backend
uv sync
export DATABASE_URL=postgresql+psycopg://postgres:test@localhost:55432/postgres
uv run pytest -q                       # testy (bez Claude API: fałszywy agent i klasyfikator)
uv run ruff check . ../scripts && uv run ruff format --check . ../scripts
uv run mypy                            # --strict
uv run python ../scripts/check_threat_model.py   # każde zagrożenie wskazuje istniejący test
```

Frontend:

```bash
cd frontend
npm ci
npx vitest run
npm run lint && npx tsc --noEmit
```

Dokumentacja (12 sekcji arc42, diagramy Mermaid, linki):

```bash
python3 scripts/check_docs.py          # --skip-mermaid pomija renderowanie diagramów
```

CI (GitHub Actions) uruchamia wszystkie te kroki oraz gitleaks na każdym pull requeście.

### Ewaluacja na żywo (płatna, ręczna)

[`scripts/eval_live.py`](scripts/eval_live.py) analizuje prawdziwym Claude cały korpus
syntetycznych umów. Skrypt kończy się kodem 1, gdy:

- umowa z wstrzyknięciem nie trafi do kwarantanny;
- którakolwiek teza ma cytat spoza dokumentu.

Koszt to w przybliżeniu liczba umów × `AGENT_MAX_BUDGET_USD`. Bez flagi skrypt podaje tylko
szacunek.

```bash
docker compose run --rm -v ./scripts:/scripts:ro -v ./data:/data:ro \
  backend python /scripts/eval_live.py --zgoda-na-koszt
```

## Bezpieczeństwo w skrócie

- **Wstrzyknięcia w umowie.** Heurystyki i klasyfikator działają przed agentem. Trafienie albo
  niedostępny klasyfikator kierują analizę do kwarantanny, a raport jest ukryty do decyzji prawnika.
- **Spotlighting.** Agent czyta umowę wyłącznie przez narzędzie, w znacznikach
  `<untrusted_contract_fragment>`, a prompt deklaruje ich zawartość jako dane.
- **Najmniejsze uprawnienia.** Agent ma tylko 5 własnych narzędzi (odczyt jednej umowy, wzorce,
  zgłaszanie tez, wnioski). Nie ma powłoki, plików ani sieci.
- **Cytaty weryfikowane kodem.** Teza bez dosłownego cytatu jest odrzucana i nie trafia do raportu.
- **Człowiek w pętli.** Oficjalna opinia, zmiana wzorca, eksport i zwolnienie z kwarantanny
  wymagają zatwierdzenia przez prawnika. Każda decyzja trafia do dziennika audytu.
- **Limity.** Liczba kroków, budżet, czas i liczba tez na analizę są konfigurowane w `.env`.
- **Brak wycieku.**
  - Treść umów nie trafia do logów ani komunikatów błędów.
  - Frontend wyświetla tekst wyłącznie jako tekst; obowiązuje nagłówek CSP.
  - Sesja jest w ciasteczku `HttpOnly`.
  - Sekrety są tylko w `.env`, a gitleaks działa w CI.

Szczegóły: [model zagrożeń](docs/threat-model.md).

## Dokumentacja

- [Architektura (arc42)](docs/arc42/README.md) — 12 sekcji z diagramami C4 i sekwencji.
- [Decyzje architektoniczne (ADR)](docs/adr/README.md) — 0001–0008.
- [Model zagrożeń](docs/threat-model.md) — STRIDE i OWASP Top 10 for LLM, każde zagrożenie
  z obroną i testem.
- [Specyfikacja](docs/superpowers/specs/2026-10-15-analizator-umow-design.md) i
  [plan implementacji](docs/superpowers/plans/2026-10-15-analizator-umow.md).

## Struktura repozytorium

```
backend/    app/{domain,agent,services,repo,api,security}, tests/, alembic/
frontend/   src/, tests/, nginx.conf
data/       umowy syntetyczne, warianty z wstrzyknięciami, wzorce klauzul (seed)
docs/       arc42/, adr/, threat-model.md, superpowers/ (spec i plan)
scripts/    check_threat_model.py, check_docs.py, eval_live.py
```
