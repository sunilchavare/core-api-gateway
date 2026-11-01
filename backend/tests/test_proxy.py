import gzip

import httpx
import pytest

API_KEY = {"X-API-Key": "unused"}


def test_hello_goes_through_the_generic_proxy_route(mocked_client, fake_downstream):
    def downstream(request):
        assert request.url.path == "/hello"
        return httpx.Response(200, json={"message": "Hello, world!"})

    fake_downstream(downstream)

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, world!"}


def test_unknown_service_returns_404(mocked_client):
    response = mocked_client.get("/api/v1/proxy/nope/anything", headers=API_KEY)

    assert response.status_code == 404
    assert response.json()["detail"] == "Service not found"


def test_proxy_does_not_forward_stale_encoding_headers(mocked_client, fake_downstream):
    body = b'{"message":"Hello, world!"}'
    compressed = gzip.compress(body)

    def downstream(request):
        return httpx.Response(
            200,
            content=compressed,
            headers={"content-encoding": "gzip", "content-type": "application/json"},
        )

    fake_downstream(downstream)

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == 200
    assert response.json() == {"message": "Hello, world!"}
    assert "content-encoding" not in response.headers
    assert response.headers["content-length"] == str(len(body))


def test_proxy_filters_request_headers(mocked_client, fake_downstream):
    seen = {}

    def downstream(request):
        seen["headers"] = request.headers
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    fake_downstream(downstream)

    response = mocked_client.post(
        "/api/v1/proxy/hello/echo",
        json={"a": 1},
        headers={
            "X-API-Key": "secret-key",
            "X-Client-Name": "demo",
            "Keep-Alive": "timeout=5",
        },
    )

    assert response.status_code == 200
    headers = seen["headers"]
    # Gateway-only credentials and connection-level headers stay here.
    assert "x-api-key" not in headers
    assert "keep-alive" not in headers
    # Host must describe the downstream, not the gateway.
    assert headers["host"] == "downstream.test"
    # Content-Length must match the body that was actually sent.
    assert headers["content-length"] == str(len(seen["body"]))
    # Normal application headers still pass through.
    assert headers["x-client-name"] == "demo"


@pytest.mark.parametrize(
    "error, expected_status, expected_detail",
    [
        (httpx.ConnectTimeout("connect timed out"), 504, "Downstream service timeout"),
        (httpx.ReadTimeout("read timed out"), 504, "Downstream service timeout"),
        (httpx.PoolTimeout("pool timed out"), 504, "Downstream service timeout"),
        (httpx.ConnectError("refused"), 502, "Downstream service unavailable"),
        (httpx.ReadError("connection reset"), 502, "Downstream request failed"),
    ],
)
def test_proxy_maps_downstream_errors(
    mocked_client, fake_downstream, error, expected_status, expected_detail
):
    def downstream(request):
        raise error

    fake_downstream(downstream)

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == expected_status
    assert response.json()["detail"] == expected_detail


def test_proxy_passes_downstream_error_status_through(mocked_client, fake_downstream):
    def downstream(request):
        return httpx.Response(404, json={"detail": "nope"})

    fake_downstream(downstream)

    response = mocked_client.get("/api/v1/proxy/hello/hello", headers=API_KEY)

    assert response.status_code == 404
    assert response.json() == {"detail": "nope"}
