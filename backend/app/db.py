from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


async def init_db(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    engine = sessionmaker.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def build_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def close_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    engine = sessionmaker.kw["bind"]
    await engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
