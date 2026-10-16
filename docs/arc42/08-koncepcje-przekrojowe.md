# 8. Koncepcje przekrojowe

## Bezpieczeństwo agenta

Treść umowy kontrahenta to dane nieufne. Obrona jest warstwowa, więc żadna pojedyncza warstwa nie
musi być doskonała. Szczegółowe zagrożenia, obrony i testy są w
[modelu zagrożeń](../threat-model.md).

| Warstwa | Mechanizm | Kod |
|---|---|---|
| 1. Detekcja przed agentem | Heurystyki: frazy rozkazowe do AI, zero-width i bidi, homoglify, pseudo-znaczniki, bloki base64. Do tego klasyfikator Claude bez narzędzi, z odpowiedzią w schemacie JSON. Każde trafienie ma zweryfikowany cytat. | [`domain/injection.py`](../../backend/app/domain/injection.py), [`agent/classifier.py`](../../backend/app/agent/classifier.py) |
| 2. Spotlighting | Treść tylko przez `read_fragment`, w `<untrusted_contract_fragment>`; znaczniki z treści neutralizowane; prompt deklaruje zawartość jako dane i nie zawiera treści umowy. | [`agent/tools.py`](../../backend/app/agent/tools.py), [`agent/prompt.py`](../../backend/app/agent/prompt.py) |
| 3. Najmniejsze uprawnienia | Wbudowane narzędzia SDK wyłączone; tylko 5 własnych narzędzi; zestaw narzędzi sprawdzany przy starcie (fail closed); `analysis_id`/`version_id` z kontekstu serwera; w procesie agenta zostają tylko zmienne z listy dozwolonych (ścieżki, locale, proxy, certyfikaty CA) i klucz API. | [`agent/sdk_runner.py`](../../backend/app/agent/sdk_runner.py), [`agent/context.py`](../../backend/app/agent/context.py) |
| 4. Weryfikacja cytatów | Teza przyjęta tylko z dosłownym cytatem (po normalizacji białych znaków, min. 12 znaków) we wskazanym fragmencie. | [`domain/quotes.py`](../../backend/app/domain/quotes.py) |
| 5. Człowiek w pętli | Opinia, wzorzec, eksport i zwolnienie z kwarantanny tylko jako wnioski zatwierdzane przez prawnika. | [`services/actions.py`](../../backend/app/services/actions.py) |
| 6. Limity | `AGENT_MAX_TURNS=30`, `AGENT_MAX_BUDGET_USD=0.50`, `AGENT_MAX_FINDINGS=60`, `AGENT_TIMEOUT_S=300` → `budget_exceeded` z tezami oznaczonymi jako niepełne; najwyżej `MAX_ACTIVE_ANALYSES=5` analiz naraz → 429. | [`agent/guard.py`](../../backend/app/agent/guard.py), [`repo/analyses.py`](../../backend/app/repo/analyses.py) |
| 7. Brak wycieku | Redakcja logów; eksport tylko po zatwierdzeniu; frontend renderuje tekst jako tekst, CSP; sekrety tylko w `.env`, gitleaks w CI. | [`security/logging.py`](../../backend/app/security/logging.py), [`frontend/nginx.conf`](../../frontend/nginx.conf) |

## Uwierzytelnianie i autoryzacja

- Hasła są hashowane argon2. Odpowiedź dla nieznanego loginu i złego hasła jest taka sama.
  Przy nieznanym loginie serwer weryfikuje atrapę hasha, żeby ścieżka kodu była ta sama; czasu nie
  mierzą testy.
- Sesja jest przechowywana po stronie serwera, w bazie tylko jako hash SHA-256 tokenu.
  W przeglądarce token leży w ciasteczku `sid` (`HttpOnly`, `SameSite=Strict`, `Path=/api`,
  `Secure` z ustawień). Wygasłe sesje są usuwane przy każdym logowaniu.
- Obrona w głąb przed CSRF: żądania `POST`/`PUT`/`PATCH`/`DELETE` z nagłówkiem `Origin` innej
  witryny dostają 403 ([`api/middleware.py`](../../backend/app/api/middleware.py)). Logowanie
  ogranicza nginx: 10 prób na minutę z jednego adresu IP.
- Są dwie role: `asystent` i `prawnik`. Decyzje o wnioskach wymagają roli `prawnik`
  (`require_role`), w pozostałych przypadkach API zwraca 403.
- Brak podziału umów między użytkowników: jedna kancelaria.

## Obsługa błędów

- Błędy API mają format `application/problem+json`: `type`, stały polski `title`, `status`
  i `request_id`. Nigdy nie zawierają treści żądania ani śladu stosu. Błędy walidacji 422
  zawierają tylko `loc` i `type`.
- `X-Request-ID` jest przyjmowany od klienta, jeśli pasuje do bezpiecznego wzorca; w przeciwnym
  razie serwer generuje nowy. Frontend pokazuje tytuł błędu i identyfikator żądania.
- Błąd przebiegu agenta daje status `failed` z kodem przyczyny (nazwa klasy wyjątku, bez
  komunikatu). Zweryfikowane tezy zostają zachowane.
- Klient Anthropic klasyfikatora ponawia żądania z domyślną polityką SDK. Po porażce klasyfikator
  jest uznany za niedostępny, co prowadzi do kwarantanny.

## Logowanie

- Logi strukturalne JSON (structlog) idą na stdout.
- Filtr redakcji usuwa pola z treścią umowy, skraca długie napisy i tracebacki. Obejmuje też
  loggery stdlib i uvicorn.
- Kroki agenta są logowane jako nazwa narzędzia, wynik i identyfikatory, bez argumentów.

## Persystencja i transakcje

- Wersje umów są niezmienne. Przy wgraniu tekst jest normalizowany do NFC, dostaje skrót SHA-256
  i jest dzielony na fragmenty.
- Funkcje `repo/` wykonują `flush`, a transakcję zatwierdza wywołujący.
- Krytyczne operacje używają blokad wierszy:
  - start analizy: `FOR UPDATE` na wersji;
  - decyzja: `FOR UPDATE` na wniosku;
  - idempotentne wnioski: częściowy unikalny indeks.
- Dziennik audytu jest tylko dopisywany: aplikacja nie ma operacji zmiany ani usuwania wpisów. To konwencja kodu, nie wymuszają jej uprawnienia ani wyzwalacze w bazie.

## Testowanie

| Poziom | Zakres | Narzędzia |
|---|---|---|
| Domena (test-first) | fragmenty, cytaty, heurystyki, diff, model tez | pytest |
| Narzędzia agenta i agent | odrzucanie złych cytatów, izolacja umów, limity; fałszywy runner bez sieci | pytest |
| Repozytoria i API | role, przepływy end-to-end, wyścigi na dwóch połączeniach | pytest + TestClient, PostgreSQL |
| Frontend | segmentacja, renderowanie jako tekst, kolejka wniosków, odpytywanie | Vitest + Testing Library |
| Dokumentacja | spójność modelu zagrożeń z testami, sekcje arc42, diagramy, linki | `scripts/check_threat_model.py`, `scripts/check_docs.py` |
| Ewaluacja na żywo (ręcznie) | prawdziwy Claude na korpusie syntetycznym | `scripts/eval_live.py` |

CI na każdym PR:

- ruff;
- mypy `--strict`;
- pytest;
- ESLint;
- `tsc --noEmit`;
- Vitest;
- gitleaks;
- sprawdzenie dokumentacji.
