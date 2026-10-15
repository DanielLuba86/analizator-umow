import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

REDACTED_KEYS = frozenset(
    {"text", "tekst", "tresc", "cytat", "quote", "teza", "content", "uzasadnienie", "payload"}
)
MAX_LEN = 200
_MAX_DEPTH = 10
_FOREIGN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy")
_HANDLER_MARK = "_au_structlog_handler"


def _redact(value: Any, depth: int) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return f"<redacted len={len(value)}>" if len(value) > MAX_LEN else value
    if depth >= _MAX_DEPTH:
        return "<redacted depth>"
    if isinstance(value, dict):
        return {
            k: "<redacted>"
            if isinstance(k, str) and k.lower() in REDACTED_KEYS
            else _redact(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [_redact(v, depth + 1) for v in value]
    return _redact(repr(value), depth + 1)


def redact_contract_text(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    result: EventDict = _redact(dict(event_dict), 0)
    return result


def configure_logging(level: str) -> None:
    lvl = logging.getLevelName(level.upper())
    if not isinstance(lvl, int):
        lvl = logging.INFO
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.format_exc_info,
        redact_contract_text,
    ]
    structlog.configure(
        processors=[*shared, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )
    handler = logging.StreamHandler(sys.stdout)
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[
                shared[0],
                structlog.stdlib.add_log_level,
                *shared[2:],
            ],
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    for name in _FOREIGN_LOGGERS:
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    for name in list(logging.root.manager.loggerDict):
        if name.startswith("sqlalchemy."):
            child = logging.getLogger(name)
            child.handlers.clear()
            child.propagate = True
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, _HANDLER_MARK, False)]:
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(lvl)
