"""Lightweight in-process metrics.

We avoid adding a heavy metrics backend for MVP. The metrics object keeps
counters/gauges/histograms in memory and exposes a snapshot. If the project
later needs Prometheus, the only change is in this module.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Iterator


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        self._histograms: dict[str, list[float]] = defaultdict(list)

    def inc(self, name: str, value: int = 1, **labels: Any) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._counters[key] += value

    def gauge(self, name: str, value: float, **labels: Any) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._gauges[key] = value

    def observe(self, name: str, value: float, **labels: Any) -> None:
        key = self._key(name, labels)
        with self._lock:
            self._histograms[key].append(value)
            # Bound memory for MVP
            if len(self._histograms[key]) > 1000:
                self._histograms[key] = self._histograms[key][-1000:]

    @contextmanager
    def time(self, name: str, **labels: Any) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.observe(name, time.perf_counter() - start, **labels)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "avg": (sum(v) / len(v)) if v else 0.0,
                        "p95": (
                            sorted(v)[int(0.95 * len(v))]
                            if v
                            else 0.0
                        ),
                    }
                    for k, v in self._histograms.items()
                },
            }

    @staticmethod
    def _key(name: str, labels: dict[str, Any]) -> str:
        if not labels:
            return name
        return name + "{" + ",".join(f"{k}={v}" for k, v in sorted(labels.items())) + "}"


_metrics: Metrics | None = None


def get_metrics() -> Metrics:
    global _metrics
    if _metrics is None:
        _metrics = Metrics()
    return _metrics


def reset_metrics() -> None:
    global _metrics
    _metrics = Metrics()
