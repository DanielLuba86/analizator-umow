# 0010. Raport PDF generowany przez fpdf2 z zamrożonego eksportu

- Status: Przyjęta
- Data: 2026-10-16

## Kontekst

Zatwierdzony eksport był dostępny tylko jako JSON, a kancelaria wysyła raporty klientom. Raport dla
klienta musi mieć polskie znaki, nagłówek kancelarii i wyraźne oznaczenie, czy jest oficjalną
opinią. Teza, cytat i uzasadnienie pochodzą od agenta i z umowy kontrahenta, więc są danymi
nieufnymi (T22).

## Decyzja

PDF generuje [`services/pdf_report.py`](../../backend/app/services/pdf_report.py) biblioteką fpdf2
na żądanie (`GET /api/exports/{id}/pdf`) z tej samej zamrożonej treści `exports.content` co JSON.
Nie ma osobnego wniosku ani zapisu pliku w bazie. Czcionka DejaVu Sans jest dołączona do pakietu.
Tekst trafia do PDF wyłącznie przez `multi_cell(..., markdown=False)`. Raport, który nie jest
oficjalną opinią, dostaje baner „WERSJA ROBOCZA”.

## Rozważane opcje

- fpdf2: czysty Python, bez pakietów systemowych w obrazie, tekst bez interpretacji znaczników;
  układ trzeba opisać w kodzie.
- WeasyPrint (HTML + CSS): wygodny układ, ale wymaga Pango w obrazie, a nieufny tekst trzeba
  escapować w szablonie HTML.
- Druk z przeglądarki (`window.print`): bez zależności, ale wygląd zależy od przeglądarki
  i nie ma gwarancji banera ani stopki.

## Konsekwencje

- PDF zawsze odpowiada temu, co zatwierdził prawnik; zmiana wyglądu działa też dla starych eksportów.
- Nowa zależność runtime (`fpdf2`, z nią `pillow`) i około 2 MB czcionek w obrazie.
- Każde pobranie generuje PDF od nowa (kilkadziesiąt ms dla typowego raportu).
- Login prawnika w banerze opinii jest odczytywany przy pobraniu; usunięte konto daje „nieznany”.
