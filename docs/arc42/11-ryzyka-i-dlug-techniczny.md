# 11. Ryzyka i dług techniczny

## Ryzyka

| Ryzyko | Wpływ | Łagodzenie / stan |
|---|---|---|
| Nowe techniki prompt injection omijają heurystyki i klasyfikator | Agent może sformułować tezy pod dyktando atakującego | Cytaty muszą istnieć w tekście, agent nie ma narzędzi wykonawczych, decyzje podejmuje prawnik; korpus testowy do rozbudowy |
| Prawdziwy cytat użyty do błędnej tezy | Myląca ocena ryzyka | Raport jest wsparciem, nie opinią; oficjalna opinia wymaga zatwierdzenia prawnika |
| Zmiany w Claude Agent SDK (nazwy pól, zachowanie `allowed_tools`) | Agent mógłby dostać niezamierzone narzędzia albo przestać działać | Wersje zablokowane w `uv.lock`; kontrola zestawu narzędzi przy starcie (fail closed) |
| Koszt API przy wielu równoległych analizach | Wysoki rachunek | Limity na analizę, ścisły limit `MAX_ACTIVE_ANALYSES_PER_USER` na osobę i miękki limit `MAX_ACTIVE_ANALYSES` analiz naraz (429) |
| Awaria klasyfikatora | Wszystkie analizy trafiają do kwarantanny | Świadomy wybór fail closed; prawnik może zwolnić raport |

## Dług techniczny

| Pozycja | Skutek | Proponowane rozwiązanie |
|---|---|---|
| Analizy w `BackgroundTasks` jednego procesu | Brak skalowania poziomego; restart przerywa analizy | Kolejka zadań (np. arq, Celery), gdy wzrośnie ruch |
| Ponowienia wywołań Claude API tylko wewnątrz jednego przebiegu (`CLASSIFIER_MAX_RETRIES`, `AGENT_MAX_RETRIES`) | Awaria dłuższa niż ponowienia kończy analizę kwarantanną (klasyfikator) albo statusem `failed` (agent); trzeba ręcznie uruchomić analizę ponownie albo zwolnić kwarantannę | Automatyczne ponowne uruchomienie analizy po awarii, z rozwiązaniem duplikatów tez z pierwszego przebiegu |
