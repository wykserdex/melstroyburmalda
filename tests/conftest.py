"""Shared pytest fixtures."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Make `src` importable for tests
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    from telegram_outreach.config.settings import reset_settings_cache

    # Provide required secrets for Settings()
    os.environ.setdefault("TELEGRAM_API_ID", "12345")
    os.environ.setdefault("TELEGRAM_API_HASH", "0123456789abcdef0123")
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.fixture
def settings():
    from telegram_outreach.config.settings import Settings, reset_settings_cache

    reset_settings_cache()
    return Settings()  # type: ignore[call-arg]


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
