"""All enums used by the domain. No I/O, no infrastructure references."""
from __future__ import annotations

from enum import Enum


class VacancyStatus(str, Enum):
    DISCOVERED = "discovered"
    PARSED = "parsed"
    DUPLICATE = "duplicate"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    CLOSED = "closed"


class LeadStatus(str, Enum):
    CREATED = "created"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    OUTREACH_DRAFTED = "outreach_drafted"
    OUTREACH_APPROVED = "outreach_approved"
    OUTREACH_SENT = "outreach_sent"
    CLOSED = "closed"


class OutreachStatus(str, Enum):
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"
    REPLIED = "replied"
    FOLLOWUP_SCHEDULED = "followup_scheduled"
    REJECTED = "rejected"
    CLOSED = "closed"
    FAILED = "failed"


class ConversationStatus(str, Enum):
    OPEN = "open"
    WAITING_REPLY = "waiting_reply"
    REPLIED = "replied"
    FOLLOWUP_SCHEDULED = "followup_scheduled"
    CLOSED = "closed"


class ChannelSource(str, Enum):
    SEARCH = "search"
    MANUAL = "manual"
    REFERRAL = "referral"
    SEED = "seed"


class ContactSource(str, Enum):
    CHANNEL_ADMIN = "channel_admin"
    POST_AUTHOR = "post_author"
    MENTIONED = "mentioned"
    MANUAL = "manual"


class IdempotencyState(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    LEAD_DISCOVERED = "lead_discovered"
    VACANCY_PARSED = "vacancy_parsed"
    VACANCY_DEDUPLICATED = "vacancy_deduplicated"
    LEAD_QUALIFIED = "lead_qualified"
    LEAD_REJECTED = "lead_rejected"
    MESSAGE_DRAFTED = "message_drafted"
    MESSAGE_APPROVED = "message_approved"
    MESSAGE_REJECTED = "message_rejected"
    MESSAGE_SENT = "message_sent"
    REPLY_RECEIVED = "reply_received"
    REPLY_ANALYZED = "reply_analyzed"
    FOLLOWUP_SCHEDULED = "followup_scheduled"
    FOLLOWUP_CANCELLED = "followup_cancelled"
    OUTREACH_CLOSED = "outreach_closed"
    OPT_OUT = "opt_out"
    RATE_LIMITED = "rate_limited"
    FLOOD_WAIT = "flood_wait"
    DLQ_RECORDED = "dlq_recorded"
