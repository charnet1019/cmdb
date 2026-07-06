"""
Database Connection
Async SQLAlchemy engine and session management
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings


# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG,
)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database connection and seed default data"""
    async with engine.begin() as conn:
        # Create tables (use Alembic for migrations in production)
        await conn.run_sync(Base.metadata.create_all)
    # Seed default admin user and settings (idempotent)
    from app.init_db import seed_default_data
    await seed_default_data()


async def close_db():
    """Close database connection"""
    await engine.dispose()