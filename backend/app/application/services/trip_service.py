from sqlalchemy.orm import Session

from infrastructure.database.models import RideRequests, Rides


def list_my_trips(db: Session, user_id: int):
    host_rides = db.query(Rides).filter(Rides.host_id == user_id).all()
    accepted_requests = db.query(RideRequests).filter(RideRequests.passenger_id == user_id, RideRequests.status == "accepted").all()

    trips = []
    for ride in host_rides:
        trips.append({"ride_id": ride.id, "role": "host", "status": ride.status, "destination": ride.destination})
    for request in accepted_requests:
        ride = db.query(Rides).filter(Rides.id == request.ride_id).first()
        if ride:
            trips.append({"ride_id": ride.id, "role": "passenger", "status": ride.status, "destination": ride.destination})
    return trips
