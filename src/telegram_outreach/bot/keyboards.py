"""Inline keyboards for the management bot."""
from __future__ import annotations


def approval_keyboard(outreach_id: str):
    """Telethon InlineKeyboardMarkup; rendered as a plain dict for portability."""
    from telethon.tl.custom import Button

    return [
        [
            Button.inline("✅ Approve", data=f"approve:{outreach_id}".encode()),
            Button.inline("❌ Reject", data=f"reject:{outreach_id}".encode()),
        ],
        [
            Button.inline("👁 Full text", data=f"view:{outreach_id}".encode()),
        ],
    ]


def main_menu_keyboard():
    from telethon.tl.custom import Button

    return [
        [
            Button.inline("📋 Pending", data=b"menu:pending"),
            Button.inline("📊 Stats", data=b"menu:stats"),
        ],
        [
            Button.inline("🚫 Blacklist", data=b"menu:blacklist"),
        ],
    ]
