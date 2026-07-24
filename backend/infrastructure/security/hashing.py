import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from jose import jwt
from passlib.context import CryptContext

ENV_FILES = [
    Path(__file__).resolve().parents[2] / ".env",  # backend/.env
    Path(__file__).resolve().parents[3] / ".env",  # repository root/.env
]
for env_file in ENV_FILES:
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
        break

load_dotenv()  # fallback to the current working directory

SECRET_KEY = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET_KEY") or "dev-secret-key"

ALGORITHM = "HS256"
# Minutes till your access token expires.
ACCESS_TOKEN_EXPIRY_DURATION = 60 * 24 * 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRY_DURATION))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)