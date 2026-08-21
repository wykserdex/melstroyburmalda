"""scan_channels — find channels + ingest their recent messages.

Read from Telegram (only read operations — safe in dry-run).
Idempotent at message level via (channel_id, telegram_message_id) unique key.
"""
from __future__ import annotations

from collections.abc import Sequence

from ...config.settings import Settings
from ...domain.entities import Channel, Message
from ...domain.enums import ChannelSource, EventType
from ...ports.repositories import (
    ChannelRepository,
    EventLogRepository,
    MessageRepository,
)
from ...ports.telegram import TelegramClientPort
from .._common import log_event, new_id, now


class ScanChannelsUseCase:
    def __init__(
        self,
        telegram: TelegramClientPort,
        uow_factory,
        settings: Settings,
    ) -> None:
        self._tg = telegram
        self._uow_factory = uow_factory
        self._settings = settings

    async def execute(
        self,
        *,
        keywords: Sequence[str] | None = None,
        cities: Sequence[str] | None = None,
        limit: int | None = None,
        min_subscribers: int | None = None,
    ) -> dict:
        keywords = list(keywords or self._settings.keyword_list)
        cities = list(cities or self._settings.city_list)
        limit = limit or self._settings.max_sample_messages
        min_subs = (
            min_subscribers
            if min_subscribers is not None
            else self._settings.min_subscribers
        )

        report = {
            "channels_scanned": 0,
            "channels_new": 0,
            "messages_new": 0,
            "messages_duplicate": 0,
        }

        queries = self._build_queries(keywords, cities)

        async with self._uow_factory() as uow:
            assert (
                uow.channels is not None
                and uow.messages is not None
                and uow.events is not None
            )
            for q in queries:
                infos = await self._tg.search_channels(q, limit=50)
                for info in infos:
                    ch = await self._register_channel(uow.channels, info, uow.events, report)
                    if ch.matches_excluded(
                        self._settings.excluded_channel_list,
                        self._settings.excluded_keyword_list,
                    ):
                        continue
                    if not ch.meets_min_subscribers(min_subs):
                        continue
                    new_msgs, dup_msgs = await self._ingest_messages(
                        uow.channels, uow.messages, ch, uow.events, limit=limit
                    )
                    report["channels_scanned"] += 1
                    report["messages_new"] += new_msgs
                    report["messages_duplicate"] += dup_msgs
                await uow.commit()

        return report

    @staticmethod
    def _build_queries(keywords: list[str], cities: list[str]) -> list[str]:
        out: list[str] = []
        for kw in keywords:
            out.append(kw)
            for c in cities:
                out.append(f"{kw} {c}")
        return out

    async def _register_channel(
        self,
        repo: ChannelRepository,
        info,
        events: EventLogRepository,
        report: dict,
    ) -> Channel:
        existing = await repo.get_by_telegram_id(info.telegram_id)
        if existing is not None:
            return existing
        ch = Channel(
            id=new_id("ch"),
            telegram_id=info.telegram_id,
            username=info.username,
            title=info.title,
            description=info.description,
            subscribers=info.subscribers,
            source=ChannelSource.SEARCH,
        )
        await repo.add(ch)
        report["channels_new"] += 1
        await log_event(
            events,
            event_type=EventType.LEAD_DISCOVERED,
            entity_type="channel",
            entity_id=ch.id,
            metadata={"telegram_id": ch.telegram_id, "title": ch.title},
        )
        return ch

    async def _ingest_messages(
        self,
        channel_repo: ChannelRepository,
        msg_repo: MessageRepository,
        ch: Channel,
        events: EventLogRepository,
        *,
        limit: int,
    ) -> tuple[int, int]:
        recent = await self._tg.get_recent_messages(ch.telegram_id, limit)
        new = 0
        dup = 0
        ts = now()
        for rm in recent:
            existing = await msg_repo.get_by_channel_and_tmid(ch.id, rm.telegram_message_id)
            if existing is not None:
                dup += 1
                continue
            msg = Message(
                id=new_id("msg"),
                channel=ch,
                telegram_message_id=rm.telegram_message_id,
                text=rm.text,
                posted_at=rm.posted_at,
                author_user_id=rm.author_user_id,
                metadata=rm.metadata,
                discovered_at=ts,
            )
            await msg_repo.add(msg)
            await log_event(
                events,
                event_type=EventType.LEAD_DISCOVERED,
                entity_type="message",
                entity_id=msg.id,
                metadata={"channel_id": ch.id, "telegram_message_id": rm.telegram_message_id},
            )
            new += 1
        await channel_repo.update_last_scanned(ch.id, ts)
        return new, dup
