# Core API Gateway

A robust, enterprise-grade API Gateway backend architecture designed to handle secure multi-tenant user authentication, programmatic API key generation, and distributed request throttling.

## 🚀 Core Features
* **Strict Payload Validation:** Schema filtering built natively with Pydantic and FastAPI models.
* **Production-Grade Security:** Industrial password salting via `bcrypt` and bearer authentication via `python-jose` JSON Web Tokens (JWT).
* **High-Throughput Rate Limiting:** High-speed in-memory request counting leveraging Redis cache layers to block distributed denial-of-service attempts.
* **Persistent Architecture:** Scalable relational data modeling mapped natively via SQLAlchemy ORM into a PostgreSQL engine core.
* **Containerized Deployment:** Fully isolated development and production environments configured via multi-stage Docker configurations.

## 🛠️ Tech Stack
* **Language:** Python 3.12+
* **Framework:** FastAPI / Uvicorn Server
* **Database:** PostgreSQL
* **Caching & Queues:** Redis
* **ORM:** SQLAlchemy / SQLModel
