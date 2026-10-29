from fastapi import FastAPI, HTTPException, status , Depends, Request, Response
from app.schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, APIKeyResponse, RegisterResponse
from uuid import uuid4
from app.database import get_db
from sqlalchemy import select
from app.security import hash_password, verify_password, create_access_token, get_current_user, get_current_api_key, generate_api_key_value, hash_api_key, DUMMY_PASSWORD_HASH
from app.models import User, APIKey
from app.routes import DOWNSTREAM_SERVICES
import httpx
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


import os
from dotenv import load_dotenv

load_dotenv()


app=FastAPI(title="Core API Gateway Skeleton")

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
# Seconds to wait on the downstream service; httpx applies it to connect,
# read, write and pool-acquire separately. Defaults to 10 if unset.
DOWNSTREAM_TIMEOUT = float(os.getenv("DOWNSTREAM_TIMEOUT", "10"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", status_code=status.HTTP_200_OK)
def check_health():
    return {
        "status":"ok"
    }
    

@app.post("/api/v1/auth/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserRegisterRequest ,
    db = Depends(get_db)
    ):
    result= await db.execute(
        select(User).where(User.username==payload.username)
    )
    existing_user = result.scalar_one_or_none()
    user=User(
        username=payload.username,
        hashed_password=hash_password(payload.password)
    )
    if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
    
    db.add(user)
    await db.commit()
    
    return {
    "message": "User successfully registered",
    "username": payload.username,
    
}
    
@app.post("/api/v1/auth/login",response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login_user(
    payload: UserLoginRequest,
    db=Depends(get_db)
    ):

    result= await db.execute(
    select(User).where(User.username== payload.username)
   )
    user= result.scalar_one_or_none()
    
        
    hash_to_check = user.hashed_password if user else DUMMY_PASSWORD_HASH
    password_ok = verify_password(payload.password, hash_to_check)

    if user is None or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
   
    access_token= create_access_token(
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
        api_key=raw_api_key,
        status="active"
    )
    
@app.get("/api/v1/auth/me")
async def get_me(current_user: User= Depends(get_current_user)):
    return{
        "id":current_user.id,
        "username": current_user.username
    }
@app.get("/api/v1/test-api-key")
async def test_api_key(
    key: APIKey= Depends(get_current_api_key)
):
    return{
        "message": "API key is valid",
        "user_id": key.user_id,
        "quota_limit": key.quota_limit
    }
    

@app.get("/api/v1/proxy/hello")
async def proxy_hello(
    key: APIKey = Depends(get_current_api_key)
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{DOWNSTREAM_SERVICES['hello']}/hello"
            )
            response.raise_for_status()
            return response.json()

    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail="Downstream service unavailable"
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Downstream service timed out"
        )

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
        async with httpx.AsyncClient(timeout=DOWNSTREAM_TIMEOUT) as client:
            response = await client.request(
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