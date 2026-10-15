# 0008. Sesje po stronie serwera (HttpOnly) i dwie role

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Aplikacja ma logowanie i dwie role: `asystent` i `prawnik`. Tylko `prawnik` zatwierdza wnioski. Potrzebujemy prostego uwierzytelniania, które da się unieważnić i które nie wystawia tokenu skryptom w przeglądarce.

## Decyzja

- Sesje przechowujemy po stronie serwera w tabeli `sessions`. W bazie jest wyłącznie hash SHA-256 tokenu (`secrets.token_urlsafe(32)`), więc wyciek bazy nie ujawnia działających tokenów. Wygasłe sesje są usuwane przy próbie użycia.
- Token trafia do ciasteczka `sid` z atrybutami `HttpOnly`, `SameSite=Strict`, `Secure` (włączane konfiguracją, wyłączone tylko lokalnie bez TLS) i `Path=/api`.
- Role: `asystent` i `prawnik`; uprawnienia sprawdza warstwa API.
- Hasła hashujemy argon2 (ADR nie zmienia Zadania 3.2).
- Ochrona przed CSRF: `SameSite=Strict` (bez osobnych tokenów CSRF).

## Rozważane opcje

- JWT w ciasteczku lub nagłówku: bezstanowe, ale trudne do unieważnienia (wylogowanie, zmiana roli) i wymaga zarządzania kluczami; przy jednej aplikacji i bazie nie daje korzyści.
- Sesje w bazie: proste, natychmiast unieważnialne, kosztem jednego zapytania na żądanie.

## Konsekwencje

- Wylogowanie i wygaszanie sesji działają natychmiast.
- Każde żądanie uwierzytelnione wymaga zapytania do bazy.
- Frontend i API muszą być w tej samej witrynie (same-site), inaczej `SameSite=Strict` zablokuje ciasteczko.
- Logi są strukturalne (JSON) z redakcją treści umów (`app/security/logging.py`).
