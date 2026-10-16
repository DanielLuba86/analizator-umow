# Architecture Decision Records

Krótkie zapisy decyzji architektonicznych w formacie MADR. Każdy ADR mieści się na jednej stronie.

## Indeks

| Nr | Tytuł | Status | Data |
|---|---|---|---|
| [0001](0001-python-fastapi-i-react.md) | Backend w Pythonie (FastAPI) i frontend w React | Przyjęta | 2026-10-15 |
| [0002](0002-claude-agent-sdk-z-wlasnymi-narzedziami.md) | Claude Agent SDK wyłącznie z własnymi narzędziami | Przyjęta | 2026-10-15 |
| [0003](0003-tezy-przez-narzedzie-z-weryfikacja-cytatow.md) | Tezy tylko przez narzędzie z weryfikacją cytatów | Przyjęta | 2026-10-15 |
| [0004](0004-detekcja-wstrzykniec-przed-agentem.md) | Detekcja wstrzyknięć przed agentem | Przyjęta | 2026-10-15 |
| [0005](0005-wnioski-zamiast-narzedzi-wykonawczych.md) | Wnioski zamiast narzędzi wykonawczych | Przyjęta | 2026-10-15 |
| [0006](0006-postgresql-w-docker-compose.md) | PostgreSQL w docker-compose | Przyjęta | 2026-10-15 |
| [0007](0007-zadania-w-tle-bez-kolejki.md) | Zadania w tle bez kolejki | Przyjęta | 2026-10-15 |
| [0008](0008-sesje-httponly-i-dwie-role.md) | Sesje po stronie serwera (HttpOnly) i dwie role | Przyjęta | 2026-10-15 |
| [0009](0009-dostawca-modelu-jako-ustawienie.md) | Dostawca modelu (Claude API albo Microsoft Foundry) jako ustawienie | Przyjęta | 2026-10-16 |
| [0010](0010-raport-pdf-z-fpdf2.md) | Raport PDF generowany przez fpdf2 z zamrożonego eksportu | Przyjęta | 2026-10-16 |

## Szablon MADR

```markdown
# NNNN. Tytuł decyzji

- Status: Proponowana | Przyjęta | Odrzucona | Zastąpiona przez NNNN
- Data: RRRR-MM-DD

## Kontekst

Jaki problem rozwiązujemy i jakie są ograniczenia.

## Decyzja

Co wybieramy i dlaczego.

## Rozważane opcje

- Opcja A: zalety, wady
- Opcja B: zalety, wady

## Konsekwencje

Co się zmienia na plus i na minus.
```
