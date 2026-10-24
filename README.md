# Core API Gateway

A backend API gateway built with FastAPI, PostgreSQL, SQLAlchemy, Alembic, Redis, and HTTPX. The project demonstrates authentication, API key generation, request proxying, and rate limiting.

Getting Started

Clone the repository and enter the project directory:

git clone https://github.com/sunilchavare/core-api-gateway.git
cd core-api-gateway

Then follow the setup instructions below.

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

Install Docker Engine and the Docker Compose plugin.

### 1. Configure environment

Copy the example environment file into `.env` at the project root:

```bash
cp -n .env.example .env
```

Edit `.env` and set the required values:

- **`POSTGRES_PASSWORD`**: Choose a local database password containing only letters, numbers, and underscores. Docker Compose uses this value in the PostgreSQL connection URL.

- **`SECRET_KEY`**: A secret used to sign JWT authentication tokens. Generate one with:

  ```bash
  openssl rand -hex 32
  ```

Replace the placeholder values in `.env` with your chosen database password and generated secret.

**Security:** Keep `.env` private. Do not commit it to GitHub or share its secrets. Use a unique `SECRET_KEY` for each environment.

### 2. Start services

    docker compose up --build -d

This starts the API gateway, PostgreSQL, Redis, and the downstream service.

### 3. Apply database migrations

    docker compose exec gateway alembic upgrade head

### 4. Verify the gateway

    curl http://localhost:8000/health

Expected response:

    {"status":"ok"}

Interactive API documentation is available at http://localhost:8000/docs.

### 5. Test proxying

Authenticate through the API documentation and generate an API key. Then run:

    curl http://localhost:8000/api/v1/proxy/hello \
      -H "x-api-key: YOUR_API_KEY"

Replace `YOUR_API_KEY` with your generated key.

Expected response:

    {"message":"Hello, world!"}

### 6. Stop services

    docker compose down

The PostgreSQL data volume is retained when you stop services this way. Do not use `docker compose down -v` unless you intend to delete the stored volume.

## Run the Frontend

The React and Vite frontend is maintained separately from the Docker Compose backend services.

### 1. Install dependencies

```bash
cd frontend
npm install
```

### 2. Start the development server

```bash
npm run dev
```

Open the local URL printed by Vite in your terminal.

### 3. Build and lint

```bash
npm run build
npm run lint
```

The frontend is not included in the Docker Compose services.

## Run Tests Locally

Ensure you have completed the environment configuration in the Docker Compose section above. If .env already exists, preserve it rather than overwriting it.


### 1. Install dependencies

From the repository root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Start required services

Return to the repository root and start the Docker Compose services:

```bash
cd ..
docker compose up --build -d
docker compose exec gateway alembic upgrade head
```

The tests require PostgreSQL and Redis. Redis is published locally at `127.0.0.1:6379`. Ensure the local test process uses the correct database and Redis configuration.

### 3. Run tests

From the `backend` directory:

```bash
cd backend
python -m pytest -q
```

## Main Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/api/v1/auth/register` | Register a user |
| POST | `/api/v1/auth/login` | Log in |
| POST | `/api/v1/keys/generate` | Generate an API key |
| GET | `/api/v1/auth/me` | Get current authenticated user |
| GET | `/api/v1/test-api-key` | Test API key authentication |
| GET | `/api/v1/proxy/hello` | Proxy a request to the downstream service |
| GET/POST/PUT/PATCH/DELETE | `/api/v1/proxy/{service}/{path}` | Forward supported requests to downstream services |

Some endpoints require authentication or an API key.

## Project Status

The Docker Compose environment has been tested locally, including the health endpoint, database migration, and authenticated downstream proxy request.

This project is intended as a backend learning and portfolio project. It is not presented as a production-hardened deployment.
