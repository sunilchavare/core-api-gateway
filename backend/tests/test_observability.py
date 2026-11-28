import asyncio
import json
import logging
import re

import fakeredis.aioredis
import httpx
import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

import app.security as security
from app.config import settings
from app.database import get_db
from app.logging_config import JsonFormatter, request_id_var
from main import app

API_KEY = {"X-API-Key": "unused"}
GENERATED_ID = re.compile(r"^[0-9a-f]{32}$")


def sample(name, labels=None):
    """Current value of a Prometheus sample, 0 if it does not exist yet."""
    return REGISTRY.get_sample_value(name, labels or {}) or 0.0


@pytest.fixture
def plain_client():
    return TestClient(app)


# --- Correlation IDs --------------------------------------------------------


def test_response_gets_a_generated_correlation_id(plain_client):
    response = plain_client.get("/health")

    assert GENERATED_ID.match(response.headers["X-Correlation-ID"])


def test_every_request_gets_a_different_id(plain_client):
    first = plain_client.get("/health").headers["X-Correlation-ID"]
    second = plain_client.get("/health").headers["X-Correlation-ID"]

    assert first != second


def test_a_valid_incoming_id_is_kept(plain_client):
    response = plain_client.get("/health", headers={"X-Correlation-ID": "trace-abc_123.x"})

    assert response.headers["X-Correlation-ID"] == "trace-abc_123.x"


@pytest.mark.parametrize(
    "unsafe",
    ["a" * 65, "has space", "<script>", "a,b", ""],
)
def test_unsafe_incoming_ids_are_replaced(plain_client, unsafe):
    # The id ends up in logs and in a downstream header, so it is never trusted blindly.
    response = plain_client.get("/health", headers={"X-Correlation-ID": unsafe})

    assert GENERATED_ID.match(response.headers["X-Correlation-ID"])


def test_the_id_is_forwarded_to_the_downstream_service(mocked_client, fake_downstream):
    seen = {}

    def downstream(request):
        seen["id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={})

    fake_downstream(downstream)

    response = mocked_client.get(
        "/api/v1/proxy/hello/hello",
        headers={**API_KEY, "X-Correlation-ID": "client-trace-1"},
    )

    assert response.status_code == 200
    assert seen["id"] == "client-trace-1"


def test_a_generated_id_is_forwarded_when_the_client_sends_none(mocked_client, fake_downstream):
    seen = {}

    def downstream(request):
        seen["id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={})

    fake_downstream(downstream)

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert seen["id"] == response.headers["X-Correlation-ID"]
    assert GENERATED_ID.match(seen["id"])


def test_an_unsafe_client_id_never_reaches_the_downstream_service(mocked_client, fake_downstream):
    seen = {}

    def downstream(request):
        seen["id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={})

    fake_downstream(downstream)

    mocked_client.get(
        "/api/v1/proxy/hello/hello",
        headers={**API_KEY, "X-Correlation-ID": "bad id with spaces"},
    )

    assert GENERATED_ID.match(seen["id"])


def test_the_id_is_available_to_code_running_inside_the_request(mocked_client, fake_downstream):
    # This is what lets every log line from one request carry the same id.
    seen = {}

    def downstream(request):
        seen["context_id"] = request_id_var.get()
        return httpx.Response(200, json={})

    fake_downstream(downstream)

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert seen["context_id"] == response.headers["X-Correlation-ID"]


# --- Logs -------------------------------------------------------------------


def access_records(caplog):
    return [r for r in caplog.records if r.name == "gateway.access"]


def test_each_request_writes_one_access_log_record(mocked_client, caplog):
    with caplog.at_level(logging.INFO):
        response = mocked_client.get("/api/v1/proxy/nope/anything", headers=API_KEY)

    (record,) = access_records(caplog)
    assert record.method == "GET"
    assert record.path == "/api/v1/proxy/nope/anything"
    assert record.status == 404
    assert record.duration_ms >= 0
    assert record.request_id == response.headers["X-Correlation-ID"]


def test_query_strings_and_secrets_are_not_logged(mocked_client, caplog):
    with caplog.at_level(logging.DEBUG):
        mocked_client.get(
            "/api/v1/proxy/nope/anything?token=query-secret",
            headers={"X-API-Key": "header-secret", "Authorization": "Bearer bearer-secret"},
        )

    # The test client logs its own requests (including the URL), so only the
    # gateway's records are checked here.
    gateway_logs = " ".join(
        f"{record.getMessage()} {record.__dict__}"
        for record in caplog.records
        if record.name.startswith("gateway")
    )
    assert gateway_logs
    assert "query-secret" not in gateway_logs
    assert "header-secret" not in gateway_logs
    assert "bearer-secret" not in gateway_logs


@pytest.mark.parametrize("path", ["/health", "/metrics"])
def test_probe_endpoints_do_not_spam_the_info_log(plain_client, caplog, path):
    with caplog.at_level(logging.INFO):
        plain_client.get(path)

    assert access_records(caplog) == []


def test_the_readiness_probe_does_not_spam_the_info_log(monkeypatch, caplog):
    # Same fakes as test_ready.py, so no real database or Redis is touched.
    class HealthyDb:
        async def execute(self, statement):
            return None

    async def fake_get_db():
        yield HealthyDb()

    app.dependency_overrides[get_db] = fake_get_db
    monkeypatch.setattr("main.redis_client", fakeredis.aioredis.FakeRedis())
    try:
        with caplog.at_level(logging.INFO):
            response = TestClient(app).get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert access_records(caplog) == []


def test_unhandled_errors_are_logged_with_the_request_id_and_counted(
    mocked_client, fake_downstream, caplog
):
    def downstream(request):
        raise RuntimeError("boom")  # not an httpx error, so nothing handles it

    fake_downstream(downstream)
    crashing_client = TestClient(app, raise_server_exceptions=False)
    before = sample(
        "gateway_http_requests_total",
        {"method": "GET", "route": "/api/v1/proxy/{service}/{path:path}", "status": "500"},
    )

    with caplog.at_level(logging.INFO):
        response = crashing_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == 500
    errors = [r for r in caplog.records if r.name == "gateway.access" and r.levelno >= logging.ERROR]
    assert errors and errors[0].exc_info is not None
    assert sample(
        "gateway_http_requests_total",
        {"method": "GET", "route": "/api/v1/proxy/{service}/{path:path}", "status": "500"},
    ) == before + 1


def make_record(text="hello", level=logging.INFO, exc_info=None, extra=None):
    record = logging.LogRecord("test.logger", level, __file__, 1, text, None, exc_info)
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


def test_json_formatter_outputs_one_json_object_per_record():
    line = JsonFormatter().format(make_record("something happened", extra={"user_id": 7}))
    data = json.loads(line)

    assert "\n" not in line
    assert data["message"] == "something happened"
    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["user_id"] == 7
    assert data["timestamp"].endswith("+00:00")


def test_json_formatter_adds_the_request_id_from_context():
    token = request_id_var.set("req-123")
    try:
        data = json.loads(JsonFormatter().format(make_record()))
    finally:
        request_id_var.reset(token)

    assert data["request_id"] == "req-123"
    assert "request_id" not in json.loads(JsonFormatter().format(make_record()))


def test_json_formatter_includes_exceptions_in_the_same_line():
    try:
        raise ValueError("bad value")
    except ValueError:
        import sys

        line = JsonFormatter().format(make_record("failed", logging.ERROR, exc_info=sys.exc_info()))

    data = json.loads(line)
    assert "ValueError: bad value" in data["exception"]
    assert "\n" not in line


def test_extra_fields_cannot_overwrite_core_fields():
    data = json.loads(JsonFormatter().format(make_record("real message", extra={"level": "FAKE", "message": "spoofed"})))

    assert data["level"] == "INFO"
    assert data["message"] == "real message"


def test_json_formatter_survives_values_json_cannot_encode():
    data = json.loads(JsonFormatter().format(make_record(extra={"obj": object()})))

    assert data["obj"].startswith("<object object")


# --- Metrics ----------------------------------------------------------------


def test_requests_are_counted_by_method_route_and_status(plain_client):
    labels = {"method": "GET", "route": "/health", "status": "200"}
    before = sample("gateway_http_requests_total", labels)

    plain_client.get("/health")

    assert sample("gateway_http_requests_total", labels) == before + 1


def test_the_route_label_is_the_template_not_the_raw_path(mocked_client):
    labels = {
        "method": "GET",
        "route": "/api/v1/proxy/{service}/{path:path}",
        "status": "404",
    }
    before = sample("gateway_http_requests_total", labels)

    mocked_client.get("/api/v1/proxy/unknown-service-xyz/some/deep/path", headers=API_KEY)

    assert sample("gateway_http_requests_total", labels) == before + 1
    assert "unknown-service-xyz" not in TestClient(app).get("/metrics").text


def test_unknown_paths_share_one_label_so_scanners_cannot_flood_metrics(plain_client):
    labels = {"method": "GET", "route": "unmatched", "status": "404"}
    before = sample("gateway_http_requests_total", labels)

    plain_client.get("/wp-admin/setup-config.php")
    plain_client.get("/.env")

    assert sample("gateway_http_requests_total", labels) == before + 2
    body = plain_client.get("/metrics").text
    assert "wp-admin" not in body
    assert "/.env" not in body


def test_request_duration_is_recorded(plain_client):
    labels = {"method": "GET", "route": "/health"}
    before = sample("gateway_http_request_duration_seconds_count", labels)

    plain_client.get("/health")

    assert sample("gateway_http_request_duration_seconds_count", labels) == before + 1


def test_metrics_endpoint_serves_prometheus_text(plain_client):
    response = plain_client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "gateway_http_requests_total" in response.text


def test_metrics_endpoint_requires_the_token_when_one_is_configured(plain_client, monkeypatch):
    monkeypatch.setattr(settings, "metrics_token", "s3cret-token")

    missing = plain_client.get("/metrics")
    wrong = plain_client.get("/metrics", headers={"Authorization": "Bearer nope"})
    right = plain_client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert right.status_code == 200


def upstream(outcome):
    return {"service": "hello", "outcome": outcome}


def test_successful_upstream_calls_are_counted_and_timed(mocked_client, fake_downstream):
    fake_downstream(lambda request: httpx.Response(200, json={}))
    before = sample("gateway_upstream_requests_total", upstream("success"))
    before_timed = sample("gateway_upstream_request_duration_seconds_count", {"service": "hello"})

    mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert sample("gateway_upstream_requests_total", upstream("success")) == before + 1
    assert sample(
        "gateway_upstream_request_duration_seconds_count", {"service": "hello"}
    ) == before_timed + 1


def test_upstream_server_errors_are_counted_separately(mocked_client, fake_downstream):
    fake_downstream(lambda request: httpx.Response(503, json={}))
    before = sample("gateway_upstream_requests_total", upstream("http_5xx"))

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == 503  # the proxy still passes the answer through
    assert sample("gateway_upstream_requests_total", upstream("http_5xx")) == before + 1


@pytest.mark.parametrize(
    "exception, expected_status, outcome",
    [
        (httpx.ReadTimeout("slow"), 504, "timeout"),
        (httpx.ConnectError("refused"), 502, "connect_error"),
        (httpx.RemoteProtocolError("garbage"), 502, "request_error"),
    ],
)
def test_upstream_failures_are_counted_by_kind(
    mocked_client, fake_downstream, exception, expected_status, outcome
):
    def downstream(request):
        raise exception

    fake_downstream(downstream)
    before = sample("gateway_upstream_requests_total", upstream(outcome))

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == expected_status
    assert sample("gateway_upstream_requests_total", upstream(outcome)) == before + 1


def test_upstream_failures_are_logged_as_warnings(mocked_client, fake_downstream, caplog):
    def downstream(request):
        raise httpx.ReadTimeout("slow")

    fake_downstream(downstream)

    with caplog.at_level(logging.WARNING):
        mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    warnings = [r for r in caplog.records if r.name == "gateway.proxy"]
    assert warnings and warnings[0].service == "hello"
    assert warnings[0].outcome == "timeout"


def test_unknown_services_are_not_counted_as_upstream_calls(mocked_client):
    # The service name comes from the URL, so it must never become a label value.
    mocked_client.get("/api/v1/proxy/made-up-name/x", headers=API_KEY)

    assert "made-up-name" not in TestClient(app).get("/metrics").text


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


def test_rate_limit_rejections_are_counted(monkeypatch):
    async def blocked(api_key, quota_limit):
        return False, 5

    monkeypatch.setattr(security, "check_rate_limit", blocked)
    before = sample("gateway_rate_limit_rejections_total")

    with pytest.raises(Exception):
        asyncio.run(security.get_current_api_key(api_key="k", db=FakeDb()))

    assert sample("gateway_rate_limit_rejections_total") == before + 1


def test_allowed_requests_are_not_counted_as_rejections(monkeypatch):
    async def allowed(api_key, quota_limit):
        return True, 0

    monkeypatch.setattr(security, "check_rate_limit", allowed)
    before = sample("gateway_rate_limit_rejections_total")

    asyncio.run(security.get_current_api_key(api_key="k", db=FakeDb()))

    assert sample("gateway_rate_limit_rejections_total") == before
