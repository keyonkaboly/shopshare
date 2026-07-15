from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageBase(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class MessageCreate(MessageBase):
    pass


class MessageResponse(MessageBase):
    id: int
    conversation_id: int
    sender_id: int
    sent_at: datetime
    model_config = ConfigDict(from_attributes=True)
