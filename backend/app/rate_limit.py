import logging
import math
import uuid

from redis.exceptions import RedisError

from app.metrics import RATE_LIMIT_REDIS_ERRORS
from app.redis import redis_client

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 60

# A new prefix, so old fixed-window counters (plain integers under the old key
# name) can never collide with the sorted sets used here.
KEY_PREFIX = "ratelimit:sw:"

# Sliding window log. Each allowed request is stored in a sorted set, scored by
# its timestamp in milliseconds. A request is allowed when fewer than `limit`
# requests were made in the last `window` milliseconds.
#
# It runs as one Lua script because Redis executes a script atomically: the
# count and the insert cannot be interleaved with another gateway request.
# Time comes from Redis, not from this process, so several gateway instances
# with slightly different clocks still agree.
#
# Returns {1, 0} when allowed, or {0, ms_until_a_slot_frees} when blocked.
SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local member = ARGV[3]

local t = redis.call('TIME')
local now_ms = t[1] * 1000 + math.floor(t[2] / 1000)

-- Forget requests that have left the window.
redis.call('ZREMRANGEBYSCORE', key, '-inf', now_ms - window_ms)

if redis.call('ZCARD', key) < limit then
    redis.call('ZADD', key, now_ms, member)
    -- Idle keys disappear on their own, so Redis does not fill up.
    redis.call('PEXPIRE', key, window_ms)
    return {1, 0}
end

-- Blocked: the next slot frees when the oldest request leaves the window.
-- Blocked requests are not recorded, so hammering a blocked key changes nothing.
local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
if #oldest == 0 then
    return {0, window_ms}
end
return {0, tonumber(oldest[2]) + window_ms - now_ms}
"""

_sliding_window_script = redis_client.register_script(SLIDING_WINDOW_LUA)


async def check_rate_limit(
    api_key: str,
    quota_limit: int,
    window_seconds: int = RATE_LIMIT_WINDOW_SECONDS,
) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds).

    retry_after_seconds is only meaningful when the request is blocked.
    """
    try:
        allowed, retry_after_ms = await _sliding_window_script(
            keys=[f"{KEY_PREFIX}{api_key}"],
            args=[window_seconds * 1000, quota_limit, uuid.uuid4().hex],
        )
    except RedisError:
        RATE_LIMIT_REDIS_ERRORS.inc()
        logger.warning("Redis unavailable, rate limiting skipped", exc_info=True)
        return True, 0

    if allowed:
        return True, 0

    return False, max(math.ceil(retry_after_ms / 1000), 1)
