from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationResponse(BaseModel):
    id: int
    ride_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)