from fastapi import FastAPI, HTTPException, status , Depends
from app.schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, APIKeyResponse
from uuid import uuid4
from app.database import get_db
from app.models import User
from sqlalchemy import select
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
        hashed_password=payload.password
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
    if user.hashed_password!=payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password doesn't match"
        )
   
    return AuthResponse(
    message="Login Successful",
    username=payload.username
)
    
@app.post("/api/v1/keys/generate", response_model=APIKeyResponse)
async def generate_api_key(user_id: int, db=Depends(get_db)):
    result = await db.execute(
        select(User).where(User.id==user_id)
    )
    
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code= status.HTTP_404_NOT_FOUND,
            detail= "User doesn't exist"
        )
    api_key = APIKey(
        key_value=str(uuid4()),
        user_id=user_id,
        is_active=True,
        quota_limit=10
    )
    db.add(api_key)
    await db.commit()
        
    return APIKeyResponse(
        api_key=api_key.key_value,
        status="active"
    )