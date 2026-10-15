# 0004. Detekcja wstrzyknięć przed agentem

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Umowy pochodzą m.in. od kontrahentów i mogą zawierać instrukcje skierowane do AI (jawne polecenia, znaki zero-width, homoglify, pseudo-znaczniki, zakodowane bloki). Sam prompt systemowy i znaczniki `<untrusted_contract_fragment>` zmniejszają ryzyko, ale go nie eliminują.

## Decyzja

Orkiestrator przed uruchomieniem agenta skanuje umowę heurystykami z warstwy `domain` oraz klasyfikatorem: osobnym wywołaniem Claude (`CLASSIFIER_MODEL`) bez narzędzi, z fragmentami opakowanymi jak dla agenta i odpowiedzią w ścisłym schemacie JSON. Każde trafienie przechodzi przez weryfikator cytatów; zweryfikowane zapisujemy jako tezę typu `wstrzyknięcie`. Agent działa niezależnie od wyniku, ale zweryfikowane trafienie (także zgłoszone przez samego agenta) albo niedostępny klasyfikator (odmowa, błąd API, niepoprawna odpowiedź — fail-closed) kończy analizę statusem `quarantined` i wnioskiem `kwarantanna` do zatwierdzenia przez prawnika.

## Rozważane opcje

- Heurystyki + klasyfikator przed agentem: tanie reguły łapią znane wzorce, model łapie sformułowania nowe; koszt jednego dodatkowego wywołania.
- Tylko heurystyki: deterministyczne i darmowe, ale łatwe do obejścia parafrazą.
- Tylko obrona w promptach agenta: brak sygnału dla człowieka, że umowa była wroga.

## Konsekwencje

- Wroga umowa nie daje raportu bez decyzji prawnika; fałszywe alarmy kosztują jedną decyzję.
- Awaria klasyfikatora blokuje raporty (kwarantanna) zamiast przepuszczać je bez kontroli.
- Trafienie klasyfikatora z cytatem spoza umowy jest odrzucane i samo nie powoduje kwarantanny.
