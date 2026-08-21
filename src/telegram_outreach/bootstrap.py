"""Composition root.

`build()` instantiates every concrete implementation, wires them together
and returns a `Container` with use cases, workers, and adapters. `main.py`
calls `build()` once and then runs the chosen entry point.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .application.use_cases import (
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
from .bot import BotHandlers, BotNotifier
from .config.logging import configure_logging
from .config.settings import Settings, get_settings
from .domain.policies import FrequencyPolicy, MessagePolicy, OutreachPolicy
from .infrastructure.llm import LLMMessageGenerator, OllamaClient
from .infrastructure.persistence import database as db
from .infrastructure.persistence.unit_of_work import SqlUnitOfWork
from .infrastructure.queue import AsyncioQueueBroker
from .infrastructure.similarity import NGramSimilarityChecker
from .infrastructure.telegram import (
    DryRunTelegramClient,
    TelegramAdapter,
    TelegramSession,
    TelethonChannelScanner,
    TelethonMessageSender,
    TelethonReplyListener,
)
from .observability.tracing import bind_correlation_id
from .ports.queue import QueuePort
from .ports.repositories import UnitOfWork
from .ports.telegram import TelegramClientPort
from .workers import (
    AnalyzerWorker,
    FollowupWorker,
    OutreachWorker,
    ReplyWorker,
    ScannerWorker,
)


@dataclass
class Container:
    settings: Settings
    uow_factory: type[SqlUnitOfWork]
    telegram: TelegramClientPort
    ollama: OllamaClient
    llm_generator: LLMMessageGenerator
    similarity: NGramSimilarityChecker
    queue: QueuePort
    message_policy: MessagePolicy
    outreach_policy: OutreachPolicy
    use_cases: "UseCases"
    workers: "Workers"
    bot_handlers: BotHandlers | None
    incoming_queue: asyncio.Queue
    telegram_session: TelegramSession | None
    bot_client: object | None


@dataclass
class UseCases:
    scan: ScanChannelsUseCase
    parse: ParseVacancyUseCase
    dedupe: DeduplicateUseCase
    qualify: QualifyVacancyUseCase
    generate: GenerateMessageUseCase
    approve: ApproveMessageUseCase
    reject: RejectMessageUseCase
    send: SendMessageUseCase
    process_reply: ProcessReplyUseCase
    schedule_followup: ScheduleFollowupUseCase
    run_followup: RunFollowupUseCase


@dataclass
class Workers:
    scanner: ScannerWorker
    analyzer: AnalyzerWorker
    outreach: OutreachWorker
    reply: ReplyWorker
    followup: FollowupWorker


def build(settings: Settings | None = None) -> Container:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_json)
    bind_correlation_id(None)

    # --- DB ----------------------------------------------------------------
    db.init_engine(settings)
    engine = db.get_engine()
    sm = db.get_sessionmaker()

    # --- Telegram (real or dry-run) ---------------------------------------
    telegram_session: TelegramSession | None = None
    telegram: TelegramClientPort
    incoming_queue: asyncio.Queue = asyncio.Queue()
    if not settings.dry_run:
        telegram_session = TelegramSession(settings)
        scanner = TelethonChannelScanner(telegram_session)
        sender = TelethonMessageSender(telegram_session)
        listener = TelethonReplyListener(telegram_session, incoming_queue)
        telegram = TelegramAdapter(scanner, sender, listener, incoming_queue)
    else:
        # In dry-run we still need *some* Telegram client; use a real one
        # for read ops but wrap in DryRunTelegramClient for writes.
        telegram_session = TelegramSession(settings)
        scanner = TelethonChannelScanner(telegram_session)
        sender = TelethonMessageSender(telegram_session)
        listener = TelethonReplyListener(telegram_session, incoming_queue)
        real = TelegramAdapter(scanner, sender, listener, incoming_queue)
        telegram = DryRunTelegramClient(real)

    # --- LLM ---------------------------------------------------------------
    ollama = OllamaClient(settings)
    llm_generator = LLMMessageGenerator(ollama)

    # --- Policies ----------------------------------------------------------
    frequency = FrequencyPolicy(
        min_interval_seconds=settings.min_delay_seconds,
        per_recipient_cooldown_hours=settings.per_recipient_cooldown_hours,
        daily_message_limit=settings.daily_message_limit,
        global_hourly_limit=settings.global_hourly_limit,
    )
    message_policy = MessagePolicy()
    outreach_policy = OutreachPolicy(frequency=frequency)

    # --- Queue -------------------------------------------------------------
    queue: QueuePort = AsyncioQueueBroker(sm)

    # --- Similarity --------------------------------------------------------
    similarity = NGramSimilarityChecker(threshold=settings.similarity_threshold)

    # --- UoW factory -------------------------------------------------------
    def uow_factory() -> UnitOfWork:
        return SqlUnitOfWork(sm)

    # --- Use cases ---------------------------------------------------------
    use_cases = UseCases(
        scan=ScanChannelsUseCase(telegram, uow_factory, settings),
        parse=ParseVacancyUseCase(ollama, uow_factory),
        dedupe=DeduplicateUseCase(uow_factory),
        qualify=QualifyVacancyUseCase(ollama, uow_factory, settings),
        generate=GenerateMessageUseCase(
            llm=ollama,
            message_generator=llm_generator,
            similarity=similarity,
            message_policy=message_policy,
            outreach_policy=outreach_policy,
            uow_factory=uow_factory,
            settings=settings,
        ),
        approve=ApproveMessageUseCase(uow_factory, queue, settings),
        reject=RejectMessageUseCase(uow_factory),
        send=SendMessageUseCase(telegram, uow_factory, queue, settings, outreach_policy),
        process_reply=ProcessReplyUseCase(ollama, uow_factory, queue, settings),
        schedule_followup=ScheduleFollowupUseCase(uow_factory, queue, settings),
        run_followup=RunFollowupUseCase(telegram, uow_factory, settings),
    )

    # --- Bot (optional) ----------------------------------------------------
    # Собирается ДО воркеров: анализатору нотификатор нужен в конструкторе,
    # иначе пришлось бы дописывать его в уже готовый объект.
    bot_handlers: BotHandlers | None = None
    bot_client = None
    bot_notifier: BotNotifier | None = None
    if settings.bot_token and settings.bot_allowed_user_ids:
        # Imported lazily to avoid hard dependency on Telethon's bot API at import time
        from telethon import TelegramClient as TgClient  # noqa: WPS433

        from .infrastructure.telegram.bot import TelethonBotNotifier

        bot_client = TgClient(
            session="management_bot",
            api_id=settings.telegram_api_id,
            api_hash=settings.telegram_api_hash,
        )
        # start as bot
        # We don't await here — the main loop will handle it.
        bot_handlers = BotHandlers(
            bot_client,
            uow_factory,
            use_cases.approve,
            use_cases.reject,
            settings,
        )
        bot_notifier = BotNotifier(
            TelethonBotNotifier(bot_client, settings.bot_allowed_user_ids)
        )

    # --- Workers -----------------------------------------------------------
    workers = Workers(
        scanner=ScannerWorker(use_cases.scan, use_cases.parse, queue, settings),
        analyzer=AnalyzerWorker(
            use_cases.parse,
            use_cases.dedupe,
            use_cases.qualify,
            use_cases.generate,
            queue,
            uow_factory,
            settings,
            # Без нотификатора черновик молча ждёт в БД, пока оператор сам не
            # вызовет /pending.
            notifier=bot_notifier,
        ),
        outreach=OutreachWorker(use_cases.send, queue, uow_factory, settings),
        reply=ReplyWorker(use_cases.process_reply, incoming_queue),
        followup=FollowupWorker(
            use_cases.schedule_followup,
            use_cases.run_followup,
            queue,
            uow_factory,
            settings,
        ),
    )

    return Container(
        settings=settings,
        uow_factory=SqlUnitOfWork,  # type: ignore[arg-type]
        telegram=telegram,
        ollama=ollama,
        llm_generator=llm_generator,
        similarity=similarity,
        queue=queue,
        message_policy=message_policy,
        outreach_policy=outreach_policy,
        use_cases=use_cases,
        workers=workers,
        bot_handlers=bot_handlers,
        incoming_queue=incoming_queue,
        telegram_session=telegram_session,
        bot_client=bot_client,
    )
