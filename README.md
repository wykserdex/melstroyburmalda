# Telegram Outreach Platform

Production-oriented Telegram outreach platform with Clean / Hexagonal architecture.

It analyses Telegram channels, detects job vacancies, scores them, drafts a
personalised message, requires human approval by default, and sends the
message to the contact — all behind strict rate limits, idempotency,
opt-out, and a fully typed domain.

> Optimised for **quality of qualification**, **relevance**, **absence of
> duplicates**, **personalisation correctness**, **human control**,
> **reliability**, **idempotency**, **respect for Telegram limits** —
> not raw throughput.

---

## 1. Architecture overview

```
                main.py / CLI / workers / bot
                              │
                       bootstrap.py  (composition root)
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   infrastructure        application            domain
   (Telethon,           (use cases, DTO)        (entities, enums,
   Ollama, SQLAlchemy,                            policies, scoring,
   queue, similarity)                             transitions, value objects)
        ▲                     ▲                     ▲
        └────── ports (interfaces) ─────────────────┘
```

Dependency rule (one-way):

```
domain ← application ← ports ← infrastructure
```

`domain` does not import Telethon / SQLAlchemy / httpx / Ollama.
`application` does not import Telethon.

---

## 2. Project structure

```
telegram_outreach/
├── pyproject.toml
├── README.md
├── .env.example
├── docker-compose.yml
├── alembic.ini
├── src/telegram_outreach/
│   ├── main.py             # CLI entry point
│   ├── bootstrap.py        # composition root
│   ├── config/             # settings + structured logging
│   ├── domain/             # pure business rules
│   │   ├── entities/       # Channel, Contact, Vacancy, Lead, Outreach, Conversation, Message
│   │   ├── enums.py        # all status enums + EventType
│   │   ├── exceptions.py
│   │   ├── scoring.py
│   │   ├── value_objects.py
│   │   └── policies/       # transitions, frequency, duplicate, message, outreach
│   ├── application/        # use cases + DTOs
│   │   ├── dto/
│   │   └── use_cases/      # scan / parse / dedupe / qualify / generate / approve / send / reply / follow-up
│   ├── ports/              # interfaces (telegram, llm, queue, repositories, similarity)
│   ├── infrastructure/
│   │   ├── telegram/       # Telethon adapters + dry-run wrapper
│   │   ├── llm/            # Ollama httpx client + parser + prompts
│   │   ├── persistence/    # SQLAlchemy 2.x async, models, mappers, repos, migrations
│   │   ├── queue/          # asyncio broker with persistent idempotency
│   │   └── similarity/     # n-gram shingle Jaccard
│   ├── workers/            # scanner / analyzer / outreach / reply / followup
│   ├── bot/                # management Telegram bot (approval + stats)
│   └── observability/      # metrics + tracing
├── tests/
│   ├── unit/               # domain, policies, scoring, similarity, parser, dry-run
│   ├── integration/        # repositories with in-memory SQLite
│   ├── e2e/                # full pipeline with fakes
│   └── fixtures/           # in-memory fakes
└── scripts/
    ├── run_worker.py
    └── seed_channels.py
```

---

## 3. Requirements

- Python 3.11+
- PostgreSQL 14+ (or SQLite for dev — `sqlite+aiosqlite:///...`)
- A Telegram user account (outreach) and optionally a bot token (approval)
- Ollama running locally (or remotely) with `qwen3:14b` (configurable)

---

## 4. Installation

```bash
git clone <repo>
cd telegram_outreach
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# fill in TELEGRAM_API_ID, TELEGRAM_API_HASH, DATABASE_URL, etc.
```

---

## 5. `.env` configuration

See [`.env.example`](.env.example). Required:

- `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` from <https://my.telegram.org>
- `DATABASE_URL` — `postgresql+asyncpg://...` (production) or `sqlite+aiosqlite:///...` (dev)
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL`

Optional but recommended:

- `BOT_TOKEN` and `BOT_ALLOWED_USERS` — for in-Telegram approval
- `AUTO_APPROVE=false` (default) — drafts wait for human approval
- `RELEVANCE_THRESHOLD` (0.6) and `CONFIDENCE_THRESHOLD` (0.75)
- `DAILY_MESSAGE_LIMIT` (40) and `MIN_DELAY_SECONDS` (120)

---

## 6. Telegram API setup

1. Go to <https://my.telegram.org/apps> and create an app.
2. Copy the `api_id` and `api_hash` into `.env`.
3. Run `python -m telegram_outreach auth` and follow the prompts
   (phone number, code, 2FA if enabled). A `outreach.session` file is
   created in the working directory. **Never commit it.**

---

## 7. Ollama setup

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:14b
ollama serve
```

The LLM client expects `/api/chat` with `stream: false` (Ollama's default).

---

## 8. Database setup

Production: run Postgres (docker-compose provides one):

```bash
docker compose up -d postgres
alembic upgrade head
```

Dev / tests: SQLite works out of the box (the `DATABASE_URL` is the only
place to switch).

---

## 9. Migrations

```bash
alembic revision --autogenerate -m "add x"
alembic upgrade head
alembic downgrade -1
```

---

## 10. Dry-run

```bash
python -m telegram_outreach run --dry-run --limit 10
```

This:
- scans channels
- analyses messages
- deduplicates
- qualifies
- generates messages
- runs validation
- **does not** call any Telegram write method (the `DryRunTelegramClient`
  blocks `send_message` with a `PolicyViolation`)

---

## 11. Production run

```bash
# 1) Start everything in one process (single-tenant / dev)
python -m telegram_outreach run-all

# 2) Or split into worker processes
python -m scripts.run_worker scanner
python -m scripts.run_worker analyzer
python -m scripts.run_worker outreach
python -m scripts.run_worker followup

# The reply worker needs a separate process because it holds the
# long-running Telethon update listener.
```

CLI approval (works without the management bot):

```bash
python -m telegram_outreach outreach list --status drafted
python -m telegram_outreach outreach approve <id> --reason "looks good"
python -m telegram_outreach outreach reject <id> --reason "not relevant"
```

---

## 12. Management bot

If `BOT_TOKEN` and `BOT_ALLOWED_USERS` are set, the bot starts alongside
the workers. Commands:

- `/start` — main menu
- `/pending` — list DRAFTED outreaches with inline approve / reject buttons
- `/stats` — counts by status
- `/blacklist` — instructions for blocking / unblocking contacts

---

## 13. Tests

```bash
pytest                     # all
pytest tests/unit          # domain, policies, scoring, similarity, parser
pytest tests/integration   # SQLAlchemy repos with in-memory SQLite
pytest tests/e2e           # full pipeline with in-memory fakes
```

Tests do not require real Telegram credentials or a running Ollama — they
use deterministic fakes (`tests/fixtures/fakes.py`).

---

## 14. Troubleshooting

| Symptom | Fix |
|---|---|
| `RuntimeError: Telegram session is not authorised` | Run `python -m telegram_outreach auth` |
| `MISSING GREENLET` from SQLAlchemy | We use `selectin` loading on relationships; do not access relationships outside an open session |
| LLM returns malformed JSON | The parser retries up to 3 times; if it keeps failing, lower `temperature` in `infrastructure/llm/client.py` |
| `TELEGRAM_FLOOD_WAIT` | We respect it. The task is re-enqueued with the requested delay. **Do not** try to bypass it. |
| `PolicyViolation: contact c1 cannot be contacted` | The contact has opted out. They will be skipped. |

---

## 15. Rate limits

Defaults (override via `.env`):

- `DAILY_MESSAGE_LIMIT=40` per day
- `GLOBAL_HOURLY_LIMIT=20` per hour
- `MIN_DELAY_SECONDS=120` between any two sends
- `PER_RECIPIENT_COOLDOWN_HOURS=24`

Telegram `FloodWait` errors are honoured: the task is re-enqueued with
the delay requested by Telegram, not bypassed.

---

## 16. Privacy & Security

- **Never** commit `.env` or `*.session` files. They are in `.gitignore`.
- `config/logging.py` redacts API hashes, tokens, and bot tokens from
  logs by default (both dict-level keys and pattern-level).
- The system never fabricates owner identity for channels. If a channel
  has no public contact, the lead is silently skipped.
- `Contact.opted_out` is sticky; the moment a user asks to stop, we:
  1. set `opted_out=true`
  2. cancel any scheduled follow-ups
  3. stop creating new outreach for that contact
  4. log the `OPT_OUT` event
- The system does not store or transmit the full text of personal
  messages in plain-text application logs.
- The LLM is instructed **never to invent facts** — we explicitly pass
  "no fabrication" rules in `infrastructure/llm/prompts.py`.

### What we deliberately do NOT do

- No account rotation, no proxy rotation, no SMS-service bypass.
- No automatic opt-in scraping.
- No DM to users who didn't post a vacancy.
- No "magic" unblock of contacts.

---

## 17. Idempotency

Every send has an `idempotency_key` derived from
`hash(vacancy_id + contact_id + outreach_type + prompt_version)`. The key
is stored in `idempotency_keys` table with `state ∈ {pending, completed, failed}`.

- **Pre-send**: if a completed key exists, the send is skipped.
- **In-send**: `state=pending` prevents concurrent double-send.
- **Post-send**: `state=completed` is set in the same transaction as
  `outreach.status = SENT` and `outreach.sent_message_id`.
- **Restart**: pending keys can be inspected and re-driven; the next
  attempt will re-check `outreach.status` first.

---

## 18. Production notes

- Run separate worker processes via `scripts/run_worker.py` for
  isolation. A crash in one worker should not affect the others.
- The asyncio queue is in-process. To scale horizontally, replace
  `AsyncioQueueBroker` with an ARQ or Dramatiq adapter implementing
  the same `QueuePort`.
- Set `LOG_JSON=true` in production for machine-readable logs.
- Use a managed Postgres (e.g. RDS, Cloud SQL) and tune pool size.
