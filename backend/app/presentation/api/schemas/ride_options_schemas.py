from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime

class RideOptionBase(BaseModel):
    pickup_location: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=25)
    departure_time: datetime
    ### Ensure that seats and price are atleast equal to 0 (ge greater or equal to 0)
    available_seats: int = Field(ge=0)
    price_per_person: float = Field(ge=0)
    status: str = Field(default="open")

class RideOptionCreate(RideOptionBase):
    pass

class RideOptionResponse(RideOptionBase):
    id: int
    host_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)