from fastapi import Cookie, Depends, HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from infrastructure.database.database import get_db
from infrastructure.database.models import (
    Conversations,
    DriverVerification,
    Messages,
    Notifications,
    Payments,
    RideRatings,
    RideRequests,
    Rides,
    User,
)
from infrastructure.security.hashing import ALGORITHM, SECRET_KEY


def get_current_user(access_token: str | None = Cookie(None), db: Session = Depends(get_db)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def delete_user_account(db: Session, user: User) -> None:
    """Remove a user and everything that references them.

    SQLite here doesn't enforce foreign keys, so a plain db.delete(user)
    would silently leave orphaned rides/messages/notifications/ratings
    behind. Clean those up explicitly instead.
    """
    hosted_ride_ids = [ride.id for ride in db.query(Rides).filter(Rides.host_id == user.id).all()]

    if hosted_ride_ids:
        db.query(Payments).filter(Payments.ride_id.in_(hosted_ride_ids)).delete(synchronize_session=False)
        db.query(RideRequests).filter(RideRequests.ride_id.in_(hosted_ride_ids)).delete(synchronize_session=False)
        conversation_ids = [
            c.id for c in db.query(Conversations).filter(Conversations.ride_id.in_(hosted_ride_ids)).all()
        ]
        if conversation_ids:
            db.query(Messages).filter(Messages.conversation_id.in_(conversation_ids)).delete(synchronize_session=False)
            db.query(Conversations).filter(Conversations.id.in_(conversation_ids)).delete(synchronize_session=False)
        db.query(Rides).filter(Rides.id.in_(hosted_ride_ids)).delete(synchronize_session=False)

    db.query(RideRequests).filter(RideRequests.passenger_id == user.id).delete(synchronize_session=False)
    db.query(Messages).filter(Messages.sender_id == user.id).delete(synchronize_session=False)
    db.query(Notifications).filter(Notifications.user_id == user.id).delete(synchronize_session=False)
    db.query(RideRatings).filter(
        (RideRatings.from_user_id == user.id) | (RideRatings.to_user_id == user.id)
    ).delete(synchronize_session=False)
    db.query(Payments).filter(
        (Payments.payer_id == user.id) | (Payments.payee_id == user.id)
    ).delete(synchronize_session=False)
    db.query(DriverVerification).filter(DriverVerification.user_id == user.id).delete(synchronize_session=False)

    db.delete(user)
    db.commit()