from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import RideRequests, Rides

from .notification_service import create_notification


def create_request(db: Session, ride_id: int, passenger_id: int, message: str | None = None) -> RideRequests:
    ride = db.query(Rides).filter(Rides.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    if ride.host_id == passenger_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot request your own ride")

    existing = db.query(RideRequests).filter(RideRequests.ride_id == ride_id, RideRequests.passenger_id == passenger_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already requested this ride")

    request = RideRequests(ride_id=ride_id, passenger_id=passenger_id, status="pending")
    db.add(request)
    db.commit()
    db.refresh(request)

    create_notification(db, ride.host_id, f"New ride request for {ride.destination}")
    return request


def list_requests_for_ride(db: Session, ride_id: int):
    ride = db.query(Rides).filter(Rides.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return db.query(RideRequests).filter(RideRequests.ride_id == ride_id).order_by(RideRequests.created_at).all()


def accept_request(db: Session, request_id: int, host_id: int) -> RideRequests:
    request = db.query(RideRequests).filter(RideRequests.id == request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride request not found")

    ride = db.query(Rides).filter(Rides.id == request.ride_id).first()
    if ride.host_id != host_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can accept this request")
    if ride.available_seats <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No seats left")

    request.status = "accepted"
    ride.available_seats -= 1
    db.commit()
    db.refresh(request)
    create_notification(db, request.passenger_id, f"Your ride request for {ride.destination} was accepted")
    return request


def reject_request(db: Session, request_id: int, host_id: int) -> RideRequests:
    request = db.query(RideRequests).filter(RideRequests.id == request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride request not found")

    ride = db.query(Rides).filter(Rides.id == request.ride_id).first()
    if ride.host_id != host_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can reject this request")

    request.status = "rejected"
    db.commit()
    db.refresh(request)
    create_notification(db, request.passenger_id, f"Your ride request for {ride.destination} was rejected")
    return request
