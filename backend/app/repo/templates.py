from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.repo.models import Template

TemplateRow = Template


def _escape_like(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_templates(s: Session, kind: str, query: str, limit: int = 5) -> list[TemplateRow]:
    latest = (
        select(Template.nazwa_klauzuli, func.max(Template.wersja).label("w"))
        .where(Template.kind == kind)
        .group_by(Template.nazwa_klauzuli)
        .subquery()
    )
    stmt = (
        select(Template)
        .join(
            latest,
            (Template.nazwa_klauzuli == latest.c.nazwa_klauzuli) & (Template.wersja == latest.c.w),
        )
        .where(Template.kind == kind)
    )
    if query:
        pat = f"%{_escape_like(query)}%"
        stmt = stmt.where(
            or_(
                Template.nazwa_klauzuli.ilike(pat, escape="\\"),
                Template.tresc.ilike(pat, escape="\\"),
            )
        )
    return list(s.scalars(stmt.order_by(Template.nazwa_klauzuli).limit(limit)))


def add_template_version(s: Session, kind: str, name: str, text: str) -> int:
    # Nie ma wiersza nadrzędnego do zablokowania (pierwsza wersja też musi czekać),
    # więc blokada doradcza na (rodzaj, nazwa) do końca transakcji szereguje max + 1.
    s.execute(select(func.pg_advisory_xact_lock(func.hashtext(kind), func.hashtext(name))))
    current: int = s.execute(
        select(func.coalesce(func.max(Template.wersja), 0)).where(
            Template.kind == kind, Template.nazwa_klauzuli == name
        )
    ).scalar_one()
    wersja = current + 1
    t = Template(kind=kind, nazwa_klauzuli=name, tresc=text, wersja=wersja)
    s.add(t)
    s.flush()
    return wersja
