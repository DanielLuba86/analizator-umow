"""Skrypty check_threat_model.py i check_docs.py nie przepuszczają po cichu błędów."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


tm = load("check_threat_model")
docs = load("check_docs")

BACKEND = {"tests/api/test_auth.py::test_ok", "tests/x.py::TestKlasa::test_m"}
JOBS = {"gitleaks"}


def row(cell: str) -> str:
    return f"| T1 | LLM01 | opis | obrona | {cell} | ryzyko |"


def test_valid_row_has_no_errors() -> None:
    line = row("`tests/api/test_auth.py::test_ok`<br>`ci:gitleaks`")
    assert tm.row_errors(line, BACKEND, JOBS) == []


def test_malformed_backend_ref_next_to_valid_one_is_an_error() -> None:
    line = row("`tests/api/test_auth.py::test_ok`<br>`tests/api/test-typo.py::test_nope`")
    assert len(tm.row_errors(line, BACKEND, JOBS)) == 1


def test_class_based_ref_is_checked_not_skipped() -> None:
    assert tm.row_errors(row("`tests/x.py::TestKlasa::test_m`"), BACKEND, JOBS) == []
    assert len(tm.row_errors(row("`tests/x.py::TestKlasa::test_brak`"), BACKEND, JOBS)) == 1


def test_row_without_any_reference_is_an_error() -> None:
    assert len(tm.row_errors(row("brak"), BACKEND, JOBS)) == 1


def test_links_with_title_and_angle_brackets_are_extracted() -> None:
    text = 'Zob. [a](sciezka/a.md "tytuł"), [b](<katalog z spacją/b.md>) i [c](c.md#sekcja).'
    assert docs.links(text) == ["sciezka/a.md", "katalog z spacją/b.md", "c.md#sekcja"]


def test_mermaid_fence_with_trailing_space_or_indent_is_found() -> None:
    text = (
        "```mermaid \nflowchart LR\n  A --> B\n```\n\n"
        "- punkt:\n\n  ```mermaid\n  sequenceDiagram\n  ```\n"
    )
    blocks = docs.mermaid_blocks(text)
    assert len(blocks) == 2
    assert blocks[1].strip() == "sequenceDiagram"
