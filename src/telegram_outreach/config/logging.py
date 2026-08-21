"""Structured logging configuration with correlation_id and secret redaction.

Domain/application code should never import structlog directly — they receive
a bound logger via dependency injection. This module is the only place that
knows about structlog.
"""
from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar
from typing import Any

import structlog

# Per-task correlation id propagated through async context.
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


# --- Secret redaction ---------------------------------------------------------
_REDACT_KEYS = {
    "api_id", "api_hash", "session", "string_session",
    "password", "token", "bot_token", "authorization", "auth",
    "TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_SESSION",
    "BOT_TOKEN",
}

_REDACT_PATTERNS = [
    (re.compile(r"\b\d{6,8}:[A-Za-z0-9_-]{20,}\b"), "[REDACTED:tg_credential]"),
    (re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{30,}\b"), "[REDACTED:bot_token]"),
    (re.compile(r"[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"), "[REDACTED:jwt]"),
]


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: ("[REDACTED]" if k.lower() in {rk.lower() for rk in _REDACT_KEYS} else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, str):
        out = value
        for pattern, replacement in _REDACT_PATTERNS:
            out = pattern.sub(replacement, out)
        return out
    return value


def _redact_processor(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    return _redact(event_dict)  # type: ignore[return-value]


def _add_correlation_id(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    cid = correlation_id_var.get()
    if cid and "correlation_id" not in event_dict:
        event_dict["correlation_id"] = cid
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Initialise structlog + stdlib logging. Idempotent."""
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        _add_correlation_id,
        timestamper,
        _redact_processor,
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=shared_processors + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib (uvloop, sqlalchemy, telethon) into structlog format
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Tame noisy libraries
    for name in ("telethon", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[return-value]


def set_correlation_id(value: str | None) -> None:
    correlation_id_var.set(value)


def new_correlation_id() -> str:
    import uuid
    return uuid.uuid4().hex
