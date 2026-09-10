import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import DriverVerification, User
from infrastructure.payments.stripe_client import stripe_configured


def _get_or_create_record(db: Session, user_id: int) -> DriverVerification:
    record = db.query(DriverVerification).filter(DriverVerification.user_id == user_id).first()
    if not record:
        record = DriverVerification(user_id=user_id)
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def start_verification(db: Session, user: User, vehicle: dict) -> dict:
    if not stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Driver verification is not configured on this server yet. Set STRIPE_SECRET_KEY in backend/.env "
            "and enable Stripe Identity on your Stripe account.",
        )

    record = _get_or_create_record(db, user.id)
    if record.status == "verified":
        return {"status": "verified"}

    session = stripe.identity.VerificationSession.create(
        type="document",
        metadata={"user_id": str(user.id)},
        options={"document": {"require_matching_selfie": True}},
    )

    record.stripe_verification_session_id = session.id
    record.status = "pending"
    record.vehicle_make = vehicle.get("vehicle_make") or record.vehicle_make
    record.vehicle_model = vehicle.get("vehicle_model") or record.vehicle_model
    record.vehicle_color = vehicle.get("vehicle_color") or record.vehicle_color
    record.vehicle_plate = vehicle.get("vehicle_plate") or record.vehicle_plate
    db.commit()
    db.refresh(record)

    return {"status": "pending", "verification_url": session.url}


def get_verification_status(db: Session, user_id: int) -> dict:
    record = db.query(DriverVerification).filter(DriverVerification.user_id == user_id).first()
    if not record:
        return {"status": "unverified", "vehicle_make": None, "vehicle_model": None, "vehicle_color": None, "vehicle_plate": None}
    return {
        "status": record.status,
        "vehicle_make": record.vehicle_make,
        "vehicle_model": record.vehicle_model,
        "vehicle_color": record.vehicle_color,
        "vehicle_plate": record.vehicle_plate,
    }


def is_user_verified(db: Session, user_id: int) -> bool:
    record = db.query(DriverVerification).filter(DriverVerification.user_id == user_id).first()
    return bool(record and record.status == "verified")


def handle_identity_session_event(db: Session, event: dict) -> None:
    session_obj = event["data"]["object"]
    record = db.query(DriverVerification).filter(
        DriverVerification.stripe_verification_session_id == session_obj.get("id")
    ).first()
    if not record:
        return

    event_type = event.get("type", "")
    if event_type == "identity.verification_session.verified":
        record.status = "verified"
    elif event_type in ("identity.verification_session.requires_input", "identity.verification_session.canceled"):
        record.status = "rejected"
    db.commit()
