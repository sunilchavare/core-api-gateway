from app.redis import redis_client

RATE_LIMIT_WINDOW_SECONDS = 60


async def check_rate_limit(api_key: str, quota_limit: int) -> tuple[bool, int]:
    """Return (allowed, seconds until the current window resets)."""
    redis_key = f"rate_limit:{api_key}"

    # MULTI/EXEC: all commands run as one unit, so the counter can never
    # exist without an expiry. NX sets the expiry only if none exists yet,
    # so later requests don't push the window forward.
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(redis_key)
        pipe.expire(redis_key, RATE_LIMIT_WINDOW_SECONDS, nx=True)
        pipe.ttl(redis_key)
        request_count, _, ttl = await pipe.execute()

    retry_after = max(ttl, 1)
    return request_count <= quota_limit, retry_after