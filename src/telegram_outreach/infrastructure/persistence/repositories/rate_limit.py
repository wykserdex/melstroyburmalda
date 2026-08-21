"""Rate limit repository — persistent counters."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import RateLimitBucketModel


class SqlRateLimitRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_in_window(
        self, scope: str, window_start: datetime, window_end: datetime
    ) -> int:
        stmt = select(func.count(RateLimitBucketModel.id)).where(
            RateLimitBucketModel.scope == scope,
            RateLimitBucketModel.ts >= window_start,
            RateLimitBucketModel.ts < window_end,
        )
        res = await self.session.execute(stmt)
        return int(res.scalar() or 0)

    async def record(self, scope: str, at: datetime) -> None:
        self.session.add(
            RateLimitBucketModel(
                scope=scope,
                recipient_id=None,
                ts=at,
            )
        )
        await self.session.flush()

    async def last_for_recipient(self, recipient_id: str) -> datetime | None:
        stmt = (
            select(RateLimitBucketModel.ts)
            .where(
                RateLimitBucketModel.scope == "recipient",
                RateLimitBucketModel.recipient_id == recipient_id,
            )
            .order_by(RateLimitBucketModel.ts.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def record_for_recipient(self, recipient_id: str, at: datetime) -> None:
        self.session.add(
            RateLimitBucketModel(
                scope="recipient",
                recipient_id=recipient_id,
                ts=at,
            )
        )
        await self.session.flush()

    async def cleanup_older_than(self, cutoff: datetime) -> None:
        stmt = delete(RateLimitBucketModel).where(RateLimitBucketModel.ts < cutoff)
        await self.session.execute(stmt)
