from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CheckoutSessionRequest(BaseModel):
    ride_request_id: int


class CheckoutSessionResponse(BaseModel):
    payment_id: int
    checkout_url: str
    amount_cents: int
    currency: str


class PaymentStatusResponse(BaseModel):
    id: int
    ride_id: int
    ride_request_id: int
    payer_id: int
    payee_id: int
    amount_cents: int
    currency: str
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
