"""Domain entities — pure data + behaviour, no I/O."""
from .audit import EventLogEntry
from .channel import Channel
from .contact import Contact
from .conversation import Conversation, ConversationMessage
from .lead import Lead
from .message import Message
from .outreach import Outreach
from .vacancy import Vacancy

__all__ = [
    "Channel",
    "Contact",
    "Conversation",
    "ConversationMessage",
    "EventLogEntry",
    "Lead",
    "Message",
    "Outreach",
    "Vacancy",
]
