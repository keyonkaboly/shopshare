from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import Conversations, Messages, RideRequests, Rides

from .notification_service import create_notification


def list_conversations(db: Session, user_id: int):
    host_rides = db.query(Rides).filter(Rides.host_id == user_id).all()
    accepted_requests = db.query(RideRequests).filter(RideRequests.passenger_id == user_id, RideRequests.status == "accepted").all()
    ride_ids = {ride.id for ride in host_rides} | {request.ride_id for request in accepted_requests}
    return db.query(Conversations).filter(Conversations.ride_id.in_(ride_ids)).order_by(Conversations.created_at).all()


def get_conversation(db: Session, conversation_id: int, user_id: int):
    conversation = db.query(Conversations).filter(Conversations.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    ride = db.query(Rides).filter(Rides.id == conversation.ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.host_id != user_id:
        accepted_request = db.query(RideRequests).filter(RideRequests.ride_id == ride.id, RideRequests.passenger_id == user_id, RideRequests.status == "accepted").first()
        if not accepted_request:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not part of this conversation")
    return conversation


def list_messages(db: Session, conversation_id: int, user_id: int):
    conversation = get_conversation(db, conversation_id, user_id)
    return db.query(Messages).filter(Messages.conversation_id == conversation.id).order_by(Messages.sent_at).all()


def create_message(db: Session, conversation_id: int, sender_id: int, content: str):
    conversation = db.query(Conversations).filter(Conversations.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    ride = db.query(Rides).filter(Rides.id == conversation.ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

    if ride.host_id != sender_id:
        accepted_request = db.query(RideRequests).filter(RideRequests.ride_id == ride.id, RideRequests.passenger_id == sender_id, RideRequests.status == "accepted").first()
        if not accepted_request:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not part of this conversation")

    message = Messages(conversation_id=conversation.id, sender_id=sender_id, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)

    if ride.host_id == sender_id:
        recipient_id = db.query(RideRequests).filter(RideRequests.ride_id == ride.id, RideRequests.status == "accepted").first()
        if recipient_id:
            create_notification(db, recipient_id.passenger_id, "You received a new message")
    else:
        create_notification(db, ride.host_id, "You received a new message")
    return message
