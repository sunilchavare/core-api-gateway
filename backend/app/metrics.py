"""Prometheus metrics. Labels are kept to small, fixed sets of values.

Never use a client-controlled value (a raw path, an API key, a username) as a
label: every new value creates a new time series and memory is never released.
"""

from prometheus_client import Counter, Histogram

# Gateway latency is mostly the downstream call, which can take up to the
# timeout (10 s by default), so the buckets run higher than the usual defaults.
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 15)

HTTP_REQUESTS = Counter(
    "gateway_http_requests_total",
    "HTTP requests handled by the gateway.",
    ["method", "route", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "gateway_http_request_duration_seconds",
    "Time the gateway took to answer a request.",
    ["method", "route"],
    buckets=LATENCY_BUCKETS,
)

UPSTREAM_REQUESTS = Counter(
    "gateway_upstream_requests_total",
    "Requests forwarded to downstream services, by outcome.",
    ["service", "outcome"],
)

UPSTREAM_REQUEST_DURATION = Histogram(
    "gateway_upstream_request_duration_seconds",
    "Time spent waiting for a downstream service.",
    ["service"],
    buckets=LATENCY_BUCKETS,
)

RATE_LIMIT_REJECTIONS = Counter(
    "gateway_rate_limit_rejections_total",
    "Requests rejected with 429 because a key used up its quota.",
)

RATE_LIMIT_REDIS_ERRORS = Counter(
    "gateway_rate_limit_redis_errors_total",
    "Redis failures that made the rate limiter fail open.",
)
