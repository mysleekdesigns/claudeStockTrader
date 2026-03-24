from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import RiskState


class RiskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current(self) -> RiskState | None:
        query = select(RiskState).order_by(RiskState.date.desc()).limit(1)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_today(self) -> RiskState:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        query = select(RiskState).where(RiskState.date == today)
        result = await self.session.execute(query)
        state = result.scalar_one_or_none()
        if state is None:
            state = RiskState(date=today, daily_loss_pct=0.0, consecutive_stops=0, is_shutdown=False)
            self.session.add(state)
            await self.session.commit()
            await self.session.refresh(state)
        return state

    async def update_state(self, state_id: int, **kwargs) -> None:
        stmt = update(RiskState).where(RiskState.id == state_id).values(**kwargs)
        await self.session.execute(stmt)
        await self.session.commit()

    async def set_shutdown(self, state_id: int, shutdown_until: datetime | None = None) -> None:
        await self.update_state(
            state_id, is_shutdown=True, shutdown_until=shutdown_until
        )

    async def reset_shutdown(self, state_id: int) -> None:
        await self.update_state(
            state_id, is_shutdown=False, shutdown_until=None, consecutive_stops=0
        )
