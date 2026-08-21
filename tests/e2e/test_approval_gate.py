"""Гейт согласования: без Approve сообщение не уходит.

Это страховка от главного сценария страха — «агент записал меня в грузчики»:
пока оператор не нажал кнопку, SendMessageUseCase обязан отказаться работать,
даже если задача на отправку каким-то образом попала в очередь.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from telegram_outreach.application.use_cases import (
    ApproveMessageUseCase,
    DeduplicateUseCase,
    GenerateMessageUseCase,
    ParseVacancyUseCase,
    QualifyVacancyUseCase,
    RejectMessageUseCase,
    ScanChannelsUseCase,
    SendMessageUseCase,
)
from telegram_outreach.config.settings import Settings
from telegram_outreach.domain.enums import OutreachStatus
from telegram_outreach.domain.exceptions import PolicyViolation
from telegram_outreach.domain.policies import (
    FrequencyPolicy,
    MessagePolicy,
    OutreachPolicy,
)
from telegram_outreach.infrastructure.llm.message_generator import LLMMessageGenerator
from telegram_outreach.infrastructure.persistence.models import Base
from telegram_outreach.infrastructure.persistence.unit_of_work import SqlUnitOfWork
from telegram_outreach.ports.telegram import ChannelInfo, RawMessage
from tests.fixtures.fakes import (
    FakeLLM,
    FakeTelegramClient,
    InMemoryQueue,
    TrivialSimilarity,
)


@pytest.fixture
async def uow_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield lambda: SqlUnitOfWork(sm)
    await engine.dispose()


@pytest.fixture
def settings() -> Settings:
    return Settings(  # type: ignore[call-arg]
        TELEGRAM_API_ID="1",
        TELEGRAM_API_HASH="0123456789abcdef0123",
        relevance_threshold=0.5,
        confidence_threshold=0.7,
        auto_approve=False,
        max_retries=3,
        retry_base_delay=0.01,
        retry_max_delay=0.1,
        daily_message_limit=100,
        global_hourly_limit=100,
        min_subscribers=0,
    )


async def _drafted_outreach(uow_factory, settings):
    """Прогоняет пайплайн до черновика, ничего не согласовывая."""
    tg = FakeTelegramClient(
        channels=[
            ChannelInfo(
                telegram_id=100, username="jobs", title="Jobs",
                description="", subscribers=1000,
            )
        ]
    )
    tg.add_channel_messages(
        100,
        [
            RawMessage(
                channel_id=100,
                telegram_message_id=42,
                text="Ищу Python-разработчика для Telegram-бота. Бюджет 100k. @alice",
                posted_at=datetime.now(timezone.utc),
                author_user_id=555,
            )
        ],
    )
    llm = FakeLLM()
    queue = InMemoryQueue()
    frequency = FrequencyPolicy(
        min_interval_seconds=0,
        per_recipient_cooldown_hours=0,
        daily_message_limit=settings.daily_message_limit,
        global_hourly_limit=settings.global_hourly_limit,
    )
    outreach_policy = OutreachPolicy(frequency=frequency)

    await ScanChannelsUseCase(tg, uow_factory, settings).execute(limit=10)
    async with uow_factory() as uow:
        channel = (await uow.channels.list_active())[0]
        message_id = (await uow.messages.list_recent_for_channel(channel.id, None))[0].id

    vac_id = await ParseVacancyUseCase(llm, uow_factory).execute(message_id)
    await DeduplicateUseCase(uow_factory).execute(vac_id)
    lead_id = await QualifyVacancyUseCase(llm, uow_factory, settings).execute(vac_id)
    outreach_id = await GenerateMessageUseCase(
        llm=llm,
        message_generator=LLMMessageGenerator(llm),
        similarity=TrivialSimilarity(),
        message_policy=MessagePolicy(),
        outreach_policy=outreach_policy,
        uow_factory=uow_factory,
        settings=settings,
    ).execute(lead_id)

    send = SendMessageUseCase(tg, uow_factory, queue, settings, outreach_policy)
    approve = ApproveMessageUseCase(uow_factory, queue, settings)
    reject = RejectMessageUseCase(uow_factory)
    return outreach_id, tg, send, approve, reject


@pytest.mark.asyncio
async def test_drafted_outreach_is_never_sent(uow_factory, settings) -> None:
    outreach_id, tg, send, _approve, _reject = await _drafted_outreach(uow_factory, settings)

    with pytest.raises(PolicyViolation):
        await send.execute(outreach_id)

    assert tg.sent == [], "неодобренное сообщение ушло получателю"


@pytest.mark.asyncio
async def test_refusing_to_send_keeps_the_draft_approvable(uow_factory, settings) -> None:
    """Отказ отправить не должен убивать кандидата: черновик остаётся
    в DRAFTED, оператор всё ещё может согласовать его из бота."""
    outreach_id, tg, send, approve, _reject = await _drafted_outreach(uow_factory, settings)

    with pytest.raises(PolicyViolation):
        await send.execute(outreach_id)

    async with uow_factory() as uow:
        outreach = await uow.outreach.get(outreach_id)
    assert outreach.status == OutreachStatus.DRAFTED

    assert await approve.execute(outreach_id, approved_by="test")
    assert await send.execute(outreach_id) == OutreachStatus.SENT.value
    assert len(tg.sent) == 1


@pytest.mark.asyncio
async def test_rejected_outreach_is_never_sent(uow_factory, settings) -> None:
    outreach_id, tg, send, _approve, reject = await _drafted_outreach(uow_factory, settings)

    assert await reject.execute(outreach_id, reason="не мой профиль")

    with pytest.raises(PolicyViolation):
        await send.execute(outreach_id)

    assert tg.sent == []
