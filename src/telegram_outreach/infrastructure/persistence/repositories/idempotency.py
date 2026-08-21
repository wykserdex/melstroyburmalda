"""Idempotency repository — protects against duplicate side-effects."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.enums import IdempotencyState
from ....domain.value_objects import IdempotencyKey
from ..models import IdempotencyModel


class SqlIdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, key: str) -> tuple[IdempotencyState, str | None] | None:
        m = await self.session.get(IdempotencyModel, key)
        if not m:
            return None
        return IdempotencyState(m.state), m.entity_id

    async def create_pending(
        self, key: IdempotencyKey, entity_type: str, entity_id: str
    ) -> bool:
        existing = await self.session.get(IdempotencyModel, key.key)
        if existing is not None:
            return False
        try:
            self.session.add(
                IdempotencyModel(
                    key=key.key,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    state=IdempotencyState.PENDING.value,
                    attempts=1,
                )
            )
            await self.session.flush()
            return True
        except IntegrityError:
            await self.session.rollback()
            return False

    async def mark_completed(self, key: str, entity_id: str) -> None:
        m = await self.session.get(IdempotencyModel, key)
        if not m:
            m = IdempotencyModel(
                key=key,
                entity_type="",
                entity_id=entity_id,
                state=IdempotencyState.COMPLETED.value,
            )
            self.session.add(m)
        else:
            m.state = IdempotencyState.COMPLETED.value
            m.entity_id = entity_id
        await self.session.flush()

    async def mark_failed(self, key: str) -> None:
        m = await self.session.get(IdempotencyModel, key)
        if not m:
            m = IdempotencyModel(
                key=key,
                entity_type="",
                entity_id="",
                state=IdempotencyState.FAILED.value,
            )
            self.session.add(m)
        else:
            m.state = IdempotencyState.FAILED.value
        await self.session.flush()
