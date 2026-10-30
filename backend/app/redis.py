
import os
from dotenv import load_dotenv
import redis.asyncio as redis

load_dotenv()

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
    socket_connect_timeout=1,
    socket_timeout=1,
)
