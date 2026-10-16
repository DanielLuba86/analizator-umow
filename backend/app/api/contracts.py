"""Umowy i ich wersje. Tekst walidowany przed zapisem: pusty → 422, za długi → 413."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StringConstraints

from app.api.deps import DbDep, SettingsDep, UserDep, current_user
from app.api.errors import ApiError
from app.config import Settings
from app.domain.model import ContractKind, ContractSource
from app.repo import analyses as analyses_repo
from app.repo import contracts as contracts_repo
from app.repo.audit import audit

router = APIRouter(prefix="/api", tags=["contracts"], dependencies=[Depends(current_user)])

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class ContractIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    kind: ContractKind
    source: ContractSource
    text: str


class VersionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str


class ContractCreated(BaseModel):
    id: int
    version_id: int


class VersionCreated(BaseModel):
    version_id: int
    nr: int


class ContractListItem(BaseModel):
    id: int
    title: str
    kind: str
    source: str
    versions: int


class VersionListItem(BaseModel):
    id: int
    nr: int
    created_at: str


class ContractOut(BaseModel):
    id: int
    title: str
    kind: str
    source: str
    versions: list[VersionListItem]


class FragmentOut(BaseModel):
    id: str
    label: str
    start: int
    end: int


class VersionAnalysis(BaseModel):
    id: int
    status: str
    started_at: str


class VersionOut(BaseModel):
    id: int
    contract_id: int
    nr: int
    text: str
    fragments: list[FragmentOut]
    analyses: list[VersionAnalysis]


def check_contract_text(text: str, settings: Settings) -> None:
    if not text.strip():
        raise ApiError(422, "pusty_tekst", "Tekst umowy jest pusty.")
    if len(text) > settings.max_contract_chars:
        raise ApiError(413, "za_dlugi_tekst", "Tekst umowy przekracza dopuszczalną długość.")


def contract_not_found() -> ApiError:
    return ApiError(404, "nie_znaleziono_umowy", "Nie znaleziono umowy.")


def version_not_found() -> ApiError:
    return ApiError(404, "nie_znaleziono_wersji", "Nie znaleziono wersji umowy.")


@router.post("/contracts", status_code=201)
def create_contract(
    body: ContractIn, db: DbDep, user: UserDep, settings: SettingsDep
) -> ContractCreated:
    check_contract_text(body.text, settings)
    cid = contracts_repo.add_contract(
        db, title=body.title, kind=body.kind, source=body.source, created_by=user.id
    )
    vid = contracts_repo.add_version(db, cid, body.text)
    audit(db, user.id, "contract_create", f"contract:{cid}")
    db.commit()
    return ContractCreated(id=cid, version_id=vid)


@router.get("/contracts")
def list_contracts(db: DbDep) -> list[ContractListItem]:
    return [
        ContractListItem(id=c.id, title=c.title, kind=c.kind, source=c.source, versions=c.versions)
        for c in contracts_repo.list_contracts(db)
    ]


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: int, db: DbDep) -> ContractOut:
    c = contracts_repo.get_contract(db, contract_id)
    if c is None:
        raise contract_not_found()
    versions = [
        VersionListItem(id=v.id, nr=v.nr, created_at=v.created_at.isoformat())
        for v in contracts_repo.list_versions(db, contract_id)
    ]
    return ContractOut(id=c.id, title=c.title, kind=c.kind, source=c.source, versions=versions)


@router.post("/contracts/{contract_id}/versions", status_code=201)
def add_version(
    contract_id: int, body: VersionIn, db: DbDep, user: UserDep, settings: SettingsDep
) -> VersionCreated:
    if contracts_repo.get_contract(db, contract_id) is None:
        raise contract_not_found()
    check_contract_text(body.text, settings)
    vid = contracts_repo.add_version(db, contract_id, body.text)
    nr = contracts_repo.get_version(db, vid).nr
    audit(db, user.id, "version_add", f"version:{vid}")
    db.commit()
    return VersionCreated(version_id=vid, nr=nr)


@router.get("/versions/{version_id}")
def get_version(version_id: int, db: DbDep) -> VersionOut:
    v = contracts_repo.find_version(db, version_id)
    if v is None:
        raise version_not_found()
    fragments = [
        FragmentOut(id=f.id, label=f.label, start=f.start, end=f.end)
        for f in contracts_repo.list_fragments(db, version_id)
    ]
    runs = [
        VersionAnalysis(id=a.id, status=a.status, started_at=a.started_at.isoformat())
        for a in analyses_repo.list_analyses(db, version_id)
    ]
    return VersionOut(
        id=v.id,
        contract_id=v.contract_id,
        nr=v.nr,
        text=v.text,
        fragments=fragments,
        analyses=runs,
    )
