import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.presentation.api.v1 import (
    conversations,
    driver_verification,
    login,
    notifications,
    payments,
    ratings,
    ride_requests,
    rides,
    trips,
    webhooks,
)
from infrastructure.database.database import Base, engine
from infrastructure.payments.stripe_client import BACKEND_PUBLIC_URL  # noqa: F401  (triggers .env loading)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="shopshare")

# Local dev ports covered out of the box: the old prototype web frontend,
# the shopshare-web static site served locally (python -m http.server /
# VS Code Live Server / common Vite/webpack defaults), and the Android
# emulator's loopback alias. Add your deployed web app's real origin
# (e.g. https://shopshare.vercel.app) via ALLOWED_ORIGINS in backend/.env —
# comma-separated, no spaces — once it's hosted somewhere public; these
# defaults alone won't let a publicly-deployed frontend talk to a publicly
# reachable backend.
_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8123",
    "http://127.0.0.1:8123",
    "http://localhost",
    "http://127.0.0.1",
    "http://10.0.2.2:8000",
]
_extra_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(login.login_router)
app.include_router(rides.ride_router)
app.include_router(ride_requests.ride_request_router)
app.include_router(trips.trip_router)
app.include_router(conversations.conversation_router)
app.include_router(notifications.notification_router)
app.include_router(ratings.rating_router)
app.include_router(payments.payment_router)
app.include_router(driver_verification.driver_verification_router)
app.include_router(webhooks.webhook_router)

@app.get("/")
def root():
    return {"message": "Success: API is running"}