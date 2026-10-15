"""Deterministyczne różnice: między wersjami umowy i między analizami."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.quotes import normalize_whitespace


def _norm(s: str) -> str:
    return normalize_whitespace(s)[0].strip()


@dataclass(frozen=True)
class FragmentChange:
    label: str
    kind: Literal["dodany", "usunięty", "zmieniony"]
    old_text: str | None
    new_text: str | None


def diff_fragments(
    old: Sequence[tuple[str, str]], new: Sequence[tuple[str, str]]
) -> list[FragmentChange]:
    """Porównuje po etykiecie; kolejność: etykiety z `new`, potem usunięte (kolejność z `old`)."""
    old_by_label = dict(old)
    new_labels = {label for label, _ in new}
    changes: list[FragmentChange] = []
    for label, text in new:
        if label not in old_by_label:
            changes.append(FragmentChange(label, "dodany", None, text))
        elif _norm(old_by_label[label]) != _norm(text):
            changes.append(FragmentChange(label, "zmieniony", old_by_label[label], text))
    for label, text in old:
        if label not in new_labels:
            changes.append(FragmentChange(label, "usunięty", text, None))
    return changes


@dataclass(frozen=True)
class FindingKey:
    typ: str
    label: str
    cytat: str

    @classmethod
    def of(cls, typ: str, label: str, cytat: str) -> "FindingKey":
        return cls(typ, label, _norm(cytat))


def _sorted_keys(keys: Iterable[FindingKey]) -> list[FindingKey]:
    return sorted(keys, key=lambda k: (k.typ, k.label, k.cytat))


def diff_findings(
    old: Iterable[FindingKey], new: Iterable[FindingKey]
) -> dict[str, list[FindingKey]]:
    """Klucze "nowe" (tylko w `new`) i "ustąpiło" (tylko w `old`); cytat po normalizacji."""
    old_n = {FindingKey.of(k.typ, k.label, k.cytat) for k in old}
    new_n = {FindingKey.of(k.typ, k.label, k.cytat) for k in new}
    return {
        "nowe": _sorted_keys(new_n - old_n),
        "ustąpiło": _sorted_keys(old_n - new_n),
    }
