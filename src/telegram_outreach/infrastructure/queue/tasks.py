"""Task type names used throughout the queue."""
from __future__ import annotations

from enum import Enum


class TaskType(str, Enum):
    PARSE_VACANCY = "parse_vacancy"
    QUALIFY_VACANCY = "qualify_vacancy"
    GENERATE_MESSAGE = "generate_message"
    SEND_OUTREACH = "send_outreach"
    PROCESS_REPLY = "process_reply"
    SCHEDULE_FOLLOWUP = "schedule_followup"
    RUN_FOLLOWUP = "run_followup"
