from typing import cast, get_args

import pytest

from app.domain.model import (
    ACTION_STATUSES,
    ACTION_TYPES,
    ANALYSIS_STATUSES,
    FINDING_TYPES,
    RISK_LEVELS,
    ActionStatus,
    ActionType,
    AnalysisStatus,
    Claim,
    ClaimInvalid,
    FindingType,
    RiskLevel,
    validate_claim,
)


def _claim(**kw: object) -> Claim:
    base: dict[str, object] = {
        "typ": "strona",
        "teza": "Zleceniodawca to Alfa sp. z o.o.",
        "cytat": "Alfa sp. z o.o. z siedzibą w Warszawie",
        "fragment_id": "f001",
        "uzasadnienie": "Wskazanie strony umowy.",
    }
    base.update(kw)
    return Claim(**base)  # type: ignore[arg-type]


def reason_of(c: Claim) -> str:
    with pytest.raises(ClaimInvalid) as ei:
        validate_claim(c)
    assert str(ei.value) == ei.value.reason
    return ei.value.reason


def test_literal_tuples_match_literals() -> None:
    assert FINDING_TYPES == get_args(FindingType)
    assert RISK_LEVELS == get_args(RiskLevel)
    assert ACTION_TYPES == get_args(ActionType)
    assert ACTION_STATUSES == get_args(ActionStatus)
    assert ANALYSIS_STATUSES == get_args(AnalysisStatus)
    assert FINDING_TYPES == ("strona", "termin", "kara", "ryzyko", "wstrzyknięcie")
    assert RISK_LEVELS == ("niskie", "średnie", "wysokie")
    assert ACTION_TYPES == ("opinia", "wzorzec", "eksport", "kwarantanna")
    assert ACTION_STATUSES == ("oczekuje", "zatwierdzona", "odrzucona")
    assert ANALYSIS_STATUSES == (
        "queued",
        "running",
        "done",
        "failed",
        "quarantined",
        "budget_exceeded",
    )


def test_valid_claims_pass() -> None:
    validate_claim(_claim())
    validate_claim(_claim(typ="ryzyko", poziom_ryzyka="wysokie"))
    validate_claim(_claim(typ="kara"))
    validate_claim(_claim(typ="kara", poziom_ryzyka="niskie"))
    validate_claim(_claim(teza="x" * 500))


def test_risk_claim_requires_level() -> None:
    assert "poziom" in reason_of(_claim(typ="ryzyko"))


def test_empty_teza_rejected() -> None:
    reason_of(_claim(teza=""))
    reason_of(_claim(teza="   \n"))


def test_empty_uzasadnienie_rejected() -> None:
    reason_of(_claim(uzasadnienie=" "))


def test_teza_over_500_chars_rejected() -> None:
    reason_of(_claim(teza="x" * 501))


def test_level_not_allowed_on_strona() -> None:
    for typ in ("strona", "termin", "wstrzyknięcie"):
        reason_of(_claim(typ=typ, poziom_ryzyka="niskie"))


def test_unknown_values_rejected() -> None:
    reason_of(_claim(typ=cast(FindingType, "inny")))
    reason_of(_claim(typ="ryzyko", poziom_ryzyka=cast(RiskLevel, "krytyczne")))


def test_reason_does_not_leak_claim_text() -> None:
    reason = reason_of(_claim(teza="TAJNA-TEZA" * 60))
    assert "TAJNA" not in reason
