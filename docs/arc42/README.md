# Dokumentacja architektury (arc42)

Dokumentacja Analizatora umów według szablonu [arc42](https://arc42.org). Diagramy są w Mermaid
(C4 przez `C4Context` / `C4Container`), renderowane bezpośrednio przez GitHub.

| Sekcja | Zawartość |
|---|---|
| [1. Wprowadzenie i cele](01-wprowadzenie-i-cele.md) | opis zadania, cele jakościowe, interesariusze |
| [2. Ograniczenia](02-ograniczenia.md) | ograniczenia techniczne i organizacyjne, konwencje |
| [3. Kontekst i zakres](03-kontekst-i-zakres.md) | kontekst biznesowy (C4), kanały techniczne |
| [4. Strategia rozwiązania](04-strategia-rozwiazania.md) | podejście do celów jakościowych |
| [5. Widok bloków budujących](05-widok-blokow-budujacych.md) | kontenery (C4), komponenty backendu i frontendu |
| [6. Widok czasu wykonania](06-widok-czasu-wykonania.md) | analiza, zatwierdzanie wniosku, porównanie |
| [7. Widok wdrożenia](07-wdrozenie.md) | docker-compose, konfiguracja |
| [8. Koncepcje przekrojowe](08-koncepcje-przekrojowe.md) | bezpieczeństwo agenta, auth, błędy, logi, transakcje, testy |
| [9. Decyzje architektoniczne](09-decyzje.md) | ADR 0001–0008 |
| [10. Wymagania jakościowe](10-wymagania-jakosciowe.md) | drzewo jakości, scenariusze |
| [11. Ryzyka i dług techniczny](11-ryzyka-i-dlug-techniczny.md) | ryzyka, dług techniczny |
| [12. Słownik](12-slownik.md) | pojęcia domenowe |

Powiązane dokumenty:

- [model zagrożeń](../threat-model.md);
- [ADR](../adr/README.md);
- [specyfikacja](../superpowers/specs/2026-10-15-analizator-umow-design.md).

Spójność sprawdza `scripts/check_docs.py`, uruchamiany w CI. Skrypt kontroluje:

- komplet sekcji;
- brak niedokończonych miejsc;
- poprawność diagramów;
- linki względne.
