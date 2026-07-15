from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.login_service import get_current_user
from app.application.services.notification_service import list_notifications, mark_notification_read
from app.presentation.api.schemas.notifications_schemas import NotificationResponse
from infrastructure.database.database import get_db
from infrastructure.database.models import User

notification_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notification_router.get("/", response_model=list[NotificationResponse])
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_notifications(db, current_user.id)


@notification_router.post("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return mark_notification_read(db, notification_id, current_user.id)
