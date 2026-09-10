from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.application.services.driver_verification_service import get_verification_status, start_verification
from app.application.services.login_service import get_current_user
from infrastructure.database.database import get_db
from infrastructure.database.models import User

driver_verification_router = APIRouter(prefix="/driver-verification", tags=["driver-verification"])


class VehicleInfo(BaseModel):
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    vehicle_color: str | None = None
    vehicle_plate: str | None = None


@driver_verification_router.post("/start")
def start(
    vehicle: VehicleInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return start_verification(db, current_user, vehicle.model_dump())


@driver_verification_router.get("/status")
def status_endpoint(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_verification_status(db, current_user.id)
