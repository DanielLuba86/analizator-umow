# 6. Widok czasu wykonania

## Scenariusz 1: analiza umowy

```mermaid
sequenceDiagram
  actor A as Asystent
  participant FE as Frontend
  participant API as API
  participant ORCH as Orkiestrator
  participant DET as Detektor
  participant AG as Agent (SDK)
  participant T as Narzędzia
  participant DB as Baza
  A->>FE: Uruchom analizę
  FE->>API: POST /api/versions/{id}/analyses
  API->>DB: analiza queued (blokada wersji, 409 gdy aktywna)
  API-->>FE: 202 {analysis_id}
  API->>ORCH: zadanie w tle
  ORCH->>DB: status running
  ORCH->>DET: heurystyki + klasyfikator (fragmenty jako dane)
  DET-->>ORCH: trafienia z cytatami
  ORCH->>DB: trafienia jako tezy "wstrzyknięcie"
  ORCH->>AG: start (limit kroków, budżet, czas)
  loop do końca pracy lub limitu
    AG->>T: list_fragments / read_fragment / search_templates
    AG->>T: submit_finding(teza, cytat, fragment_id)
    T->>T: weryfikacja cytatu
    T->>DB: teza przyjęta albo odrzucona
    T-->>AG: zakres {start, end} albo powód odrzucenia
  end
  ORCH->>DB: kwarantanna → wniosek "kwarantanna", status quarantined
  ORCH->>DB: albo status done / budget_exceeded / failed
  loop co 2 s do stanu końcowego
    FE->>API: GET /api/analyses/{id}
    API-->>FE: status, tezy (gdy raport widoczny)
  end
```

Uwagi:

- Agent działa także wtedy, gdy detektor coś znalazł: jest izolowany. Wynik dostaje jednak status
  `quarantined` i pozostaje ukryty do decyzji prawnika.
- Niedostępny klasyfikator również prowadzi do kwarantanny (fail closed).
- Kwarantanna ma pierwszeństwo przed błędem przebiegu agenta. Analiza z wykrytym wstrzyknięciem
  nie staje się widoczna przez status `failed`.
- Po restarcie backendu analizy `queued`/`running` są oznaczane jako `failed`
  (`przerwana_restartem`).

## Scenariusz 2: zatwierdzenie wniosku

```mermaid
sequenceDiagram
  actor P as Prawnik
  participant FE as Frontend
  participant API as API
  participant S as services/actions
  participant DB as Baza
  P->>FE: Kolejka wniosków
  FE->>API: GET /api/actions?status=oczekuje
  API-->>FE: wnioski (uzasadnienie agenta ukryte, gdy raport niewidoczny)
  P->>FE: Zatwierdź
  FE->>API: POST /api/actions/{id}/decision {approve, template?}
  API->>API: require_role("prawnik"), inaczej 403
  API->>S: decide
  S->>DB: SELECT … FOR UPDATE wniosku
  alt wniosek już rozstrzygnięty
    S-->>API: ActionAlreadyDecided
    API-->>FE: 409 "Wniosek został już rozstrzygnięty."
  else oczekuje
    S->>DB: decyzja + skutek (opinia / wzorzec / eksport / zwolnienie kwarantanny) + audyt
    API-->>FE: 200 {status, export_id}
  end
```

Skutki zatwierdzenia:

| Wniosek | Skutek |
|---|---|
| `kwarantanna` | raport staje się widoczny (status `done`) |
| `opinia` | analiza oznaczona jako oficjalna opinia kancelarii |
| `wzorzec` | nowa wersja klauzuli w bazie wzorców; treść pisze prawnik w decyzji |
| `eksport` | plik JSON raportu do pobrania pod `/api/exports/{id}` |

## Scenariusz 3: porównanie wersji

Użytkownik wybiera starą i nową wersję. `POST /api/comparisons` liczy deterministyczny diff
fragmentów według etykiet (dodany, usunięty, zmieniony) oraz, gdy obie wersje mają zakończoną
analizę, zmiany tez (nowe i te, które ustąpiły). Wynik jest zapisywany w tabeli `comparisons`.
