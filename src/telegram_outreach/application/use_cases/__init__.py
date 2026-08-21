"""Use cases — application-layer orchestration."""
from .approve_message import ApproveMessageUseCase, RejectMessageUseCase
from .deduplicate import DeduplicateUseCase
from .generate_message import GenerateMessageUseCase
from .parse_vacancy import ParseVacancyUseCase
from .process_reply import ProcessReplyUseCase
from .qualify_vacancy import QualifyVacancyUseCase
from .scan_channels import ScanChannelsUseCase
from .schedule_followup import RunFollowupUseCase, ScheduleFollowupUseCase
from .send_message import SendMessageUseCase

__all__ = [
    "ApproveMessageUseCase",
    "DeduplicateUseCase",
    "GenerateMessageUseCase",
    "ParseVacancyUseCase",
    "ProcessReplyUseCase",
    "QualifyVacancyUseCase",
    "RejectMessageUseCase",
    "RunFollowupUseCase",
    "ScanChannelsUseCase",
    "ScheduleFollowupUseCase",
    "SendMessageUseCase",
]
