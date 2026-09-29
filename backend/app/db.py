from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


async def init_db(sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    engine = sessionmaker.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


# Columns added after the first release; create_all never alters existing tables.
_ADDED_COLUMNS = {
    "jobs": {
        "sample_input": "TEXT NOT NULL DEFAULT ''",
        "sample_output": "TEXT NOT NULL DEFAULT ''",
    },
}


def _add_missing_columns(conn) -> None:
    inspector = inspect(conn)
    for table, columns in _ADDED_COLUMNS.items():
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


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
