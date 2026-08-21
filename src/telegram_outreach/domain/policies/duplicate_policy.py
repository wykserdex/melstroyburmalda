"""Duplicate detection policy.

A Vacancy is a duplicate if we've already seen the same Message
(channel + telegram_message_id) OR the same normalised text hash.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicatePolicy:
    """Pure duplicate-detection logic. The repository layer does the actual lookup."""

    def is_message_duplicate(
        self,
        new_channel_id: str,
        new_telegram_message_id: int,
        existing_by_message: set[tuple[str, int]],
    ) -> bool:
        return (new_channel_id, new_telegram_message_id) in existing_by_message

    def is_text_duplicate(
        self,
        new_text_hash: str,
        existing_text_hashes: set[str],
    ) -> bool:
        return new_text_hash in existing_text_hashes

    def is_outreach_duplicate(
        self,
        new_key: str,
        existing_keys: set[str],
    ) -> bool:
        return new_key in existing_keys
