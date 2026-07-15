from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.services.login_service import get_current_user
from app.presentation.api.schemas.user_schemas import UserCreate, UserLogin, UserUpdate
from infrastructure.database.database import get_db
from infrastructure.database.models import User
from infrastructure.security.hashing import (
    ACCESS_TOKEN_EXPIRY_DURATION,
    create_access_token,
    hash_password,
    verify_password,
)

login_router = APIRouter(prefix="/login", tags=["login"])


@login_router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = hash_password(user.password)

    profile_photo_url = user.profile_photo_url or f"{user.username}.png"

    new_user = User(
        username=user.username,
        email=user.email,
        password_hash=hashed_password,
        first_name=getattr(user, "first_name", "") or "",
        last_name=getattr(user, "last_name", "") or "",
        university=getattr(user, "university", "") or "",
        phone_number=getattr(user, "phone_number", "") or "",
        is_verified_student=int(getattr(user, "is_verified_student", False) or False),
        profile_photo_url=profile_photo_url,
        rating=getattr(user, "rating", 0.0) or 0.0,
    )

    db.add(new_user)

    try:
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email or username already exists")

    return {
        "id": new_user.id,
        "username": new_user.username,
        "email": new_user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "university": user.university,
        "phone_number": user.phone_number,
    }


def authenticate_user(
    user_credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == user_credentials.email).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email")

    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRY_DURATION),
    )

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRY_DURATION * 60,
        path="/",
    )

    return {"message": "Login successful"}


@login_router.post("/login")
def login(
    user_credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    return authenticate_user(user_credentials, response, db)


@login_router.post("/actual_login", include_in_schema=False)
def actual_login(
    user_credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    return authenticate_user(user_credentials, response, db)


@login_router.get("/me")
def read_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "university": current_user.university,
        "phone_number": current_user.phone_number,
        "is_verified_student": current_user.is_verified_student,
        "profile_photo_url": current_user.profile_photo_url,
        "rating": current_user.rating,
    }


@login_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logged out successfully"}

@login_router.get("/profile")
def read_profile_alias(current_user: User = Depends(get_current_user)):
    return read_profile(current_user)


# We won't allow for email changes just for added security. Only emails and passwords.
@login_router.patch("/me")
def update_me(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_update.username and user_update.username != current_user.username:
        existing_username = db.query(User).filter(User.username == user_update.username).first()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already exists")
        current_user.username = user_update.username

    if user_update.password:
        current_user.password_hash = hash_password(user_update.password)

    db.commit()
    db.refresh(current_user)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "message": "Account updated successfuly",
    }


@login_router.patch("/profile")
def update_profile_alias(
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_me(user_update, db, current_user)


# May need to add to later... like deleeting all related is this doing that
@login_router.delete("/me")
def delete_profile(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    
    db.delete(current_user)
    db.commit()

    response.delete_cookie(key="access_token", path="/")
    return {"message": "Account and all related data deleted successfully"}


@login_router.delete("/profile")
def delete_profile_alias(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_profile(response, db, current_user)