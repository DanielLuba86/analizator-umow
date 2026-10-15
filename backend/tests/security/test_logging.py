import json
import logging
from typing import Any

import pytest
import structlog

from app.security.logging import configure_logging, redact_contract_text

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
