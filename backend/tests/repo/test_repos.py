# ruff: noqa: S106
import unicodedata
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.model import Claim
from app.domain.quotes import QuoteMatch
from app.repo import models
from app.repo.actions import ActionAlreadyDecided, decide_action, list_pending, request_action
from app.repo.analyses import (
    AnalysisAlreadyActive,
    active_analysis,
    add_finding,
    add_rejected,
    count_findings,
    create_analysis,
    list_findings,
    set_status,
)
from app.repo.audit import audit
from app.repo.contracts import (
    add_contract,
    add_version,
    get_version,
    get_version_text,
    list_fragments,
)
from app.repo.seed import seed
from app.repo.templates import add_template_version, search_templates

TEXT = "UMOWA\n\n§ 1. Przedmiot\nTreść pierwsza.\n\n§ 2. Kary\nKara umowna 100 zł.\n"


def _user(s: Session, login: str = "u1", role: str = "prawnik") -> int:
    u = models.User(login=login, password_hash="x", role=role)
    s.add(u)
    s.flush()
    return u.id


def _version(s: Session, text: str = TEXT) -> tuple[int, int]:
    uid = _user(s)
    cid = add_contract(s, title="T", kind="najem", source="wewnętrzna", created_by=uid)
    return uid, add_version(s, cid, text)


def _claim() -> Claim:
    return Claim(
        typ="kara",
        teza="Kara umowna",
        cytat="Kara umowna 100 zł.",
        fragment_id="§2",
        uzasadnienie="u",
        poziom_ryzyka="średnie",
    )


def test_add_version_increments_nr_and_stores_fragments(db_session: Session) -> None:
    uid = _user(db_session)
    cid = add_contract(db_session, title="T", kind="najem", source="wewnętrzna", created_by=uid)
    v1 = add_version(db_session, cid, TEXT)
    v2 = add_version(db_session, cid, TEXT + "więcej")
    assert get_version(db_session, v1).nr == 1
    assert get_version(db_session, v2).nr == 2
    frags = list_fragments(db_session, v1)
    assert len(frags) >= 3
    assert frags[0].label == "Komparycja"
    assert [f.start for f in frags] == sorted(f.start for f in frags)
    assert get_version_text(db_session, v1) == TEXT
    assert len(get_version(db_session, v1).sha256) == 64


def test_add_version_normalizes_to_nfc(db_session: Session) -> None:
    uid = _user(db_session)
    cid = add_contract(db_session, title="T", kind="najem", source="wewnętrzna", created_by=uid)
    nfd = unicodedata.normalize("NFD", "§ 1. Zażółć gęślą jaźń")
    vid = add_version(db_session, cid, nfd)
    stored = get_version_text(db_session, vid)
    assert stored == unicodedata.normalize("NFC", nfd)
    assert stored != nfd


def test_active_analysis_detects_running(db_session: Session) -> None:
    uid, vid = _version(db_session)
    assert active_analysis(db_session, vid) is None
    aid = create_analysis(db_session, vid, uid, "m")
    assert active_analysis(db_session, vid) == aid
    set_status(db_session, aid, "running")
    assert active_analysis(db_session, vid) == aid
    set_status(db_session, aid, "done", turns=3, cost_usd=0.1234, reason="ok")
    assert active_analysis(db_session, vid) is None
    row = db_session.get(models.Analysis, aid)
    assert row is not None
    assert row.finished_at is not None and row.turns == 3 and row.reason == "ok"
    assert float(row.cost_usd or 0) == pytest.approx(0.1234)


def test_set_status_running_has_no_finished_at(db_session: Session) -> None:
    uid, vid = _version(db_session)
    aid = create_analysis(db_session, vid, uid, "m")
    set_status(db_session, aid, "running")
    row = db_session.get(models.Analysis, aid)
    assert row is not None and row.finished_at is None


def test_create_analysis_raises_when_active(db_session: Session) -> None:
    uid, vid = _version(db_session)
    create_analysis(db_session, vid, uid, "m")
    with pytest.raises(AnalysisAlreadyActive):
        create_analysis(db_session, vid, uid, "m")


def test_findings_and_rejected(db_session: Session) -> None:
    uid, vid = _version(db_session)
    aid = create_analysis(db_session, vid, uid, "m")
    add_finding(db_session, aid, _claim(), QuoteMatch(start=50, end=70))
    add_finding(db_session, aid, _claim(), QuoteMatch(start=10, end=30))
    add_rejected(db_session, aid, _claim(), "brak_dosłownego_cytatu")
    assert count_findings(db_session, aid) == 2
    found = list_findings(db_session, aid)
    assert [f.start for f in found] == [10, 50]
    assert found[0].fragment_id == "§2" and found[0].end == 30
    rej = db_session.scalars(select(models.RejectedClaim)).all()
    assert len(rej) == 1 and rej[0].powod == "brak_dosłownego_cytatu"


def test_request_action_idempotent(db_session: Session) -> None:
    uid, vid = _version(db_session)
    aid = create_analysis(db_session, vid, uid, "m")
    a = request_action(db_session, aid, "opinia", {"x": 1})
    b = request_action(db_session, aid, "opinia", {"x": 2})
    c = request_action(db_session, aid, "eksport", {})
    assert a == b != c
    assert len(list_pending(db_session)) == 2


def test_decide_action_sets_fields(db_session: Session) -> None:
    uid, vid = _version(db_session)
    aid = create_analysis(db_session, vid, uid, "m")
    act = request_action(db_session, aid, "opinia", {})
    row = decide_action(db_session, act, uid, True)
    assert row.status == "zatwierdzona"
    assert row.decided_by == uid and row.decided_at is not None
    assert list_pending(db_session) == []


def test_decide_twice_raises(db_session: Session) -> None:
    uid, vid = _version(db_session)
    aid = create_analysis(db_session, vid, uid, "m")
    act = request_action(db_session, aid, "opinia", {})
    decide_action(db_session, act, uid, False)
    with pytest.raises(ActionAlreadyDecided):
        decide_action(db_session, act, uid, True)


def test_search_templates_filters_by_kind(db_session: Session) -> None:
    add_template_version(db_session, "najem", "Kara umowna", "wzorzec najem")
    add_template_version(db_session, "dostawa", "Kara umowna", "wzorzec dostawa")
    res = search_templates(db_session, "najem", "kara")
    assert [t.kind for t in res] == ["najem"]


def test_search_templates_returns_latest_version_only(db_session: Session) -> None:
    assert add_template_version(db_session, "najem", "Poufność", "stara treść") == 1
    assert add_template_version(db_session, "najem", "Poufność", "nowa treść") == 2
    res = search_templates(db_session, "najem", "Poufność")
    assert len(res) == 1 and res[0].wersja == 2 and res[0].tresc == "nowa treść"
    assert search_templates(db_session, "najem", "stara") == []
    assert [t.wersja for t in search_templates(db_session, "najem", "")] == [2]


def test_search_templates_escapes_wildcards(db_session: Session) -> None:
    add_template_version(db_session, "najem", "Kara", "kara 5 procent")
    assert search_templates(db_session, "najem", "%") == []
    assert search_templates(db_session, "najem", "_") == []
    assert search_templates(db_session, "najem", "\\") == []
    add_template_version(db_session, "najem", "Rabat", "rabat 100% wartości")
    assert [t.nazwa_klauzuli for t in search_templates(db_session, "najem", "%")] == ["Rabat"]


def test_audit_inserts(db_session: Session) -> None:
    uid = _user(db_session)
    audit(db_session, uid, "login", "user:1")
    audit(db_session, None, "x", "y")
    assert db_session.scalar(select(func.count()).select_from(models.AuditLog)) == 2


def _settings(**kw: str | None) -> Settings:
    return Settings(
        database_url="postgresql+psycopg://x",
        **{k: SecretStr(v) if v else None for k, v in kw.items()},  # type: ignore[arg-type]
    )


def test_seed_skips_users_without_password_env(db_session: Session) -> None:
    seed(db_session, _settings())
    assert db_session.scalar(select(func.count()).select_from(models.User)) == 0
    assert db_session.scalar(select(func.count()).select_from(models.Template)) == 12


def test_seed_is_idempotent(db_session: Session) -> None:
    s = _settings(seed_assistant_password="a-pass", seed_lawyer_password="l-pass")
    seed(db_session, s)
    seed(db_session, s)
    users = db_session.scalars(select(models.User).order_by(models.User.login)).all()
    assert [(u.login, u.role) for u in users] == [("asystent", "asystent"), ("prawnik", "prawnik")]
    assert all("pass" not in u.password_hash for u in users)
    assert db_session.scalar(select(func.count()).select_from(models.Template)) == 12
    assert db_session.scalar(select(func.max(models.Template.wersja))) == 1


def test_seed_custom_templates_path(db_session: Session, tmp_path: Path) -> None:
    p = tmp_path / "k.json"
    p.write_text('[{"kind": "najem", "nazwa_klauzuli": "X", "tresc": "Y"}]', encoding="utf-8")
    seed(db_session, _settings(), templates_path=p)
    assert db_session.scalar(select(func.count()).select_from(models.Template)) == 1
