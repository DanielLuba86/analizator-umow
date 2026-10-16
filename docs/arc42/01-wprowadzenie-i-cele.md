# 1. Wprowadzenie i cele

## Opis zadania

Analizator umów to aplikacja dla fikcyjnej kancelarii. Analizuje syntetyczne umowy najmu, dostawy
i zlecenia. Agent zbudowany na Claude Agent SDK:

- wyodrębnia strony, terminy i kary umowne;
- porównuje klauzule z bazą wzorców;
- oznacza zapisy ryzykowne z uzasadnieniem.

Backend przechowuje wersje umów, analizy i porównania. Frontend pokazuje dokument z podświetlonymi
cytatami i raport ryzyka.

Wyróżnik projektu: **umowa od kontrahenta jest danymi nieufnymi**. System wykrywa ukryte
instrukcje (prompt injection), zanim analiza stanie się widoczna. Każda teza agenta musi wskazywać
dosłowny cytat z dokumentu, który serwer weryfikuje automatycznie. Tezy bez dosłownego oparcia
są odrzucane.

Główne funkcje:

| Funkcja | Kto | Opis |
|---|---|---|
| Umowy i wersje | asystent, prawnik | wgranie tekstu (pole lub plik `.md`/`.txt`), kolejne wersje, podział na fragmenty (§, ust.) |
| Analiza | asystent, prawnik | uruchomienie agenta w tle, raport tez z cytatami i poziomem ryzyka |
| Porównanie wersji | asystent, prawnik | zmienione fragmenty i zmiany tez między wersjami, bez LLM |
| Wnioski | agent, asystent | opinia, eksport, zmiana wzorca, zwolnienie z kwarantanny jako wnioski |
| Zatwierdzanie | prawnik | decyzja o każdym wniosku; dopiero wtedy następuje skutek |

## Cele jakościowe

| Priorytet | Cel | Motywacja |
|---|---|---|
| 1 | **Bezpieczeństwo agenta** | Nieufna umowa nie może sterować agentem, wyprowadzać danych ani wywoływać skutków bez człowieka. |
| 2 | **Wiarygodność wyników** | Każda teza w raporcie ma dosłowny cytat z dokumentu, sprawdzony kodem, a nie modelem. |
| 3 | **Testowalność** | Logika domenowa powstaje test-first, a agent jest testowany bez sieci (fałszywy model). |
| 4 | **Przejrzystość decyzji** | Akcje wysokiego ryzyka zatwierdza prawnik; decyzje są w dzienniku audytu. |
| 5 | **Prostota uruchomienia** | Całość startuje przez `docker compose` na jednej maszynie. |

## Interesariusze

| Rola | Oczekiwania |
|---|---|
| Asystent kancelarii | szybka analiza umowy, czytelny raport z cytatami, porównanie wersji |
| Prawnik | kontrola nad akcjami wysokiego ryzyka, pewność, że teza opiera się na tekście umowy |
| Zespół deweloperski | jasne granice modułów, testy bez dostępu do Claude API, CI na każdym PR |
| Prowadzący / recenzent projektu | wymagania bezpieczeństwa agenta, ADR, arc42, model zagrożeń |

---

Szkic przygotowany z pomocą agenta (Claude Code); zweryfikowany w PR #8 przez: Daniel Łuba.
