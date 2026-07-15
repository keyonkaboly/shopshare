from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable = False)
    last_name = Column(String, nullable = False)
    university = Column(String, nullable = False)
    phone_number = Column(String, nullable = False)
    is_verified_student = Column(Integer, nullable = True)
    profile_photo_url = Column(String, unique=True, nullable=False)
    rating = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class RideOptions(Base):
    __tablename__ = "ride_options"
    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pickup_location = Column(String, nullable = False)
    destination = Column(String, nullable = False)
    departure_time = Column(DateTime, nullable = False)
    available_seats = Column(Integer, nullable=False)
    price_per_person = Column(Float, nullable=False, default=5.0)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Booking(Base):
    __tablename__ = "bookings"
    id = Column(Integer, primary_key=True, index = True)
    user_id = Column(Integer, ForeignKey("users.id"))
    ride_id = Column(Integer, ForeignKey("ride_options.id"))
    status = Column(String, default="pending")