"""Run a single worker process (scanner, analyzer, outreach, or followup).

Used in production: one worker per process for isolation.

Usage:
    python -m scripts.run_worker scanner
    python -m scripts.run_worker analyzer
    python -m scripts.run_worker outreach
    python -m scripts.run_worker followup
"""
from __future__ import annotations

import asyncio
import signal
import sys

from telegram_outreach.bootstrap import build
from telegram_outreach.config.settings import get_settings


async def main(name: str) -> None:
    settings = get_settings()
    container = build(settings)
    assert container.telegram_session is not None
    await container.telegram_session.start()
    await container.ollama.start()

    stop = asyncio.Event()

    def _sig() -> None:
        stop.set()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except (NotImplementedError, RuntimeError):
            pass

    if name == "scanner":
        await container.workers.scanner.run()
    elif name == "analyzer":
        await container.queue.consume(container.workers.analyzer.handle)
    elif name == "outreach":
        await container.queue.consume(container.workers.outreach.handle)
    elif name == "followup":
        await container.workers.followup.run()
    elif name == "reply":
        await container.workers.reply.run()
    else:
        print(f"unknown worker: {name}", file=sys.stderr)
        sys.exit(1)

    await container.ollama.stop()
    await container.telegram_session.stop()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "scanner"))
