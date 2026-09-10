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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="shopshare")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ],
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