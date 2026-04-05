import os
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)  # ADDED THIS!
print("DATA_DIR:", DATA_DIR)
db_path = os.path.join(DATA_DIR, 'polymarket.db')
print("DB_PATH:", db_path)
url = f"sqlite+aiosqlite:///{db_path}"
print("URL:", url)

from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine(url, echo=True)
import asyncio
async def test():
    async with engine.begin() as conn:
        print("Connected!")
asyncio.run(test())
