"""Narzędzia agenta: jedyny kanał, którym agent działa. Logika niezależna od SDK.

Każda metoda to jedna transakcja (commit przy sukcesie). Narzędzia logują wyłącznie
nazwę, wynik i identyfikatory — nigdy argumentów ani treści umowy.
"""

import json
import re
from typing import Any, cast

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.agent.context import AnalysisContext
from app.domain.fragments import fragment_text
from app.domain.model import ActionType, Claim, ClaimInvalid, validate_claim
from app.domain.quotes import QuoteNotFound, verify_quote
from app.repo import actions, analyses, contracts, templates
from app.repo.models import CONTRACT_KINDS

ToolResult = dict[str, Any]

TAG = "untrusted_contract_fragment"
_TAG_OPEN_OR_CLOSE = re.compile(rf"<(/?)({TAG})", re.IGNORECASE)
AGENT_ACTION_TYPES: tuple[str, ...] = ("opinia", "wzorzec")
MAX_ACTION_JUSTIFICATION_LEN = 2000
_LIMIT_HINT = "Osiągnięto limit tez dla tej analizy. Nie zgłaszaj kolejnych tez."

log = structlog.get_logger(__name__)


def _result(text: str, *, is_error: bool = False) -> ToolResult:
    return {"content": [{"type": "text", "text": text}], "is_error": is_error}


def _json(data: Any) -> ToolResult:
    return _result(json.dumps(data, ensure_ascii=False))


def _error(text: str) -> ToolResult:
    return _result(text, is_error=True)


def _escape_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _neutralize(body: str) -> str:
    return _TAG_OPEN_OR_CLOSE.sub(r"&lt;\1\2", body)


class AgentTools:
    def __init__(self, ctx: AnalysisContext, session_factory: sessionmaker[Session]) -> None:
        self.ctx = ctx
        self._sf = session_factory

    def _log(self, tool: str, outcome: str, **ids: int | str) -> None:
        log.info(
            "agent_tool",
            tool=tool,
            outcome=outcome,
            analysis_id=self.ctx.analysis_id,
            **ids,
        )

    async def list_fragments(self) -> ToolResult:
        with self._sf() as s:
            frags = contracts.list_fragments(s, self.ctx.version_id)
        self._log("list_fragments", "ok")
        return _json([{"id": f.id, "label": f.label, "length": f.end - f.start} for f in frags])

    async def read_fragment(self, fragment_id: str) -> ToolResult:
        if not isinstance(fragment_id, str):
            self._log("read_fragment", "invalid_input")
            return _error("Identyfikator fragmentu musi być tekstem.")
        with self._sf() as s:
            frag = next(
                (
                    f
                    for f in contracts.list_fragments(s, self.ctx.version_id)
                    if f.id == fragment_id
                ),
                None,
            )
            if frag is None:
                self._log("read_fragment", "unknown_fragment")
                return _error("Nieznany fragment. Użyj list_fragments, aby poznać identyfikatory.")
            text = fragment_text(contracts.get_version_text(s, self.ctx.version_id), frag)
        self._log("read_fragment", "ok", fragment_id=frag.id)
        body = _neutralize(text)
        return _result(
            f'<{TAG} id="{_escape_attr(frag.id)}" label="{_escape_attr(frag.label)}">\n'
            f"{body}\n</{TAG}>"
        )

    async def search_templates(self, kind: str, query: str) -> ToolResult:
        if not isinstance(kind, str) or not isinstance(query, str):
            self._log("search_templates", "invalid_input")
            return _error("Argumenty kind i query muszą być tekstem.")
        if kind not in CONTRACT_KINDS:
            self._log("search_templates", "invalid_kind")
            return _error(f"Nieznany rodzaj umowy. Dozwolone: {', '.join(CONTRACT_KINDS)}.")
        with self._sf() as s:
            rows = templates.search_templates(s, kind, query)
            data = [
                {
                    "id": t.id,
                    "kind": t.kind,
                    "nazwa_klauzuli": t.nazwa_klauzuli,
                    "tresc": t.tresc,
                    "wersja": t.wersja,
                }
                for t in rows
            ]
        self._log("search_templates", "ok", count=len(data))
        return _json(data)

    async def submit_finding(
        self,
        typ: str,
        teza: str,
        cytat: str,
        fragment_id: str,
        uzasadnienie: str,
        poziom_ryzyka: str | None = None,
        template_id: int | str | None = None,
    ) -> ToolResult:
        tid = _parse_template_id(template_id)
        strings_ok = all(isinstance(v, str) for v in (typ, teza, cytat, fragment_id, uzasadnienie))
        risk_ok = poziom_ryzyka is None or isinstance(poziom_ryzyka, str)
        if tid is False or not strings_ok or not risk_ok:
            self._log("submit_finding", "invalid_input")
            return _error("Nieprawidłowy typ argumentów tezy.")
        claim = Claim(
            typ=cast(Any, typ),
            teza=teza,
            cytat=cytat,
            fragment_id=fragment_id,
            uzasadnienie=uzasadnienie,
            poziom_ryzyka=cast(Any, poziom_ryzyka),
            template_id=tid,
        )
        aid = self.ctx.analysis_id
        with self._sf() as s:
            over_limit = analyses.count_findings(s, aid) >= self.ctx.max_findings
            try:
                validate_claim(claim)
            except ClaimInvalid as e:
                self._log("submit_finding", "claim_invalid")
                return _error(f"limit_tez: {_LIMIT_HINT}" if over_limit else e.reason)
            if over_limit:
                analyses.add_rejected(s, aid, claim, "limit_tez")
                s.commit()
                self._log("submit_finding", "rejected", reason="limit_tez")
                return _error(f"limit_tez: {_LIMIT_HINT}")
            text = contracts.get_version_text(s, self.ctx.version_id)
            frags = contracts.list_fragments(s, self.ctx.version_id)
            try:
                match = verify_quote(text, frags, claim.fragment_id, claim.cytat)
            except QuoteNotFound as e:
                analyses.add_rejected(s, aid, claim, e.reason)
                s.commit()
                self._log("submit_finding", "rejected", reason=e.reason)
                return _error(f"{e.reason}: {e.hint}")
            try:
                analyses.add_finding(s, aid, claim, match)
                s.commit()
            except IntegrityError:
                s.rollback()
                self._log("submit_finding", "invalid_template")
                return _error("Nieznany template_id. Użyj identyfikatora z search_templates.")
        self._log("submit_finding", "accepted")
        return _json({"status": "przyjęta", "start": match.start, "end": match.end})

    async def request_action(self, typ: str, uzasadnienie: str) -> ToolResult:
        if not isinstance(typ, str) or not isinstance(uzasadnienie, str):
            self._log("request_action", "invalid_input")
            return _error("Argumenty typ i uzasadnienie muszą być tekstem.")
        if typ not in AGENT_ACTION_TYPES:
            self._log("request_action", "forbidden_type")
            return _error(f"Niedozwolony typ wniosku. Dozwolone: {', '.join(AGENT_ACTION_TYPES)}.")
        if not uzasadnienie.strip() or len(uzasadnienie) > MAX_ACTION_JUSTIFICATION_LEN:
            self._log("request_action", "invalid_justification")
            return _error(
                f"Uzasadnienie nie może być puste ani dłuższe niż "
                f"{MAX_ACTION_JUSTIFICATION_LEN} znaków."
            )
        with self._sf() as s:
            action_id = actions.request_action(
                s,
                self.ctx.analysis_id,
                cast(ActionType, typ),
                {"uzasadnienie": uzasadnienie, "zrodlo": "agent"},
            )
            s.commit()
        self._log("request_action", "ok", action_id=action_id)
        return _json({"status": "wniosek_utworzony", "id": action_id})


def _parse_template_id(value: object) -> int | None | bool:
    """None gdy brak; int gdy poprawny; False gdy nieprawidłowy."""
    if value is None:
        return None
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    return False
