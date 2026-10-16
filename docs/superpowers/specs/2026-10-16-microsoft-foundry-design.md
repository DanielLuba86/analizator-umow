# Microsoft Foundry jako dostawca modelu — projekt

Data: 2026-10-16. Uzupełnia spec `2026-10-15-analizator-umow-design.md`.

## Cel

Aplikacja ma działać z modelami Claude wdrożonymi w Microsoft Foundry (Azure), nie tylko przez
Claude API z kluczem Anthropic. Zarówno agent (Claude Agent SDK, który uruchamia CLI Claude Code),
jak i klasyfikator wstrzyknięć (SDK `anthropic`) korzystają z tego samego, wybranego w konfiguracji
dostawcy.

**Kryterium sukcesu:** po ustawieniu `LLM_PROVIDER=foundry`, klucza i nazwy zasobu Foundry analiza
umowy przechodzi przez Foundry bez innych zmian. Wszystkie zabezpieczenia agenta działają jak dla
Claude API: 5 własnych narzędzi, kontrola zestawu narzędzi przy starcie, lista dozwolonych zmiennych
środowiskowych i limity.

## Decyzje użytkownika

- Logowanie do Foundry **kluczem API** (`ANTHROPIC_FOUNDRY_API_KEY` z portalu, sekcja „Endpoints and
  keys”). Entra ID jest poza zakresem.
- Wdrożenia w zasobie Foundry noszą **nazwy identyczne z identyfikatorami modeli** (`claude-opus-5-5`
  dla agenta, `claude-haiku-5-5` dla klasyfikatora). Dzięki temu `AGENT_MODEL` i `CLASSIFIER_MODEL`
  się nie zmieniają, a szacowanie kosztu w Agent SDK (podstawa `AGENT_MAX_BUDGET_USD`) rozpoznaje
  cennik modelu.

## Fakty, na których opiera się projekt

- SDK `anthropic` (1.14): `AsyncAnthropicFoundry(api_key=..., resource=...)` buduje adres
  `https://{resource}.services.ai.azure.com/anthropic/`. Bez argumentów czyta
  `ANTHROPIC_FOUNDRY_API_KEY` i `ANTHROPIC_FOUNDRY_RESOURCE` ze środowiska. Zweryfikowane lokalnie.
- Claude Code (https://code.claude.com/docs/en/microsoft-foundry):
  - `CLAUDE_CODE_USE_FOUNDRY=1` włącza Foundry;
  - `ANTHROPIC_FOUNDRY_RESOURCE` przyjmuje samą nazwę zasobu (URL jest odrzucany);
  - `ANTHROPIC_FOUNDRY_API_KEY` podaje klucz;
  - model to nazwa wdrożenia;
  - dostawca chmurowy ma pierwszeństwo przed `ANTHROPIC_API_KEY`.
- Agent SDK nakłada `options.env` na odziedziczone środowisko procesu (dlatego istnieje lista
  dozwolonych zmiennych w `agent_env`).

## Podejście

Jawny wybór dostawcy ustawieniem `LLM_PROVIDER` (`anthropic` domyślnie, `foundry`). Odrzucone:

- automatyczne wykrywanie po tym, który klucz jest ustawiony: niejednoznaczne, gdy ustawione są
  oba, a błąd konfiguracji cicho zmienia dostawcę;
- `base_url` w kliencie `AsyncAnthropic`: SDK zaleca dedykowanego klienta, a CLI agenta i tak
  wymaga własnych zmiennych.

## Projekt

### Konfiguracja (`backend/app/config.py`, `.env.example`)

- `llm_provider: Literal["anthropic", "foundry"] = "anthropic"`.
- `anthropic_foundry_api_key: SecretStr | None = None`.
- `anthropic_foundry_resource: str | None = None`. Walidacja: pasuje do `^[a-z0-9][a-z0-9-]{1,62}$`,
  w przeciwnym razie błąd walidacji przy wczytaniu ustawień (np. podany URL). Komunikat błędu nie
  zawiera wartości.
- Brak klucza lub zasobu dla wybranego dostawcy **nie** zatrzymuje startu aplikacji. Analiza kończy
  się wtedy powodem `brak_klucza_api`, jak dziś przy pustym `ANTHROPIC_API_KEY`. Aplikacja ma działać
  (logowanie, przegląd umów) także bez skonfigurowanego modelu.
- `AGENT_MODEL` i `CLASSIFIER_MODEL` oznaczają przy Foundry nazwy wdrożeń. Wartości domyślne się nie
  zmieniają.

### Moduł `backend/app/agent/provider.py`

Jedyne miejsce w kodzie, które rozróżnia dostawców.

- `has_credentials(settings: Settings) -> bool`: dla `anthropic` ustawiony `anthropic_api_key`; dla
  `foundry` ustawione `anthropic_foundry_api_key` i `anthropic_foundry_resource`.
- `agent_credentials_env(settings: Settings) -> dict[str, str]`: zmienne dodawane do środowiska
  procesu agenta.
  - `anthropic` → `{"ANTHROPIC_API_KEY": ...}`.
  - `foundry` → `{"CLAUDE_CODE_USE_FOUNDRY": "1", "ANTHROPIC_FOUNDRY_RESOURCE": ...,
    "ANTHROPIC_FOUNDRY_API_KEY": ...}`.
  - Wywoływana tylko, gdy `has_credentials` zwraca `True`.
- `classifier_client(settings: Settings) -> AsyncAnthropic | AsyncAnthropicFoundry`: klient z
  jawnie podanymi danymi z ustawień, nigdy czytanymi pośrednio ze środowiska.

### Runner agenta (`backend/app/agent/sdk_runner.py`)

- `agent_env(settings)` zamiast `agent_env(api_key)`: każda odziedziczona zmienna spoza
  `ENV_ALLOWLIST` jest czyszczona (bez zmian), a potem dokładane jest `agent_credentials_env`.
  Przy Foundry odziedziczone `ANTHROPIC_API_KEY` zostaje więc wyczyszczone, a do agenta trafia tylko
  klucz Foundry.
- `SdkAgentRunner.run`: warunek „brak klucza” to `not has_credentials(settings)`. Powód porażki
  pozostaje `brak_klucza_api`.
- Wszystkie pozostałe opcje są bez zmian: narzędzia, kontrola `init`, limity, katalog roboczy.

### Klasyfikator (`backend/app/agent/classifier.py`)

- `AnthropicClassifier._get_client` korzysta z `classifier_client(settings)`. Przy braku danych
  logowania rzuca `ClassifierUnavailable`, jak dziś, co w efekcie daje kwarantannę (fail closed).

### Dokumentacja

- README: sekcja „Microsoft Foundry”. Opisuje zasób, dwa wdrożenia o nazwach modeli, skąd wziąć
  klucz i nazwę zasobu oraz ustawienia w `.env`.
- Model zagrożeń T15: proces agenta dostaje dane logowania wybranego dostawcy (klucz Anthropic albo
  klucz i nazwę zasobu Foundry). Test w kolumnie T15 obejmuje wariant Foundry.
- arc42 §7 (konfiguracja) i §9 (tabela ADR). Nowy ADR `0009-dostawca-modelu-jako-ustawienie.md`.

## Obsługa błędów

| Sytuacja | Zachowanie |
|---|---|
| `LLM_PROVIDER` spoza listy, zasób w złym formacie | błąd walidacji ustawień przy starcie, bez wartości w komunikacie |
| brak klucza lub zasobu wybranego dostawcy | agent: `failed/brak_klucza_api`; klasyfikator: `ClassifierUnavailable` → kwarantanna |
| zły klucz, brak wdrożenia, Foundry niedostępne | jak dziś przy błędach API: agent `failed/api_error` lub nazwa klasy błędu SDK; klasyfikator → kwarantanna |

## Testy

- `test_config`: domyślny dostawca `anthropic`; wczytanie ustawień Foundry ze środowiska; URL lub
  host w `ANTHROPIC_FOUNDRY_RESOURCE` jest odrzucany; nieznany `LLM_PROVIDER` jest odrzucany.
- `test_provider`:
  - `has_credentials` dla obu dostawców, przy kompletnych i niepełnych danych;
  - `agent_credentials_env` dla obu dostawców;
  - `classifier_client` dla Foundry zwraca `AsyncAnthropicFoundry` z adresem
    `https://<zasób>.services.ai.azure.com/anthropic/`;
  - `classifier_client` dla Anthropic zwraca `AsyncAnthropic`.
- `test_sdk_options`:
  - środowisko agenta przy Foundry: odziedziczone `ANTHROPIC_API_KEY` wyczyszczone, trzy zmienne
    Foundry ustawione, reszta jak dotąd;
  - brak klucza Foundry daje `brak_klucza_api`.
- `test_classifier`: Foundry bez klucza daje `ClassifierUnavailable`.
- Weryfikacja bez kosztów: prawdziwe CLI z `CLAUDE_CODE_USE_FOUNDRY=1`, fałszywym kluczem i nazwą
  zasobu startuje, a `init` zgłasza dokładnie 5 narzędzi `mcp__umowy__*`. Przebieg kończy się
  błędem logowania (`failed`).
- Prawdziwe wywołanie Foundry: test agenta (`--smoke`) na zasobie użytkownika, po jego zgodzie na
  koszt. Nie jest częścią CI.

## Poza zakresem

- Entra ID (managed identity, `az login`).
- Amazon Bedrock, Google Vertex AI.
- Wdrożenia o nazwach innych niż identyfikatory modeli, w tym mapowanie nazw i własny cennik
  (`modelPricing`).
