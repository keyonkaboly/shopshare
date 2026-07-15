from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import Notifications


def create_notification(db: Session, user_id: int, message: str) -> Notifications:
    notification = Notifications(user_id=user_id, message=message)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def list_notifications(db: Session, user_id: int):
    return db.query(Notifications).filter(Notifications.user_id == user_id).order_by(Notifications.created_at.desc()).all()


def mark_notification_read(db: Session, notification_id: int, user_id: int) -> Notifications:
    notification = db.query(Notifications).filter(Notifications.id == notification_id, Notifications.user_id == user_id).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    db.commit()
    db.refresh(notification)
    return notification
