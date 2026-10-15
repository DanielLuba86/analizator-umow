# 0007. Zadania w tle bez kolejki

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Analiza umowy trwa od kilkunastu sekund do kilku minut (limit `AGENT_TIMEOUT_S=300`), więc nie może blokować żądania HTTP. System działa jako jeden kontener backendu w docker-compose, dla jednej kancelarii i niewielkiej liczby równoległych analiz.

## Decyzja

`POST /api/versions/{id}/analyses` zapisuje analizę ze statusem `queued`, zwraca 202 z `analysis_id` i uruchamia `run_analysis` przez FastAPI `BackgroundTasks` w tym samym procesie. Stan analizy żyje wyłącznie w tabeli `analyses`; frontend odpytuje `GET /api/analyses/{id}`. Podwójny start tej samej wersji blokuje baza (blokada wiersza wersji, 409).

## Rozważane opcje

- `BackgroundTasks` w procesie: brak dodatkowej infrastruktury, prosty kod i testy (TestClient wykonuje zadanie przed zwróceniem odpowiedzi). Zadanie ginie przy restarcie procesu; brak ponowień i limitu równoległości.
- Kolejka zadań (Celery/RQ + Redis lub kolejka w PostgreSQL): trwałość, ponowienia, osobne workery. Dodatkowe usługi i złożoność nieuzasadnione w tej skali.
- Osobny proces workera czytający `analyses` ze statusem `queued`: trwałość bez brokera, ale własna pętla, blokady i obsługa awarii do napisania.

## Konsekwencje

- Wdrożenie pozostaje jednym kontenerem backendu.
- Przerwana restartem analiza nie jest wznawiana: przy starcie aplikacja oznacza wszystkie analizy `queued`/`running` jako `failed` (`przerwana_restartem`), więc wersję można przeanalizować ponownie. To zakłada jeden proces backendu — przy wielu workerach sprzątanie przerwałoby cudze analizy.
- Wiele równoległych analiz konkuruje o zasoby jednego procesu; przy większej skali decyzję należy zastąpić kolejką.
