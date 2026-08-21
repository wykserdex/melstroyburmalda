"""DLQ repository — Dead Letter Queue for jobs that exhausted retries."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import DLQModel


class SqlDLQRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        job_type: str,
        payload: dict,
        error: str,
        attempts: int,
    ) -> None:
        self.session.add(
            DLQModel(
                job_type=job_type,
                payload=payload,
                error=error,
                attempts=attempts,
            )
        )
        await self.session.flush()

    async def list_recent(self, limit: int = 100) -> list[dict]:
        stmt = select(DLQModel).order_by(DLQModel.last_error_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        out = []
        for m in res.scalars().all():
            out.append(
                {
                    "id": m.id,
                    "job_type": m.job_type,
                    "payload": m.payload,
                    "error": m.error,
                    "attempts": m.attempts,
                    "last_error_at": m.last_error_at,
                }
            )
        return out
