"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-01-01 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "channels",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("subscribers", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(32), nullable=False, server_default="search"),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_channels_username", "channels", ["username"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "channel_id",
            sa.String(64),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("author_user_id", sa.BigInteger(), nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("channel_id", "telegram_message_id", name="uq_msg_chan_tmid"),
    )
    op.create_index("ix_msg_text_hash", "messages", ["text_hash"])

    op.create_table(
        "vacancies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("channel_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="vacancy"),
        sa.Column("title", sa.String(512), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("requirements", JSON_TYPE, nullable=False, server_default=sa.text("'[]'")),
        sa.Column("contact_hint_user_id", sa.BigInteger(), nullable=True),
        sa.Column("contact_hint_username", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("message_id", name="uq_vacancy_message"),
    )
    op.create_index("ix_vacancy_status", "vacancies", ["status"])

    op.create_table(
        "contacts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("display_name", sa.String(256), nullable=False, server_default=""),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("opted_out", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_contacts_username", "contacts", ["username"])

    op.create_table(
        "leads",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("vacancy_id", sa.String(64), nullable=False),
        sa.Column("contact_id", sa.String(64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("scoring_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.UniqueConstraint("vacancy_id", "contact_id", name="uq_lead_vacancy_contact"),
    )
    op.create_index("ix_lead_status", "leads", ["status"])

    op.create_table(
        "outreach",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("lead_id", sa.String(64), nullable=False),
        sa.Column("vacancy_id", sa.String(64), nullable=False),
        sa.Column("contact_id", sa.String(64), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("prompt_version", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64), nullable=False, server_default=""),
        sa.Column("generation_meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_message_id", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_outreach_idem"),
    )
    op.create_index("ix_outreach_status", "outreach", ["status"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("outreach_id", sa.String(64), nullable=False, unique=True),
        sa.Column("contact_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_followup_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("followup_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_conv_status", "conversations", ["status"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.String(64),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_cmsg_conv", "conversation_messages", ["conversation_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(160), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "dlq",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("payload", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "last_error_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("meta", JSON_TYPE, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_event_entity", "events", ["entity_type", "entity_id"])
    op.create_index("ix_event_type", "events", ["event_type"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("recipient_id", sa.String(64), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rl_scope_time", "rate_limit_buckets", ["scope", "ts"])


def downgrade() -> None:
    for table in (
        "rate_limit_buckets",
        "events",
        "dlq",
        "idempotency_keys",
        "conversation_messages",
        "conversations",
        "outreach",
        "leads",
        "contacts",
        "vacancies",
        "messages",
        "channels",
    ):
        op.drop_table(table)
