from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Candle, Timeframe


class CandleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, candle_data: dict) -> Candle:
        stmt = insert(Candle).values(**candle_data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_candle_symbol_tf_ts",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def upsert_many(self, candles: list[dict]) -> None:
        if not candles:
            return
        stmt = insert(Candle).values(candles)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_candle_symbol_tf_ts",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def get_range(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 1000,
    ) -> list[Candle]:
        query = (
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.timestamp.desc())
            .limit(limit)
        )
        if start:
            query = query.where(Candle.timestamp >= start)
        if end:
            query = query.where(Candle.timestamp <= end)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest(self, symbol: str, timeframe: Timeframe) -> Candle | None:
        query = (
            select(Candle)
            .where(Candle.symbol == symbol, Candle.timeframe == timeframe)
            .order_by(Candle.timestamp.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
