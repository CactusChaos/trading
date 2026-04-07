import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(DATA_DIR, 'polymarket.db')}"

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
