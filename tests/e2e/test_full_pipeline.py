"""E2E: scan → parse → dedupe → qualify → generate → approve → send → reply → follow-up."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from telegram_outreach.application.use_cases import (
    ApproveMessageUseCase,
    DeduplicateUseCase,
    GenerateMessageUseCase,
    ParseVacancyUseCase,
    ProcessReplyUseCase,
    QualifyVacancyUseCase,
    RejectMessageUseCase,
    RunFollowupUseCase,
    ScanChannelsUseCase,
    ScheduleFollowupUseCase,
    SendMessageUseCase,
)
from telegram_outreach.config.settings import Settings
from telegram_outreach.domain.enums import (
    ContactSource,
    EventType,
    OutreachStatus,
)
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


@pytest.mark.asyncio
async def test_e2e_full_pipeline(uow_factory, settings) -> None:
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
    similarity = TrivialSimilarity()
    msg_gen = LLMMessageGenerator(llm)
    message_policy = MessagePolicy()
    frequency = FrequencyPolicy(
        min_interval_seconds=0,
        per_recipient_cooldown_hours=0,
        daily_message_limit=settings.daily_message_limit,
        global_hourly_limit=settings.global_hourly_limit,
    )
    outreach_policy = OutreachPolicy(frequency=frequency)

    scan = ScanChannelsUseCase(tg, uow_factory, settings)
    parse_uc = ParseVacancyUseCase(llm, uow_factory)
    dedupe = DeduplicateUseCase(uow_factory)
    qualify = QualifyVacancyUseCase(llm, uow_factory, settings)
    gen = GenerateMessageUseCase(
        llm=llm,
        message_generator=msg_gen,
        similarity=similarity,
        message_policy=message_policy,
        outreach_policy=outreach_policy,
        uow_factory=uow_factory,
        settings=settings,
    )
    approve = ApproveMessageUseCase(uow_factory, queue, settings)
    reject = RejectMessageUseCase(uow_factory)
    send = SendMessageUseCase(tg, uow_factory, queue, settings, outreach_policy)
    process_reply = ProcessReplyUseCase(llm, uow_factory, queue, settings)
    sched_fu = ScheduleFollowupUseCase(uow_factory, queue, settings)
    run_fu = RunFollowupUseCase(tg, uow_factory, settings)

    # 1) Scan
    report = await scan.execute(limit=10)
    assert report["messages_new"] == 1

    # 2) Find the new message id
    async with uow_factory() as uow:
        msgs = await uow.messages.list_recent_for_channel(
            (await uow.channels.list_active())[0].id, None
        )
    assert len(msgs) == 1
    message_id = msgs[0].id

    # 3) Parse
    vac_id = await parse_uc.execute(message_id)
    assert vac_id is not None

    # 4) Dedupe (no dupes yet)
    assert not await dedupe.execute(vac_id)

    # 5) Qualify
    lead_id = await qualify.execute(vac_id)
    assert lead_id is not None

    # 6) Generate
    outreach_id = await gen.execute(lead_id)
    assert outreach_id is not None

    # 7) Approve
    assert await approve.execute(outreach_id, approved_by="test")

    # 8) Send (sync run)
    result = await send.execute(outreach_id)
    assert result == OutreachStatus.SENT.value
    assert len(tg.sent) == 1

    # 9) Idempotency: sending again is a no-op
    result2 = await send.execute(outreach_id)
    assert result2 == OutreachStatus.SENT.value
    assert len(tg.sent) == 1  # still 1

    # 10) Process a reply
    async with uow_factory() as uow:
        # The "outreach" was sent; we can query conversation by outreach
        from telegram_outreach.infrastructure.persistence.models import OutreachModel
        from sqlalchemy import select

        res = await uow.session.execute(select(OutreachModel))
        row = res.scalar_one()
        sent_mid = row.sent_message_id

    intent = await process_reply.execute(
        from_user_id=555,
        from_chat_id=555,
        from_username="alice",
        text="Интересно, расскажи подробнее",
        telegram_message_id=999,
        posted_at=datetime.now(timezone.utc),
        is_reply_to=sent_mid,
    )
    assert intent in {"interested", "question", "other"}

    # 11) Follow-up scheduling
    async with uow_factory() as uow:
        from telegram_outreach.infrastructure.persistence.models import ConversationModel
        from sqlalchemy import select

        res = await uow.session.execute(select(ConversationModel))
        conv_row = res.scalar_one()
        conv_id = conv_row.id

    # Because reply was received, follow-up should cancel itself
    run_at = await sched_fu.execute(conv_id)
    assert run_at is None  # cancelled because user replied
