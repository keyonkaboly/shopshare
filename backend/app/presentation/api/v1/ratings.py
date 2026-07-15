from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.services.login_service import get_current_user
from app.application.services.rating_service import create_rating, list_ratings_for_user
from app.presentation.api.schemas.rating_schemas import RatingCreate, RatingResponse
from infrastructure.database.database import get_db
from infrastructure.database.models import User

rating_router = APIRouter(prefix="", tags=["ratings"])


@rating_router.post("/rides/{ride_id}/ratings", response_model=RatingResponse)
def submit_rating(
    ride_id: int,
    payload: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rating_payload = RatingCreate(
        ride_id=ride_id,
        to_user_id=payload.to_user_id,
        rating_score=payload.rating_score,
        comment=payload.comment,
    )
    return create_rating(db, current_user.id, rating_payload)


@rating_router.get("/users/{user_id}/ratings", response_model=list[RatingResponse])
def get_ratings_for_user(user_id: int, db: Session = Depends(get_db)):
    return list_ratings_for_user(db, user_id)
