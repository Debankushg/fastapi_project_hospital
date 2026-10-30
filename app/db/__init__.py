from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.async_database_url, pool_pre_ping=True)
# expire_on_commit=False: objects stay readable after the explicit commits the services make.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """One session per request. Repositories never commit; services do."""
    async with SessionLocal() as session:
        yield session


# Inject into route functions: `s: Session`
Session = Annotated[AsyncSession, Depends(get_session)]
