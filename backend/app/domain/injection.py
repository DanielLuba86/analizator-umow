"""Heurystyki wykrywania ukrytych instrukcji (prompt injection) w niezaufanych umowach.

Moduł czysto domenowy (tylko stdlib). Każde trafienie niesie cytat, który przechodzi
przez ten sam weryfikator cytatów co tezy agenta (`verify_quote`).
"""

import re
import unicodedata
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.fragments import Fragment
from app.domain.quotes import QuoteNotFound, _is_space, _normalize, verify_quote

InjectionRule = Literal[
    "fraza_rozkazowa", "zero_width", "bidi", "homoglif", "pseudo_znacznik", "base64"
]


@dataclass(frozen=True)
class InjectionHit:
    rule: InjectionRule
    fragment_id: str
    quote: str
    start: int
    end: int


MIN_QUOTE_LEN = 12
_FLAGS = re.IGNORECASE | re.UNICODE

_COMMAND_PHRASES = re.compile(
    "|".join(
        [
            r"zignoruj\s+(?:wszystkie\s+)?(?:poprzednie|wcześniejsze)\s+(?:instrukcje|polecenia)",
            r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
            r"jako\s+(?:asystent|model)\s+(?:AI|językowy)",
            r"(?:oznacz|uznaj)\s+(?:tę|tą|niniejszą)\s+umowę\s+(?:jako|za)\s+"
            r"(?:bezpieczną|niskiego\s+ryzyka)",
            r"nie\s+(?:zgłaszaj|raportuj|oznaczaj)",
            r"system\s+prompt",
            r"you\s+are\s+now",
        ]
    ),
    _FLAGS,
)
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿]+")
_BIDI = re.compile("[‪-‮⁦-⁩]+")
_PSEUDO_TAG = re.compile(
    r"</?\s*(?:system|assistant|user|document|instructions?|untrusted_contract_fragment)\b[^>]*>",
    _FLAGS,
)
_PSEUDO_ROLE_LINE = re.compile(r"^[ \t]*((?:system|assistant)[ \t]*:)", _FLAGS | re.MULTILINE)
_BASE64 = re.compile(r"[A-Za-z0-9+/]{80,}={0,2}")


def _word_spans(text: str) -> Iterator[tuple[int, int]]:
    """Maksymalne ciągi liter (str.isalpha)."""
    start: int | None = None
    for i, ch in enumerate(text):
        if ch.isalpha():
            if start is None:
                start = i
        elif start is not None:
            yield start, i
            start = None
    if start is not None:
        yield start, len(text)


def _scripts(word: str) -> set[str]:
    found: set[str] = set()
    for ch in word:
        name = unicodedata.name(ch, "")
        for script in ("LATIN", "CYRILLIC", "GREEK"):
            if name.startswith(script):
                found.add(script)
    return found


def _raw_spans(text: str) -> Iterator[tuple[InjectionRule, int, int]]:
    for m in _COMMAND_PHRASES.finditer(text):
        yield "fraza_rozkazowa", m.start(), m.end()
    for m in _ZERO_WIDTH.finditer(text):
        yield "zero_width", m.start(), m.end()
    for m in _BIDI.finditer(text):
        yield "bidi", m.start(), m.end()
    for s, e in _word_spans(text):
        found = _scripts(text[s:e])
        if "LATIN" in found and found & {"CYRILLIC", "GREEK"}:
            yield "homoglif", s, e
    for m in _PSEUDO_TAG.finditer(text):
        yield "pseudo_znacznik", m.start(), m.end()
    for m in _PSEUDO_ROLE_LINE.finditer(text):
        yield "pseudo_znacznik", m.start(1), m.end(1)
    for m in _BASE64.finditer(text):
        yield "base64", m.start(), m.end()


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and _is_space(text[start]):
        start += 1
    while end > start and _is_space(text[end - 1]):
        end -= 1
    return start, end


def _is_verified(text: str, fragment: Fragment, start: int, end: int) -> bool:
    """Czy verify_quote zwróci dokładnie [start, end) (pierwsze wystąpienie w fragmencie)."""
    try:
        m = verify_quote(text, [fragment], fragment.id, text[start:end])
    except QuoteNotFound:
        return False
    return (m.start, m.end) == (start, end)


def _expand(text: str, fragment: Fragment, start: int, end: int) -> tuple[int, int]:
    """Rozszerza zakres w obrębie fragmentu do cytatu akceptowanego przez verify_quote.

    Rozszerza naprzemiennie w lewo i w prawo; zakres nie zaczyna się ani nie kończy
    na białym znaku. Gdy fragment jest za krótki, zwraca cały fragment bez białych znaków
    na brzegach (verify_quote odrzuci taki cytat jako za krótki).
    """
    start, end = max(start, fragment.start), min(end, fragment.end)
    go_left = True
    while True:
        s, e = _trim(text, start, end)
        if (
            s < e
            and len(_normalize(text[s:e])[0]) >= MIN_QUOTE_LEN
            and (_is_verified(text, fragment, s, e))
        ):
            return s, e
        can_left, can_right = start > fragment.start, end < fragment.end
        if not (can_left or can_right):
            return _trim(text, fragment.start, fragment.end) if e - s < MIN_QUOTE_LEN else (s, e)
        if (go_left and can_left) or not can_right:
            start -= 1
        else:
            end += 1
        go_left = not go_left


def scan_heuristics(text: str, fragments: Sequence[Fragment]) -> list[InjectionHit]:
    """Zwraca trafienia heurystyk posortowane po początku, potem po nazwie reguły."""
    hits: list[InjectionHit] = []
    for rule, raw_start, raw_end in _raw_spans(text):
        fragment = next((f for f in fragments if f.start <= raw_start < f.end), None)
        if fragment is None:
            continue
        start, end = _expand(text, fragment, raw_start, raw_end)
        hits.append(InjectionHit(rule, fragment.id, text[start:end], start, end))
    return sorted(hits, key=lambda h: (h.start, h.rule))
