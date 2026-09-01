import os
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

redis_client= redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    decode_responses=True
)