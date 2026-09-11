from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.application.services.driver_verification_service import is_user_verified
from app.application.services.login_service import get_current_user
from app.application.services.ride_request_service import create_request
from app.application.services.ride_service import create_ride, delete_ride, get_ride, list_rides, update_ride
from app.presentation.api.schemas.ride_request_schemas import RideRequestResponse
from app.presentation.api.schemas.rides_schemas import RidesCreate, RidesResponse, RidesUpdate
from infrastructure.database.database import get_db
from infrastructure.database.models import User
from infrastructure.payments.stripe_client import REQUIRE_HOST_VERIFICATION

ride_router = APIRouter(prefix="/rides", tags=["rides"])


@ride_router.post("/", response_model=RidesResponse)
def create_new_ride(
    ride_data: RidesCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if REQUIRE_HOST_VERIFICATION and not is_user_verified(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must complete driver verification before posting a ride",
        )
    return create_ride(db, current_user.id, ride_data)


@ride_router.get("/", response_model=list[RidesResponse])
def get_all_rides(
    pickup: str | None = Query(default=None),
    destination: str | None = Query(default=None),
    date: str | None = Query(default=None),
    university: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_rides(db, pickup=pickup, destination=destination, date=date, university=university)


@ride_router.get("/{ride_id}", response_model=RidesResponse)
def get_single_ride(ride_id: int, db: Session = Depends(get_db)):
    return get_ride(db, ride_id)


@ride_router.patch("/{ride_id}", response_model=RidesResponse)
def patch_ride(
    ride_id: int,
    ride_update: RidesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_ride(db, ride_id, current_user.id, ride_update)


@ride_router.delete("/{ride_id}")
def remove_ride(ride_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    delete_ride(db, ride_id, current_user.id)
    return {"message": "Ride deleted successfully"}


@ride_router.post("/{ride_id}/join", response_model=RideRequestResponse)
def join_ride(
    ride_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_request(db, ride_id, current_user.id)


