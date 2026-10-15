# 0003. Tezy tylko przez narzędzie z weryfikacją cytatów

- Status: Przyjęta
- Data: 2026-10-15

## Kontekst

Prawnik musi móc ufać, że każda teza agenta ma oparcie w tekście umowy. Model może parafrazować, łączyć fragmenty albo zmyślać, a atakujący może podsunąć fałszywe tezy przez treść umowy.

## Decyzja

Agent zgłasza tezy wyłącznie przez `submit_finding(typ, teza, cytat, fragment_id, …)`. Cytat jest sprawdzany deterministycznie (`verify_quote`): musi wystąpić dosłownie we wskazanym fragmencie po normalizacji wyłącznie białych znaków, mieć co najmniej 12 znaków, a zapisywane jest pierwsze wystąpienie z przesunięciami. Teza bez takiego cytatu trafia do `rejected_claims` z powodem (`brak_dosłownego_cytatu`, `zły_fragment`, `za_krótki_cytat`, `limit_tez`), a agent dostaje wskazówkę, by przeczytał fragment ponownie albo porzucił tezę. Weryfikator niczego nie „naprawia” (Markdown, typografia). Ten sam weryfikator obsługuje trafienia detektora wstrzyknięć.

## Rozważane opcje

- Narzędzie z deterministyczną weryfikacją: twarda gwarancja, prosta do przetestowania; agent musi kopiować cytaty dokładnie.
- Tezy w końcowej odpowiedzi tekstowej i dopasowanie rozmyte: wygodniejsze dla modelu, ale rozmyte dopasowanie przepuszcza parafrazy.
- Cytowania API (citations): wiązanie do dokumentu, ale niezgodne ze ścisłym formatem odpowiedzi i bez kontroli powodów odrzucenia.

## Konsekwencje

- W raporcie nie ma tez bez zweryfikowanego cytatu; odrzucenia są widoczne i policzalne.
- Część poprawnych merytorycznie tez przepada, gdy model nie skopiuje cytatu dosłownie.
- Limit tez (`AGENT_MAX_FINDINGS`) obejmuje także trafienia detektora.
