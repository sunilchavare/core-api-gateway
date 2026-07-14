from pydantic import BaseModel, Field

class UserRegisterRequest(BaseModel):
    #rules for checking registration data .
    username: str=Field(...,min_length=3, max_length=50)
    password: str=Field(...,min_length=8)
    
class UserLoginRequest(BaseModel):
    #rules for checking login input data.
    username: str
    password: str 
    
class AuthResponse(BaseModel):
    message: str
    username: str
class APIKeyResponse(BaseModel):
    #Standard format for returning a new API key string
    api_key: str
    status: str
    