from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RideRequestBase(BaseModel):
    message: str | None = Field(default=None, max_length=250)


class RideRequestCreate(RideRequestBase):
    pass


class RideRequestUpdate(BaseModel):
    status: str | None = None


class RideRequestResponse(RideRequestBase):
    id: int
    ride_id: int
    passenger_id: int
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
