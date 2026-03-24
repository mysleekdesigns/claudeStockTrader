"""Repository for correlation_data table."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import CorrelationData


class CorrelationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, asset: str, price: float, timestamp: datetime) -> CorrelationData:
        row = CorrelationData(asset=asset, price=price, timestamp=timestamp)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def upsert_many(self, rows: list[dict]) -> None:
        if not rows:
            return
        for row_data in rows:
            self.session.add(CorrelationData(**row_data))
        await self.session.commit()

    async def get_recent(
        self, asset: str, limit: int = 100
    ) -> list[CorrelationData]:
        query = (
            select(CorrelationData)
            .where(CorrelationData.asset == asset)
            .order_by(CorrelationData.timestamp.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_range(
        self,
        asset: str,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[CorrelationData]:
        query = (
            select(CorrelationData)
            .where(CorrelationData.asset == asset)
            .order_by(CorrelationData.timestamp.desc())
            .limit(limit)
        )
        if start:
            query = query.where(CorrelationData.timestamp >= start)
        if end:
            query = query.where(CorrelationData.timestamp <= end)
        result = await self.session.execute(query)
        return list(result.scalars().all())
