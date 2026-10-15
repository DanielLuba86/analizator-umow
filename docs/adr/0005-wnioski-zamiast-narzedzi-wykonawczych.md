# 0005. Wnioski zamiast narzędzi wykonawczych

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Niektóre skutki analizy są wysokiego ryzyka: oficjalna opinia kancelarii, zmiana bazy wzorców klauzul, eksport raportu, odblokowanie kwarantanny. Gdyby agent mógł je wykonać sam, udane wstrzyknięcie przez umowę przełożyłoby się wprost na szkodę.

## Decyzja

Agent nie ma narzędzi wykonawczych. Może jedynie złożyć wniosek przez `request_action(typ, uzasadnienie)`, i to tylko typu `opinia` lub `wzorzec`; wniosek trafia do `pending_actions` ze statusem `oczekuje` i niczego nie zmienia. `eksport` składa asystent, `kwarantanna` — orkiestrator. Skutek następuje dopiero po zatwierdzeniu przez użytkownika z rolą `prawnik`; każda decyzja trafia do `audit_log`. Identyfikatory analizy i wersji narzędzia biorą z kontekstu, nie z argumentów modelu.

## Rozważane opcje

- Wnioski zatwierdzane przez człowieka: skutki wysokiego ryzyka wymagają decyzji prawnika; wolniejszy obieg.
- Narzędzia wykonawcze z twardymi limitami: szybciej, ale wstrzyknięcie wciąż może wywołać skutek w granicach limitu.
- Brak wniosków od agenta: najbezpieczniej, ale tracimy jego sugestie (np. nowy wzorzec klauzuli).

## Konsekwencje

- Najgorszy skutek udanego wstrzyknięcia to błędny wniosek, który prawnik odrzuca.
- Wnioski są idempotentne na parę (analiza, typ) i widoczne w kolejce prawnika.
- Wymaga interfejsu kolejki wniosków i kontroli roli w API (faza 5).
