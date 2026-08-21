"""Main entry point — CLI + subcommands.

Examples:
    python -m telegram_outreach --dry-run
    python -m telegram_outreach --limit 10
    python -m telegram_outreach --keywords вакансии работа
    python -m telegram_outreach outreach approve <id>
    python -m telegram_outreach auth
    python -m telegram_outreach run-all
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from typing import Any

import click

from .bootstrap import build
from .config.settings import Settings, reset_settings_cache
from .observability.tracing import new_correlation


def _build_settings(args: argparse.Namespace) -> Settings:
    reset_settings_cache()
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    # CLI overrides
    if getattr(args, "dry_run", False):
        s.dry_run = True
    if getattr(args, "limit", None) is not None:
        s.cli_limit = args.limit
    if getattr(args, "keywords", None):
        s.cli_keywords = list(args.keywords)
    if getattr(args, "min_subs", None) is not None:
        s.cli_min_subscribers = args.min_subs
    if getattr(args, "no_bot", False):
        s.bot_token = None
    return s


async def _run_dry(args: argparse.Namespace) -> int:
    settings = _build_settings(args)
    container = build(settings)
    assert container.telegram_session is not None
    await container.telegram_session.start()
    try:
        report = await container.use_cases.scan.execute(
            limit=settings.cli_limit or settings.max_sample_messages,
            min_subscribers=getattr(args, "min_subs", None),
            keywords=getattr(args, "keywords", None) or None,
        )
        click.echo("Scan report:")
        for k, v in report.items():
            click.echo(f"  {k}: {v}")
    finally:
        await container.telegram_session.stop()
    return 0


async def _run_auth(args: argparse.Namespace) -> int:
    """Interactive first-time login for the outreach account."""
    settings = _build_settings(args)
    container = build(settings)
    assert container.telegram_session is not None
    await container.telegram_session.start()
    click.echo("Authorised. Session saved.")
    await container.telegram_session.stop()
    return 0


async def _run_outreach_approve(args: argparse.Namespace) -> int:
    settings = _build_settings(args)
    container = build(settings)
    ok = await container.use_cases.approve.execute(
        args.id, approved_by="cli", reason=args.reason
    )
    click.echo("Approved." if ok else "Could not approve.")
    return 0 if ok else 1


async def _run_outreach_reject(args: argparse.Namespace) -> int:
    settings = _build_settings(args)
    container = build(settings)
    ok = await container.use_cases.reject.execute(args.id, reason=args.reason)
    click.echo("Rejected." if ok else "Could not reject.")
    return 0 if ok else 1


async def _run_outreach_list(args: argparse.Namespace) -> int:
    from .domain.enums import OutreachStatus
    from .infrastructure.persistence.database import get_sessionmaker, init_engine
    from .infrastructure.persistence.unit_of_work import SqlUnitOfWork

    settings = _build_settings(args)
    init_engine(settings)
    sm = get_sessionmaker()
    async with SqlUnitOfWork(sm) as uow:
        assert uow.outreach is not None
        try:
            status = OutreachStatus(args.status)
        except ValueError:
            click.echo(f"Unknown status: {args.status}", err=True)
            return 1
        items = await uow.outreach.list_by_status(status)
        for o in items:
            click.echo(
                f"[{o.status.value}] {o.id} score={o.lead.score.value:.2f} "
                f"to={o.contact.identifier} preview={o.body.text[:80]!r}"
            )
    return 0


async def _run_all(args: argparse.Namespace) -> int:
    settings = _build_settings(args)
    container = build(settings)
    assert container.telegram_session is not None
    await container.telegram_session.start()
    if container.bot_client is not None:
        try:
            from telethon import functions  # noqa: F401
            await container.bot_client.start(bot_token=settings.bot_token)
            container.bot_handlers.register()  # type: ignore[union-attr]
        except Exception as e:  # noqa: BLE001
            click.echo(f"Bot start failed: {e}", err=True)

    # Also start LLM
    await container.ollama.start()

    # Run workers concurrently
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        stop_event.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except (NotImplementedError, RuntimeError):
            pass

    tasks = [
        asyncio.create_task(container.workers.scanner.run(), name="scanner"),
        asyncio.create_task(
            container.queue.consume(container.workers.analyzer.handle),
            name="analyzer-queue",
        ),
        asyncio.create_task(
            container.queue.consume(container.workers.outreach.handle),
            name="outreach-queue",
        ),
        asyncio.create_task(container.workers.reply.run(), name="reply"),
        asyncio.create_task(container.workers.followup.run(), name="followup"),
    ]
    try:
        await stop_event.wait()
    finally:
        container.workers.scanner.stop()
        container.workers.followup.stop()
        container.workers.reply.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if container.bot_client is not None:
            await container.bot_client.disconnect()
        await container.ollama.stop()
        await container.telegram_session.stop()
    return 0


@click.group()
def cli() -> None:
    """Telegram Outreach CLI."""


@cli.command("run")
@click.option("--dry-run", is_flag=True, help="Never call Telegram write methods.")
@click.option("--limit", type=int, default=None)
@click.option("--keywords", multiple=True)
@click.option("--min-subs", type=int, default=None)
def cmd_run(dry_run: bool, limit: int | None, keywords: tuple[str, ...], min_subs: int | None) -> None:
    """Run a single dry-run scan+analyse pass."""
    args = argparse.Namespace(
        dry_run=dry_run, limit=limit, keywords=list(keywords), min_subs=min_subs
    )
    # Persist CLI override for scan
    from .config.settings import reset_settings_cache
    reset_settings_cache()
    if min_subs is not None:
        from .config.settings import get_settings
        get_settings.cache_clear()
    sys.exit(asyncio.run(_run_dry(args)))


@cli.command("auth")
def cmd_auth() -> None:
    """Interactive login for the outreach account."""
    args = argparse.Namespace(dry_run=False)
    sys.exit(asyncio.run(_run_auth(args)))


@cli.command("run-all")
@click.option("--no-bot", is_flag=True)
def cmd_run_all(no_bot: bool) -> None:
    """Run all workers in one process (for dev/single-tenant)."""
    args = argparse.Namespace(dry_run=False, no_bot=no_bot)
    sys.exit(asyncio.run(_run_all(args)))


@cli.group("outreach")
def outreach() -> None:
    """Outreach management subcommands."""


@outreach.command("approve")
@click.argument("id")
@click.option("--reason", default=None)
def cmd_approve(id: str, reason: str | None) -> None:
    args = argparse.Namespace(dry_run=False, id=id, reason=reason)
    sys.exit(asyncio.run(_run_outreach_approve(args)))


@outreach.command("reject")
@click.argument("id")
@click.option("--reason", required=True)
def cmd_reject(id: str, reason: str) -> None:
    args = argparse.Namespace(dry_run=False, id=id, reason=reason)
    sys.exit(asyncio.run(_run_outreach_reject(args)))


@outreach.command("list")
@click.option("--status", default="drafted")
def cmd_list(status: str) -> None:
    args = argparse.Namespace(dry_run=False, status=status)
    sys.exit(asyncio.run(_run_outreach_list(args)))


if __name__ == "__main__":  # pragma: no cover
    cli()
