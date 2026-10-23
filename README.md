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

Install Docker Engine and the Docker Compose plugin.

### 1. Configure environment

Create a root `.env` file if you do not already have one. Preserve any existing application settings and add:

    POSTGRES_PASSWORD=choose_a_local_password

Use a password suitable for local development. Do not commit `.env` or share its secrets.

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

## Run Tests Locally

From the backend directory, activate your virtual environment and run:

    python -m pytest -q

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
