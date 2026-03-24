from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import StrategyPerformance


class PerformanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all(self) -> list[StrategyPerformance]:
        query = select(StrategyPerformance).order_by(
            StrategyPerformance.sharpe_ratio.desc()
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_by_strategy(self, strategy_name: str) -> list[StrategyPerformance]:
        query = select(StrategyPerformance).where(
            StrategyPerformance.strategy_name == strategy_name
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def upsert(self, data: dict) -> None:
        existing = await self.session.execute(
            select(StrategyPerformance).where(
                StrategyPerformance.strategy_name == data["strategy_name"],
                StrategyPerformance.window_days == data["window_days"],
            )
        )
        record = existing.scalar_one_or_none()
        if record:
            stmt = (
                update(StrategyPerformance)
                .where(StrategyPerformance.id == record.id)
                .values(**{k: v for k, v in data.items() if k not in ("strategy_name", "window_days")})
            )
            await self.session.execute(stmt)
        else:
            self.session.add(StrategyPerformance(**data))
        await self.session.commit()
