"""Frequency / rate policies. Pure functions, no I/O."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class FrequencyPolicy:
    """Decides whether a new outreach is allowed given history.

    All limits come from the outside (Settings), so the policy itself is
    pure and easy to unit test.
    """

    min_interval_seconds: int
    per_recipient_cooldown_hours: int
    daily_message_limit: int
    global_hourly_limit: int

    def per_recipient_cooldown(self) -> timedelta:
        return timedelta(hours=self.per_recipient_cooldown_hours)

    def is_within_daily_limit(self, sent_today: int) -> bool:
        return sent_today < self.daily_message_limit

    def is_within_hourly_global(self, sent_last_hour: int) -> bool:
        return sent_last_hour < self.global_hourly_limit

    def seconds_since_last(self, last_sent_at: datetime | None, now: datetime) -> float:
        if last_sent_at is None:
            return float("inf")
        return (now - last_sent_at).total_seconds()

    def can_contact_recipient(
        self,
        last_sent_at: datetime | None,
        now: datetime,
    ) -> tuple[bool, str | None]:
        delta = self.seconds_since_last(last_sent_at, now)
        if delta < self.min_interval_seconds:
            return False, f"min interval {self.min_interval_seconds}s not reached"
        if last_sent_at is not None and now - last_sent_at < self.per_recipient_cooldown():
            return False, f"per-recipient cooldown {self.per_recipient_cooldown_hours}h not reached"
        return True, None
