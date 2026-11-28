import logging
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.logging_config import request_id_var
from app.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS

logger = logging.getLogger("gateway.access")

CORRELATION_HEADER = "X-Correlation-ID"

# Letters, digits, dot, underscore, dash. Short and without spaces or newlines,
# so a client cannot inject fake log lines or odd headers through it.
VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

# Probes run every few seconds; logging each one would bury real traffic.
QUIET_PATHS = {"/health", "/health/ready", "/metrics"}


def pick_request_id(scope: Scope) -> str:
    supplied = Headers(scope=scope).get(CORRELATION_HEADER)
    if supplied and VALID_REQUEST_ID.match(supplied):
        return supplied
    return uuid.uuid4().hex


def route_label(scope: Scope) -> str:
    """The route template, for example /api/v1/proxy/{service}/{path:path}.

    The raw path is never used, so scanners probing random URLs cannot create
    an unbounded number of metric series.
    """
    route = scope.get("route")
    return getattr(route, "path", None) or "unmatched"


class ObservabilityMiddleware:
    """Gives every request a correlation id, an access log line and metrics.

    Written as plain ASGI middleware, not BaseHTTPMiddleware, so the request id
    stays visible to the endpoint code and responses are not buffered.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = pick_request_id(scope)
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500  # what the client gets if the app crashes

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[CORRELATION_HEADER] = request_id
            await send(message)

        crashed = False
        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            crashed = True
            raise
        finally:
            duration = time.perf_counter() - started
            method = scope["method"]
            route = route_label(scope)

            HTTP_REQUESTS.labels(method, route, str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(method, route).observe(duration)

            path = scope["path"]  # no query string: it can carry secrets
            fields = {
                # Set explicitly so the record carries the id even if it is
                # formatted later, outside this request's context.
                "request_id": request_id,
                "method": method,
                "path": path,
                "status": status_code,
                "duration_ms": round(duration * 1000, 1),
            }
            if crashed:
                logger.error("Unhandled exception", extra=fields, exc_info=True)
            elif path in QUIET_PATHS:
                logger.debug("request", extra=fields)
            else:
                logger.info("request", extra=fields)

            request_id_var.reset(token)
