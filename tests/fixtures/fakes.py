"""In-memory fakes for tests — full pipeline, no external services."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from telegram_outreach.domain.value_objects import ContactIdentifier
from telegram_outreach.ports.llm import (
    DraftMessage,
    LLMClientPort,
    ReplyAnalysis,
    ScoreResult,
    VacancyParse,
)
from telegram_outreach.ports.queue import QueuePort, Task, TaskHandler
from telegram_outreach.ports.similarity import SimilarityChecker, SimilarityResult
from telegram_outreach.ports.telegram import (
    ChannelInfo,
    IncomingUpdate,
    RawMessage,
    SentMessage,
    TelegramClientPort,
)


class FakeTelegramClient(TelegramClientPort):
    """In-memory Telegram. Configure with seed data."""

    def __init__(self, channels: list[ChannelInfo] | None = None) -> None:
        self.channels = list(channels or [])
        self.messages: dict[int, list[RawMessage]] = {}
        self.sent: list[tuple[ContactIdentifier, str]] = []
        self.fail_send = False
        self.flood_until: datetime | None = None

    def add_channel_messages(self, channel_id: int, messages: list[RawMessage]) -> None:
        self.messages[channel_id] = list(messages)

    async def search_channels(self, query: str, limit: int) -> list[ChannelInfo]:
        return self.channels[:limit]

    async def get_channel_info(self, telegram_id: int) -> ChannelInfo | None:
        for c in self.channels:
            if c.telegram_id == telegram_id:
                return c
        return None

    async def get_recent_messages(self, channel_id: int, limit: int) -> list[RawMessage]:
        return self.messages.get(channel_id, [])[:limit]

    async def resolve_public_contact(self, channel: ChannelInfo):
        from telegram_outreach.domain.value_objects import ContactIdentifier

        return (ContactIdentifier(chat_id=channel.telegram_id), channel.title)

    async def send_message(self, recipient: ContactIdentifier, text: str) -> SentMessage:
        if self.fail_send:
            raise RuntimeError("simulated failure")
        self.sent.append((recipient, text))
        return SentMessage(telegram_message_id=hash(text) & 0x7FFFFFFF, sent_at=datetime.utcnow())

    async def iter_incoming(self) -> AsyncIterator[IncomingUpdate]:
        if False:
            yield


class FakeLLM(LLMClientPort):
    """Deterministic LLM. Choose parse result via `next_parse`."""

    def __init__(self) -> None:
        self.next_parse: VacancyParse = VacancyParse(
            is_vacancy=True,
            kind="vacancy",
            title="Telegram bot for incoming requests",
            description="Need automation of incoming Telegram messages.",
            requirements=["Python", "aiogram", "PostgreSQL"],
            has_budget=False,
            contact_username="alice",
            confidence=0.9,
        )
        self.next_score: float = 0.85
        self.next_message: str = "Здравствуйте. У меня есть опыт с автоматизацией Telegram-ботов. Готов обсудить детали вашей задачи."
        self.next_reply: str = "interested"

    async def classify_vacancy(self, text: str) -> VacancyParse:
        return self.next_parse

    async def score_relevance(self, vacancy) -> ScoreResult:
        return ScoreResult(score=self.next_score, reason="matches stack")

    async def generate_message(self, lead) -> DraftMessage:
        return DraftMessage(
            detected_need="automation of incoming requests",
            proposed_solution="custom Telegram bot",
            message=self.next_message,
        )

    async def analyze_reply(self, message: str, conversation_context: str) -> ReplyAnalysis:
        return ReplyAnalysis(
            intent=self.next_reply,
            summary="ok",
            requires_followup=False,
        )


class TrivialSimilarity(SimilarityChecker):
    def check(self, candidate: str, history) -> SimilarityResult:
        return SimilarityResult(score=0.0, is_too_similar=False)


class InMemoryQueue(QueuePort):
    def __init__(self) -> None:
        self._q: asyncio.Queue[Task] = asyncio.Queue()
        self.processed: list[str] = []

    async def enqueue(self, task: Task) -> None:
        await self._q.put(task)

    async def enqueue_delayed(self, task: Task, run_at: datetime) -> None:
        await self._q.put(task)

    async def consume(self, handler: TaskHandler) -> None:
        while True:
            task = await self._q.get()
            await handler(task)
            self.processed.append(task.id)

    async def acknowledge(self, task_id: str) -> None:
        pass

    async def reject(self, task_id: str, requeue: bool) -> None:
        pass

    async def size(self) -> int:
        return self._q.qsize()


def make_uow_factory(in_memory_db_url: str = "sqlite+aiosqlite:///:memory:"):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from telegram_outreach.infrastructure.persistence.models import Base
    from telegram_outreach.infrastructure.persistence.unit_of_work import SqlUnitOfWork

    engine = create_async_engine(in_memory_db_url)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async def _setup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.get_event_loop().run_until_complete(_setup())

    def factory():
        return SqlUnitOfWork(sm)

    return factory
