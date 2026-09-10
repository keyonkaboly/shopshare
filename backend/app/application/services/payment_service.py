import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from infrastructure.database.models import Payments, RideRequests, Rides
from infrastructure.payments.stripe_client import BACKEND_PUBLIC_URL, stripe_configured

# Payments use Stripe Checkout: the passenger is redirected to a Stripe-hosted
# payment page in the browser rather than a native in-app card form. This
# needs only STRIPE_SECRET_KEY server-side and a plain HTTPS redirect on the
# client, so it works from any platform (including Flutter via url_launcher)
# without bundling a native Stripe SDK.


def create_checkout_session(db: Session, ride_request_id: int, payer_id: int) -> dict:
    request = db.query(RideRequests).filter(RideRequests.id == ride_request_id).first()
    if not request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride request not found")
    if request.passenger_id != payer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the passenger can pay for this request")
    if request.status != "accepted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This request must be accepted by the host before paying")

    ride = db.query(Rides).filter(Rides.id == request.ride_id).first()
    if not ride:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ride not found")

    payment = db.query(Payments).filter(Payments.ride_request_id == ride_request_id).first()
    if payment and payment.status == "succeeded":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This ride has already been paid for")

    if not stripe_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not configured on this server yet. Set STRIPE_SECRET_KEY in backend/.env.",
        )

    amount_cents = max(int(round(ride.price_per_person * 100)), 50)  # Stripe minimum charge

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "unit_amount": amount_cents,
                "product_data": {"name": f"ShopShare ride to {ride.destination}"},
            },
            "quantity": 1,
        }],
        success_url=f"{BACKEND_PUBLIC_URL}/payments/checkout/success",
        cancel_url=f"{BACKEND_PUBLIC_URL}/payments/checkout/cancel",
        metadata={
            "ride_id": str(ride.id),
            "ride_request_id": str(ride_request_id),
            "payer_id": str(payer_id),
            "payee_id": str(ride.host_id),
        },
    )

    if payment:
        payment.stripe_payment_intent_id = session.id
        payment.amount_cents = amount_cents
        payment.status = "pending"
    else:
        payment = Payments(
            ride_id=ride.id,
            ride_request_id=ride_request_id,
            payer_id=payer_id,
            payee_id=ride.host_id,
            amount_cents=amount_cents,
            currency="usd",
            stripe_payment_intent_id=session.id,
            status="pending",
        )
        db.add(payment)
    db.commit()
    db.refresh(payment)

    return {
        "payment_id": payment.id,
        "checkout_url": session.url,
        "amount_cents": amount_cents,
        "currency": "usd",
    }


def get_payment_for_request(db: Session, ride_request_id: int, user_id: int) -> Payments:
    payment = db.query(Payments).filter(Payments.ride_request_id == ride_request_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No payment found for this ride request")
    if user_id not in (payment.payer_id, payment.payee_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this payment")
    return payment


def handle_checkout_session_event(db: Session, event: dict) -> None:
    session_obj = event["data"]["object"]
    payment = db.query(Payments).filter(Payments.stripe_payment_intent_id == session_obj.get("id")).first()
    if not payment:
        return

    event_type = event.get("type", "")
    if event_type == "checkout.session.completed" and session_obj.get("payment_status") == "paid":
        payment.status = "succeeded"
    elif event_type in ("checkout.session.expired",):
        payment.status = "failed"
    db.commit()
