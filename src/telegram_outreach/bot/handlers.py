"""Bot command + callback handlers. Implements full approval workflow."""
from __future__ import annotations

from datetime import datetime, timedelta

from telethon import events
from telethon.tl.custom import Button

from ..application.use_cases import (
    ApproveMessageUseCase,
    RejectMessageUseCase,
)
from ..config.logging import get_logger
from ..config.settings import Settings
from ..domain.enums import OutreachStatus
from ..infrastructure.persistence.unit_of_work import SqlUnitOfWork
from ..observability.tracing import new_correlation
from .keyboards import approval_keyboard, main_menu_keyboard

_log = get_logger(__name__)


class BotHandlers:
    def __init__(
        self,
        client,  # Telethon client (bot)
        uow_factory,
        approve_uc: ApproveMessageUseCase,
        reject_uc: RejectMessageUseCase,
        settings: Settings,
    ) -> None:
        self._client = client
        self._uow_factory = uow_factory
        self._approve = approve_uc
        self._reject = reject_uc
        self._settings = settings

    def is_allowed(self, user_id: int) -> bool:
        return user_id in self._settings.bot_allowed_user_ids

    def register(self) -> None:
        self._client.add_event_handler(self._cmd_start, events.NewMessage(pattern=r"/start"))
        self._client.add_event_handler(self._cmd_pending, events.NewMessage(pattern=r"/pending"))
        self._client.add_event_handler(self._cmd_stats, events.NewMessage(pattern=r"/stats"))
        self._client.add_event_handler(self._cmd_blacklist, events.NewMessage(pattern=r"/blacklist"))
        self._client.add_event_handler(self._on_callback, events.CallbackQuery())

    # --- Commands -----------------------------------------------------------
    async def _cmd_start(self, event) -> None:
        if not self.is_allowed(event.sender_id):
            return
        await event.respond("Welcome. Use the menu or /pending.", buttons=main_menu_keyboard())

    async def _cmd_pending(self, event) -> None:
        if not self.is_allowed(event.sender_id):
            return
        new_correlation()
        async with self._uow_factory() as uow:
            assert uow.outreach is not None
            items = await uow.outreach.list_by_status(OutreachStatus.DRAFTED)
        if not items:
            await event.respond("No pending outreaches. ✅")
            return
        for o in items[:10]:
            preview = o.body.text[:200]
            score = o.lead.score.value
            text = (
                f"📨 *Outreach `{o.id}`*\n"
                f"Score: {score:.2f}\n"
                f"Vacancy: {o.lead.vacancy.title[:80]}\n\n"
                f"{preview}…"
            )
            await event.respond(text, buttons=approval_keyboard(o.id))

    async def _cmd_stats(self, event) -> None:
        if not self.is_allowed(event.sender_id):
            return
        async with self._uow_factory() as uow:
            assert uow.outreach is not None and uow.conversations is not None
            drafted = await uow.outreach.list_by_status(OutreachStatus.DRAFTED)
            approved = await uow.outreach.list_by_status(OutreachStatus.APPROVED)
            sent = await uow.outreach.list_by_status(OutreachStatus.SENT)
            replied = await uow.outreach.list_by_status(OutreachStatus.REPLIED)
        await event.respond(
            "📊 *Stats*\n"
            f"Drafted: {len(drafted)}\n"
            f"Approved: {len(approved)}\n"
            f"Sent: {len(sent)}\n"
            f"Replied: {len(replied)}"
        )

    async def _cmd_blacklist(self, event) -> None:
        if not self.is_allowed(event.sender_id):
            return
        await event.respond(
            "Send `/block <user_id>` or `/unblock <user_id>` to manage blacklisted contacts."
        )

    # --- Callbacks ----------------------------------------------------------
    async def _on_callback(self, event) -> None:
        if not self.is_allowed(event.sender_id):
            await event.answer("Not allowed.", alert=True)
            return
        data = (event.data or b"").decode()
        new_correlation()
        if data.startswith("approve:"):
            oid = data.split(":", 1)[1]
            ok = await self._approve.execute(oid, approved_by=f"bot:{event.sender_id}")
            await event.answer("Approved ✅" if ok else "Could not approve")
            try:
                await event.edit(f"✅ Approved `{oid}`")
            except Exception:  # noqa: BLE001
                pass
        elif data.startswith("reject:"):
            oid = data.split(":", 1)[1]
            ok = await self._reject.execute(oid, reason="rejected via bot")
            await event.answer("Rejected ❌" if ok else "Could not reject")
            try:
                await event.edit(f"❌ Rejected `{oid}`")
            except Exception:  # noqa: BLE001
                pass
        elif data.startswith("view:"):
            oid = data.split(":", 1)[1]
            async with self._uow_factory() as uow:
                o = await uow.outreach.get(oid)
            if o is None:
                await event.answer("Not found")
            else:
                await event.answer(o.body.text[:200], alert=True)
        elif data.startswith("menu:"):
            sub = data.split(":", 1)[1]
            if sub == "pending":
                await self._cmd_pending(event)
            elif sub == "stats":
                await self._cmd_stats(event)
            elif sub == "blacklist":
                await self._cmd_blacklist(event)
