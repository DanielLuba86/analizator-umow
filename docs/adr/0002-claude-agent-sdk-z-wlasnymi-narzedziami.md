# 0002. Claude Agent SDK wyłącznie z własnymi narzędziami

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Agent analizuje niezaufane umowy, które mogą zawierać ukryte instrukcje. Potrzebujemy pętli agenta (wiele tur, wywołania narzędzi, limity kosztu), ale każda zdolność agenta poza czytaniem jednej umowy i zgłaszaniem tez zwiększa skutki udanego wstrzyknięcia.

## Decyzja

Agent działa na Claude Agent SDK z pięcioma własnymi narzędziami MCP uruchamianymi w procesie (`list_fragments`, `read_fragment`, `search_templates`, `submit_finding`, `request_action`). Wbudowane narzędzia są wyłączone (`tools=[]`), lista dozwolonych zawiera tylko te pięć, `permission_mode="dontAsk"` odrzuca wszystko inne bez pytania, `setting_sources=[]` pomija ustawienia z dysku, a katalog roboczy jest pusty i tymczasowy. Dziedziczone zmienne z sekretami są nadpisywane pustymi wartościami. Runner sprawdza zestaw narzędzi z komunikatu `init` przed pierwszą turą; niezgodność przerywa analizę (`niezgodny_zestaw_narzedzi`), a narzędzia pozostają zamknięte do czasu tej weryfikacji. Limity tur, budżetu i czasu pochodzą ze zmiennych środowiskowych.

## Rozważane opcje

- Claude Agent SDK z własnymi narzędziami: gotowa pętla, limity `max_turns` / `max_budget_usd`, raport kosztu; wymaga pilnowania domyślnych narzędzi i ustawień SDK (stąd kontrola `init`).
- Własna pętla na Messages API: pełna kontrola, ale więcej kodu (pętla, limity, koszt) do utrzymania.
- SDK z domyślnymi narzędziami: najmniej pracy, niedopuszczalne skutki wstrzyknięcia (system plików, powłoka, sieć).

## Konsekwencje

- Agent nie ma dostępu do plików, powłoki ani sieci; jedyne skutki to tezy i wnioski.
- Zmiana semantyki opcji w nowej wersji SDK kończy się bezpiecznym błędem, nie cichym poszerzeniem uprawnień; po każdej aktualizacji SDK trzeba powtórzyć smoke test (`python -m app.agent.sdk_runner --smoke`).
- Testy CI używają fałszywego runnera; zachowanie z prawdziwym modelem sprawdza tylko ręczny smoke test.
