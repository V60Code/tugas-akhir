from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Password constraints applied consistently on create and update.
# min_length=8  : OWASP A07 — prevents trivially weak passwords.
# max_length=128 : bcrypt silently truncates at 72 bytes; capping at 128
#                  prevents CPU-exhaustion via oversized inputs.
_PasswordField = Annotated[str, Field(min_length=8, max_length=128)]


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: _PasswordField


class UserUpdate(UserBase):
    password: Optional[_PasswordField] = None


class UserResponse(UserBase):
    """Read-only user representation returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str
