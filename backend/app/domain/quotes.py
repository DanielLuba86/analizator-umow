"""Weryfikator dosłownych cytatów: twierdzenie agenta musi mieć pokrycie w tekście."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.fragments import Fragment, fragment_text

MIN_QUOTE_LEN = 12

RejectReason = Literal["brak_dosłownego_cytatu", "zły_fragment", "za_krótki_cytat", "limit_tez"]

# Wszystkie poniższe znaki są też białymi znakami wg str.isspace(); lista jawna dla czytelności.
EXTRA_WHITESPACE = frozenset({" ", " ", " "})

# limit_tez nie ma podpowiedzi tutaj: zgłasza go narzędzie agenta, nie weryfikator cytatów.
_HINTS: Mapping[RejectReason, str] = {
    "brak_dosłownego_cytatu": (
        "Cytat musi występować dosłownie we wskazanym fragmencie, łącznie z interpunkcją "
        "i znacznikami formatowania. Przeczytaj fragment ponownie narzędziem read_fragment "
        "i skopiuj tekst dosłownie."
    ),
    "zły_fragment": (
        "Wskazany identyfikator fragmentu nie istnieje. Sprawdź dostępne identyfikatory "
        "narzędziem list_fragments i podaj poprawny."
    ),
    "za_krótki_cytat": (
        "Cytat jest zbyt krótki, by jednoznacznie wskazywać miejsce w umowie. "
        "Podaj dłuższy, dosłowny cytat o długości co najmniej {min_len} znaków."
    ),
}


class QuoteNotFound(Exception):
    """Cytat odrzucony. Komunikat nie zawiera cytatu ani treści umowy (trafia do logów)."""

    def __init__(self, reason: RejectReason, hint: str) -> None:
        super().__init__(f"{reason}: {hint}")
        self.reason: RejectReason = reason
        self.hint: str = hint


@dataclass(frozen=True)
class QuoteMatch:
    start: int
    end: int


def is_quote_space(ch: str) -> bool:
    return ch.isspace() or ch in EXTRA_WHITESPACE


def normalize_whitespace(s: str) -> tuple[str, list[int], list[int]]:
    """Zwraca (znormalizowany tekst, początki, końce) — przesunięcia w oryginale `s`.

    Każdy ciąg białych znaków staje się jedną spacją; dla znaku i znormalizowanego
    pokrywane jest [starts[i], ends[i]) w oryginale.
    """
    out: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    i, n = 0, len(s)
    while i < n:
        if is_quote_space(s[i]):
            j = i + 1
            while j < n and is_quote_space(s[j]):
                j += 1
            out.append(" ")
            starts.append(i)
            ends.append(j)
            i = j
        else:
            out.append(s[i])
            starts.append(i)
            ends.append(i + 1)
            i += 1
    return "".join(out), starts, ends


def verify_quote(
    text: str,
    fragments: Sequence[Fragment],
    fragment_id: str,
    quote: str,
    min_len: int = MIN_QUOTE_LEN,
) -> QuoteMatch:
    """Zwraca przesunięcia pierwszego dosłownego wystąpienia cytatu we wskazanym fragmencie.

    Dopuszczalna różnica: wyłącznie białe znaki. Przesunięcia są bezwzględne (w `text`).
    """
    if min_len < 0:
        raise ValueError("min_len nie może być ujemne")
    fragment = next((f for f in fragments if f.id == fragment_id), None)
    if fragment is None:
        raise QuoteNotFound("zły_fragment", _HINTS["zły_fragment"])

    needle = normalize_whitespace(quote)[0].strip(" ")
    if not needle or len(needle) < min_len:
        raise QuoteNotFound("za_krótki_cytat", _HINTS["za_krótki_cytat"].format(min_len=min_len))

    haystack, starts, ends = normalize_whitespace(fragment_text(text, fragment))
    pos = haystack.find(needle)
    if pos < 0:
        raise QuoteNotFound("brak_dosłownego_cytatu", _HINTS["brak_dosłownego_cytatu"])
    return QuoteMatch(
        start=fragment.start + starts[pos],
        end=fragment.start + ends[pos + len(needle) - 1],
    )
