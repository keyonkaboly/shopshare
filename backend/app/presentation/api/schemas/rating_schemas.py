from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RatingCreate(BaseModel):
    ride_id: int
    to_user_id: int
    rating_score: int = Field(ge=1, le=5)
    comment: str | None = None


class RatingResponse(BaseModel):
    id: int
    ride_id: int
    from_user_id: int
    to_user_id: int
    rating_score: int
    comment: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
