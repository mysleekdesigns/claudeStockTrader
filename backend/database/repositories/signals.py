from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Signal, SignalStatus


class SignalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, signal_data: dict) -> Signal:
        signal = Signal(**signal_data)
        self.session.add(signal)
        await self.session.commit()
        await self.session.refresh(signal)
        return signal

    async def get_by_id(self, signal_id: int) -> Signal | None:
        return await self.session.get(Signal, signal_id)

    async def list_signals(
        self,
        strategy_name: str | None = None,
        status: SignalStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Signal]:
        query = select(Signal).order_by(Signal.created_at.desc()).limit(limit).offset(offset)
        if strategy_name:
            query = query.where(Signal.strategy_name == strategy_name)
        if status:
            query = query.where(Signal.status == status)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pending_and_active(self) -> list[Signal]:
        query = select(Signal).where(
            Signal.status.in_([SignalStatus.PENDING, SignalStatus.ACTIVE])
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def resolve(
        self, signal_id: int, status: SignalStatus, pips_result: float
    ) -> None:
        stmt = (
            update(Signal)
            .where(Signal.id == signal_id)
            .values(status=status, pips_result=pips_result, resolved_at=datetime.now())
        )
        await self.session.execute(stmt)
        await self.session.commit()
