"""Tracing — minimal context-based correlation_id propagation.

We don't pull in OpenTelemetry for MVP. The pattern here is compatible with
OTel — we can replace `correlation_id_var` with OTel's `trace.get_current_span()`
without touching business code.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from ..config.logging import correlation_id_var, new_correlation_id


def current_correlation_id() -> str | None:
    return correlation_id_var.get()


def bind_correlation_id(value: str | None) -> None:
    correlation_id_var.set(value)


def new_correlation() -> str:
    cid = new_correlation_id()
    correlation_id_var.set(cid)
    return cid


class Tracer:
    """No-op tracer interface so that callers don't import OTel directly."""

    def start_span(self, name: str, **attrs: Any) -> "Span":
        return Span(name=name, attrs=attrs)


class Span:
    def __init__(self, name: str, attrs: dict | None = None) -> None:
        self.name = name
        self.attrs = attrs or {}
        self.cid = current_correlation_id()

    def set_attribute(self, key: str, value: Any) -> None:
        self.attrs[key] = value

    def __enter__(self) -> "Span":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None
