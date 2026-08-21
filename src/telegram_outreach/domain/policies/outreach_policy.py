"""Outreach policy — decides whether an outreach may be sent.

Combines: opt-out, frequency, contact validity, message validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..exceptions import OptedOut, PolicyViolation
from ..value_objects import MessageBody
from .frequency_policy import FrequencyPolicy

if TYPE_CHECKING:
    from ..entities.contact import Contact
    from ..entities.lead import Lead
    from ..entities.outreach import Outreach


@dataclass
class OutreachPolicy:
    frequency: FrequencyPolicy

    def can_send(
        self,
        outreach: "Outreach",
        contact: "Contact",
        now_sent_today: int,
        now_sent_last_hour: int,
    ) -> None:
        """Raise PolicyViolation if not allowed. Idempotent (no side effects)."""
        if not contact.can_be_contacted():
            raise PolicyViolation("outreach", f"contact {contact.id} cannot be contacted")
        if contact.opted_out:
            raise OptedOut(f"contact {contact.id} has opted out")
        if outreach.status.name not in {"APPROVED", "SENT"}:
            raise PolicyViolation("outreach", f"status {outreach.status} not sendable")
        if not self.frequency.is_within_daily_limit(now_sent_today):
            raise PolicyViolation("outreach", "daily message limit reached")
        if not self.frequency.is_within_hourly_global(now_sent_last_hour):
            raise PolicyViolation("outreach", "global hourly limit reached")
        try:
            outreach.body.validate()
        except Exception as e:  # noqa: BLE001
            raise PolicyViolation("outreach", f"body invalid: {e}") from e

    def can_generate(
        self,
        lead: "Lead",
        contact: "Contact",
        body: MessageBody,
    ) -> None:
        if not contact.can_be_contacted():
            raise PolicyViolation("generate", f"contact {contact.id} cannot be contacted")
        if contact.opted_out:
            raise OptedOut(f"contact {contact.id} has opted out")
        body.validate()
