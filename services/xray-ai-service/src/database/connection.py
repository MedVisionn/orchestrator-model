"""
Database connection management
AsyncPG with SQLAlchemy async support
"""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Create declarative base
Base = declarative_base()

# Global engine and session maker
_engine: Optional[create_async_engine] = None
_async_session_maker: Optional[async_sessionmaker] = None


def get_database_url() -> str:
    """
    Get database URL with async driver
    
    Returns:
        Async database URL
    """
    # Replace postgresql:// with postgresql+asyncpg://
    url = settings.database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def init_database() -> None:
    """
    Initialize database connection pool
    Should be called on application startup
    """
    global _engine, _async_session_maker
    
    try:
        database_url = get_database_url()
        
        logger.info("Initializing database connection", url=database_url.split("@")[-1])
        
        # Create async engine
        _engine = create_async_engine(
            database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,  # Verify connections before using
            echo=settings.debug,  # SQL logging in debug mode
            poolclass=NullPool if settings.environment == "test" else None,
        )
        
        # Create session maker
        _async_session_maker = async_sessionmaker(
            _engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        # Test connection
        async with _engine.begin() as conn:
            await conn.execute("SELECT 1")
        
        logger.info("Database connection initialized successfully")
        
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e), exc_info=True)
        raise


async def close_database() -> None:
    """
    Close database connection pool
    Should be called on application shutdown
    """
    global _engine
    
    if _engine is not None:
        logger.info("Closing database connections")
        await _engine.dispose()
        _engine = None
        logger.info("Database connections closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get database session (FastAPI dependency)
    
    Yields:
        AsyncSession instance
    
    Example:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> bool:
    """
    Check database connection health
    
    Returns:
        True if healthy, False otherwise
    """
    if _engine is None:
        return False
    
    try:
        async with _engine.begin() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        return False


async def create_tables() -> None:
    """
    Create all tables (for development/testing)
    In production, use Alembic migrations
    """
    global _engine
    
    if _engine is None:
        raise RuntimeError("Database not initialized")
    
    logger.info("Creating database tables")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created")


async def drop_tables() -> None:
    """
    Drop all tables (for testing only)
    """
    global _engine
    
    if _engine is None:
        raise RuntimeError("Database not initialized")
    
    if settings.environment == "production":
        raise RuntimeError("Cannot drop tables in production")
    
    logger.warning("Dropping all database tables")
    
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.warning("Database tables dropped")
