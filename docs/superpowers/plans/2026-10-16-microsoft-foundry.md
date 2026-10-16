# Microsoft Foundry jako dostawca modelu — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Cel:** po ustawieniu `LLM_PROVIDER=foundry`, klucza i nazwy zasobu agent i klasyfikator łączą się z Claude w Microsoft Foundry. Działanie domyślne (`anthropic`) się nie zmienia.

**Architektura:** nowy moduł `backend/app/agent/provider.py` jako jedyne miejsce rozróżniające dostawców. Runner agenta dokłada do wyczyszczonego środowiska zmienne dostawcy, a klasyfikator bierze z modułu klienta SDK. Konfiguracja przez trzy nowe pola `Settings`.

**Stos:** pydantic-settings, `anthropic` 1.14 (`AsyncAnthropicFoundry`), claude-agent-sdk (CLI Claude Code ze zmienną `CLAUDE_CODE_USE_FOUNDRY`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-microsoft-foundry-design.md`.

## Ograniczenia globalne

- Gałąź `foundry` (spec już na niej jest). Jeden PR, merge po decyzji użytkownika.
- Komunikaty commitów po polsku, zakończone `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Test-first: każda zmiana zachowania ma test, który najpierw pada.
- Po każdym zadaniu z kodem przechodzą: `cd backend && DATABASE_URL=postgresql+psycopg://postgres:test@localhost:55432/postgres uv run pytest -q`, `uv run ruff check . ../scripts`, `uv run ruff format --check . ../scripts` i `uv run mypy`. Baza testowa: `docker run -d --rm --name analizator-testdb -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:16`.
- Bez nowych zależności. `ENV_ALLOWLIST` się nie zmienia.
- Wartości sekretów i nazwa zasobu nie trafiają do logów ani komunikatów błędów.
- Nazwy zmiennych: `LLM_PROVIDER`, `ANTHROPIC_FOUNDRY_API_KEY`, `ANTHROPIC_FOUNDRY_RESOURCE`, `CLAUDE_CODE_USE_FOUNDRY`. Wzorzec nazwy zasobu: `^[a-z0-9][a-z0-9-]{1,62}$`.

## Na co uważać w przeglądzie

1. **Odziedziczony klucz Anthropic przy Foundry.** Jeśli w środowisku procesu jest `ANTHROPIC_API_KEY`, a dostawcą jest Foundry, agent nie może go dostać: wartość musi być pusta. Test w zadaniu 2.
2. **Pusty `ANTHROPIC_FOUNDRY_RESOURCE=` z `.env.example`.** Dzięki `env_ignore_empty` daje `None` i nie wywołuje błędu walidacji formatu. Test w zadaniu 1.
3. **Nazwa zasobu z wielkimi literami lub spacją na końcu.** Zostaje odrzucona przy starcie, z komunikatem bez wartości. Test w zadaniu 1.
4. **`LLM_PROVIDER=Foundry` (wielka litera).** Zostaje odrzucony: `Literal` jest wrażliwy na wielkość liter, a README podaje małe litery. Test w zadaniu 1.
5. **Klasyfikator przy Foundry i kluczu Anthropic ustawionym, ale bez klucza Foundry.** Musi dać `ClassifierUnavailable`, a nie po cichu użyć Claude API. Test w zadaniu 2.

---

### Task 1: Konfiguracja i moduł dostawcy

**Pliki:**
- Modyfikacja: `backend/app/config.py`
- Nowy plik: `backend/app/agent/provider.py`
- Testy: `backend/tests/test_config.py`, `backend/tests/agent/test_provider.py` (nowy)

**Interfejsy (produkuje):**
- `Settings.llm_provider: Literal["anthropic", "foundry"] = "anthropic"`
- `Settings.anthropic_foundry_api_key: SecretStr | None = None`
- `Settings.anthropic_foundry_resource: str | None = None` (walidator pola: wzorzec z ograniczeń globalnych; przy niezgodności `ValueError("ANTHROPIC_FOUNDRY_RESOURCE: podaj samą nazwę zasobu Foundry")`)
- `provider.has_credentials(settings: Settings) -> bool`
- `provider.agent_credentials_env(settings: Settings) -> dict[str, str]` (przy braku danych logowania: `ValueError("brak danych logowania dostawcy")`)
- `provider.classifier_client(settings: Settings) -> anthropic.AsyncAnthropic | anthropic.AsyncAnthropicFoundry` (przy braku danych logowania: ten sam `ValueError`)

- [ ] **Krok 1 (testy, RED):**
  - `test_config.py`:
    - `test_settings_defaults` rozszerzony o `llm_provider == "anthropic"` i oba pola Foundry `None`;
    - `test_foundry_settings_from_env` (`LLM_PROVIDER=foundry`, `ANTHROPIC_FOUNDRY_API_KEY=k`, `ANTHROPIC_FOUNDRY_RESOURCE=moj-zasob`);
    - `test_foundry_resource_rejects_url_host_uppercase_and_trailing_space` (parametryzowany: `https://moj-zasob.services.ai.azure.com/anthropic`, `moj-zasob.services.ai.azure.com`, `Moj-Zasob`, `moj-zasob `; `ValidationError`, a `str(exc)` nie zawiera wartości);
    - `test_empty_foundry_resource_is_unset` (`ANTHROPIC_FOUNDRY_RESOURCE=` → `None`);
    - `test_unknown_or_capitalized_provider_rejected` (`bedrock`, `Foundry`).
  - `test_provider.py`:
    - `test_has_credentials` (parametryzowany: anthropic z kluczem → True, bez → False; foundry z kluczem i zasobem → True, bez klucza → False, bez zasobu → False, z samym `anthropic_api_key` → False);
    - `test_agent_env_anthropic` (`{"ANTHROPIC_API_KEY": "sk-a"}`);
    - `test_agent_env_foundry` (`{"CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_RESOURCE": "moj-zasob", "ANTHROPIC_FOUNDRY_API_KEY": "k-f"}`, bez `ANTHROPIC_API_KEY` nawet przy ustawionym kluczu Anthropic);
    - `test_agent_env_without_credentials_raises`;
    - `test_classifier_client_foundry` (`isinstance(c, anthropic.AsyncAnthropicFoundry)`, `str(c.base_url) == "https://moj-zasob.services.ai.azure.com/anthropic/"`, `c.api_key == "k-f"`);
    - `test_classifier_client_anthropic` (`type(c) is anthropic.AsyncAnthropic`, `c.api_key == "sk-a"`).
  - Ustawienia budować przez `Settings(database_url=URL, ...)` po wyczyszczeniu zmiennych środowiskowych, jak w istniejącym `test_config.py`.
- [ ] **Krok 2:** uruchomić `uv run pytest -q tests/test_config.py tests/agent/test_provider.py`. Oczekiwane: FAIL (brak pól lub modułu).
- [ ] **Krok 3:** implementacja pól i walidatora w `config.py` oraz trzech funkcji w `provider.py`. Klienta budować z jawnie podanymi argumentami (`api_key=`, `resource=`), nigdy z odczytu środowiska w SDK.
- [ ] **Krok 4:** pełny `pytest`, ruff, mypy. Oczekiwane: wszystko zielone.
- [ ] **Krok 5:** commit „Dodaj ustawienia i moduł dostawcy modelu (Anthropic, Microsoft Foundry)”.

### Task 2: Runner agenta i klasyfikator korzystają z dostawcy

**Pliki:**
- Modyfikacja: `backend/app/agent/sdk_runner.py`, `backend/app/agent/classifier.py`
- Testy: `backend/tests/agent/test_sdk_options.py`, `backend/tests/agent/test_classifier.py`

**Interfejsy:** konsumuje `has_credentials`, `agent_credentials_env` i `classifier_client` z zadania 1. Zmienia `sdk_runner.agent_env(api_key: str)` na `agent_env(settings: Settings) -> dict[str, str]`: wyczyszczone zmienne spoza `ENV_ALLOWLIST` plus `agent_credentials_env(settings)`.

- [ ] **Krok 1 (testy, RED):**
  - `test_sdk_options.py`:
    - `test_agent_env_foundry_blanks_inherited_anthropic_key`: środowisko wyczyszczone, potem `PATH`, `ANTHROPIC_API_KEY=z-otoczenia`, `DATABASE_URL=...`; ustawienia Foundry. Oczekiwane `_options(settings).env == {"ANTHROPIC_API_KEY": "", "DATABASE_URL": "", "CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_RESOURCE": "moj-zasob", "ANTHROPIC_FOUNDRY_API_KEY": "k-f"}`;
    - `test_missing_foundry_key_fails_with_brak_klucza` (foundry z zasobem, bez klucza; `("failed", "brak_klucza_api")`);
    - istniejący `test_build_options_requires_api_key` zmienia oczekiwany komunikat na „brak danych logowania”.
  - `test_classifier.py`:
    - `test_foundry_without_foundry_key_is_unavailable` (foundry, ustawiony tylko `anthropic_api_key`; `ClassifierUnavailable`);
    - `test_foundry_classifier_uses_foundry_client` (`AnthropicClassifier(settings)._get_client()` to instancja `AsyncAnthropicFoundry`).
- [ ] **Krok 2:** uruchomić `uv run pytest -q tests/agent`. Oczekiwane: nowe testy FAIL.
- [ ] **Krok 3:** implementacja:
  - `build_options`: `if not has_credentials(settings): raise ValueError("brak danych logowania dostawcy")`, potem `env=agent_env(settings)`;
  - `SdkAgentRunner.run`: warunek `not has_credentials(self._settings)` → `NO_API_KEY`;
  - `AnthropicClassifier._get_client`: przy braku danych logowania `ClassifierUnavailable("brak_klucza")`, w przeciwnym razie `classifier_client(settings)`;
  - usunąć bezpośredni import i użycie `anthropic.AsyncAnthropic` w `classifier.py`, jeśli przestaną być potrzebne.
- [ ] **Krok 4:** pełny `pytest`, ruff, mypy. Oczekiwane: zielone.
- [ ] **Krok 5 (weryfikacja bez kosztów):** sonda ze skryptu w scratchpadzie (jak próba w PR #9): `SdkAgentRunner` z ustawieniami `llm_provider="foundry"`, `anthropic_foundry_api_key="fałszywy"`, `anthropic_foundry_resource="nie-istnieje-analizator"`, `agent_timeout_s=60` i atrapą narzędzi. Oczekiwane: `runner.init_tools` to dokładnie 5 nazw `mcp__umowy__*`, a wynik ma status `failed`. Wynik zapisać w opisie PR.
- [ ] **Krok 6:** commit „Łącz agenta i klasyfikator z wybranym dostawcą modelu”.

### Task 3: Dokumentacja

**Pliki:** `.env.example`, `README.md`, `docs/threat-model.md` (T15), `docs/adr/0009-dostawca-modelu-jako-ustawienie.md` (nowy, format jak 0007), `docs/arc42/09-decyzje.md` (wiersz 0009), `docs/arc42/07-wdrozenie.md` (lista konfiguracji).

- [ ] **Krok 1:** `.env.example`: pod `ANTHROPIC_API_KEY=` dodać `LLM_PROVIDER=anthropic` z komentarzem `# anthropic | foundry`, a pod nim `ANTHROPIC_FOUNDRY_API_KEY=` i `ANTHROPIC_FOUNDRY_RESOURCE=` z komentarzem „tylko dla LLM_PROVIDER=foundry; sama nazwa zasobu, nie URL”.
- [ ] **Krok 2:** README, sekcja „Microsoft Foundry” po konfiguracji `.env`:
  - zasób Foundry z dwoma wdrożeniami o nazwach `claude-opus-5-5` i `claude-haiku-5-5` (inne nazwy psują szacowanie kosztu, więc i `AGENT_MAX_BUDGET_USD`);
  - klucz i nazwa zasobu z „Endpoints and keys”;
  - trzy zmienne w `.env`;
  - informacja, że koszt rozlicza Microsoft według stawek Claude API.
- [ ] **Krok 3:** T15: w kolumnie obrony „Proces agenta dostaje dane logowania wybranego dostawcy (klucz Claude API albo klucz i nazwę zasobu Foundry)”; do kolumny testów dopisać `tests/agent/test_sdk_options.py::test_agent_env_foundry_blanks_inherited_anthropic_key`. ADR 0009 (kontekst, decyzja `LLM_PROVIDER`, odrzucone opcje ze specu, konsekwencje). Wiersz w arc42 §9. W §7 punkt „dostawca modelu (`LLM_PROVIDER`) i jego dane logowania”.
- [ ] **Krok 4:** `python3 scripts/check_docs.py` → `błędów: 0`; `cd backend && uv run python ../scripts/check_threat_model.py` → `błędów: 0`.
- [ ] **Krok 5:** commit „Opisz konfigurację Microsoft Foundry”.

### Task 4: Weryfikacja końcowa i PR

- [ ] **Krok 1:** frontend bez zmian, ale dla pewności `cd frontend && npx vitest run`.
- [ ] **Krok 2:** przegląd całej gałęzi przez świeżego recenzenta, poprawki Critical i Important.
- [ ] **Krok 3:** push, PR „Obsługa Microsoft Foundry”, zielone CI. Merge po decyzji użytkownika. Prawdziwy test na Foundry (`--smoke`) dopiero na zasobie użytkownika, za jego zgodą.
