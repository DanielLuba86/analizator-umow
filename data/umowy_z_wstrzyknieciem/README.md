# Korpus umów z wstrzyknięciem

Syntetyczne umowy (kopie `data/umowy/umowa_najmu.md`) z jedną ukrytą instrukcją każda.
Służą do testowania heurystyk wykrywania wstrzyknięć (`backend/app/domain/injection.py`).
Plik README.md nie jest umową i jest pomijany w testach.

- `jawne_polecenie.md` — jawna fraza rozkazowa w § 4 ust. 2 (reguła `fraza_rozkazowa`).
- `zero_width.md` — fraza rozkazowa rozbita znakami zerowej szerokości U+200B (`zero_width`).
- `homoglify.md` — słowa z cyrylickimi odpowiednikami liter łacińskich (`homoglif`).
- `pseudo_znacznik.md` — fałszywy znacznik zamykający i linia `system:` (`pseudo_znacznik`).
- `instrukcja_w_zalaczniku.md` — instrukcja w dodatkowym Załączniku nr 2 (`fraza_rozkazowa`).
