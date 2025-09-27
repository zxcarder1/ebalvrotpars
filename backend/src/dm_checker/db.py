"""Database engine and session helpers."""

from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import AppSettings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: AppSettings) -> AsyncEngine:
    """Return a singleton async engine instance."""

    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database.dsn, echo=settings.database.echo)
    return _engine


def get_session_factory(settings: AppSettings) -> async_sessionmaker[AsyncSession]:
    """Return a lazily initialised session factory."""

    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(settings), expire_on_commit=False)
    return _session_factory


@asynccontextmanager
async def session_scope(settings: AppSettings):
    """Provide a transactional scope around async operations."""

    factory = get_session_factory(settings)
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
