# 11. Ryzyka i dług techniczny

## Ryzyka

| Ryzyko | Wpływ | Łagodzenie / stan |
|---|---|---|
| Nowe techniki prompt injection omijają heurystyki i klasyfikator | Agent może sformułować tezy pod dyktando atakującego | Cytaty muszą istnieć w tekście, agent nie ma narzędzi wykonawczych, decyzje podejmuje prawnik; korpus testowy do rozbudowy |
| Prawdziwy cytat użyty do błędnej tezy | Myląca ocena ryzyka | Raport jest wsparciem, nie opinią; oficjalna opinia wymaga zatwierdzenia prawnika |
| Zmiany w Claude Agent SDK (nazwy pól, zachowanie `allowed_tools`) | Agent mógłby dostać niezamierzone narzędzia albo przestać działać | Wersje zablokowane w `uv.lock`; kontrola zestawu narzędzi przy starcie (fail closed) |
| Koszt API przy wielu równoległych analizach | Wysoki rachunek | Limity na analizę; brak globalnego limitu — dług poniżej |
| Awaria klasyfikatora | Wszystkie analizy trafiają do kwarantanny | Świadomy wybór fail closed; prawnik może zwolnić raport |

## Dług techniczny

| Pozycja | Skutek | Proponowane rozwiązanie |
|---|---|---|
| Brak globalnego limitu aktywnych analiz i limitu na użytkownika | Możliwy DoS kosztowy | Licznik aktywnych analiz w `create_analysis`, 429 po przekroczeniu |
| Brak limitu prób logowania | Zgadywanie haseł | Licznik nieudanych prób w bazie lub reverse proxy |
| Analizy w `BackgroundTasks` jednego procesu | Brak skalowania poziomego; restart przerywa analizy | Kolejka zadań (np. arq, Celery), gdy wzrośnie ruch |
| Ponowienia wywołań Claude API tylko w domyślnej polityce SDK | Przejściowy błąd kończy analizę statusem `failed` | Własna polityka ponowień z backoffem dla błędów 429/5xx |
| Wygasłe sesje usuwane tylko przy próbie użycia | Rosnąca tabela `sessions` | Okresowe sprzątanie |
| Brak sprawdzania `Origin`/`Referer` | Mniej obrony w głąb przed CSRF (`SameSite=Strict` pokrywa przypadek główny) | Middleware sprawdzający `Origin` dla metod modyfikujących |
| Eksport bez nagłówków `nosniff` i `Cache-Control: no-store` | Raport może zostać w cache przeglądarki | Dodanie nagłówków w `GET /api/exports/{id}` |
| `/api/actions` bez filtra po analizie | Strona umowy pobiera całą listę wniosków | Parametr `?analysis_id=` |
| Frontend: brak przycisku „Odśwież” i obsługi nieznanych tras | Asystent nie widzi zwolnienia kwarantanny bez przeładowania strony | Przycisk odświeżania i strona „nie znaleziono” |
| Zakaz stylów inline tylko umowny | Nowy `style=` zostałby zablokowany przez CSP w produkcji | Reguła ESLint `react/forbid-dom-props` dla `style` |
