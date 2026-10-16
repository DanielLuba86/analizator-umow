# 4. Strategia rozwiązania

| Cel jakościowy | Podejście | Gdzie |
|---|---|---|
| Bezpieczeństwo agenta | Obrona warstwowa: detekcja wstrzyknięć przed agentem, spotlighting fragmentów, tylko 5 własnych narzędzi, wnioski zamiast akcji, limity pętli i budżetu | [ADR 0002](../adr/0002-claude-agent-sdk-z-wlasnymi-narzedziami.md), [ADR 0004](../adr/0004-detekcja-wstrzykniec-przed-agentem.md), [ADR 0005](../adr/0005-wnioski-zamiast-narzedzi-wykonawczych.md), [sekcja 8](08-koncepcje-przekrojowe.md) |
| Wiarygodność wyników | Tezy wyłącznie przez narzędzie `submit_finding`; deterministyczny weryfikator cytatów w czystej domenie; odrzucone tezy nie trafiają do raportu | [ADR 0003](../adr/0003-tezy-przez-narzedzie-z-weryfikacja-cytatow.md) |
| Testowalność | Warstwa `domain` bez I/O, test-first; interfejsy `AgentRunner` i `InjectionClassifier` z fałszywymi implementacjami; testy API na prawdziwym PostgreSQL w transakcji wycofywanej | [sekcja 8](08-koncepcje-przekrojowe.md#testowanie) |
| Przejrzystość decyzji | Wnioski `pending_actions` z decyzją prawnika w jednej transakcji ze skutkiem i wpisem audytu | [ADR 0005](../adr/0005-wnioski-zamiast-narzedzi-wykonawczych.md) |
| Prostota uruchomienia | Trzy kontenery w docker-compose (db, backend, frontend); analizy jako zadania w tle procesu backendu | [ADR 0006](../adr/0006-postgresql-w-docker-compose.md), [ADR 0007](../adr/0007-zadania-w-tle-bez-kolejki.md) |

## Kluczowe decyzje technologiczne

- **Backend:** FastAPI + Pydantic. Walidacja na granicy API i `extra="forbid"` w modelach wejścia.
- **Warstwy backendu:** `domain` → `agent` / `repo` → `services` → `api`. Zależności idą tylko
  w dół, a `domain` nie importuje nic z projektu.
- **Frontend:** React bez routera zewnętrznego (router na `location.hash`). Tekst umów i agenta
  jest wyświetlany wyłącznie jako węzły tekstowe Reacta. Style są tylko w pliku CSS (CSP).
- **Sesje:** po stronie serwera, w przeglądarce tylko token w ciasteczku `HttpOnly`
  ([ADR 0008](../adr/0008-sesje-httponly-i-dwie-role.md)).

## Organizacja pracy

Projekt powstał w siedmiu fazach, każda na osobnej gałęzi z PR, przeglądem i zielonym CI:

1. szkielet;
2. domena;
3. baza i auth;
4. agent;
5. API;
6. frontend;
7. dokumentacja.

Specyfikacja i plan są w [`docs/superpowers/`](../superpowers/specs/2026-10-15-analizator-umow-design.md).
