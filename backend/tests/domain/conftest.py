from pathlib import Path

import pytest

UMOWY_DIR = Path(__file__).resolve().parents[3] / "data" / "umowy"


@pytest.fixture(scope="session")
def umowy_dir() -> Path:
    return UMOWY_DIR


@pytest.fixture(scope="session")
def zlecenie_text() -> str:
    return (UMOWY_DIR / "umowa_zlecenia.md").read_text(encoding="utf-8")
