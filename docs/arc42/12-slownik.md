# 12. Słownik

| Termin | Znaczenie |
|---|---|
| Analiza | Jeden przebieg detektora i agenta dla jednej wersji umowy. Statusy: `queued`, `running`, `done`, `failed`, `quarantined`, `budget_exceeded`. |
| Asystent | Rola użytkownika: wgrywa umowy, uruchamia analizy, składa wnioski `eksport` i `opinia`; nie zatwierdza wniosków. |
| `budget_exceeded` | Status analizy przerwanej limitem kroków, kosztu lub czasu; zweryfikowane tezy są zachowane i oznaczone jako niepełne. |
| Cytat | Dosłowny fragment tekstu umowy wskazany przez tezę; weryfikowany po normalizacji wyłącznie białych znaków, minimum 12 znaków. |
| Detektor wstrzyknięć | Etap przed agentem: heurystyki w domenie i klasyfikator Claude bez narzędzi. |
| Eksport | Raport analizy zamrożony po zatwierdzeniu wniosku `eksport`; do pobrania jako JSON albo PDF dla klienta (z banerem „wersja robocza”, jeśli raport nie jest oficjalną opinią). |
| Fragment | Część wersji umowy o stałych granicach (`start`, `end`) i etykiecie, np. „Komparycja”, „§ 4 ust. 2”, „Akapit 3”. |
| Kwarantanna | Stan analizy, w której wykryto możliwe wstrzyknięcie lub nie dało się go sprawdzić; raport jest ukryty do zatwierdzenia wniosku `kwarantanna`. |
| Oficjalna opinia | Analiza oznaczona przez prawnika jako stanowisko kancelarii (zatwierdzony wniosek `opinia`). |
| Prawnik | Rola użytkownika: wszystko co asystent oraz decyzje o wnioskach. |
| Prompt injection (wstrzyknięcie poleceń) | Instrukcja ukryta w danych (tu: w treści umowy), która próbuje zmienić zachowanie modelu. |
| Raport ryzyka | Lista tez analizy z cytatami, poziomem ryzyka i uzasadnieniem; widoczny tylko dla analiz poza kwarantanną. |
| Spotlighting | Oznaczanie nieufnych danych znacznikami (`<untrusted_contract_fragment>`) i deklaracja w prompcie, że ich zawartość to dane, nie polecenia. |
| Teza (finding) | Stwierdzenie agenta lub detektora o umowie. Typy: `strona`, `termin`, `kara`, `ryzyko`, `wstrzyknięcie`. Poziomy ryzyka: `niskie`, `średnie`, `wysokie`. |
| Teza odrzucona | Teza bez poprawnego cytatu. Zapisywana w `rejected_claims` z powodem: `brak_dosłownego_cytatu`, `zły_fragment`, `za_krótki_cytat`, `limit_tez`. Nigdy nie trafia do raportu. |
| Wersja umowy | Niezmienny tekst umowy o kolejnym numerze, z podziałem na fragmenty i skrótem SHA-256. |
| Wniosek (`pending_action`) | Prośba o akcję wysokiego ryzyka (`opinia`, `wzorzec`, `eksport`, `kwarantanna`) ze statusem `oczekuje`, `zatwierdzona` lub `odrzucona`. |
| Wzorzec klauzuli | Wzorcowa treść klauzuli dla rodzaju umowy (`najem`, `dostawa`, `zlecenie`), wersjonowana; agent może ją wyszukać narzędziem `search_templates`. |
