"""Status transition tests."""
from __future__ import annotations

import pytest

from telegram_outreach.domain.enums import (
    ConversationStatus,
    LeadStatus,
    OutreachStatus,
    VacancyStatus,
)
from telegram_outreach.domain.exceptions import InvalidStateTransition
from telegram_outreach.domain.policies import transitions


def test_vacancy_happy_path() -> None:
    transitions.assert_vacancy_transition(VacancyStatus.DISCOVERED, VacancyStatus.PARSED)
    transitions.assert_vacancy_transition(VacancyStatus.PARSED, VacancyStatus.QUALIFIED)
    transitions.assert_vacancy_transition(VacancyStatus.QUALIFIED, VacancyStatus.CLOSED)


def test_vacancy_invalid() -> None:
    with pytest.raises(InvalidStateTransition):
        transitions.assert_vacancy_transition(VacancyStatus.DISCOVERED, VacancyStatus.QUALIFIED)
    with pytest.raises(InvalidStateTransition):
        transitions.assert_vacancy_transition(VacancyStatus.CLOSED, VacancyStatus.PARSED)


def test_outreach_draft_to_approved_to_sent() -> None:
    transitions.assert_outreach_transition(OutreachStatus.DRAFTED, OutreachStatus.APPROVED)
    transitions.assert_outreach_transition(OutreachStatus.APPROVED, OutreachStatus.SENT)
    transitions.assert_outreach_transition(OutreachStatus.SENT, OutreachStatus.FOLLOWUP_SCHEDULED)


def test_outreach_cannot_skip_approval() -> None:
    with pytest.raises(InvalidStateTransition):
        transitions.assert_outreach_transition(OutreachStatus.DRAFTED, OutreachStatus.SENT)


def test_lead_transitions() -> None:
    transitions.assert_lead_transition(LeadStatus.QUALIFIED, LeadStatus.OUTREACH_DRAFTED)
    transitions.assert_lead_transition(LeadStatus.OUTREACH_SENT, LeadStatus.CLOSED)
    with pytest.raises(InvalidStateTransition):
        transitions.assert_lead_transition(LeadStatus.QUALIFIED, LeadStatus.OUTREACH_SENT)


def test_conversation_transitions() -> None:
    transitions.assert_conversation_transition(
        ConversationStatus.WAITING_REPLY, ConversationStatus.FOLLOWUP_SCHEDULED
    )
    with pytest.raises(InvalidStateTransition):
        transitions.assert_conversation_transition(
            ConversationStatus.CLOSED, ConversationStatus.OPEN
        )
