import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("SECRET_KEY", "test-secret")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from infrastructure.database.database import Base
from infrastructure.database import database as database_module
from main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[database_module.get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register_user(client, username, email, password="password123"):
    payload = {
        "username": username,
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "User",
        "university": "Test Uni",
        "phone_number": "123456789",
        "is_verified_student": True,
        "profile_photo_url": "avatar.png",
    }
    response = client.post("/login/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def login_user(client, email, password="password123"):
    response = client.post(
        "/login/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response


def test_register_login_and_profile(client):
    user = register_user(client, "hostuser", "host@example.com")
    assert user["username"] == "hostuser"

    login_response = login_user(client, "host@example.com")
    assert login_response.json()["message"] == "Login successful"

    profile_response = client.get("/login/me")
    assert profile_response.status_code == 200
    profile_data = profile_response.json()
    assert profile_data["email"] == "host@example.com"
    assert profile_data["username"] == "hostuser"


def test_create_and_list_rides(client):
    register_user(client, "hostride", "hostride@example.com")
    login_user(client, "hostride@example.com")

    ride_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    ride_payload = {
        "pickup_location": "Main Campus",
        "destination": "Walmart",
        "departure_time": ride_time,
        "available_seats": 2,
        "price_per_person": 5.5,
    }

    create_response = client.post("/rides/", json=ride_payload)
    assert create_response.status_code == 200, create_response.text
    ride = create_response.json()
    assert ride["destination"] == "Walmart"

    list_response = client.get("/rides/")
    assert list_response.status_code == 200
    listed_rides = list_response.json()
    assert len(listed_rides) == 1
    assert listed_rides[0]["destination"] == "Walmart"


def test_join_request_accept_and_notifications(client):
    register_user(client, "hostreq", "hostreq@example.com")
    register_user(client, "passengerreq", "passengerreq@example.com")

    login_user(client, "hostreq@example.com")
    ride_time = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    ride_response = client.post(
        "/rides/",
        json={
            "pickup_location": "Library",
            "destination": "Target",
            "departure_time": ride_time,
            "available_seats": 1,
            "price_per_person": 3.0,
        },
    )
    ride_id = ride_response.json()["id"]

    client.cookies.clear()
    login_user(client, "passengerreq@example.com")
    join_response = client.post(f"/rides/{ride_id}/join")
    assert join_response.status_code == 200, join_response.text
    request_data = join_response.json()
    assert request_data["status"] == "pending"

    client.cookies.clear()
    login_user(client, "hostreq@example.com")
    requests_response = client.get(f"/rides/{ride_id}/requests")
    assert requests_response.status_code == 200
    assert len(requests_response.json()) == 1

    accept_response = client.post(f"/rides/{ride_id}/requests/1/accept")
    assert accept_response.status_code == 200, accept_response.text
    assert accept_response.json()["status"] == "accepted"

    client.cookies.clear()
    login_user(client, "passengerreq@example.com")
    notifications_response = client.get("/notifications/")
    assert notifications_response.status_code == 200
    assert len(notifications_response.json()) >= 1


def test_conversations_and_messages(client):
    register_user(client, "hostchat", "hostchat@example.com")
    register_user(client, "passengerchat", "passengerchat@example.com")

    login_user(client, "hostchat@example.com")
    ride_time = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    ride_response = client.post(
        "/rides/",
        json={
            "pickup_location": "Dorm",
            "destination": "Grocery Store",
            "departure_time": ride_time,
            "available_seats": 2,
            "price_per_person": 2.0,
        },
    )
    ride_id = ride_response.json()["id"]

    client.cookies.clear()
    login_user(client, "passengerchat@example.com")
    client.post(f"/rides/{ride_id}/join")

    client.cookies.clear()
    login_user(client, "hostchat@example.com")
    client.post(f"/rides/{ride_id}/requests/1/accept")

    conversations_response = client.get("/conversations/")
    assert conversations_response.status_code == 200
    conversation_list = conversations_response.json()
    assert len(conversation_list) >= 1

    conversation_id = conversation_list[0]["id"]
    message_response = client.post(
        f"/conversations/{conversation_id}/messages",
        json={"content": "I’ll meet you at the entrance."},
    )
    assert message_response.status_code == 200, message_response.text
    assert message_response.json()["content"] == "I’ll meet you at the entrance."


def test_ratings_flow(client):
    register_user(client, "hostrate", "hostrate@example.com")
    register_user(client, "passengerrate", "passengerrate@example.com")

    login_user(client, "hostrate@example.com")
    ride_time = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    ride_response = client.post(
        "/rides/",
        json={
            "pickup_location": "Campus",
            "destination": "Trader Joe's",
            "departure_time": ride_time,
            "available_seats": 1,
            "price_per_person": 4.0,
        },
    )
    ride_id = ride_response.json()["id"]

    client.cookies.clear()
    login_user(client, "passengerrate@example.com")
    client.post(f"/rides/{ride_id}/join")

    client.cookies.clear()
    login_user(client, "hostrate@example.com")
    client.post(f"/rides/{ride_id}/requests/1/accept")

    client.cookies.clear()
    login_user(client, "passengerrate@example.com")
    rating_response = client.post(
        f"/rides/{ride_id}/ratings",
        json={"to_user_id": 1, "rating_score": 5, "comment": "Great host"},
    )
    assert rating_response.status_code == 200, rating_response.text
    assert rating_response.json()["rating_score"] == 5

    ratings_response = client.get("/users/1/ratings")
    assert ratings_response.status_code == 200
    assert len(ratings_response.json()) == 1


def test_login_cookie_persists_for_device_login(client):
    register_user(client, "deviceuser", "device@example.com")

    login_response = login_user(client, "device@example.com")
    set_cookie_header = login_response.headers.get("set-cookie", "")

    assert "access_token=" in set_cookie_header
    assert "Max-Age=2592000" in set_cookie_header


def test_rider_can_see_accepted_request_status(client):
    register_user(client, "hoststatus", "hoststatus@example.com")
    register_user(client, "riderstatus", "riderstatus@example.com")

    login_user(client, "hoststatus@example.com")
    ride_time = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
    ride_response = client.post(
        "/rides/",
        json={
            "pickup_location": "Dorm",
            "destination": "Costco",
            "departure_time": ride_time,
            "available_seats": 1,
            "price_per_person": 6.0,
        },
    )
    ride_id = ride_response.json()["id"]

    client.cookies.clear()
    login_user(client, "riderstatus@example.com")
    client.post(f"/rides/{ride_id}/join")

    client.cookies.clear()
    login_user(client, "hoststatus@example.com")
    client.post(f"/rides/{ride_id}/requests/1/accept")

    client.cookies.clear()
    login_user(client, "riderstatus@example.com")
    response = client.get("/rides/me/requests")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["status"] == "accepted"
    assert payload[0]["ride"]["destination"] == "Costco"
