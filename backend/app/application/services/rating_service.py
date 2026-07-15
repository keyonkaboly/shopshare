from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import RideRatings, RideRequests, Rides, User


def create_rating(db: Session, from_user_id: int, payload) -> RideRatings:
    ride = db.query(Rides).filter(Rides.id == payload.ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

    target_user = db.query(User).filter(User.id == payload.to_user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if ride.host_id != from_user_id:
        accepted_request = db.query(RideRequests).filter(
            RideRequests.ride_id == ride.id,
            RideRequests.passenger_id == from_user_id,
            RideRequests.status == "accepted",
        ).first()
        if not accepted_request:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not allowed to rate this ride")

    if payload.to_user_id not in {ride.host_id}:
        accepted_request = db.query(RideRequests).filter(
            RideRequests.ride_id == ride.id,
            RideRequests.passenger_id == payload.to_user_id,
            RideRequests.status == "accepted",
        ).first()
        if not accepted_request:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user must be the host or an accepted passenger")

    rating = RideRatings(
        ride_id=payload.ride_id,
        from_user_id=from_user_id,
        to_user_id=payload.to_user_id,
        rating_score=payload.rating_score,
        comment=payload.comment,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def list_ratings_for_user(db: Session, user_id: int):
    return db.query(RideRatings).filter(RideRatings.to_user_id == user_id).order_by(RideRatings.created_at.desc()).all()
