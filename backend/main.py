from fastapi import FastAPI

from app.presentation.api.v1 import (
    conversations,
    login,
    notifications,
    ratings,
    ride_requests,
    rides,
    trips,
)
from infrastructure.database.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="shopshare")

app.include_router(login.login_router)
app.include_router(rides.ride_router)
app.include_router(ride_requests.ride_request_router)
app.include_router(trips.trip_router)
app.include_router(conversations.conversation_router)
app.include_router(notifications.notification_router)
app.include_router(ratings.rating_router)

@app.get("/")
def root():
    return {"message": "Success: API is running"}