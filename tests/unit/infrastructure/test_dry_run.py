"""Dry-run adapter test — confirms write methods refuse to act."""
from __future__ import annotations

from datetime import datetime

import pytest

from telegram_outreach.domain.exceptions import PolicyViolation
from telegram_outreach.domain.value_objects import ContactIdentifier
from telegram_outreach.infrastructure.telegram.dry_run import DryRunTelegramClient
from telegram_outreach.ports.telegram import (
    ChannelInfo,
    IncomingUpdate,
    RawMessage,
    SentMessage,
)


class FakeRealClient:
    def __init__(self) -> None:
        self.send_called = 0

    async def search_channels(self, q, limit):
        return []

    async def get_channel_info(self, tid):
        return None

    async def get_recent_messages(self, cid, limit):
        return []

    async def resolve_public_contact(self, channel):
        return None

    async def send_message(self, recipient, text):
        self.send_called += 1
        return SentMessage(telegram_message_id=1, sent_at=datetime.utcnow())

    async def iter_incoming(self):
        if False:
            yield


@pytest.mark.asyncio
async def test_dry_run_blocks_send() -> None:
    real = FakeRealClient()
    dry = DryRunTelegramClient(real)
    with pytest.raises(PolicyViolation):
        await dry.send_message(ContactIdentifier(user_id=1), "hi")
    assert real.send_called == 0


@pytest.mark.asyncio
async def test_dry_run_allows_reads() -> None:
    real = FakeRealClient()
    dry = DryRunTelegramClient(real)
    assert await dry.search_channels("x", 10) == []
    assert await dry.get_channel_info(1) is None
