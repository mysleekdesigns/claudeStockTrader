from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

async_engine = create_async_engine(
    settings.database_url,
    pool_size=20,
    max_overflow=10,
    echo=False,
)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
