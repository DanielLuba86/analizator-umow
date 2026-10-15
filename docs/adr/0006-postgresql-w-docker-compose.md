# 0006. PostgreSQL w docker-compose

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

System przechowuje użytkowników, analizy, tezy z cytatami i wnioski o akcje wysokiego ryzyka. Wdrożenie docelowe to docker-compose (db, backend, frontend); wdrożenie produkcyjne w chmurze i kolejka zadań są poza zakresem.

## Decyzja

Dane trzymamy w PostgreSQL 16 uruchamianym jako usługa `db` w docker-compose. Dostęp przez SQLAlchemy (sterownik psycopg), migracje przez Alembic. Konfiguracja wyłącznie przez zmienne środowiskowe (`DATABASE_URL`), wzór w `.env.example`. W CI testy dostają usługę `postgres:16`.

## Rozważane opcje

- PostgreSQL w docker-compose: te same silnik i zachowanie lokalnie, w CI i na wdrożeniu; transakcje i ograniczenia integralności. Wymaga Dockera.
- SQLite: zero konfiguracji, ale inne zachowanie typów i współbieżności niż docelowo, trudniejsze równoległe zapisy z analiz w tle.
- Zarządzana baza w chmurze: poza zakresem projektu, dodaje koszt i zależność.

## Konsekwencje

- Jedno polecenie `docker compose up` uruchamia cały system.
- CI musi startować kontener Postgresa (job `backend`).
- Dane trwałe leżą w wolumenie Dockera; kopie zapasowe są odpowiedzialnością operatora.
