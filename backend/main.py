from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import settings
from app.database import get_db
from app.models import APIKey, User
from app.redis import redis_client
from app.routes import DOWNSTREAM_SERVICES
from app.schemas import (
    APIKeyInfo,
    APIKeyResponse,
    AuthResponse,
    RegisterResponse,
    UserLoginRequest,
    UserRegisterRequest,
)
from app.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    generate_api_key_value,
    get_current_api_key,
    get_current_user,
    hash_api_key,
    hash_password,
    verify_password,
)

# Headers that describe one network hop, not the end-to-end request.
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

# Never forwarded to the downstream service:
# - x-api-key: the gateway's own credential
# - host: must describe the downstream, httpx sets it from the URL
# - content-length: httpx recalculates it for the body we send
EXCLUDED_REQUEST_HEADERS = HOP_BY_HOP_HEADERS | {"x-api-key", "host", "content-length"}

# httpx already decoded the body, so these no longer describe it.
# Starlette sets a correct content-length itself.
EXCLUDED_RESPONSE_HEADERS = HOP_BY_HOP_HEADERS | {"content-encoding", "content-length"}

# Each key has its own rate limit quota, so an unlimited number of keys
# would mean an unlimited quota. Cap how many active keys one user can hold.
MAX_ACTIVE_KEYS_PER_USER = 5


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One shared client for all proxied requests, so connections are
    # pooled and reused instead of opened for every request.
    app.state.http_client = httpx.AsyncClient(timeout=settings.downstream_timeout)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="Core API Gateway", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK)
def check_health():
    """Liveness: the process is up. Does not touch any dependency."""
    return {"status": "ok"}


@app.get("/health/ready")
async def check_ready(db=Depends(get_db)):
    """Readiness: the gateway can reach PostgreSQL and Redis."""
    checks = {}

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError:
        checks["database"] = "unavailable"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except RedisError:
        checks["redis"] = "unavailable"

    ready = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={"status": "ok" if ready else "unavailable", **checks},
    )


@app.post("/api/v1/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegisterRequest,
    db=Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.username == payload.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered"
        )

    user = User(
        username=payload.username,
        hashed_password=hash_password(payload.password)
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Another request registered the same username between our
        # check above and this commit; the unique constraint caught it.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered"
        )

    return {
        "message": "User successfully registered",
        "username": payload.username,
    }


@app.post("/api/v1/auth/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login_user(
    payload: UserLoginRequest,
    db=Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.username == payload.username)
    )
    user = result.scalar_one_or_none()

    hash_to_check = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, hash_to_check)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    access_token = create_access_token(
        {"sub": str(user.id)}
    )

    return AuthResponse(
        message="Login Successful",
        username=payload.username,
        access_token=access_token
    )


@app.post("/api/v1/keys/generate", response_model=APIKeyResponse)
async def generate_api_key(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Lock this user's row until the transaction ends, so two requests
    # arriving at the same time can't both pass the check below.
    await db.execute(
        select(User.id).where(User.id == current_user.id).with_for_update()
    )

    active_keys = (
        await db.execute(
            select(func.count())
            .select_from(APIKey)
            .where(APIKey.user_id == current_user.id, APIKey.is_active.is_(True))
        )
    ).scalar_one()

    if active_keys >= MAX_ACTIVE_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Key limit reached ({MAX_ACTIVE_KEYS_PER_USER} active keys per user)"
        )

    raw_api_key = generate_api_key_value()

    api_key = APIKey(
        key_value=hash_api_key(raw_api_key),
        user_id=current_user.id,
        is_active=True,
        quota_limit=10
    )

    db.add(api_key)
    await db.commit()

    return APIKeyResponse(
        id=api_key.id,
        api_key=raw_api_key,
        status="active"
    )


@app.get("/api/v1/keys", response_model=list[APIKeyInfo])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    result = await db.execute(
        select(APIKey).where(APIKey.user_id == current_user.id).order_by(APIKey.id)
    )
    return result.scalars().all()


@app.delete("/api/v1/keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    # Filtering by user_id means other users' keys look like "not found".
    result = await db.execute(
        select(APIKey).where(APIKey.id == key_id, APIKey.user_id == current_user.id)
    )
    api_key = result.scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found"
        )

    # Revoking twice is harmless. The key stays in the table, inactive, so
    # it stops working immediately and no longer counts toward the key limit.
    api_key.is_active = False
    await db.commit()


@app.get("/api/v1/auth/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username
    }


@app.get("/api/v1/test-api-key")
async def test_api_key(
    key: APIKey = Depends(get_current_api_key)
):
    return {
        "message": "API key is valid",
        "user_id": key.user_id,
        "quota_limit": key.quota_limit
    }


@app.api_route(
    "/api/v1/proxy/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"]
)
async def proxy_request(
    service: str,
    path: str,
    request: Request,
    key: APIKey = Depends(get_current_api_key)
):
    base_url = DOWNSTREAM_SERVICES.get(service)

    if base_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    target_url = f"{base_url}/{path}"

    body = await request.body()
    try:
        response = await request.app.state.http_client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            headers={
                name: value
                for name, value in request.headers.items()
                if name.lower() not in EXCLUDED_REQUEST_HEADERS
            },
            content=body
        )
    except httpx.TimeoutException:
        # Covers connect, read, write and pool timeouts.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Downstream service timeout"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Downstream service unavailable"
        )
    except httpx.RequestError:
        # Any other network or protocol failure talking to the downstream.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Downstream request failed"
        )

    response_headers = {
        name: value
        for name, value in response.headers.items()
        if name.lower() not in EXCLUDED_RESPONSE_HEADERS
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers
    )
