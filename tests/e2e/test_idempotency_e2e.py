"""Test: opt-out propagation + idempotency on restart."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from telegram_outreach.application.use_cases import (
    ApproveMessageUseCase,
    GenerateMessageUseCase,
    ProcessReplyUseCase,
    QualifyVacancyUseCase,
    ScanChannelsUseCase,
    SendMessageUseCase,
)
from telegram_outreach.config.settings import Settings
from telegram_outreach.domain.enums import OutreachStatus
from telegram_outreach.domain.policies import FrequencyPolicy, MessagePolicy, OutreachPolicy
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


@pytest.mark.asyncio
async def test_opt_out_propagates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory = lambda: SqlUnitOfWork(sm)

    settings = Settings(  # type: ignore[call-arg]
        TELEGRAM_API_ID="1", TELEGRAM_API_HASH="0123456789abcdef0123",
        relevance_threshold=0.5, confidence_threshold=0.7,
        daily_message_limit=100, global_hourly_limit=100,
        min_subscribers=0,
    )
    tg = FakeTelegramClient(
        channels=[ChannelInfo(telegram_id=1, username="c", title="c", description="", subscribers=10)]
    )
    tg.add_channel_messages(
        1,
        [RawMessage(
            channel_id=1, telegram_message_id=1,
            text="Need a bot. @bob",
            posted_at=datetime.now(timezone.utc), author_user_id=10,
        )],
    )
    llm = FakeLLM()
    queue = InMemoryQueue()
    similarity = TrivialSimilarity()
    msg_gen = LLMMessageGenerator(llm)
    message_policy = MessagePolicy()
    frequency = FrequencyPolicy(
        min_interval_seconds=0, per_recipient_cooldown_hours=0,
        daily_message_limit=100, global_hourly_limit=100,
    )
    outreach_policy = OutreachPolicy(frequency=frequency)

    await ScanChannelsUseCase(tg, uow_factory, settings).execute(limit=1)

    async with uow_factory() as uow:
        chans = await uow.channels.list_active()
        msgs = await uow.messages.list_recent_for_channel(chans[0].id, None)
    assert len(msgs) == 1
    msg_id = msgs[0].id

    from telegram_outreach.application.use_cases import ParseVacancyUseCase, DeduplicateUseCase
    parse = ParseVacancyUseCase(llm, uow_factory)
    dedupe = DeduplicateUseCase(uow_factory)
    qualify = QualifyVacancyUseCase(llm, uow_factory, settings)
    gen = GenerateMessageUseCase(
        llm=llm, message_generator=msg_gen, similarity=similarity,
        message_policy=message_policy, outreach_policy=outreach_policy,
        uow_factory=uow_factory, settings=settings,
    )
    approve = ApproveMessageUseCase(uow_factory, queue, settings)
    send = SendMessageUseCase(tg, uow_factory, queue, settings, outreach_policy)
    process_reply = ProcessReplyUseCase(llm, uow_factory, queue, settings)

    vac_id = await parse.execute(msg_id)
    assert vac_id
    assert not await dedupe.execute(vac_id)
    lead_id = await qualify.execute(vac_id)
    out_id = await gen.execute(lead_id)
    await approve.execute(out_id)
    assert await send.execute(out_id) == OutreachStatus.SENT.value

    # User replies "no thanks, don't contact me" → opt_out
    async with uow_factory() as uow:
        from sqlalchemy import select
        from telegram_outreach.infrastructure.persistence.models import OutreachModel, ConversationModel

        out_row = (await uow.session.execute(select(OutreachModel))).scalar_one()
        conv_row = (await uow.session.execute(select(ConversationModel))).scalar_one()
        sent_mid = out_row.sent_message_id

    llm.next_reply = "opt_out"
    result = await process_reply.execute(
        from_user_id=10, from_chat_id=10, from_username="bob",
        text="Не пишите мне больше",
        telegram_message_id=42, posted_at=datetime.now(timezone.utc),
        is_reply_to=sent_mid,
    )
    assert result == "opted_out"

    # Confirm contact is opted_out
    async with uow_factory() as uow:
        from sqlalchemy import select
        from telegram_outreach.infrastructure.persistence.models import ContactModel

        c_row = (await uow.session.execute(select(ContactModel))).scalar_one()
        assert c_row.opted_out is True
