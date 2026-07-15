from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.login_service import get_current_user
from app.application.services.trip_service import list_my_trips
from infrastructure.database.database import get_db
from infrastructure.database.models import User

trip_router = APIRouter(prefix="/trips", tags=["trips"])


@trip_router.get("/")
def get_my_trips(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_my_trips(db, current_user.id)

