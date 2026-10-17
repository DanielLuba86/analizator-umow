# Narzędzia agenta i ich uprawnienia

Agent analizujący umowę działa na Claude Agent SDK
([ADR 0002](adr/0002-claude-agent-sdk-z-wlasnymi-narzedziami.md)) i ma wyłącznie pięć własnych
narzędzi MCP uruchamianych w procesie backendu. Ten dokument opisuje, co każde narzędzie
przyjmuje, co czyta i zapisuje, jak waliduje dane oraz czego agent zrobić nie może.

## Model uprawnień w skrócie

- **Zakres jednej analizy.** Identyfikatory analizy i wersji umowy pochodzą z kontekstu
  przebiegu (`AnalysisContext`), nie z argumentów modelu. Agent nie może odczytać innej umowy,
  innej wersji ani cudzej analizy.
- **Odczyt umowy, wzorców i nic więcej.** Agent nie ma powłoki, systemu plików, sieci ani
  wbudowanych narzędzi Claude Code.
- **Zapis tylko w dwóch miejscach:** tezy (`findings`, a odrzucone w `rejected_claims`) i wnioski
  ze statusem `oczekuje` (`pending_actions`).
- **Żadnych skutków bez człowieka.** Oficjalna opinia, zmiana wzorca, eksport i zwolnienie
  z kwarantanny wymagają decyzji użytkownika z rolą `prawnik`
  ([ADR 0005](adr/0005-wnioski-zamiast-narzedzi-wykonawczych.md)).
- **Treść umowy to dane.** Fragmenty trafiają do modelu w znacznikach
  `<untrusted_contract_fragment>`, a prompt systemowy deklaruje ich zawartość jako dane, nie
  polecenia. Detekcja wstrzyknięć działa przed agentem
  ([ADR 0004](adr/0004-detekcja-wstrzykniec-przed-agentem.md)).

## Narzędzia

Pełna nazwa narzędzia w SDK ma postać `mcp__umowy__<nazwa>`. Każde narzędzie zwraca wynik
tekstowy; błąd ma `is_error: true` i krótką wskazówkę dla modelu, która nigdy nie powtarza
cytatu ani treści umowy. Każde wywołanie jest logowane jako zdarzenie `agent_tool` z polami
`tool` i `outcome`.

| Narzędzie | Parametry | Czyta | Zapisuje |
|---|---|---|---|
| `list_fragments` | — | fragmenty bieżącej wersji umowy | — |
| `read_fragment` | `fragment_id` | treść jednego fragmentu bieżącej wersji | — |
| `search_templates` | `kind`, `query` | wzorce klauzul kancelarii (najnowsze wersje) | — |
| `submit_finding` | `typ`, `teza`, `cytat`, `fragment_id`, `uzasadnienie`, `poziom_ryzyka`?, `template_id`? | tekst i fragmenty bieżącej wersji | `findings` albo `rejected_claims` |
| `request_action` | `typ`, `uzasadnienie` | — | `pending_actions` (status `oczekuje`) |

### `list_fragments`

Zwraca listę JSON `{id, label, length}` dla fragmentów bieżącej wersji (np. `f003`, „§ 7 ust. 1”).
Nie zwraca treści.

### `read_fragment`

Zwraca treść jednego fragmentu owiniętą w
`<untrusted_contract_fragment id="…" label="…">…</untrusted_contract_fragment>`. Atrybuty są
ucieknięte, a znaczniki o tej samej nazwie wewnątrz treści (także wielkimi literami) są
neutralizowane, żeby umowa nie mogła „zamknąć” bloku danych. Nieznany identyfikator albo
fragment innej wersji kończy się błędem z podpowiedzią, by użyć `list_fragments`.

### `search_templates`

Szuka we wzorcach klauzul danego rodzaju umowy (`najem`, `dostawa`, `zlecenie`) frazy `query`
w nazwie i treści klauzuli. Zwraca do 5 wyników `{id, kind, nazwa_klauzuli, tresc, wersja}`,
zawsze w najnowszej wersji każdej klauzuli. Inny rodzaj umowy to błąd z listą dozwolonych.

### `submit_finding`

Jedyna droga, którą teza trafia do raportu
([ADR 0003](adr/0003-tezy-przez-narzedzie-z-weryfikacja-cytatow.md)). Kolejność sprawdzeń:

1. **Typy argumentów.** Teksty muszą być tekstami, a `template_id` liczbą całkowitą w zakresie
   kolumny bazy. Inaczej: `invalid_input` lub `invalid_template`.
2. **Reguły tezy** (`validate_claim`). `typ` ∈ `strona`, `termin`, `kara`, `ryzyko`,
   `wstrzyknięcie`; `poziom_ryzyka` ∈ `niskie`, `średnie`, `wysokie` i tylko dla typów `ryzyko`
   (tam wymagany) oraz `kara`; niepusta `teza` do 500 znaków; niepuste `uzasadnienie`. Naruszenie
   zwraca opis reguły jako błąd (`claim_invalid`, powód w polu `reason` logu) i **niczego nie
   zapisuje**.
3. **Limit tez na analizę** (`AGENT_MAX_FINDINGS`). Po jego osiągnięciu teza trafia do
   `rejected_claims` z powodem `limit_tez`.
4. **Weryfikacja cytatu** (`verify_quote`, czysta domena). Cytat musi występować dosłownie we
   wskazanym fragmencie (tolerowane są tylko różnice w białych znakach) i mieć co najmniej
   12 znaków. Odrzucenie zapisuje tezę w `rejected_claims` z powodem `brak_dosłownego_cytatu`,
   `zły_fragment` albo `za_krótki_cytat`. Odrzucone tezy nie trafiają do raportu.
5. **Zapis.** Przyjęta teza trafia do `findings` z przesunięciami `start` i `end` cytatu
   w tekście umowy, a narzędzie zwraca `{status: "przyjęta", start, end}`. Nieistniejący
   `template_id` daje błąd z podpowiedzią, by użyć `search_templates`.

Liczenie tez i zapis odbywają się pod blokadą wiersza analizy, więc równoległe wywołania nie
przekroczą limitu.

### `request_action`

Składa wniosek do prawnika i **niczego nie wykonuje**. Agent może wnioskować tylko o typy
`opinia` i `wzorzec`; `eksport` i `kwarantanna` są odrzucane (`forbidden_type`). Uzasadnienie
jest wymagane i ma najwyżej 2000 znaków. Wniosek zapisuje się z `zrodlo: "agent"`, a jego
uzasadnienie jest ukryte w kolejce prawnika, dopóki raport analizy jest w kwarantannie.

## Kto wykonuje skutki

| Wniosek | Kto składa | Skutek po zatwierdzeniu przez prawnika |
|---|---|---|
| `opinia` | agent albo użytkownik | analiza oznaczona jako oficjalna opinia |
| `wzorzec` | agent | nowa wersja wzorca klauzuli; nazwę i treść podaje prawnik, nie agent |
| `eksport` | użytkownik | zamrożony eksport raportu (JSON i PDF) |
| `kwarantanna` | orkiestrator analizy | raport zwolniony z kwarantanny |

`opinia`, `wzorzec` i `eksport` wymagają, żeby raport był widoczny, czyli nie w kwarantannie.
Decyzja, jej skutek i wpis w `audit_log` zapisują się w jednej transakcji
([`services/actions.py`](../backend/app/services/actions.py)).

## Konfiguracja SDK jako granica uprawnień

Opcje przebiegu buduje `build_options` w
[`agent/sdk_runner.py`](../backend/app/agent/sdk_runner.py):

| Ustawienie | Wartość | Skutek |
|---|---|---|
| `tools` | `[]` | wyłączone wszystkie wbudowane narzędzia (Bash, Read, Write, WebFetch…) |
| `allowed_tools` | pięć nazw `mcp__umowy__*` | tylko własne narzędzia są dozwolone |
| `permission_mode` | `"dontAsk"` | wszystko spoza listy dozwolonych jest odrzucane bez pytania |
| `setting_sources` | `[]` | żadne ustawienia z dysku (użytkownika, projektu, lokalne) nie są wczytywane |
| `cwd` | pusty katalog tymczasowy | usuwany po przebiegu |
| `env` | lista dozwolonych zmiennych | każda inna dziedziczona zmienna jest nadpisywana pustą wartością, dochodzą tylko dane logowania dostawcy ([ADR 0009](adr/0009-dostawca-modelu-jako-ustawienie.md)) i liczba ponowień |
| `max_turns`, `max_budget_usd` | z ustawień | limity przebiegu |

Dodatkowo runner działa **fail closed**:

- Przed pierwszą turą sprawdza zestaw narzędzi zgłoszony przez CLI w komunikacie `init`.
  Musi to być dokładnie pięć `mcp__umowy__*`; każda różnica kończy analizę statusem `failed`
  z powodem `niezgodny_zestaw_narzedzi`. Brak komunikatu `init` daje `brak_init`.
- Do czasu tej weryfikacji narzędzia są zamknięte i odpowiadają „Narzędzia są niedostępne.”.

Ten sam zestaw narzędzi sprawdza ręczny smoke test, powtarzany po każdej aktualizacji
`claude-agent-sdk`:

```bash
docker compose run --rm -v "$PWD/data:/data:ro" backend \
  python -m app.agent.sdk_runner --smoke /data/umowy/umowa_zlecenia.md
```

## Limity

| Zmienna | Domyślnie | Co ogranicza |
|---|---|---|
| `AGENT_MAX_TURNS` | 30 | liczba odpowiedzi modelu w przebiegu (`max_turns` SDK); przekroczenie → `budget_exceeded` |
| `AGENT_MAX_BUDGET_USD` | 0.50 | koszt jednego przebiegu; przekroczenie → `budget_exceeded` |
| `AGENT_TIMEOUT_S` | 300 | czas przebiegu; przekroczenie → `budget_exceeded` |
| `AGENT_MAX_FINDINGS` | 60 | liczba tez w analizie (`limit_tez`) |
| `AGENT_MAX_RETRIES` | 10 | ponowienia wywołań API przez CLI (`CLAUDE_CODE_MAX_RETRIES`) |
| `MAX_ACTIVE_ANALYSES` | 5 | analizy `queued`/`running` naraz w całej aplikacji (429) |
| `MAX_ACTIVE_ANALYSES_PER_USER` | 2 | analizy `queued`/`running` naraz jednej osoby (429) |

**Tura to jedna odpowiedź modelu**, a nie jedno wywołanie narzędzia. Model może w jednej
odpowiedzi wywołać kilka narzędzi naraz, więc liczba wywołań narzędzi jest zwykle kilka razy
większa niż liczba tur. Pomiar z 2026-10-17 na `umowa_zlecenia.md`: 9 tur i 55 wywołań narzędzi.
Liczbę wywołań ogranicza w praktyce budżet, czas i limit tez, a nie `AGENT_MAX_TURNS`.

Runner zapisuje w `analyses.turns` i w logu `agent_run` liczbę tur w tej samej jednostce co
limit: liczbę różnych odpowiedzi modelu (`message_id`). Nie używa `num_turns` z wyniku CLI, bo
przy udanym przebiegu ta wartość jest bliska liczbie wywołań narzędzi.

Wartości ustawia się w `.env` ([`.env.example`](../.env.example)).

## Kod i testy

| Obszar | Kod | Testy |
|---|---|---|
| implementacja narzędzi | [`agent/tools.py`](../backend/app/agent/tools.py) | [`tests/agent/test_tools.py`](../backend/tests/agent/test_tools.py) |
| definicje MCP, opcje SDK, weryfikacja `init` | [`agent/sdk_runner.py`](../backend/app/agent/sdk_runner.py) | [`tests/agent/test_sdk_options.py`](../backend/tests/agent/test_sdk_options.py) |
| reguły tezy | [`domain/model.py`](../backend/app/domain/model.py) | [`tests/agent/test_tools.py`](../backend/tests/agent/test_tools.py) |
| weryfikator cytatów | [`domain/quotes.py`](../backend/app/domain/quotes.py) | [`tests/domain/test_quotes.py`](../backend/tests/domain/test_quotes.py) |
| prompt systemowy | [`agent/prompt.py`](../backend/app/agent/prompt.py) | [`tests/agent/test_prompt.py`](../backend/tests/agent/test_prompt.py) |
| skutki zatwierdzeń | [`services/actions.py`](../backend/app/services/actions.py) | — |

Przykładowe testy, które pilnują granic uprawnień:

- `test_methods_do_not_accept_analysis_or_version_ids`: narzędzia nie przyjmują identyfikatorów
  z argumentów modelu.
- `test_read_fragment_of_other_version_is_not_reachable`: brak dostępu do innej wersji.
- `test_request_action_creates_pending_and_executes_nothing` i
  `test_request_action_rejects_eksport_and_kwarantanna`.
- `test_options_disable_builtin_tools`, `test_options_allow_only_own_tools`,
  `test_options_no_filesystem_settings`, `test_agent_env_blanks_everything_but_allowlist`.
- `test_check_init_tools_rejects_builtin_extra` i `test_mcp_tools_closed_until_gate_opens`.

Zagrożenia, przed którymi chronią te mechanizmy, opisuje [model zagrożeń](threat-model.md).
