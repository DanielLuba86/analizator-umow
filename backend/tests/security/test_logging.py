import json
import logging
import logging.config
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from uvicorn.config import LOGGING_CONFIG

from app.security.logging import configure_logging, redact_contract_text


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    names = ["", "uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy"]
    saved = [
        (n, list(logging.getLogger(n).handlers), logging.getLogger(n).propagate) for n in names
    ]
    level = logging.getLogger().level
    yield
    structlog.reset_defaults()
    for n, handlers, prop in saved:
        lg = logging.getLogger(n)
        lg.handlers[:] = handlers
        lg.propagate = prop
    logging.getLogger().setLevel(level)


LONG = "Zamawiający zapłaci karę umowną. " * 20


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    out = capsys.readouterr().out
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def test_redaction_removes_contract_fields(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger().info("zapis", cytat="Tajny cytat umowy", id=5)
    raw = capsys.readouterr().out
    assert "Tajny cytat" not in raw
    rec = json.loads(raw.splitlines()[-1])
    assert rec["cytat"] == "<redacted>"
    assert rec["id"] == 5
    assert rec["level"] == "info"
    assert "timestamp" in rec


def test_redaction_truncates_long_strings(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger().info("x", other=LONG)
    rec = _lines(capsys)[-1]
    assert rec["other"] == f"<redacted len={len(LONG)}>"


def test_event_is_subject_to_length_rule(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.get_logger().info(LONG)
    assert _lines(capsys)[-1]["event"] == f"<redacted len={len(LONG)}>"


def test_redaction_nested_dict() -> None:
    ev = redact_contract_text(
        None,
        "info",
        {
            "event": "e",
            "claim": {"cytat": "sekret", "ok": "tak", "deep": {"teza": "s"}},
            "items": [{"quote": "s"}, LONG, "krótki"],
        },
    )
    assert ev["claim"] == {"cytat": "<redacted>", "ok": "tak", "deep": {"teza": "<redacted>"}}
    assert ev["items"][0] == {"quote": "<redacted>"}
    assert ev["items"][1] == f"<redacted len={len(LONG)}>"
    assert ev["items"][2] == "krótki"


@pytest.mark.parametrize(
    "key", ["text", "tresc", "cytat", "quote", "teza", "content", "uzasadnienie", "payload"]
)
def test_all_sensitive_keys(key: str) -> None:
    assert redact_contract_text(None, "info", {key: "a"})[key] == "<redacted>"


def test_long_traceback_is_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    try:
        raise ValueError(LONG)
    except ValueError:
        structlog.get_logger().error("fail", exc_info=True)
    raw = capsys.readouterr().out
    assert "karę umowną" not in raw
    rec = json.loads(raw.splitlines()[-1])
    assert rec["exception"].startswith("<redacted len=")


def test_stdlib_logger_is_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logging.getLogger("x").info("wiadomość %s", LONG)
    raw = capsys.readouterr().out
    assert "karę umowną" not in raw
    rec = json.loads(raw.splitlines()[-1])
    assert rec["event"].startswith("<redacted len=")
    assert rec["level"] == "info"


def test_configure_logging_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    configure_logging("INFO")
    capsys.readouterr()
    logging.getLogger("y").info("raz")
    assert len(_lines(capsys)) == 1
    structlog.get_logger().info("dwa")
    assert len(_lines(capsys)) == 1


def test_uvicorn_loggers_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
    configure_logging("INFO")
    capsys.readouterr()
    try:
        raise ValueError(LONG)
    except ValueError:
        logging.getLogger("uvicorn.error").exception("błąd")
    logging.getLogger("uvicorn.access").info('%s - "%s %s"', "1.2.3.4", "GET", "/api/x")
    raw = capsys.readouterr().out
    assert "karę umowną" not in raw
    recs = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert len(recs) == 2
    assert recs[0]["exception"].startswith("<redacted len=")


def test_depth_cap_fails_closed() -> None:
    nested: Any = "sekret"
    for _ in range(12):
        nested = {"a": nested}
    out = redact_contract_text(None, "info", {"n": nested})
    cur: Any = out["n"]
    while isinstance(cur, dict):
        cur = cur["a"]
    assert cur == "<redacted depth>"


def test_non_str_values_are_length_checked() -> None:
    class Big:
        def __repr__(self) -> str:
            return "x" * 300

    ev = redact_contract_text(None, "info", {"b": b"y" * 300, "s": {"z" * 300}, "o": Big(), "n": 3})
    assert ev["b"] == "<redacted len=303>"
    assert ev["s"] == ["<redacted len=300>"]
    assert ev["o"] == "<redacted len=300>"
    assert ev["n"] == 3


def test_keys_case_insensitive_and_tekst() -> None:
    ev = redact_contract_text(None, "info", {"Cytat": "a", "tekst": "b", "TEXT": "c"})
    assert ev == {"Cytat": "<redacted>", "tekst": "<redacted>", "TEXT": "<redacted>"}
