from dotenv import load_dotenv
import os
from sqlalchemy.ext.asyncio import create_async_engine , async_sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(
    DATABASE_URL,
    echo=True
   
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False
)

async def get_db():
    async with SessionLocal() as db:
        yield db
       