import json

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.application.services.driver_verification_service import handle_identity_session_event
from app.application.services.payment_service import handle_checkout_session_event
from infrastructure.database.database import get_db
from infrastructure.payments.stripe_client import STRIPE_WEBHOOK_SECRET

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@webhook_router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Stripe webhook signature")
    else:
        # No webhook secret configured yet (local dev). Trust the payload as-is;
        # set STRIPE_WEBHOOK_SECRET in backend/.env before going to production.
        try:
            event = json.loads(payload)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    event_type = event.get("type", "")
    if event_type.startswith("checkout.session."):
        handle_checkout_session_event(db, event)
    elif event_type.startswith("identity.verification_session."):
        handle_identity_session_event(db, event)

    return {"received": True}
