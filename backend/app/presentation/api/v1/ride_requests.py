from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.login_service import get_current_user
from app.application.services.ride_request_service import accept_request, list_requests_for_ride, list_requests_for_user, reject_request
from app.presentation.api.schemas.ride_request_schemas import RideRequestResponse, RideRequestWithRideResponse
from infrastructure.database.database import get_db
from infrastructure.database.models import User

ride_request_router = APIRouter(prefix="/rides", tags=["ride-requests"])


@ride_request_router.get("/me/requests", response_model=list[RideRequestWithRideResponse])
def get_my_ride_requests(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_requests_for_user(db, current_user.id)


@ride_request_router.get("/{ride_id}/requests", response_model=list[RideRequestResponse])
def get_ride_requests(ride_id: int, db: Session = Depends(get_db)):
    return list_requests_for_ride(db, ride_id)


@ride_request_router.post("/{ride_id}/requests/{request_id}/accept", response_model=RideRequestResponse)
def accept_ride_request(
    ride_id: int,
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return accept_request(db, request_id, current_user.id)


@ride_request_router.post("/{ride_id}/requests/{request_id}/reject", response_model=RideRequestResponse)
def reject_ride_request(
    ride_id: int,
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return reject_request(db, request_id, current_user.id)



