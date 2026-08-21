"""Telegram infrastructure: Telethon adapters."""
from .channel_scanner import TelethonChannelScanner
from .client import TelegramSession
from .composite import TelegramAdapter
from .dry_run import DryRunTelegramClient
from .message_sender import TelethonMessageSender
from .reply_listener import TelethonReplyListener

__all__ = [
    "DryRunTelegramClient",
    "TelegramAdapter",
    "TelegramSession",
    "TelethonChannelScanner",
    "TelethonMessageSender",
    "TelethonReplyListener",
]
