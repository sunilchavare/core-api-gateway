from app.redis import redis_client

RATE_LIMIT_WINDOW_SECONDS = 60


async def check_rate_limit(api_key: str, quota_limit: int):
    redis_key = f"rate_limit:{api_key}"

    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(redis_key)
        pipe.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS, nx=True)
        request_count, _ = await pipe.execute()

    return request_count <= quota_limit