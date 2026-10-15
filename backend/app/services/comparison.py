"""Porównanie dwóch wersji umowy: deterministyczny diff fragmentów i tez, bez LLM."""

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.domain.diff import FindingKey, diff_findings, diff_fragments
from app.domain.fragments import fragment_text
from app.repo import analyses, comparisons, contracts


class VersionsOfDifferentContracts(Exception):
    """Porównywane wersje należą do różnych umów."""


@dataclass(frozen=True)
class ComparisonResult:
    id: int
    fragment_changes: list[dict[str, Any]]
    finding_changes: dict[str, list[dict[str, str]]] | None


def _labelled_fragments(s: Session, version_id: int) -> list[tuple[str, str]]:
    text = contracts.get_version_text(s, version_id)
    return [(f.label, fragment_text(text, f)) for f in contracts.list_fragments(s, version_id)]


def _finding_keys(s: Session, version_id: int) -> list[FindingKey] | None:
    analysis_id = analyses.latest_done_analysis(s, version_id)
    if analysis_id is None:
        return None
    labels = {f.id: f.label for f in contracts.list_fragments(s, version_id)}
    return [
        FindingKey(f.typ, labels.get(f.fragment_id, f.fragment_id), f.cytat)
        for f in analyses.list_findings(s, analysis_id)
    ]


def compare_versions(s: Session, version_a: int, version_b: int) -> ComparisonResult:
    """`version_a` to stara, `version_b` nowa wersja. Zapisuje wynik w `comparisons` (flush)."""
    va, vb = contracts.get_version(s, version_a), contracts.get_version(s, version_b)
    if va.contract_id != vb.contract_id:
        raise VersionsOfDifferentContracts
    fragment_changes = [
        asdict(c)
        for c in diff_fragments(
            _labelled_fragments(s, version_a), _labelled_fragments(s, version_b)
        )
    ]
    keys_a, keys_b = _finding_keys(s, version_a), _finding_keys(s, version_b)
    finding_changes = (
        None
        if keys_a is None or keys_b is None
        else {k: [asdict(x) for x in v] for k, v in diff_findings(keys_a, keys_b).items()}
    )
    cid = comparisons.add_comparison(s, version_a, version_b, fragment_changes, finding_changes)
    return ComparisonResult(cid, fragment_changes, finding_changes)
