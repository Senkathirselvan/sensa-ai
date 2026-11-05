from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from backend.app.config import settings
from backend.app.db.models import Base

db_url = settings.DATABASE_URL

engine = create_async_engine(
    db_url,
    echo=False,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_db():
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"[Resume-Prep-Agent DB] Connected to PostgreSQL successfully.")
    except Exception as e:
        print(f"[Resume-Prep-Agent DB] Primary DB connection failed ({e}). Falling back to SQLite...")
        engine = create_async_engine(settings.SQLITE_FALLBACK_URL, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"[Resume-Prep-Agent DB] Initialized SQLite fallback at {settings.SQLITE_FALLBACK_URL}")

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

