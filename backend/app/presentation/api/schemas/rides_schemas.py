from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RidesBase(BaseModel):
    pickup_location: str = Field(min_length=2, max_length=100)
    destination: str = Field(min_length=2, max_length=100)
    departure_time: datetime
    available_seats: int = Field(ge=0)
    price_per_person: float = Field(ge=0)
    status: str = Field(default="open")


class RidesCreate(RidesBase):
    pass


class RidesUpdate(BaseModel):
    pickup_location: str | None = Field(default=None, min_length=2, max_length=100)
    destination: str | None = Field(default=None, min_length=2, max_length=100)
    departure_time: datetime | None = None
    available_seats: int | None = Field(default=None, ge=0)
    price_per_person: float | None = Field(default=None, ge=0)
    status: str | None = None


class RidesResponse(RidesBase):
    id: int
    host_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)