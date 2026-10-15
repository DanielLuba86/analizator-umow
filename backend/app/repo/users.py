from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repo.models import User

UserRow = User


def get_user_by_login(s: Session, login: str) -> UserRow | None:
    return s.scalar(select(User).where(User.login == login))
