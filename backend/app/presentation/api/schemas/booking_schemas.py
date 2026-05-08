from pydantic import BaseModel, EmailStr, Field, ConfigDict

class BookBase(BaseModel):
    ride_id: int

class BookingCreate(BookBase):
    pass

class BookingResponse(BookBase):
    id: int
    user_id: int
    status: str

    model_config = ConfigDict(from_attributes=True)
