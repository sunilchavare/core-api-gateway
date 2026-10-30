import logging

from redis.exceptions import RedisError

from app.redis import redis_client

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 60


async def check_rate_limit(api_key: str, quota_limit: int) -> tuple[bool, int]:
   
    redis_key = f"rate_limit:{api_key}"

    try:
        
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.incr(redis_key)
            pipe.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS, nx=True)
            pipe.ttl(redis_key)
            request_count, _, ttl = await pipe.execute()
    except RedisError:
        logger.warning("Redis unavailable, rate limiting skipped", exc_info=True)
        return True, 0

    retry_after = max(ttl, 1)
    return request_count <= quota_limit, retry_after