from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import Conversations, RideRequests, Rides


def create_ride(db: Session, host_id: int, ride_data) -> Rides:
    ride = Rides(
        host_id=host_id,
        pickup_location=ride_data.pickup_location,
        destination=ride_data.destination,
        departure_time=ride_data.departure_time,
        available_seats=ride_data.available_seats,
        price_per_person=ride_data.price_per_person,
        status=ride_data.status or "open",
    )
    db.add(ride)
    db.commit()
    db.refresh(ride)

    conversation = Conversations(ride_id=ride.id, created_at=datetime.now(timezone.utc))
    db.add(conversation)
    db.commit()
    return ride


def list_rides(db: Session, pickup: str | None = None, destination: str | None = None, date: str | None = None):
    query = db.query(Rides)
    if pickup:
        query = query.filter(Rides.pickup_location.ilike(f"%{pickup}%"))
    if destination:
        query = query.filter(Rides.destination.ilike(f"%{destination}%"))
    if date:
        try:
            target_day = datetime.fromisoformat(date)
            query = query.filter(Rides.departure_time >= target_day, Rides.departure_time < target_day.replace(hour=23, minute=59, second=59))
        except ValueError:
            raise HTTPException(status_code=400, detail="date must be ISO-8601")
    return query.order_by(Rides.departure_time).all()


def get_ride(db: Session, ride_id: int) -> Rides:
    ride = db.query(Rides).filter(Rides.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")
    return ride


def update_ride(db: Session, ride_id: int, host_id: int, ride_update) -> Rides:
    ride = get_ride(db, ride_id)
    if ride.host_id != host_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can update this ride")

    for field, value in ride_update.model_dump(exclude_unset=True).items():
        setattr(ride, field, value)

    db.commit()
    db.refresh(ride)
    return ride


def delete_ride(db: Session, ride_id: int, host_id: int) -> None:
    ride = get_ride(db, ride_id)
    if ride.host_id != host_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the host can delete this ride")

    db.query(RideRequests).filter(RideRequests.ride_id == ride_id).delete(synchronize_session=False)
    db.query(Conversations).filter(Conversations.ride_id == ride_id).delete(synchronize_session=False)
    db.delete(ride)
    db.commit()
