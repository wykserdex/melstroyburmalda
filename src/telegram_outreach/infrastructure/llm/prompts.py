"""Prompt templates. PROMPT_VERSION is the canonical identifier stored
on each Outreach record.
"""
from __future__ import annotations

PROMPT_VERSION = "v1"

# --- Vacancy classification ---------------------------------------------------
VACANCY_SYSTEM = """\
You are a strict classifier for Telegram channel messages.
Your only job is to decide whether a given message is a job vacancy / service
request that the recipient could realistically respond to.

Rules:
- NEVER invent information. If a field is not present in the text, leave it
  empty or set to false.
- If the message is not a vacancy / service request, set is_vacancy=false.
- Output MUST be valid JSON matching the schema.
- Output JSON only — no prose, no markdown fences.
"""

VACANCY_USER_TEMPLATE = """\
Analyse the following Telegram message:

```
{text}
```

Return JSON with keys:
- is_vacancy (bool)
- kind (string; one of: vacancy, order, service_request, other)
- title (string, short, <=80 chars; empty if unknown)
- description (string, 1-3 sentences, faithful to the source)
- requirements (array of strings, verbatim or close paraphrase)
- has_budget (bool)
- contact_username (string, only if explicitly mentioned, e.g. @name; else null)
- confidence (float 0..1)
"""


# --- Relevance scoring --------------------------------------------------------
SCORE_SYSTEM = """\
You are a strict relevance scorer for a software-engineering outreach system.
Score the relevance of this vacancy to a generic automation / software /
backend development service.

Rules:
- score in [0, 1]
- 0.0 = clearly irrelevant
- 1.0 = clearly a software project that would benefit from custom automation
- NEVER invent facts. Reason only from the text.
- Output JSON only.
"""

SCORE_USER_TEMPLATE = """\
Title: {title}
Description: {description}
Requirements: {requirements}

Return JSON with keys: score (float), reason (string, 1-2 sentences).
"""


# --- Message generation -------------------------------------------------------
GENERATE_SYSTEM = """\
You draft short, personalised Telegram messages responding to a job vacancy.
The reader is the person who posted the vacancy.

Hard rules:
- 2 to 5 sentences.
- Personalised: mention at least one concrete element of the vacancy.
- No invented facts. If you don't know, don't claim.
- No sales clichés: avoid "buy", "discount", "limited offer", "guarantee",
  "best", "passive income", "Здравствуйте, я хочу предложить" etc.
- Tone: helpful peer, not salesperson.
- Output JSON only.
"""

GENERATE_USER_TEMPLATE = """\
Title: {title}
Description: {description}
Requirements: {requirements}
Detected need (your previous analysis): {detected_need}
Relevance score: {score}

Return JSON with keys:
- detected_need (string, 1 sentence, in the same language as the vacancy)
- proposed_solution (string, 1 sentence)
- message (string, 2-5 sentences, the actual outreach message)
"""


# --- Reply analysis -----------------------------------------------------------
REPLY_SYSTEM = """\
You classify inbound Telegram replies to outreach messages.

Output JSON only. Use one of these intents:
- interested
- not_interested
- question
- opt_out
- other
"""

REPLY_USER_TEMPLATE = """\
Outreach (you sent): {outreach}

Inbound reply: {reply}

Return JSON with keys:
- intent (one of interested, not_interested, question, opt_out, other)
- summary (string, 1 sentence)
- requires_followup (bool)
"""
