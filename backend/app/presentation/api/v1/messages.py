from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.conversation_service import create_message, list_conversations, list_messages
from app.application.services.login_service import get_current_user
from app.presentation.api.schemas.message_schemas import MessageCreate, MessageResponse
from infrastructure.database.database import get_db
from infrastructure.database.models import User

conversation_router = APIRouter(prefix="/conversations", tags=["conversations"])


@conversation_router.get("/", response_model=list[dict])
def get_conversations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_conversations(db, current_user.id)


@conversation_router.get("/{conversation_id}", response_model=list[MessageResponse])
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_messages(db, conversation_id, current_user.id)


@conversation_router.post("/{conversation_id}/messages", response_model=MessageResponse)
def send_message(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_message(db, conversation_id, current_user.id, payload.content)

