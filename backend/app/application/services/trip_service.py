from sqlalchemy.orm import Session

from infrastructure.database.models import RideRequests, Rides


def _ride_summary(ride: Rides) -> dict:
    return {
        "ride_id": ride.id,
        "host_id": ride.host_id,
        "pickup_location": ride.pickup_location,
        "destination": ride.destination,
        "departure_time": ride.departure_time,
        "price_per_person": ride.price_per_person,
        "ride_status": ride.status,
    }


def list_my_trips(db: Session, user_id: int):
    host_rides = db.query(Rides).filter(Rides.host_id == user_id).all()
    my_requests = db.query(RideRequests).filter(
        RideRequests.passenger_id == user_id,
        RideRequests.status.in_(["pending", "accepted"]),
    ).all()

    trips = []
    for ride in host_rides:
        trips.append({**_ride_summary(ride), "role": "host", "request_status": None})
    for request in my_requests:
        ride = db.query(Rides).filter(Rides.id == request.ride_id).first()
        if ride:
            trips.append({**_ride_summary(ride), "role": "passenger", "request_status": request.status})
    trips.sort(key=lambda t: t["departure_time"], reverse=True)
    return trips
