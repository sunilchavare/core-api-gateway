from fastapi import FastAPI, HTTPException, status , Depends
from app.schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, APIKeyResponse
from uuid import uuid4
from app.database import get_db
from app.models import User
from sqlalchemy import select
from app.security import hash_password, verify_password, create_access_token, get_current_user
from app.models import User, APIKey
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