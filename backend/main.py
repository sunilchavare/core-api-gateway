from fastapi import FastAPI, HTTPException, status
from app.schemas import UserRegisterRequest, UserLoginRequest, AuthResponse, APIKeyResponse

app=FastAPI(title="Core API Gateway Skeleton")
MOCK_USER_DB={}


@app.get("/health", status_code=status.HTTP_200_OK)
def check_health():
    return {
        "status":"ok"
    }

@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegisterRequest):
    if payload.username in MOCK_USER_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    MOCK_USER_DB[payload.username]=payload.password
        
    return AuthResponse(
        message="User successfully registered",
        username=payload.username
    )
    
@app.post("/api/v1/auth/login",response_model=AuthResponse, status_code=status.HTTP_200_OK)
def login_user(payload: UserLoginRequest):
    if payload.username not in MOCK_USER_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User doesn't exist"
            
        ) 
    if MOCK_USER_DB[payload.username] != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password Doesn't Match"
        )
   
    return AuthResponse(
    message="Login Successful",
    username=payload.username
)