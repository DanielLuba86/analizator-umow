# 9. Decyzje architektoniczne

Decyzje są zapisane jako krótkie ADR w formacie MADR w katalogu [`docs/adr/`](../adr/README.md).

| Nr | Decyzja | Najważniejsza konsekwencja |
|---|---|---|
| [0001](../adr/0001-python-fastapi-i-react.md) | Backend w Pythonie (FastAPI), frontend w React | Agent SDK i backend w jednym procesie i języku; dwa ekosystemy narzędzi w CI |
| [0002](../adr/0002-claude-agent-sdk-z-wlasnymi-narzedziami.md) | Claude Agent SDK wyłącznie z własnymi narzędziami MCP in-process | Agent nie ma powłoki, plików ani sieci; zestaw narzędzi weryfikowany przy starcie |
| [0003](../adr/0003-tezy-przez-narzedzie-z-weryfikacja-cytatow.md) | Tezy tylko przez narzędzie z deterministyczną weryfikacją cytatów | Raport zawiera wyłącznie tezy z dosłownym cytatem; parafrazy są odrzucane |
| [0004](../adr/0004-detekcja-wstrzykniec-przed-agentem.md) | Detekcja wstrzyknięć jako osobny etap przed agentem | Trafienie lub niedostępny klasyfikator → kwarantanna do decyzji prawnika |
| [0005](../adr/0005-wnioski-zamiast-narzedzi-wykonawczych.md) | Wnioski `pending_actions` zamiast narzędzi wykonawczych | Akcje wysokiego ryzyka wymagają zatwierdzenia; decyzja, skutek i audyt w jednej transakcji |
| [0006](../adr/0006-postgresql-w-docker-compose.md) | PostgreSQL w docker-compose | Transakcje i blokady wierszy; testy na prawdziwym Postgresie |
| [0007](../adr/0007-zadania-w-tle-bez-kolejki.md) | Zadania w tle bez zewnętrznej kolejki | Prosty deployment; jedna instancja backendu, sprzątanie przerwanych analiz przy starcie |
| [0008](../adr/0008-sesje-httponly-i-dwie-role.md) | Sesje po stronie serwera w ciasteczku HttpOnly i dwie role | Brak tokenów w JavaScript; unieważnienie sesji po stronie serwera |

Mniejsze decyzje podjęte w trakcie implementacji (np. kształt odpowiedzi API, widoczność raportu,
router frontendu) są opisane w opisach pull requestów poszczególnych faz.
