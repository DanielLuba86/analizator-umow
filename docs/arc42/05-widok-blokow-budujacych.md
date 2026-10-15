# 5. Widok bloków budujących

## Poziom 1: kontenery

```mermaid
C4Container
  title Analizator umów — kontenery
  Person(user, "Asystent / Prawnik")
  System_Ext(claude, "Claude API")
  System_Boundary(sys, "Analizator umów (docker-compose)") {
    Container(fe, "Frontend", "React, Vite, nginx", "SPA; renderuje treść jako tekst; proxy /api do backendu")
    Container(be, "Backend", "Python, FastAPI, Claude Agent SDK", "API REST, orkiestrator analizy, agent i detektor wstrzyknięć")
    ContainerDb(db, "Baza danych", "PostgreSQL 16", "Umowy, wersje, fragmenty, analizy, tezy, wnioski, audyt, sesje")
  }
  Rel(user, fe, "Używa", "HTTPS")
  Rel(fe, be, "REST /api", "JSON, ciasteczko HttpOnly")
  Rel(be, db, "SQL", "psycopg 3")
  Rel(be, claude, "Agent i klasyfikator", "HTTPS")
```

| Kontener | Odpowiedzialność | Kod |
|---|---|---|
| Frontend | logowanie, lista umów, widok dokumentu z adnotacjami, raport ryzyka, porównanie, kolejka wniosków | [`frontend/src/`](../../frontend/src/App.tsx) |
| Backend | API, uwierzytelnianie i role, orkiestracja analizy, agent, detektor, porównania, wnioski | [`backend/app/`](../../backend/app/main.py) |
| Baza danych | trwały stan; schemat w migracji Alembic | [`backend/alembic/`](../../backend/alembic/versions/0001_schemat.py) |

## Poziom 2: komponenty backendu

```mermaid
flowchart TB
  subgraph api["api/ — endpointy FastAPI"]
    AUTH["auth.py<br/>logowanie, sesja"]
    CON["contracts.py<br/>umowy, wersje"]
    ANA["analyses.py<br/>analizy, raport, porównania"]
    ACT["actions.py<br/>wnioski, decyzje, eksport"]
    ERR["errors.py<br/>problem+json, request_id"]
  end
  subgraph services["services/ — przypadki użycia"]
    SA["analysis.py<br/>orkiestrator"]
    SR["reports.py<br/>widoczność raportu"]
    SACT["actions.py<br/>skutki zatwierdzeń"]
    SC["comparison.py<br/>porównanie wersji"]
    REC["recovery.py<br/>przerwane analizy"]
  end
  subgraph agent["agent/ — agent i detektor"]
    RUN["sdk_runner.py<br/>Claude Agent SDK"]
    TOOLS["tools.py<br/>5 narzędzi"]
    GUARD["guard.py<br/>limity pętli"]
    CLS["classifier.py<br/>klasyfikator wstrzyknięć"]
    PR["prompt.py"]
  end
  subgraph domain["domain/ — czysta logika, test-first"]
    FR["fragments.py"]
    QU["quotes.py<br/>weryfikator cytatów"]
    INJ["injection.py<br/>heurystyki"]
    DF["diff.py"]
    MD["model.py"]
  end
  subgraph repo["repo/ — SQLAlchemy"]
    RP["contracts, analyses, actions,<br/>templates, exports, audit, users"]
  end
  subgraph security["security/"]
    SEC["passwords, sessions, logging"]
  end
  api --> services
  api --> security
  services --> agent
  services --> domain
  services --> repo
  agent --> domain
  agent --> repo
  security --> repo
```

| Moduł | Odpowiedzialność | Zależy od |
|---|---|---|
| `domain/` | podział na fragmenty, weryfikacja cytatów, heurystyki wstrzyknięć, diff wersji, model tez; bez I/O | — |
| `agent/` | konfiguracja Agent SDK, prompt systemowy, narzędzia, strażnik limitów, klasyfikator, fałszywy runner do testów | `domain`, `repo` |
| `services/` | orkiestracja analizy, widoczność raportu, skutki zatwierdzeń, porównania, sprzątanie po restarcie | `domain`, `agent`, `repo` |
| `repo/` | jedyny dostęp do bazy; funkcje robią `flush`, transakcję zatwierdza wywołujący | PostgreSQL |
| `api/` | endpointy, zależności autoryzacji (`current_user`, `require_role`), mapowanie błędów | `services`, `security` |
| `security/` | argon2, sesje (hash tokenu), redakcja logów | `repo` |

## Poziom 2: komponenty frontendu

| Komponent | Odpowiedzialność |
|---|---|
| `api/client.ts`, `api/types.ts` | `apiFetch` z `credentials: "same-origin"`, `ApiError` z `request_id`, typy odpowiedzi |
| `auth/AuthContext.tsx` | bieżący użytkownik, logowanie, wylogowanie, reakcja na wygasłą sesję |
| `document/segments.ts` | podział tekstu na segmenty w granicach zakresów cytatów |
| `document/DocumentView.tsx`, `RiskReport.tsx`, `useAnalysis.ts` | dokument z podświetleniami, raport, odpytywanie statusu |
| `pages/*` | lista umów, strona umowy, porównanie, kolejka wniosków, logowanie |
