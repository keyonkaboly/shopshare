from fastapi import FastAPI

from app.presentation.api.v1 import login
from infrastructure.database.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="shopshare")

app.include_router(login.login_router)

@app.get("/")
def root():
    return {"message": "Success: API is running"}