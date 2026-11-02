from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

# bcrypt only uses the first 72 bytes of a password.
MAX_PASSWORD_BYTES = 72


class UserRegisterRequest(BaseModel):
    # Surrounding whitespace is removed so "bob " and "bob" are the same user.
    username: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=50)
    ]
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class UserLoginRequest(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True)]
    password: str


class AuthResponse(BaseModel):
    message: str
    username: str
    access_token: str


class APIKeyResponse(BaseModel):
    # Returned once, when the key is created. Only its hash is stored.
    id: int
    api_key: str
    status: str


class APIKeyInfo(BaseModel):
    """What the list endpoint shows. Never includes the key itself."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    quota_limit: int
    created_at: datetime


class RegisterResponse(BaseModel):
    message: str
    username: str
