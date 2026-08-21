"""Channel scanner — uses Telethon to search and fetch messages."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import SearchRequest
from telethon.tl.types import Channel as TgChannel
from telethon.tl.types import InputPeerEmpty, Message as TgMessage

from ...config.logging import get_logger
from ...ports.telegram import ChannelInfo, RawMessage, TelegramClientPort
from .client import TelegramSession

_log = get_logger(__name__)


class TelethonChannelScanner:
    """Adapter implementing TelegramClientPort for the outreach account."""

    def __init__(self, session: TelegramSession) -> None:
        self._session = session

    async def search_channels(self, query: str, limit: int) -> list[ChannelInfo]:
        client = self._session.client
        results: list[ChannelInfo] = []
        try:
            req = await client(SearchRequest(q=query, limit=min(limit, 200), peer=InputPeerEmpty()))
            for chat in req.chats:
                if not isinstance(chat, TgChannel):
                    continue
                info = ChannelInfo(
                    telegram_id=chat.id,
                    username=getattr(chat, "username", None),
                    title=getattr(chat, "title", "") or "",
                    description="",
                    subscribers=int(getattr(chat, "participants_count", 0) or 0),
                )
                results.append(info)
        except Exception as e:  # noqa: BLE001
            _log.warning("telegram.search_failed", query=query, error=str(e))
        return results[:limit]

    async def get_channel_info(self, telegram_id: int) -> ChannelInfo | None:
        client = self._session.client
        try:
            entity = await client.get_entity(telegram_id)
            if not isinstance(entity, TgChannel):
                return None
            full = await client(GetFullChannelRequest(channel=entity))
            about = getattr(full.full_chat, "about", "") or ""
            subs = int(getattr(full.full_chat, "participants_count", 0) or 0)
            return ChannelInfo(
                telegram_id=entity.id,
                username=getattr(entity, "username", None),
                title=getattr(entity, "title", "") or "",
                description=about,
                subscribers=subs,
            )
        except Exception as e:  # noqa: BLE001
            _log.warning("telegram.get_channel_failed", telegram_id=telegram_id, error=str(e))
            return None

    async def get_recent_messages(self, channel_id: int, limit: int) -> list[RawMessage]:
        client = self._session.client
        out: list[RawMessage] = []
        try:
            entity = await client.get_entity(channel_id)
            async for msg in client.iter_messages(entity, limit=limit):
                if not isinstance(msg, TgMessage):
                    continue
                text = (msg.message or "").strip()
                if not text:
                    continue
                posted = msg.date
                if posted.tzinfo is None:
                    posted = posted.replace(tzinfo=timezone.utc)
                out.append(
                    RawMessage(
                        channel_id=channel_id,
                        telegram_message_id=msg.id,
                        text=text,
                        posted_at=posted.astimezone(timezone.utc).replace(tzinfo=None),
                        author_user_id=msg.from_id.user_id if msg.from_id else None,
                        metadata={"views": msg.views or 0, "forwards": msg.forwards or 0},
                    )
                )
        except Exception as e:  # noqa: BLE001
            _log.warning("telegram.iter_messages_failed", channel_id=channel_id, error=str(e))
        return out

    async def resolve_public_contact(self, channel: ChannelInfo):
        """Return (identifier, display_name) only if the channel exposes a
        public discussion/owner. NEVER guess.

        Telegram's "discussion group" / "linked chat" is the only public
        surface we trust. We do NOT enumerate admins.
        """
        client = self._session.client
        try:
            entity = await client.get_entity(channel.telegram_id)
            full = await client(GetFullChannelRequest(channel=entity))
            linked_chat_id = getattr(full.full_chat, "linked_chat_id", None)
            if linked_chat_id is None:
                return None
            linked = await client.get_entity(linked_chat_id)
            from ...domain.value_objects import ContactIdentifier

            return (
                ContactIdentifier(
                    chat_id=int(linked.id),
                    username=getattr(linked, "username", None),
                ),
                getattr(linked, "title", "") or "discussion",
            )
        except Exception as e:  # noqa: BLE001
            _log.info(
                "telegram.resolve_public_contact_failed",
                telegram_id=channel.telegram_id,
                error=str(e),
            )
            return None

    async def send_message(self, recipient, text: str):  # not used here
        raise NotImplementedError("Use TelethonMessageSender")

    async def iter_incoming(self):  # not used here
        raise NotImplementedError("Use TelethonReplyListener")
        yield  # for type checkers


def scanner_implements_port(scanner: TelethonChannelScanner) -> TelegramClientPort:
    """Cast helper. The scanner only implements the read side of the port."""
    return scanner  # type: ignore[return-value]
