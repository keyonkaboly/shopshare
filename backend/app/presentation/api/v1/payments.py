from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.application.services.login_service import get_current_user
from app.application.services.payment_service import create_checkout_session, get_payment_for_request
from app.presentation.api.schemas.payment_schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    PaymentStatusResponse,
)
from infrastructure.database.database import get_db
from infrastructure.database.models import User

payment_router = APIRouter(prefix="/payments", tags=["payments"])

_CONFIRMATION_PAGE = """
<!DOCTYPE html>
<html>
  <head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ShopShare Payment</title>
    <style>
      body {{ font-family: -apple-system, sans-serif; text-align: center; padding: 48px 24px; }}
      h1 {{ font-size: 22px; }}
      p {{ color: #555; }}
    </style>
  </head>
  <body>
    <h1>{heading}</h1>
    <p>{message}</p>
    <p>You can close this window and return to the ShopShare app.</p>
  </body>
</html>
"""


@payment_router.post("/checkout", response_model=CheckoutSessionResponse)
def create_checkout(
    payload: CheckoutSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_checkout_session(db, payload.ride_request_id, current_user.id)


@payment_router.get("/ride-requests/{ride_request_id}", response_model=PaymentStatusResponse)
def get_payment_status(
    ride_request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_payment_for_request(db, ride_request_id, current_user.id)


@payment_router.get("/checkout/success", response_class=HTMLResponse, include_in_schema=False)
def checkout_success():
    return _CONFIRMATION_PAGE.format(heading="Payment received", message="Thanks — your host has been paid.")


@payment_router.get("/checkout/cancel", response_class=HTMLResponse, include_in_schema=False)
def checkout_cancel():
    return _CONFIRMATION_PAGE.format(heading="Payment cancelled", message="No charge was made.")
