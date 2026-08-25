from passlib.context import CryptContext
from jose import JWTError, jwt 
from dotenv import load_dotenv
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, Security
import os 

from app.database import get_db
from app.models import User, APIKey
from sqlalchemy import select

load_dotenv()

SECRET_KEY =os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES= 30 

pwd_context= CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_scheme = HTTPBearer()

api_key_header= APIKeyHeader(
    name="x-api-key"
)

def hash_password(password: str)-> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str)-> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict)->str:
    to_encode=data.copy()
    
    expire = datetime.now(timezone.utc) + timedelta(
        minutes= ACCESS_TOKEN_EXPIRE_MINUTES
    )
    
    to_encode.update({"exp":expire})
    
    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db = Depends(get_db)
):
    token = credentials.credentials
    try:
        payload=jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    user_id= payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    result = await db.execute(
        select(User).where(User.id==int(user_id))
    )
    
    user= result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User doesn't exist"
        )
    return user

async def get_current_api_key(
    api_key: str= Security(api_key_header),
    db=Depends(get_db)
):
    result= await db.execute(
        select(APIKey).where(APIKey.key_value==api_key)
    )
    key= result.scalar_one_or_none()
    
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    if not key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is inactive"
        )
    return key

        