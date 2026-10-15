from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisContext:
    """Stały kontekst jednej analizy; narzędzia agenta biorą identyfikatory wyłącznie stąd."""

    analysis_id: int
    version_id: int
    kind: str
    max_findings: int
