from fastapi import FastAPI

app = FastAPI(title="shopshare")

@app.get("/")
def root():
    return {"message": "Success: API is running"}