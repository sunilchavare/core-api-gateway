import redis.asyncio as redis

from app.config import settings

redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password or None,
    decode_responses=True,
    # Fail fast instead of hanging every request when Redis is slow or down.
    socket_connect_timeout=1,
    socket_timeout=1,
)
