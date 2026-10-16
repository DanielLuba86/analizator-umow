# 0009. Dostawca modelu jako ustawienie

- Status: Przyjęta
- Data: 2026-10-16

## Kontekst

Agent (Claude Agent SDK uruchamiający CLI Claude Code) i klasyfikator wstrzyknięć (SDK `anthropic`) łączyły się wyłącznie z Claude API kluczem `ANTHROPIC_API_KEY`. Kancelaria może mieć dostęp do Claude przez Microsoft Foundry w ramach subskrypcji Azure. CLI wybiera Foundry zmiennymi środowiskowymi (`CLAUDE_CODE_USE_FOUNDRY`, `ANTHROPIC_FOUNDRY_RESOURCE`, `ANTHROPIC_FOUNDRY_API_KEY`), a SDK `anthropic` — osobną klasą klienta (`AsyncAnthropicFoundry`).

## Decyzja

Dostawcę wybiera ustawienie `LLM_PROVIDER` (`anthropic` domyślnie albo `foundry`). Tylko moduł [`agent/provider.py`](../../backend/app/agent/provider.py) rozróżnia dostawców: podaje zmienne dla procesu agenta i klienta dla klasyfikatora, zawsze z danych w ustawieniach, nigdy z odczytu środowiska. Lista dozwolonych zmiennych agenta się nie zmienia, więc przy Foundry odziedziczony klucz Claude API jest czyszczony. Logowanie do Foundry kluczem API; wdrożenia noszą nazwy identyczne z identyfikatorami modeli.

## Rozważane opcje

- Jawne ustawienie `LLM_PROVIDER`: jednoznaczne, łatwe do przetestowania, jedna dodatkowa zmienna w `.env`.
- Wykrywanie dostawcy po tym, który klucz jest ustawiony: wygodne, ale niejednoznaczne przy dwóch kluczach, a błąd konfiguracji cicho zmienia dostawcę.
- `base_url` w zwykłym kliencie `AsyncAnthropic`: SDK zaleca dedykowanego klienta, a CLI agenta i tak wymaga własnych zmiennych.

## Konsekwencje

- Zabezpieczenia agenta (5 własnych narzędzi, kontrola `init`, lista dozwolonych zmiennych, limity) działają bez zmian u obu dostawców.
- Entra ID, Amazon Bedrock i Google Vertex AI nie są obsługiwane; dodanie ich oznacza nową gałąź w `agent/provider.py` i testy.
- Wdrożenia o innych nazwach niż identyfikatory modeli psują szacowanie kosztu w Agent SDK, a z nim limit `AGENT_MAX_BUDGET_USD`.
- Błędna, ale poprawnie zapisana nazwa zasobu kończy analizę dopiero po `AGENT_TIMEOUT_S` (CLI ponawia połączenie).
