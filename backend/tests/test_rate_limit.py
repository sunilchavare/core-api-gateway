import asyncio
import time

import fakeredis.aioredis
import pytest
import redis.asyncio
from fastapi import HTTPException
from prometheus_client import REGISTRY

import app.rate_limit as rate_limit
import app.security as security
from app.config import settings

WINDOW_SECONDS = rate_limit.RATE_LIMIT_WINDOW_SECONDS


def redis_key(api_key):
    return f"{rate_limit.KEY_PREFIX}{api_key}"


@pytest.fixture
def run_with_fake_redis(monkeypatch):
    """Run an async scenario against an in-memory Redis instead of the real one."""

    def run(scenario):
        async def wrapper():
            client = fakeredis.aioredis.FakeRedis(decode_responses=True)
            monkeypatch.setattr(rate_limit, "redis_client", client)
            # The script object is bound to a client, so rebuild it for the fake.
            monkeypatch.setattr(
                rate_limit, "_sliding_window_script", client.register_script(rate_limit.SLIDING_WINDOW_LUA)
            )
            return await scenario(client)

        return asyncio.run(wrapper())

    return run


def test_allows_up_to_the_quota_then_blocks(run_with_fake_redis):
    async def scenario(client):
        return [(await rate_limit.check_rate_limit("key-a", 3))[0] for _ in range(5)]

    assert run_with_fake_redis(scenario) == [True, True, True, False, False]


def test_keys_are_limited_independently(run_with_fake_redis):
    async def scenario(client):
        for _ in range(3):
            await rate_limit.check_rate_limit("key-one", 3)
        blocked = (await rate_limit.check_rate_limit("key-one", 3))[0]
        other = (await rate_limit.check_rate_limit("key-two", 3))[0]
        return blocked, other

    assert run_with_fake_redis(scenario) == (False, True)


def test_blocked_requests_are_not_recorded(run_with_fake_redis):
    # Hammering a blocked key must not use up memory or push the reset later.
    async def scenario(client):
        for _ in range(200):
            await rate_limit.check_rate_limit("key-b", 5)
        return await client.zcard(redis_key("key-b"))

    assert run_with_fake_redis(scenario) == 5


def test_no_burst_across_a_window_boundary(run_with_fake_redis):
    # With a fixed window, a client could send `limit` requests at the end of
    # one window and `limit` more right after it resets: 2x the quota in a
    # fraction of a window. A sliding window must keep counting the recent ones.
    window = 1  # second

    async def scenario(client):
        limit = 3
        results = [(await rate_limit.check_rate_limit("key-c", limit, window))[0]]  # t = 0.0
        await asyncio.sleep(0.6)
        results += [(await rate_limit.check_rate_limit("key-c", limit, window))[0] for _ in range(2)]  # t = 0.6
        await asyncio.sleep(0.5)  # t = 1.1: the first request has aged out, the other two have not
        results += [(await rate_limit.check_rate_limit("key-c", limit, window))[0] for _ in range(3)]
        return results

    # A fixed window would reset at t = 1.0 and allow all three late requests.
    assert run_with_fake_redis(scenario) == [True, True, True, True, False, False]


def test_requests_are_allowed_again_once_they_age_out(run_with_fake_redis):
    async def scenario(client):
        for _ in range(2):
            await rate_limit.check_rate_limit("key-d", 2, 1)
        blocked = (await rate_limit.check_rate_limit("key-d", 2, 1))[0]
        await asyncio.sleep(1.2)
        allowed = (await rate_limit.check_rate_limit("key-d", 2, 1))[0]
        return blocked, allowed

    assert run_with_fake_redis(scenario) == (False, True)


def test_retry_after_is_when_the_oldest_request_ages_out(run_with_fake_redis):
    async def scenario(client):
        seconds, micros = await client.time()
        now_ms = seconds * 1000 + micros // 1000
        # One request made 50 seconds ago: it leaves the 60 second window in 10 seconds.
        await client.zadd(redis_key("key-e"), {"old-request": now_ms - 50_000})
        return await rate_limit.check_rate_limit("key-e", 1)

    allowed, retry_after = run_with_fake_redis(scenario)
    assert allowed is False
    assert 9 <= retry_after <= 11


def test_retry_after_is_at_least_one_second(run_with_fake_redis):
    async def scenario(client):
        seconds, micros = await client.time()
        now_ms = seconds * 1000 + micros // 1000
        # Leaves the window in about 100 ms, which must still report a whole second.
        await client.zadd(redis_key("key-f"), {"old-request": now_ms - (WINDOW_SECONDS * 1000 - 100)})
        return await rate_limit.check_rate_limit("key-f", 1)

    allowed, retry_after = run_with_fake_redis(scenario)
    assert allowed is False
    assert retry_after == 1


def test_idle_keys_expire_so_redis_does_not_fill_up(run_with_fake_redis):
    async def scenario(client):
        await rate_limit.check_rate_limit("key-g", 10)
        return await client.ttl(redis_key("key-g"))

    assert 0 < run_with_fake_redis(scenario) <= WINDOW_SECONDS


class FakeKey:
    id = 1
    is_active = True
    quota_limit = 10
    user_id = 1


class FakeResult:
    def scalar_one_or_none(self):
        return FakeKey()


class FakeDb:
    async def execute(self, statement):
        return FakeResult()


def test_429_response_has_retry_after_header(monkeypatch):
    async def blocked(api_key, quota_limit):
        return False, 42

    monkeypatch.setattr(security, "check_rate_limit", blocked)

    with pytest.raises(HTTPException) as error:
        asyncio.run(security.get_current_api_key(api_key="k", db=FakeDb()))

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"] == "42"


def test_allowed_request_returns_the_key(monkeypatch):
    async def allowed(api_key, quota_limit):
        return True, 30

    monkeypatch.setattr(security, "check_rate_limit", allowed)

    key = asyncio.run(security.get_current_api_key(api_key="k", db=FakeDb()))

    assert key.quota_limit == 10


def test_fails_open_when_redis_is_down(monkeypatch, caplog):
    # Nothing listens on port 1, so every command raises ConnectionError.
    dead_redis = redis.asyncio.Redis(
        host="127.0.0.1", port=1, socket_connect_timeout=1
    )
    monkeypatch.setattr(rate_limit, "redis_client", dead_redis)
    monkeypatch.setattr(
        rate_limit, "_sliding_window_script", dead_redis.register_script(rate_limit.SLIDING_WINDOW_LUA)
    )

    before = REGISTRY.get_sample_value("gateway_rate_limit_redis_errors_total") or 0.0

    with caplog.at_level("WARNING"):
        result = asyncio.run(rate_limit.check_rate_limit("key-x", 3))

    assert result == (True, 0)
    assert "Redis unavailable" in caplog.text
    # Failing open is invisible to clients, so it must be visible in metrics.
    assert REGISTRY.get_sample_value("gateway_rate_limit_redis_errors_total") == before + 1


@pytest.mark.integration
def test_concurrent_requests_cannot_exceed_the_quota(monkeypatch):
    # Real Redis: 50 requests race for 5 slots. The check and the update happen
    # in one atomic Lua script, so exactly 5 must get through.
    async def scenario():
        client = redis.asyncio.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        monkeypatch.setattr(rate_limit, "redis_client", client)
        monkeypatch.setattr(
            rate_limit, "_sliding_window_script", client.register_script(rate_limit.SLIDING_WINDOW_LUA)
        )
        key = f"race-{time.time_ns()}"
        try:
            results = await asyncio.gather(
                *(rate_limit.check_rate_limit(key, 5) for _ in range(50))
            )
            return sum(1 for allowed, _ in results if allowed)
        finally:
            await client.delete(redis_key(key))
            await client.aclose()

    assert asyncio.run(scenario()) == 5
