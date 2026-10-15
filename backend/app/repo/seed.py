"""Dane początkowe: wzorce klauzul i konta demo (idempotentne)."""

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.repo.db import make_engine, session_factory
from app.repo.models import Template, User
from app.repo.templates import add_template_version
from app.security.passwords import hash_password

# repo/backend/app/repo/seed.py -> korzeń repo; w obrazie Dockera ścieżkę zadaje templates_path
DEFAULT_TEMPLATES_PATH = Path(__file__).resolve().parents[3] / "data" / "wzorce" / "klauzule.json"


def _seed_templates(s: Session, path: Path) -> None:
    entries = json.loads(path.read_text(encoding="utf-8"))
    for e in entries:
        exists = s.scalar(
            select(Template.id)
            .where(Template.kind == e["kind"], Template.nazwa_klauzuli == e["nazwa_klauzuli"])
            .limit(1)
        )
        if exists is None:
            add_template_version(s, e["kind"], e["nazwa_klauzuli"], e["tresc"])


def _seed_user(s: Session, login: str, role: str, password: str | None) -> None:
    if not password:
        return
    if s.scalar(select(User.id).where(User.login == login)) is None:
        s.add(User(login=login, password_hash=hash_password(password), role=role))
        s.flush()


def seed(s: Session, settings: Settings, templates_path: Path = DEFAULT_TEMPLATES_PATH) -> None:
    _seed_templates(s, templates_path)
    assistant = settings.seed_assistant_password
    lawyer = settings.seed_lawyer_password
    _seed_user(s, "asystent", "asystent", assistant.get_secret_value() if assistant else None)
    _seed_user(s, "prawnik", "prawnik", lawyer.get_secret_value() if lawyer else None)


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    with session_factory(engine)() as s:
        seed(s, settings)
        s.commit()
    engine.dispose()


if __name__ == "__main__":
    main()
