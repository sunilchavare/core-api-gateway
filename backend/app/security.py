from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from jose import JWTError, jwt 
from dotenv import load_dotenv
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status, Security
import os 
import hashlib,secrets

from app.database import get_db
from app.models import User, APIKey
from sqlalchemy import select
from app.rate_limit import check_rate_limit

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in the environment")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES= 30 

password_hash = PasswordHash((BcryptHasher(),))
DUMMY_PASSWORD_HASH = password_hash.hash("dummy-password-for-timing")

oauth2_scheme = HTTPBearer()

api_key_header= APIKeyHeader(
    name="x-api-key"
)

def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

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
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    
    user= result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User doesn't exist"
        )
    return user

async def get_current_api_key(
    api_key: str = Security(api_key_header),
    db=Depends(get_db)
):
    hashed_key = hash_api_key(api_key)

    result = await db.execute(
        select(APIKey).where(APIKey.key_value == hashed_key)
    )
    key = result.scalar_one_or_none()

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

    allowed, retry_after = await check_rate_limit(
        hashed_key,
        key.quota_limit
    )

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)}
        )

    return key

def generate_api_key_value() -> str:
    return "cg_" + secrets.token_urlsafe(32)

def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        
