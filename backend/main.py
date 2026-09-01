from fastapi import FastAPI, HTTPException, status , Depends, Request
from app.schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, APIKeyResponse
from uuid import uuid4
from app.database import get_db
from sqlalchemy import select
from app.security import hash_password, verify_password, create_access_token, get_current_user, get_current_api_key
from app.models import User, APIKey
from app.routes import DOWNSTREAM_SERVICES
import httpx
from fastapi.responses import JSONResponse

app=FastAPI(title="Core API Gateway Skeleton")

@app.get("/health", status_code=status.HTTP_200_OK)
def check_health():
    return {
        "status":"ok"
    }
    

@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
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
    
    return AuthResponse(
        message="User successfully registered",
        username=payload.username
    )
    
@app.post("/api/v1/auth/login",response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login_user(
    payload: UserLoginRequest,
    db=Depends(get_db)
    ):

    result= await db.execute(
    select(User).where(User.username== payload.username)
   )
    user= result.scalar_one_or_none()
    
        
    if user is None: 
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User doesn't exist"
        )
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password doesn't match"
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
 
    api_key = APIKey(
        key_value=str(uuid4()),
        user_id=current_user.id,
        is_active=True,
        quota_limit=10
    )
    db.add(api_key)
    await db.commit()
        
    return APIKeyResponse(
        api_key=api_key.key_value,
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
    key: APIKey= Depends(get_current_api_key)
):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{DOWNSTREAM_SERVICES['hello']}/hello"
        )
        return response.json()
    
@app.api_route(
    "/api/v1/proxy/{service}/{path:path}",
    methods=["GET","POST","PUT","DELETE","PATCH"]
               )
async def proxy_request(
    service: str,
    path: str,
    request: Request,
    name: str= None,
    body: dict | None= None,
    key: APIKey = Depends(get_current_api_key)
):
    base_url= DOWNSTREAM_SERVICES.get(service)
    
    if base_url is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found"
        )
    target_url = f"{base_url}/{path}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response =  await client.request(
            method=request.method,
            url=target_url,
            params=request.query_params,
            headers={
                key: value 
                for key, value in request.headers.items()
                if key.lower()!= "x-api-key"
                },
            json=body
            )
    except httpx.ReadTimeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Downstream service timeout"
        )    
    
    return JSONResponse(
        content=response.json(),
        status_code=response.status_code
    )
