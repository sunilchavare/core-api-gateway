# Core API Gateway

A backend API gateway built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Redis, and HTTPX. The project demonstrates authentication, API key generation, request proxying, and rate limiting.

## Features

- User registration and login
- API key generation and authentication
- Proxy requests to downstream services
- Request timeout handling
- Redis-backed rate limiting
- PostgreSQL database with SQLAlchemy
- Database migrations using Alembic
- Automated tests
- Docker Compose development environment

## Tech Stack

- Python 3.12
- FastAPI and Uvicorn
- PostgreSQL
- SQLAlchemy and Alembic
- Redis
- HTTPX
- Pytest
- Docker Compose
- React and Vite frontend

## Run with Docker Compose

### Prerequisites

Install Docker Engine and the Docker Compose plugin. You do not need to install PostgreSQL or Redis separately.

Clone the repository and enter the project directory:

```bash
git clone https://github.com/sunilchavare/core-api-gateway.git
cd core-api-gateway
```

### 1. Configure environment

Copy the example environment file to `.env` in the project root. The `-n` flag keeps an existing `.env` from being overwritten:

```bash
cp -n .env.example .env
```

Edit `.env` and replace the placeholder values:

- **`POSTGRES_PASSWORD`**: a local database password containing only letters, numbers, and underscores. Docker Compose uses it in the PostgreSQL connection URL.
- **`SECRET_KEY`**: the secret used to sign JWT authentication tokens. Generate one with:

  ```bash
  openssl rand -hex 32
  ```

**Security:** keep `.env` private and do not commit it to GitHub. Use a unique `SECRET_KEY` for each environment.

### 2. Start services

```bash
docker compose up --build -d
```

This starts the API gateway, PostgreSQL, Redis, and the downstream service.

### 3. Apply database migrations

```bash
docker compose exec gateway alembic upgrade head
```

### 4. Verify the gateway

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Interactive API documentation is available at http://localhost:8000/docs.

### 5. Test proxying

1. Open http://localhost:8000/api/v1/proxy/hello/hello
2. Register a user with `POST /api/v1/auth/register`, then log in with `POST /api/v1/auth/login`.
3. Click **Authorize** and paste the `access_token` from the login response.
4. Call `POST /api/v1/keys/generate` and copy the `api_key`. It is shown only once.

Then run:

```bash
curl http://localhost:8000/api/v1/proxy/hello \
  -H "x-api-key: YOUR_API_KEY"
```

Replace `YOUR_API_KEY` with your generated key.

Expected response:

```json
{"message":"Hello, world!"}
```

### 6. Stop services

```bash
docker compose down
```

The PostgreSQL data volume is kept when you stop services this way. Do not use `docker compose down -v` unless you intend to delete the stored data.

## Run the Frontend

The React and Vite frontend is a development tool for sending requests to the gateway. It is not part of the Docker Compose services, so start the backend first.

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite in your terminal.

To check the code:

```bash
npm run build
npm run lint
```

## Run Tests Locally

The tests need PostgreSQL, Redis, and the demo downstream service, so the Compose services must be running first.

### 1. Start services

From the repository root. Skip this step if you already completed steps 2 and 3 above and the services are still running:

```bash
docker compose up --build -d
docker compose exec gateway alembic upgrade head
```

Compose publishes Redis at `127.0.0.1:6379` and the demo downstream service at `127.0.0.1:8001` for the tests.

### 2. Install dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 3. Run tests

From the `backend` directory:

```bash
python -m pytest -q
```

The test process also needs `SECRET_KEY` and `DATABASE_URL` set in its environment, with `DATABASE_URL` pointing at a reachable PostgreSQL database.

## Main Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/auth/register` | Register a user |
| POST | `/api/v1/auth/login` | Log in |
| POST | `/api/v1/keys/generate` | Generate an API key |
| GET | `/api/v1/auth/me` | Get current authenticated user |
| GET | `/api/v1/test-api-key` | Test API key authentication |
| GET/POST/PUT/PATCH/DELETE | `/api/v1/proxy/{service}/{path}` | Forward supported requests to downstream services |

Some endpoints require authentication or an API key.

## Project Status

The Docker Compose environment has been tested locally, including the health endpoint, database migration, and authenticated downstream proxy request.

This project is intended as a backend learning and portfolio project. It is not presented as a production-hardened deployment.