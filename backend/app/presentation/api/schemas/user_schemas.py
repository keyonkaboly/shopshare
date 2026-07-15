from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    username: str = Field(min_length=6, max_length=25)
    email: EmailStr
    first_name: Optional[str] = Field(default="")
    last_name: Optional[str] = Field(default="")
    university: Optional[str] = Field(default="")
    phone_number: Optional[str] = Field(default="")
    is_verified_student: Optional[bool] = Field(default=False)
    profile_photo_url: Optional[str] = Field(default=None)
    rating: Optional[float] = Field(default=0.0)


class UserCreate(UserBase):
    password: str = Field(min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(UserBase):
    id: int
    model_config = ConfigDict(from_attirbutes=True)

class RideHostCreate(UserCreate):
    ride_host_id: int

class RideHostResponse(UserResponse):
    ride_host_id: int
    user_type: str

### "JWT Token" to ensure user stays logged in so u dont need to type pw everytime
class Token(BaseModel):
    access_token: str
    token_type: str

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=6, max_length=25)
    password: Optional[str] = Field(default=None, min_length=6)
    email: Optional[EmailStr] = None
