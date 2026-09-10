import os
from pathlib import Path

import stripe
from dotenv import load_dotenv

# Same .env discovery pattern as infrastructure/security/hashing.py, so a
# single backend/.env (or repo-root .env) covers both JWT and Stripe secrets.
ENV_FILES = [
    Path(__file__).resolve().parents[2] / ".env",  # backend/.env
    Path(__file__).resolve().parents[3] / ".env",  # repository root/.env
]
for env_file in ENV_FILES:
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
        break

load_dotenv()  # fallback to the current working directory

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Publicly reachable base URL for this backend, used for Stripe Checkout's
# success/cancel redirect pages. Defaults to the Android emulator's loopback
# alias; set this in .env to your real deployed URL (e.g. via ngrok or your
# production host) once you're testing on a physical device or going live.
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://10.0.2.2:8000")

# Whether posting a new ride requires a "verified" DriverVerification record.
# Defaults to off so the app stays fully testable before you've enabled
# Stripe Identity on your account. Flip to "true" in .env once you're ready
# to require host verification in production.
REQUIRE_HOST_VERIFICATION = os.getenv("REQUIRE_HOST_VERIFICATION", "false").lower() == "true"

stripe.api_key = STRIPE_SECRET_KEY


def stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY)
