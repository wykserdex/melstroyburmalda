"""Status transition tables — the only place transitions are defined.

Keep these explicit, not generic, so they're easy to audit.
"""
from __future__ import annotations

from ..enums import ConversationStatus, LeadStatus, OutreachStatus, VacancyStatus
from ..exceptions import InvalidStateTransition


_VACANCY: dict[VacancyStatus, set[VacancyStatus]] = {
    VacancyStatus.DISCOVERED: {VacancyStatus.PARSED, VacancyStatus.DUPLICATE, VacancyStatus.REJECTED},
    VacancyStatus.PARSED: {VacancyStatus.QUALIFIED, VacancyStatus.DUPLICATE, VacancyStatus.REJECTED},
    VacancyStatus.QUALIFIED: {VacancyStatus.CLOSED, VacancyStatus.REJECTED},
    VacancyStatus.DUPLICATE: set(),
    VacancyStatus.REJECTED: {VacancyStatus.CLOSED},
    VacancyStatus.CLOSED: set(),
}

_LEAD: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.CREATED: {LeadStatus.QUALIFIED, LeadStatus.REJECTED},
    LeadStatus.QUALIFIED: {
        LeadStatus.OUTREACH_DRAFTED,
        LeadStatus.OUTREACH_APPROVED,
        LeadStatus.REJECTED,
    },
    LeadStatus.OUTREACH_DRAFTED: {
        LeadStatus.OUTREACH_APPROVED,
        LeadStatus.OUTREACH_SENT,
        LeadStatus.REJECTED,
    },
    LeadStatus.OUTREACH_APPROVED: {LeadStatus.OUTREACH_SENT, LeadStatus.REJECTED},
    LeadStatus.OUTREACH_SENT: {LeadStatus.CLOSED},
    LeadStatus.REJECTED: {LeadStatus.CLOSED},
    LeadStatus.CLOSED: set(),
}

_OUTREACH: dict[OutreachStatus, set[OutreachStatus]] = {
    OutreachStatus.DRAFTED: {
        OutreachStatus.APPROVED,
        OutreachStatus.REJECTED,
        OutreachStatus.FAILED,
    },
    OutreachStatus.APPROVED: {
        OutreachStatus.SENT,
        OutreachStatus.FAILED,
    },
    OutreachStatus.SENT: {
        OutreachStatus.REPLIED,
        OutreachStatus.FOLLOWUP_SCHEDULED,
        OutreachStatus.CLOSED,
        OutreachStatus.FAILED,
    },
    OutreachStatus.REPLIED: {OutreachStatus.FOLLOWUP_SCHEDULED, OutreachStatus.CLOSED},
    OutreachStatus.FOLLOWUP_SCHEDULED: {
        OutreachStatus.SENT,
        OutreachStatus.CLOSED,
        OutreachStatus.FAILED,
    },
    OutreachStatus.REJECTED: {OutreachStatus.CLOSED},
    OutreachStatus.FAILED: {OutreachStatus.CLOSED, OutreachStatus.DRAFTED},
    OutreachStatus.CLOSED: set(),
}

_CONVERSATION: dict[ConversationStatus, set[ConversationStatus]] = {
    ConversationStatus.OPEN: {
        ConversationStatus.WAITING_REPLY,
        ConversationStatus.CLOSED,
    },
    ConversationStatus.WAITING_REPLY: {
        ConversationStatus.REPLIED,
        ConversationStatus.FOLLOWUP_SCHEDULED,
        ConversationStatus.CLOSED,
    },
    ConversationStatus.REPLIED: {
        ConversationStatus.FOLLOWUP_SCHEDULED,
        ConversationStatus.CLOSED,
    },
    ConversationStatus.FOLLOWUP_SCHEDULED: {
        ConversationStatus.WAITING_REPLY,
        ConversationStatus.REPLIED,
        ConversationStatus.CLOSED,
    },
    ConversationStatus.CLOSED: set(),
}


def assert_vacancy_transition(cur: VacancyStatus, target: VacancyStatus) -> None:
    if target not in _VACANCY.get(cur, set()):
        raise InvalidStateTransition("vacancy", cur.value, target.value)


def assert_lead_transition(cur: LeadStatus, target: LeadStatus) -> None:
    if target not in _LEAD.get(cur, set()):
        raise InvalidStateTransition("lead", cur.value, target.value)


def assert_outreach_transition(cur: OutreachStatus, target: OutreachStatus) -> None:
    if target not in _OUTREACH.get(cur, set()):
        raise InvalidStateTransition("outreach", cur.value, target.value)


def assert_conversation_transition(cur: ConversationStatus, target: ConversationStatus) -> None:
    if target not in _CONVERSATION.get(cur, set()):
        raise InvalidStateTransition("conversation", cur.value, target.value)
