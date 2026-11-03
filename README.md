# Core API Gateway

[![CI](https://github.com/sunilchavare/core-api-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/sunilchavare/core-api-gateway/actions/workflows/ci.yml)

An API gateway built with FastAPI, PostgreSQL, Redis, and HTTPX. Users register, create API keys, and send requests through the gateway to downstream services. The gateway checks each key, rate-limits it, and forwards the request.

> **Status:** a backend learning and portfolio project, tested locally with Docker Compose and in CI. It is not a production-hardened deployment. See [Known Limitations](#known-limitations).

## Table of Contents

- [Features](#features)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Using the API](#using-the-api)
- [Configuration](#configuration)
- [Run the Frontend](#run-the-frontend)
- [Run Tests](#run-tests)
- [Endpoints](#endpoints)
- [Design Notes](#design-notes)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [License](#license)

## Features

- Registration and login with JWT access tokens (bcrypt password hashing)
- API keys shown once and stored only as SHA-256 hashes; list and revoke your own keys; at most 5 active keys per user
- Proxying of GET, POST, PUT, PATCH, and DELETE requests to downstream services, with clear gateway errors (502, 504)
- Redis-backed rate limiting per API key, with `Retry-After` on 429 responses
- Separate liveness (`/health`) and readiness (`/health/ready`) endpoints
- PostgreSQL with SQLAlchemy 2.0 (async) and Alembic migrations
- Docker Compose environment: non-root containers, healthchecks, dropped capabilities
- Pytest suite (unit and integration) and a GitHub Actions pipeline that runs the backend tests and frontend lint and build
- React and Vite request-builder frontend for trying the gateway

## How It Works

```
Client ──► Gateway (:8000) ──► Downstream service (:8001, internal)
              │   │
              │   └──► Redis      (rate-limit counters)
              └──────► PostgreSQL (users and API keys)
```

1. A user registers and logs in to receive a JWT.
2. The user uses the JWT to generate an API key.
3. Clients send the key in the `X-API-Key` header on proxy requests.
4. For each proxy request the gateway validates the key, applies the rate limit, strips sensitive and hop-by-hop headers, and forwards the request to the downstream service over a shared connection pool.

## Quick Start

### Prerequisites

Docker Engine and the Docker Compose plugin. You do not need to install PostgreSQL or Redis separately.

```bash
git clone https://github.com/sunilchavare/core-api-gateway.git
cd core-api-gateway
```

### 1. Configure environment

Copy the example file. `-n` means an existing `.env` is never overwritten:

```bash
cp -n .env.example .env
```

Edit `.env` and replace the placeholder values:

- **`POSTGRES_PASSWORD`**: letters, numbers, and underscores only. Compose inserts it into the database URL, so other characters can break the URL.
- **`SECRET_KEY`**: the secret used to sign JWTs. Generate one with:

  ```bash
  openssl rand -hex 32
  ```

> **Security:** keep `.env` private and never commit it. Use a unique `SECRET_KEY` for each environment.

### 2. Start services

```bash
docker compose up --build -d
```

This starts the gateway, PostgreSQL, Redis, and a demo downstream service. The gateway starts after the database, Redis, and downstream report healthy.

### 3. Apply database migrations

```bash
docker compose exec gateway alembic upgrade head
```

Run this again after pulling changes that add a migration.

### 4. Verify the gateway

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

`/health` returns `{"status":"ok"}`. `/health/ready` also checks PostgreSQL and Redis and returns `503` if either is unavailable:

```json
{"status":"ok","database":"ok","redis":"ok"}
```

Interactive API documentation is at http://localhost:8000/docs.

### 5. Stop services

```bash
docker compose down
```

The PostgreSQL data volume is kept. Do not use `docker compose down -v` unless you intend to delete the stored data.

## Using the API

### 1. Register

Usernames are 3 to 50 characters (surrounding spaces are trimmed). Passwords are 8 to 72 bytes, which is the bcrypt limit.

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "demo_user", "password": "ChangeMe123!"}'
```

### 2. Log in

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo_user", "password": "ChangeMe123!"}'
```

The response contains an `access_token` that expires after 30 minutes.

### 3. Generate an API key

```bash
curl -X POST http://localhost:8000/api/v1/keys/generate \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Copy the `api_key` from the response. **It is shown only once**; the database stores only its hash. You can hold up to 5 active keys at a time (a 6th request returns `409`).

### 4. Manage your keys

List your keys (the secret is never returned):

```bash
curl http://localhost:8000/api/v1/keys \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

Revoke a key by its `id`. The key stops working immediately and frees a slot:

```bash
curl -X DELETE http://localhost:8000/api/v1/keys/KEY_ID \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Call a downstream service through the gateway

```bash
curl http://localhost:8000/api/v1/proxy/hello/hello \
  -H "X-API-Key: YOUR_API_KEY"
```

Expected response:

```json
{"message":"Hello, world!"}
```

### Rate limiting

Each API key has a `quota_limit`. New keys allow **10 requests per 60 seconds**, counted in a fixed window. Extra requests receive `HTTP 429` with `{"detail": "Rate limit exceeded"}` and a `Retry-After` header giving the seconds until the window resets.

### Proxy routing

`/api/v1/proxy/{service}/{path}` forwards the request to the base URL registered for `{service}`, with `{path}` appended. One service is registered:

| Service name | Base URL setting |
|---|---|
| `hello` | `DOWNSTREAM_HELLO_URL` |

The demo downstream service exposes:

| Method | Path | Purpose |
|---|---|---|
| GET | `/hello` | Returns a greeting (optional `name` query parameter) |
| POST, PUT, PATCH | `/echo` | Echoes the JSON body back |
| DELETE | `/echo` | Returns a confirmation message |
| GET | `/slow` | Waits 15 seconds, useful for testing timeouts |

Gateway error responses:

| Status | Meaning |
|---|---|
| 401 | Missing, invalid, or revoked API key |
| 404 | Unknown service name |
| 409 | Username already taken, or active key limit reached |
| 429 | Rate limit exceeded |
| 502 | Downstream service unavailable or request failed |
| 504 | Downstream service timed out |

## Configuration

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | Yes | Password for the `coreapi` database user |
| `SECRET_KEY` | Yes | Secret used to sign JWTs |
| `DOWNSTREAM_TIMEOUT` | No | Downstream timeout in seconds (default `10`) |

Docker Compose sets `DATABASE_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, and `DOWNSTREAM_HELLO_URL` for the gateway automatically. The same variables, plus `CORS_ORIGINS` (default `http://localhost:5173,http://127.0.0.1:5173`) and `SQL_ECHO`, are read by the app through `backend/app/config.py`, which fails at startup if `SECRET_KEY` or `DATABASE_URL` is missing.

## Run the Frontend

The React and Vite frontend is a development tool for sending requests and inspecting responses. It is not part of the Compose services, so start the backend first.

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, enter your API key, and send a request. To point it at a different gateway URL, copy `frontend/.env.example` to `frontend/.env.local` and set `VITE_API_BASE`.

```bash
npm run lint
npm run build
```

## Run Tests

The suite has two parts:

- **Unit tests** need nothing running. They use fake Redis and a mocked downstream.
- **Integration tests** (marked `integration`) need PostgreSQL, Redis, and the demo downstream service on `127.0.0.1:8001`.

Set up a virtual environment first:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Run only the unit tests:

```bash
python -m pytest -q -m "not integration"
```

For the full suite, start Redis and the downstream service with Compose and make PostgreSQL reachable from your machine. The Compose database is not published to the host, so either run a local PostgreSQL or add a `docker-compose.override.yml` next to `docker-compose.yml`:

```yaml
services:
  db:
    ports:
      - "127.0.0.1:5432:5432"
```

Then put these in the `.env` file at the project root (use your own password) and run the migrations against that database:

```
DATABASE_URL=postgresql+psycopg://coreapi:YOUR_POSTGRES_PASSWORD@localhost:5432/core_api_gateway
REDIS_HOST=localhost
```

```bash
docker compose up -d
python -m alembic upgrade head
python -m pytest -q
```

Allow a few seconds after `docker compose up -d` for the services to become healthy. The timeout test waits on the 15-second `/slow` endpoint, so the full run takes about 30 seconds.

The same backend and frontend checks run on every push through GitHub Actions (`.github/workflows/ci.yml`).

## Endpoints

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | None | Liveness check |
| GET | `/health/ready` | None | Readiness check (PostgreSQL and Redis) |
| POST | `/api/v1/auth/register` | None | Register a user |
| POST | `/api/v1/auth/login` | None | Log in and receive a JWT |
| GET | `/api/v1/auth/me` | Bearer token | Get the current user |
| POST | `/api/v1/keys/generate` | Bearer token | Generate an API key |
| GET | `/api/v1/keys` | Bearer token | List your API keys |
| DELETE | `/api/v1/keys/{key_id}` | Bearer token | Revoke one of your keys |
| GET | `/api/v1/test-api-key` | API key | Verify a key and show its quota |
| GET, POST, PUT, PATCH, DELETE | `/api/v1/proxy/{service}/{path}` | API key | Forward a request to a downstream service |

## Design Notes

- **No user enumeration:** login returns the same `401` for an unknown user and a wrong password, and always runs a bcrypt check so response time does not reveal which usernames exist.
- **Safe proxying:** hop-by-hop headers and the client's `X-API-Key` and `Host` are not forwarded. Encoding and length headers are dropped from responses because HTTPX has already decoded the body.
- **Atomic rate limiting:** the counter and its expiry are set in one Redis transaction, so a counter can never be left without an expiry. If Redis is down the limiter fails open and logs a warning, so a Redis outage does not take the gateway down.
- **Race-safe key limit:** the per-user key cap is enforced under a row lock, so concurrent requests cannot exceed it.
- **Timestamps:** stored as timezone-aware UTC.
- **Containers:** the gateway and downstream run as a non-root user with all Linux capabilities dropped. The gateway healthcheck uses the liveness endpoint, so a Redis outage does not mark it unhealthy.

## Troubleshooting

- **Compose says `POSTGRES_PASSWORD` is not set:** create `.env` from `.env.example` and set the value.
- **Database connection errors after changing the password:** the old password is stored in the data volume. Run `docker compose down -v` to recreate it (this deletes local data), then start again and re-run migrations.
- **Tests fail with `column ... does not exist`:** the database the tests use has not been migrated. Run `python -m alembic upgrade head` from `backend`. The container's database and the one your tests use can be different servers.
- **Integration tests return 502 right after startup:** the downstream service is still starting. Wait a few seconds and rerun.
- **Port 8000 or 5173 already in use:** stop the other process, or change the published port.
- **Frontend shows a network error:** check that the gateway is running and that the frontend origin is in `CORS_ORIGINS`.
- **429 responses during manual testing:** wait for the 60-second window to reset.

## Known Limitations

- Rate limiting uses a fixed window, so bursts around a window boundary can briefly exceed the intended rate.
- Only one downstream service is registered, and routing is configured through environment variables.
- Revoked keys are kept in the database (soft delete), and there is no cleanup job.
- No refresh tokens or password reset; access tokens simply expire after 30 minutes.
- Designed for local development, not production use. There is no TLS termination, metrics, or log aggregation.

## License

MIT. See [LICENSE](LICENSE).
