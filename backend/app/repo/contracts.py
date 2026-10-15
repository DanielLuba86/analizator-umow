import hashlib
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.fragments import Fragment, split_into_fragments
from app.repo.models import Contract, ContractVersion
from app.repo.models import Fragment as FragmentRow

VersionRow = ContractVersion


def add_contract(s: Session, *, title: str, kind: str, source: str, created_by: int) -> int:
    c = Contract(title=title, kind=kind, source=source, created_by=created_by)
    s.add(c)
    s.flush()
    return c.id


def add_version(s: Session, contract_id: int, text: str) -> int:
    text = unicodedata.normalize("NFC", text)
    # blokada kontraktu serializuje równoległe dodawanie wersji (nr = max+1)
    s.execute(select(Contract.id).where(Contract.id == contract_id).with_for_update()).one()
    nr = (
        s.scalar(
            select(func.coalesce(func.max(ContractVersion.nr), 0)).where(
                ContractVersion.contract_id == contract_id
            )
        )
        or 0
    ) + 1
    v = ContractVersion(
        contract_id=contract_id,
        nr=nr,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    s.add(v)
    s.flush()
    s.add_all(
        FragmentRow(version_id=v.id, frag_id=f.id, label=f.label, start=f.start, end=f.end)
        for f in split_into_fragments(text)
    )
    s.flush()
    return v.id


def get_version(s: Session, version_id: int) -> VersionRow:
    return s.execute(select(ContractVersion).where(ContractVersion.id == version_id)).scalar_one()


def list_fragments(s: Session, version_id: int) -> list[Fragment]:
    rows = s.scalars(
        select(FragmentRow).where(FragmentRow.version_id == version_id).order_by(FragmentRow.start)
    )
    return [Fragment(id=r.frag_id, label=r.label, start=r.start, end=r.end) for r in rows]


def get_version_text(s: Session, version_id: int) -> str:
    return get_version(s, version_id).text
