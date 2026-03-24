from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import DecisionLog


class DecisionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, decision_data: dict) -> DecisionLog:
        decision = DecisionLog(**decision_data)
        self.session.add(decision)
        await self.session.commit()
        await self.session.refresh(decision)
        return decision

    async def list_recent(self, limit: int = 50) -> list[DecisionLog]:
        query = (
            select(DecisionLog)
            .order_by(DecisionLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
