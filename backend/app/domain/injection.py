"""Heurystyki wykrywania ukrytych instrukcji (prompt injection) w niezaufanych umowach.

Moduł czysto domenowy (tylko stdlib). Każde trafienie niesie cytat, który przechodzi
przez ten sam weryfikator cytatów co tezy agenta (`verify_quote`).
"""

import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.fragments import Fragment
from app.domain.quotes import MIN_QUOTE_LEN, normalize_whitespace

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


MAX_EXPAND_LEN = 200
_FLAGS = re.IGNORECASE | re.UNICODE

_COMMAND_PHRASES = re.compile(
    r"\b(?:"
    + "|".join(
        [
            r"zignoruj\s+(?:wszystkie\s+)?(?:poprzednie|wcześniejsze)\s+(?:instrukcje|polecenia)",
            r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
            r"jako\s+(?:asystent|model)\s+(?:AI|językowy)",
            r"(?:oznacz|uznaj)\s+(?:tę|tą|niniejszą)\s+umowę\s+(?:jako|za)\s+"
            r"(?:bezpieczną|niskiego\s+ryzyka)",
            r"nie\s+(?:zgłaszaj|raportuj|oznaczaj)",
            r"system\s+prompt",
            r"you\s+are\s+now\b",  # poza „if you are now” (warunek umowny) — _after_if
        ]
    )
    + r")\b",
    _FLAGS,
)
_ZERO_WIDTH = re.compile(r"[\u00ad\u200b\u200c\u200d\u2060\ufeff]+")
_BIDI = re.compile(r"[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]+")
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


_IF_BEFORE = re.compile(r"\bif[\s,]*$", _FLAGS)
_IF_LOOKBACK = 20


def _after_if(text: str, start: int) -> bool:
    """„if you are now…” to zwrot warunkowy w umowach anglojęzycznych, nie polecenie."""
    return _IF_BEFORE.search(text[max(0, start - _IF_LOOKBACK) : start]) is not None


def _raw_spans(text: str) -> Iterator[tuple[InjectionRule, int, int]]:
    for m in _COMMAND_PHRASES.finditer(text):
        if m.group().lower().startswith("you") and _after_if(text, m.start()):
            continue
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


@dataclass(frozen=True)
class _Normalized:
    """Fragment znormalizowany raz: tekst oraz przesunięcia w oryginale."""

    text: str
    starts: list[int]
    ends: list[int]


def _expand(frag: Fragment, norm: _Normalized, raw_start: int, raw_end: int) -> tuple[int, int]:
    """Rozszerza trafienie w obrębie fragmentu do cytatu akceptowanego przez verify_quote.

    Pracuje na znormalizowanym fragmencie (policzonym raz). Rozszerza naprzemiennie w lewo
    i w prawo do >= MIN_QUOTE_LEN znaków, nie więcej niż MAX_EXPAND_LEN. Gdy okno nie jest
    jednoznaczne, zwraca pierwsze wystąpienie tego samego tekstu (tak jak verify_quote).
    Zbyt krótki fragment: cały fragment bez białych znaków na brzegach.
    """
    hay, starts, ends = norm.text, norm.starts, norm.ends
    if not hay:
        return raw_start, raw_end
    a = max(bisect_right(starts, max(raw_start, frag.start) - frag.start) - 1, 0)
    b = min(bisect_left(ends, min(raw_end, frag.end) - frag.start) + 1, len(hay))
    b = max(b, a + 1)
    go_left = True
    while True:
        ta, tb = a, b
        while ta < tb and hay[ta] == " ":
            ta += 1
        while tb > ta and hay[tb - 1] == " ":
            tb -= 1
        size = tb - ta
        if size >= MIN_QUOTE_LEN:
            pos = hay.find(hay[ta:tb])
            if pos == ta or size >= MAX_EXPAND_LEN:
                ta, tb = pos, pos + size
                break
        can_left, can_right = a > 0, b < len(hay)
        if not (can_left or can_right):
            if size < MIN_QUOTE_LEN:  # cały fragment, bez białych znaków na brzegach
                ta, tb = 0, len(hay)
                while ta < tb and hay[ta] == " ":
                    ta += 1
                while tb > ta and hay[tb - 1] == " ":
                    tb -= 1
            break
        if (go_left and can_left) or not can_right:
            a -= 1
        else:
            b += 1
        go_left = not go_left
    a, b = ta, tb
    return frag.start + starts[a], frag.start + ends[b - 1]


def scan_heuristics(text: str, fragments: Sequence[Fragment]) -> list[InjectionHit]:
    """Zwraca trafienia heurystyk posortowane po początku, potem po nazwie reguły."""
    hits: list[InjectionHit] = []
    cache: dict[str, _Normalized] = {}
    ordered = sorted(fragments, key=lambda f: f.start)
    starts = [f.start for f in ordered]
    for rule, raw_start, raw_end in _raw_spans(text):
        i = bisect_right(starts, raw_start) - 1
        fragment = ordered[i] if i >= 0 and raw_start < ordered[i].end else None
        if fragment is None:
            continue
        norm = cache.get(fragment.id)
        if norm is None:
            t, st, en = normalize_whitespace(text[fragment.start : fragment.end])
            norm = cache[fragment.id] = _Normalized(t, st, en)
        start, end = _expand(fragment, norm, raw_start, raw_end)
        hits.append(InjectionHit(rule, fragment.id, text[start:end], start, end))
    return sorted(hits, key=lambda h: (h.start, h.rule))
