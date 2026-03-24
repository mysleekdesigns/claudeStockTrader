from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import ABTestRun


class ABTestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: dict) -> ABTestRun:
        run = ABTestRun(**data)
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def update_outcomes(
        self, run_id: int, signals_won: int, signals_lost: int
    ) -> ABTestRun | None:
        result = await self.session.execute(
            select(ABTestRun).where(ABTestRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if run is None:
            return None
        run.signals_won = signals_won
        run.signals_lost = signals_lost
        total = signals_won + signals_lost
        run.win_rate = signals_won / total if total > 0 else 0.0
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_by_decision_cycle(self, decision_cycle_id: int) -> ABTestRun | None:
        result = await self.session.execute(
            select(ABTestRun).where(ABTestRun.decision_cycle_id == decision_cycle_id)
        )
        return result.scalar_one_or_none()

    async def list_recent(self, limit: int = 100) -> list[ABTestRun]:
        query = (
            select(ABTestRun)
            .order_by(ABTestRun.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_variant_summary(self) -> list[dict]:
        """Aggregate win/loss stats per variant."""
        query = (
            select(
                ABTestRun.variant_name,
                func.count(ABTestRun.id).label("total_cycles"),
                func.sum(ABTestRun.signals_created).label("total_signals"),
                func.sum(ABTestRun.signals_won).label("total_won"),
                func.sum(ABTestRun.signals_lost).label("total_lost"),
            )
            .group_by(ABTestRun.variant_name)
        )
        result = await self.session.execute(query)
        rows = result.all()
        return [
            {
                "variant_name": row.variant_name,
                "total_cycles": row.total_cycles,
                "total_signals": row.total_signals or 0,
                "total_won": row.total_won or 0,
                "total_lost": row.total_lost or 0,
            }
            for row in rows
        ]
