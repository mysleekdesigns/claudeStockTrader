from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import BacktestRun, OptimisedParams


class BacktestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_runs(self, limit: int = 50) -> list[BacktestRun]:
        query = (
            select(BacktestRun)
            .order_by(BacktestRun.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_active_params(self) -> list[OptimisedParams]:
        query = select(OptimisedParams).where(OptimisedParams.is_active.is_(True))
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_all_params(self, limit: int = 100) -> list[OptimisedParams]:
        query = (
            select(OptimisedParams)
            .order_by(OptimisedParams.id.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
