# 11. Ryzyka i dług techniczny

## Ryzyka

| Ryzyko | Wpływ | Łagodzenie / stan |
|---|---|---|
| Nowe techniki prompt injection omijają heurystyki i klasyfikator | Agent może sformułować tezy pod dyktando atakującego | Cytaty muszą istnieć w tekście, agent nie ma narzędzi wykonawczych, decyzje podejmuje prawnik; korpus testowy do rozbudowy |
| Prawdziwy cytat użyty do błędnej tezy | Myląca ocena ryzyka | Raport jest wsparciem, nie opinią; oficjalna opinia wymaga zatwierdzenia prawnika |
| Zmiany w Claude Agent SDK (nazwy pól, zachowanie `allowed_tools`) | Agent mógłby dostać niezamierzone narzędzia albo przestać działać | Wersje zablokowane w `uv.lock`; kontrola zestawu narzędzi przy starcie (fail closed) |
| Koszt API przy wielu równoległych analizach | Wysoki rachunek | Limity na analizę i miękki limit `MAX_ACTIVE_ANALYSES` analiz naraz (429); brak limitu na użytkownika |
| Awaria klasyfikatora | Wszystkie analizy trafiają do kwarantanny | Świadomy wybór fail closed; prawnik może zwolnić raport |

## Dług techniczny

| Pozycja | Skutek | Proponowane rozwiązanie |
|---|---|---|
| Brak limitu analiz na użytkownika | Jeden użytkownik może zająć cały limit globalny | Licznik aktywnych analiz per `started_by` |
| Analizy w `BackgroundTasks` jednego procesu | Brak skalowania poziomego; restart przerywa analizy | Kolejka zadań (np. arq, Celery), gdy wzrośnie ruch |
| Ponowienia wywołań Claude API tylko w domyślnej polityce SDK | Przejściowy błąd kończy analizę statusem `failed` | Własna polityka ponowień z backoffem dla błędów 429/5xx |
| Limit prób logowania tylko w nginx, bez testu automatycznego | Zmiana konfiguracji nginx mogłaby go po cichu wyłączyć | Test E2E na stosie compose w CI |
