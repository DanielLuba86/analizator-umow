# Odłożone poprawki — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Cel:** domknąć drobne uwagi z przeglądów faz 1–7, które zapisano jako odłożone w `.superpowers/sdd/2026-10-15-analizator-umow/progress.md` i które według przeglądu kodu z 2026-10-16 nadal występują w `main` (`e0728e9`).

**Architektura:** bez nowych komponentów. Jedna nowa migracja (`0002`), jedno middleware HTTP (rozmiar ciała żądania i nagłówek Origin), poprawki punktowe w istniejących modułach. Wszystko na jednej gałęzi `poprawki-odlozone`, jeden PR.

**Stos:** FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16, claude-agent-sdk, React + TypeScript + Vitest, nginx, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-15-analizator-umow-design.md`. Poprzedni plan: `docs/superpowers/plans/2026-10-15-analizator-umow.md`.

## Ograniczenia globalne

- Komunikaty commitów po polsku, zakończone linią `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Każda zmiana zachowania jest test-first (RED → GREEN). Zmiany wyłącznie w konfiguracji lub dokumentacji weryfikuje się poleceniem z kroku weryfikacji.
- Po każdym zadaniu przechodzą: `cd backend && uv run ruff check . ../scripts && uv run ruff format --check . ../scripts && uv run mypy && uv run pytest -q` oraz `cd frontend && npm run lint && npx tsc --noEmit && npx vitest run`.
- Bez nowych zależności runtime. Wyjątek: obraz `nginxinc/nginx-unprivileged`.
- Limit tekstu umowy pozostaje `max_contract_chars = 200_000` (`backend/app/config.py`).
- Odpowiedzi błędów mają nadal format problem+json z `request_id` i bez treści umowy.

## Poza zakresem (z uzasadnieniem)

- **A4c** `uv run mypy .` (z kropką) pada na zduplikowanych `conftest`. Obsługiwane wywołanie to `uv run mypy` (CI, `packages=["app"]`), testy nie są typowane.
- **B10c** `request_action` wołane przez agenta bez obsługi wyścigu. Na jedną analizę przypada jeden agent, więc wyścig nie występuje.
- **B12** zawieszone analizy po restarcie zostały już naprawione (`services/recovery.py`).
- **A15b** katalog tymczasowy z `build_options` sprząta tylko `run`. Wystarczy komentarz w docstringu, bo `build_options` nie jest wołane nigdzie indziej.

## Na co uważać w przeglądzie

1. **Origin za nginx.** Przeglądarka wysyła `Origin: http://localhost:8080`, a nginx przekazuje `Host $host`, czyli bez portu. Bez zmiany na `$http_host` każde logowanie przez UI dostanie 403. Test w zadaniu 5, sprawdzenie E2E w zadaniu 8.
2. **Przejścia statusów analizy.** Nowa walidacja w `set_status` nie może zablokować odzyskiwania po restarcie (`fail_interrupted`), zatwierdzenia ani odrzucenia kwarantanny. Testy w zadaniu 2 pokrywają każdą z tych ścieżek.
3. **Agent z listą dozwolonych zmiennych środowiskowych.** CLI Claude musi nadal wystartować i zgłosić dokładnie 5 narzędzi `mcp__umowy__*`. Test z fałszywym kluczem w zadaniu 3.
4. **nginx bez roota.** Port w kontenerze zmienia się z 80 na 8080. Mapowanie w compose, healthchecki i README muszą to uwzględnić. Sprawdzenie na świeżym klonie w zadaniu 8.
5. **Rate limit logowania** liczy żądania per IP. Za nginx backend widzi IP proxy, więc limit musi być w nginx, nie w aplikacji. Sprawdzenie w zadaniu 8: 20 szybkich logowań daje 429.

---

### Task 1: Infrastruktura i CI

Pozycje: B1, B2, B3, B5, B6, B7, B11 (część nginx), B20, C11.

**Pliki:** `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`, `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml`, `.github/dependabot.yml` (nowy), `scripts/check_docs.py`, `backend/tests/scripts/test_checkers.py`, `README.md`.

- [x] **Krok 1:** `backend/Dockerfile`: `ghcr.io/astral-sh/uv:<wersja>@sha256:<digest>` (wersja zgodna z `uv --version` używanym w CI; digest z `docker buildx imagetools inspect`).
- [x] **Krok 2:** `frontend/Dockerfile`: `FROM nginxinc/nginx-unprivileged:1.27-alpine`; `nginx.conf`: `listen 8080;`, `proxy_set_header Host $http_host;`, `client_max_body_size 1m;`, na początku pliku `limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m;`, osobna `location = /api/auth/login { limit_req zone=login burst=5 nodelay; limit_req_status 429; proxy_pass … }` (te same nagłówki proxy co `/api/`).
- [x] **Krok 3:** `docker-compose.yml`: frontend `"8080:8080"`; usunąć `ports` backendu (B5).
- [x] **Krok 4:** `.env.example`: komentarz nad `DATABASE_URL`, że hasło musi być równe `POSTGRES_PASSWORD`. README: usunąć zdanie o `http://localhost:8000`; dodać akapit, że za TLS ustawia się `COOKIE_SECURE=true` (B20).
- [x] **Krok 5:** `ci.yml`: `concurrency: {group: ci-${{ github.ref }}, cancel-in-progress: true}`, `timeout-minutes: 15` na każdym jobie, `enable-cache: true` w `setup-uv`. `.github/dependabot.yml`: ekosystemy `github-actions` (/), `uv` (/backend), `npm` (/frontend), `docker` (/backend, /frontend), interwał `weekly`.
- [x] **Krok 6 (test):** `test_checkers.py::test_mermaid_timeout_reported_as_error`: podmieniony `subprocess.run` rzuca `TimeoutExpired`, a wynik `check_docs` zawiera błąd z nazwą pliku i słowem „timeout”. RED.
- [x] **Krok 7:** `scripts/check_docs.py`: `subprocess.run(..., timeout=120)`, `TimeoutExpired` → błąd. GREEN.
- [x] **Krok 8 (weryfikacja):** `docker compose up --build -d`; `curl -s localhost:8080/api/health` → `{"status":"ok"}`; `curl -s localhost:8000` → connection refused; `docker compose exec frontend id -u` ≠ 0.
- [x] **Krok 9:** commit „Przypnij obrazy, uruchom nginx bez roota i uszczelnij CI”.

### Task 2: Schemat i repozytoria

Pozycje: B8, B9, B10 (bez c), A10 (repo), A11 (kolumna), B17 (repo).

**Pliki:** `backend/alembic/versions/0002_indeksy_i_powod_agenta.py` (nowy), `backend/alembic/env.py`, `backend/app/repo/models.py`, `backend/app/repo/analyses.py`, `backend/app/repo/templates.py`, `backend/app/security/sessions.py`, `backend/tests/repo/test_schema.py`, `backend/tests/repo/test_repos.py`, `backend/tests/repo/test_concurrency.py`.

**Interfejsy (produkuje):**
- `claim_analysis(session, analysis_id: int) -> bool`: `UPDATE analyses SET status='running', started_at=now() WHERE id=:id AND status='queued'`, zwraca `rowcount == 1`.
- `set_status(...)` rzuca `InvalidTransition(old, new)` (nowa klasa w `repo/analyses.py`) poza dozwolonymi przejściami: `queued→{running, failed}`, `running→{done, quarantined, failed}`, `quarantined→{done, failed}`. Najpierw sprawdzić w kodzie, jaki status ustawia odrzucenie kwarantanny, i dopisać je do mapy, jeśli różni się od podanych.
- kolumna `analyses.agent_reason: str | None` (TEXT NULL).
- `delete_expired_sessions(session, now: datetime) -> int` w `security/sessions.py`.

- [x] **Krok 1 (testy, RED):** `test_claim_analysis_only_from_queued` (drugi `claim` → `False`); `test_set_status_rejects_done_to_running`; `test_recovery_and_quarantine_decisions_still_allowed` (running→failed, quarantined→done, quarantined→failed); `test_add_template_version_concurrent` w `test_concurrency.py` (dwa połączenia, obie wersje zapisane z numerami 1 i 2, bez `IntegrityError`); `test_delete_expired_sessions_keeps_live`; `test_child_fk_columns_indexed` (inspektor SQLAlchemy: indeks na `findings.analysis_id`, `rejected_claims.analysis_id`, `analyses.version_id`, `fragments.version_id`, `comparisons.version_a`, `comparisons.version_b`, `exports.action_id`, `sessions.user_id`, plus każda inna kolumna FK bez indeksu, którą znajdzie inspektor); B9: test kaskady filtruje po id usuniętej umowy, a druga umowa utworzona w teście zostaje nietknięta.
- [x] **Krok 2:** migracja `0002`: indeksy `ix_<tabela>_<kolumna>`, kolumna `agent_reason`; `downgrade` odwraca. `models.py`: `index=True` na tych kolumnach, jawne `ondelete="CASCADE"` w `comparisons.version_a/b` i `exports.action_id`, `agent_reason`. `env.py`: `engine_from_config(..., poolclass=pool.NullPool)`.
- [x] **Krok 3:** `add_template_version`: `SELECT … FOR UPDATE` na wierszu klauzuli (szablonu nadrzędnego) przed `max+1`; usunąć zbędne `or 0`.
- [x] **Krok 4 (GREEN):** pełny `pytest`, `alembic upgrade head && alembic downgrade base && alembic upgrade head` na czystej bazie testowej.
- [x] **Krok 5:** commit „Dodaj indeksy kluczy obcych, walidację przejść statusu i blokadę wersji wzorca”.

### Task 3: Agent i serwis analizy

Pozycje: A5–A16 (bez A15b), A10/A11 (serwis).

**Pliki:** `backend/app/agent/tools.py`, `fake_runner.py`, `sdk_runner.py`, `backend/app/services/analysis.py`, `backend/tests/agent/*`, `backend/tests/services/*`.

**Interfejsy:** konsumuje `claim_analysis`, `agent_reason` (zadanie 2). Produkuje `TOOL_NAMES: tuple[str, ...]` w `tools.py` (jedyne źródło; `fake_runner` i `sdk_runner` importują) oraz `run_analysis(analysis_id: int, *, request_id: str | None = None)` (używane w zadaniu 5).

- [x] **Krok 1 (testy, RED):**
  - `test_run_analysis_twice_does_not_duplicate_findings`: drugi `run_analysis` nic nie robi, bo `claim` zwraca `False`.
  - `test_quarantine_keeps_agent_reason`: `analyses.reason == <powód kwarantanny>`, `agent_reason == outcome.reason`.
  - `test_integrity_error_other_than_fk_is_not_template_hint`.
  - `test_over_limit_invalid_claim_recorded_as_rejected_with_validation_reason`: nieprawidłowa teza ponad limitem trafia do `rejected_claims` z powodem walidacji; prawidłowa ponad limitem zwraca `limit_tez`, jak dotąd.
  - `test_submit_finding_too_short_quote`.
  - `test_list_fragments_ignores_other_versions`.
  - Usunąć tautologię w `test_tools.py:84`, zastąpić konkretną asercją.
  - `test_fake_runner_tool_timeout_is_failure_not_budget` (narzędzie rzuca `TimeoutError` → `failed`, reason `TimeoutError`).
  - `test_unknown_tool_does_not_consume_turn`.
  - `test_mismatched_tool_args_fail_with_type_error`.
  - `test_result_before_init_is_brak_init` (dodać wartość `brak_init` do enumu powodów, jeśli jej nie ma).
  - `test_timeout_records_turns_seen` (liczba `AssistantMessage` przed timeoutem; koszt zostaje 0, bo SDK podaje koszt tylko w `ResultMessage`, co trzeba zapisać w komentarzu).
  - `test_missing_api_key_fails_with_brak_klucza` (`failed`, reason `brak_klucza_api`, bez `ValueError`).
  - `test_agent_env_blanks_everything_but_allowlist`: każdy klucz z `os.environ` poza `{"PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR"}` ma wartość `""`, a `ANTHROPIC_API_KEY` jest ustawiony.
  - `test_closed_options_not_shared`: mutacja zwróconego słownika nie wpływa na kolejne wywołanie.
  - `test_run_analysis_binds_request_id` (structlog `capture_logs`: wpisy z analizy mają `request_id`).
- [x] **Krok 2:** implementacja. A5: `isinstance(e.orig, psycopg.errors.ForeignKeyViolation)` → podpowiedź o szablonie, inne błędy propagują. A14: w transakcji count+insert najpierw `SELECT … FROM analyses WHERE id=:id FOR UPDATE`. A15: `_CLOSED` jako `MappingProxyType` lub kopia; narzędzia wołają repo przez `await asyncio.to_thread(...)`. A16: zastąpić regex `_INHERITED_SECRET` listą dozwolonych z testu.
- [x] **Krok 3 (GREEN):** pełny `pytest`.
- [x] **Krok 4 (weryfikacja, bez kosztów):** powtórzyć próbę inicjalizacji z fałszywym kluczem (procedura Task 4.3 z `progress.md`). Komunikat `init` musi zawierać dokładnie 5 narzędzi `mcp__umowy__*`, a wynik to `failed/api_error`.
- [x] **Krok 5:** commit „Uszczelnij agenta: lista dozwolonych zmiennych, jednokrotny start analizy, dokładniejsze powody błędów”.

### Task 4: Domena

Pozycje: A1, A2, A3, A4 (a, b, d).

**Pliki:** `backend/app/domain/quotes.py`, `injection.py`, `diff.py`, `backend/tests/domain/*`.

- [x] **Krok 1 (testy, RED):** `test_negative_min_len_rejected` (`ValueError`); `test_nfc_text_nfd_quote` i `test_nfd_text_nfc_quote` (oba kierunki, poprawione nazwy zmiennych); `test_case_and_typography_must_match` sprawdza `exc.value.reason`; `test_if_double_space_you_are_now_not_flagged`, `test_if_comma_you_are_now_not_flagged`, `test_you_are_now_still_flagged`; `test_diff_fragments_duplicate_labels_rejected` (`ValueError`; etykiety są unikalne zgodnie z R7, więc duplikat oznacza błąd wywołującego); `test_diff_findings_returns_original_quote`.
- [x] **Krok 2:** `_HINTS: Mapping[RejectReason, str]`; walidacja `min_len >= 0`. W `injection.py` usunąć lookbehind i odrzucać trafienie, gdy `re.search(r"\bif[\s,]*$", text[max(0, start - 20):start], re.IGNORECASE)`. A3: `bisect_right` po posortowanych `start` fragmentów. A4: rozpakowanie krotki z `normalize_whitespace` zamiast indeksu `[0]`.
- [x] **Krok 3 (GREEN)** i commit „Popraw heurystykę wstrzyknięć i walidację cytatów”.

### Task 5: API

Pozycje: B4, B11 (aplikacja), B13, B14, B15, B16, B17 (wywołanie), B18, B19 (wywołanie), B21, B22, B23 (backend).

**Pliki:** `backend/app/config.py`, `backend/app/main.py`, `backend/app/api/middleware.py` (nowy), `deps.py`, `auth.py`, `actions.py`, `contracts.py`, `analyses.py`, `backend/app/repo/actions.py`, `backend/tests/api/*`, `backend/tests/test_config.py` (nowy).

**Interfejsy (produkuje):** `GET /api/actions?analysis_id=<int>` (opcjonalny, łączy się z `status`); `Settings.max_body_bytes: int = 1_048_576`, `Settings.max_active_analyses: int = 5`.

- [x] **Krok 1 (testy, RED):**
  - `test_settings_defaults` (przypina obecne wartości domyślne, w tym `cookie_secure`) i `test_settings_env_override`.
  - `test_body_over_limit_413_before_parsing`: `Content-Length` > `max_body_bytes` → 413 problem+json.
  - `test_post_with_foreign_origin_403`, `test_post_with_matching_origin_ok` (`Origin: http://localhost:8080`, `Host: localhost:8080`), `test_post_without_origin_ok`, `test_get_with_foreign_origin_ok`.
  - `test_api_errors_do_not_share_traceback` (dwa kolejne 401 to różne obiekty wyjątków).
  - `test_existing_pending_action_returns_200`, `test_new_action_returns_201`.
  - `test_template_with_rejection_422`, `test_template_for_non_wzorzec_422`.
  - `test_login_deletes_expired_sessions`.
  - `test_global_active_analyses_cap_429` (przy `max_active_analyses=1` druga analiza innej wersji → 429).
  - `test_export_headers` (`X-Content-Type-Options: nosniff`, `Cache-Control: no-store`).
  - `test_list_actions_filter_by_analysis`.
  - `test_background_analysis_logs_request_id`.
- [x] **Krok 2:** implementacja. Middleware w `api/middleware.py`: limit rozmiaru i sprawdzenie Origin dla `POST`/`PUT`/`PATCH`/`DELETE` (porównanie `urlsplit(origin).netloc == request.headers["host"]`; brak `Origin` przepuszcza). B13: singletony zamienione na funkcje-fabryki. B14: `threading.Lock` w `get_session_factory`. Analizę w tle wywołuje się z `request_id`.
- [x] **Krok 3 (GREEN):** pełny `pytest`. Uruchomić `npx vitest run`, bo frontend może zakładać 201.
- [x] **Krok 4:** commit „Dodaj limit rozmiaru żądania, kontrolę Origin i globalny limit analiz w API”.

### Task 6: Frontend

Pozycje: C1–C9, C4 (przełączenie na filtr z zadania 5).

**Pliki:** `frontend/src/pages/ContractPage.tsx`, `frontend/src/document/RiskReport.tsx`, `DocumentView.tsx`, `frontend/src/App.tsx`, `frontend/src/pages/NotFoundPage.tsx` (nowy), `frontend/src/pages/textFile.ts`, `frontend/eslint.config.js`, `frontend/src/styles.css`, `frontend/tests/*`.

- [x] **Krok 1 (testy, RED):**
  - `quarantine banner has refresh button that reloads analysis`.
  - `analysis error is announced` (`role="alert"`).
  - `repeated click on overlapping highlight cycles findings` (kolejne kliknięcia: id1 → id2 → id1).
  - `actions are fetched for the analysis only` (URL zawiera `?analysis_id=`).
  - `unknown route shows not found` oraz testy `matchRoute` w `router.test.ts`: każda trasa i trasa nieznana.
  - `rejects file larger than limit before reading` (`file.size > 800_000`, `text` nie jest wołane) i `rejects text longer than 200000 chars`.
  - Poprawić asercję „Wersja 2”, żeby dotyczyła załadowanej wersji, nie linku w nawigacji.
  - `AnalysisRedirect` (przekierowanie na najnowszą analizę).
  - `asystent typing #/approvals sees no approvals`.
  - `errorMessage without request id`.
  - `double click submits once` (logowanie, decyzja, start analizy).
- [x] **Krok 2:** implementacja. Stała `MAX_CONTRACT_CHARS = 200_000`, próg bajtów `4 * MAX_CONTRACT_CHARS`. ESLint: `"react/forbid-dom-props": ["error", { forbid: ["style"] }]`.
- [x] **Krok 3 (GREEN):** `npm run lint && npx tsc --noEmit && npx vitest run`.
- [x] **Krok 4:** commit „Dodaj odświeżanie kwarantanny, stronę 404 i limit rozmiaru pliku we frontendzie”.

### Task 7: Dokumentacja

Pozycje: C10 oraz dokumentacja nowych zabezpieczeń.

**Pliki:** `docs/threat-model.md`, `docs/arc42/07-wdrozenie.md`, `08-koncepcje-przekrojowe.md`, `11-ryzyka-i-dlug-techniczny.md`.

- [x] **Krok 1:** T18 linkuje `api/contracts.py`, `repo/analyses.py` i middleware. Nowe obrony z linkami do testów z zadań 1–6: rate limit logowania (nginx, `ci:` niedostępne, więc opis ręcznej weryfikacji), Origin, globalny limit analiz, lista dozwolonych zmiennych agenta. Usunąć ryzyko szczątkowe T15 dotyczące listy zabronionych. arc42 §7: nginx bez roota na porcie 8080, backend niedostępny z hosta. §11: usunąć spłacone pozycje długu.
- [x] **Krok 2 (weryfikacja):** `python3 scripts/check_docs.py` → 0 błędów; `cd backend && uv run python ../scripts/check_threat_model.py` → 0 błędów.
- [x] **Krok 3:** commit „Zaktualizuj model zagrożeń i arc42 po poprawkach”.

### Task 8: Weryfikacja końcowa i PR

- [x] **Krok 1:** świeży klon, README krok po kroku z nowym `COMPOSE_PROJECT_NAME` (nowy wolumen). Playwright: asystent wgrywa `jawne_polecenie.md` → kwarantanna → prawnik zatwierdza → asystent klika „Odśwież” → 2 podświetlenia. Logowanie przez UI działa (Origin za nginx). 20 szybkich `POST /api/auth/login` → co najmniej jedno 429.
- [x] **Krok 2:** przegląd całej gałęzi, poprawki, wpis w `progress.md`.
- [x] **Krok 3:** PR „Odłożone poprawki z przeglądów faz 1–7”, CI zielone. Merge dopiero po decyzji użytkownika.
