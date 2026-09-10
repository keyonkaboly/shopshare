"""Extended coverage for rides, ride requests, trips, ratings, payments,
driver verification, webhooks, and account lifecycle edge cases that
tests/test_backend_api.py's happy-path tests don't reach.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import stripe
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


def register_user(client, username, email, password="password123", **extra):
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
        "terms_accepted": True,
    }
    payload.update(extra)
    response = client.post("/login/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def login_user(client, email, password="password123"):
    response = client.post("/login/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response


def create_ride(client, hours_from_now=2, **overrides):
    ride_time = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat()
    payload = {
        "pickup_location": "Main Campus",
        "destination": "Walmart",
        "departure_time": ride_time,
        "available_seats": 1,
        "price_per_person": 5.0,
    }
    payload.update(overrides)
    response = client.post("/rides/", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Registration / login edge cases
# ---------------------------------------------------------------------------


def test_register_requires_terms_acceptance(client):
    response = client.post(
        "/login/register",
        json={
            "username": "noterms",
            "email": "noterms@example.com",
            "password": "password123",
            "terms_accepted": False,
        },
    )
    assert response.status_code == 400
    assert "Terms" in response.json()["detail"]


def test_register_duplicate_email_rejected(client):
    register_user(client, "dupuser", "dup@example.com")
    response = client.post(
        "/login/register",
        json={
            "username": "dupuser2",
            "email": "dup@example.com",
            "password": "password123",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_login_wrong_email_and_password(client):
    register_user(client, "loginfail", "loginfail@example.com")

    wrong_email = client.post("/login/login", json={"email": "nope@example.com", "password": "password123"})
    assert wrong_email.status_code == 401
    assert wrong_email.json()["detail"] == "Invalid email"

    wrong_password = client.post("/login/login", json={"email": "loginfail@example.com", "password": "wrongpass"})
    assert wrong_password.status_code == 401
    assert wrong_password.json()["detail"] == "Invalid password"


def test_me_requires_authentication(client):
    response = client.get("/login/me")
    assert response.status_code == 401


def test_me_rejects_garbage_token(client):
    client.cookies.set("access_token", "not-a-real-jwt")
    response = client.get("/login/me")
    assert response.status_code == 401


def test_logout_clears_session(client):
    register_user(client, "logoutuser", "logout@example.com")
    login_user(client, "logout@example.com")
    logout_response = client.post("/login/logout")
    assert logout_response.status_code == 200

    profile_response = client.get("/login/me")
    assert profile_response.status_code == 401


def test_update_profile_fields_and_username_conflict(client):
    register_user(client, "profileuser", "profileuser@example.com")
    register_user(client, "otheruser", "otheruser@example.com")
    login_user(client, "profileuser@example.com")

    update_response = client.patch(
        "/login/me",
        json={
            "first_name": "Updated",
            "last_name": "Name",
            "university": "New University",
            "phone_number": "5551234567",
        },
    )
    assert update_response.status_code == 200, update_response.text
    body = update_response.json()
    assert body["first_name"] == "Updated"
    assert body["university"] == "New University"

    me_response = client.get("/login/me")
    assert me_response.json()["university"] == "New University"

    conflict_response = client.patch("/login/me", json={"username": "otheruser"})
    assert conflict_response.status_code == 400
    assert "Username already exists" in conflict_response.json()["detail"]


def test_delete_account_cascades_related_data(client):
    register_user(client, "hostdelete", "hostdelete@example.com")
    register_user(client, "passengerdelete", "passengerdelete@example.com")

    login_user(client, "hostdelete@example.com")
    ride = create_ride(client)
    ride_id = ride["id"]

    client.cookies.clear()
    login_user(client, "passengerdelete@example.com")
    client.post(f"/rides/{ride_id}/join")

    client.cookies.clear()
    login_user(client, "hostdelete@example.com")
    client.post(f"/rides/{ride_id}/requests/1/accept")

    delete_response = client.delete("/login/me")
    assert delete_response.status_code == 200

    # The host is gone, and everything hanging off their ride went with them.
    profile_after_delete = client.get("/login/me")
    assert profile_after_delete.status_code == 401

    client.cookies.clear()
    login_user(client, "passengerdelete@example.com")
    rides_response = client.get("/rides/")
    assert rides_response.status_code == 200
    assert all(r["id"] != ride_id for r in rides_response.json())

    my_requests = client.get("/rides/me/requests")
    assert my_requests.json() == []


# ---------------------------------------------------------------------------
# Rides
# ---------------------------------------------------------------------------


def test_ride_response_includes_host_username(client):
    register_user(client, "hostname", "hostname@example.com")
    login_user(client, "hostname@example.com")
    ride = create_ride(client)
    assert ride["host_username"] == "hostname"

    fetched = client.get(f"/rides/{ride['id']}")
    assert fetched.json()["host_username"] == "hostname"


def test_get_unknown_ride_returns_404(client):
    register_user(client, "someone", "someone@example.com")
    login_user(client, "someone@example.com")
    response = client.get("/rides/999")
    assert response.status_code == 404


def test_list_rides_filters_by_pickup_destination_and_date(client):
    register_user(client, "filteruser", "filteruser@example.com")
    login_user(client, "filteruser@example.com")
    ride = create_ride(client, hours_from_now=5, pickup_location="North Campus", destination="Costco")
    create_ride(client, hours_from_now=6, pickup_location="South Campus", destination="Save-On")

    by_pickup = client.get("/rides/", params={"pickup": "North"})
    assert len(by_pickup.json()) == 1
    assert by_pickup.json()[0]["destination"] == "Costco"

    by_destination = client.get("/rides/", params={"destination": "Save-On"})
    assert len(by_destination.json()) == 1

    ride_date = ride["departure_time"][:10]
    by_date = client.get("/rides/", params={"date": ride_date})
    assert len(by_date.json()) >= 1

    bad_date = client.get("/rides/", params={"date": "not-a-date"})
    assert bad_date.status_code == 400


def test_only_host_can_update_or_delete_ride(client):
    register_user(client, "rideowner", "rideowner@example.com")
    register_user(client, "notowner", "notowner@example.com")

    login_user(client, "rideowner@example.com")
    ride = create_ride(client)

    client.cookies.clear()
    login_user(client, "notowner@example.com")
    patch_response = client.patch(f"/rides/{ride['id']}", json={"status": "cancelled"})
    assert patch_response.status_code == 403

    delete_response = client.delete(f"/rides/{ride['id']}")
    assert delete_response.status_code == 403


def test_host_can_update_and_delete_own_ride(client):
    register_user(client, "rideowner2", "rideowner2@example.com")
    login_user(client, "rideowner2@example.com")
    ride = create_ride(client)

    patch_response = client.patch(f"/rides/{ride['id']}", json={"status": "completed"})
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "completed"

    delete_response = client.delete(f"/rides/{ride['id']}")
    assert delete_response.status_code == 200

    get_response = client.get(f"/rides/{ride['id']}")
    assert get_response.status_code == 404


def test_driver_verification_gate_can_be_enabled(client, monkeypatch):
    monkeypatch.setattr("app.presentation.api.v1.rides.REQUIRE_HOST_VERIFICATION", True)
    register_user(client, "unverifiedhost", "unverifiedhost@example.com")
    login_user(client, "unverifiedhost@example.com")

    response = client.post(
        "/rides/",
        json={
            "pickup_location": "Campus A",
            "destination": "Store B",
            "departure_time": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            "available_seats": 1,
            "price_per_person": 5.0,
        },
    )
    assert response.status_code == 403
    assert "driver verification" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Ride requests
# ---------------------------------------------------------------------------


def test_cannot_request_own_ride(client):
    register_user(client, "selfhost", "selfhost@example.com")
    login_user(client, "selfhost@example.com")
    ride = create_ride(client)

    response = client.post(f"/rides/{ride['id']}/join")
    assert response.status_code == 400
    assert "cannot request your own ride" in response.json()["detail"]


def test_duplicate_request_blocked_but_allowed_after_rejection(client):
    register_user(client, "hostdup", "hostdup@example.com")
    register_user(client, "passengerdup", "passengerdup@example.com")

    login_user(client, "hostdup@example.com")
    ride = create_ride(client, available_seats=2)

    client.cookies.clear()
    login_user(client, "passengerdup@example.com")
    first = client.post(f"/rides/{ride['id']}/join")
    assert first.status_code == 200

    duplicate = client.post(f"/rides/{ride['id']}/join")
    assert duplicate.status_code == 400
    assert "already requested" in duplicate.json()["detail"]

    client.cookies.clear()
    login_user(client, "hostdup@example.com")
    reject = client.post(f"/rides/{ride['id']}/requests/{first.json()['id']}/reject")
    assert reject.status_code == 200
    assert reject.json()["status"] == "rejected"

    client.cookies.clear()
    login_user(client, "passengerdup@example.com")
    retry = client.post(f"/rides/{ride['id']}/join")
    assert retry.status_code == 200, retry.text


def test_join_unknown_ride_returns_404(client):
    register_user(client, "joiner", "joiner@example.com")
    login_user(client, "joiner@example.com")
    response = client.post("/rides/999/join")
    assert response.status_code == 404


def test_only_host_can_list_ride_requests(client):
    register_user(client, "hostlist", "hostlist@example.com")
    register_user(client, "outsider", "outsider@example.com")

    login_user(client, "hostlist@example.com")
    ride = create_ride(client)

    client.cookies.clear()
    login_user(client, "outsider@example.com")
    response = client.get(f"/rides/{ride['id']}/requests")
    assert response.status_code == 403


def test_accept_fails_when_no_seats_left(client):
    register_user(client, "hostseats", "hostseats@example.com")
    register_user(client, "rider1", "rider1@example.com")
    register_user(client, "rider2", "rider2@example.com")

    login_user(client, "hostseats@example.com")
    ride = create_ride(client, available_seats=1)

    client.cookies.clear()
    login_user(client, "rider1@example.com")
    req1 = client.post(f"/rides/{ride['id']}/join").json()

    client.cookies.clear()
    login_user(client, "rider2@example.com")
    req2 = client.post(f"/rides/{ride['id']}/join").json()

    client.cookies.clear()
    login_user(client, "hostseats@example.com")
    accept1 = client.post(f"/rides/{ride['id']}/requests/{req1['id']}/accept")
    assert accept1.status_code == 200

    accept2 = client.post(f"/rides/{ride['id']}/requests/{req2['id']}/accept")
    assert accept2.status_code == 400
    assert "No seats left" in accept2.json()["detail"]


def test_accept_and_reject_require_host(client):
    register_user(client, "hostperm", "hostperm@example.com")
    register_user(client, "passengerperm", "passengerperm@example.com")

    login_user(client, "hostperm@example.com")
    ride = create_ride(client)

    client.cookies.clear()
    login_user(client, "passengerperm@example.com")
    req = client.post(f"/rides/{ride['id']}/join").json()

    accept_by_passenger = client.post(f"/rides/{ride['id']}/requests/{req['id']}/accept")
    assert accept_by_passenger.status_code == 403

    reject_by_passenger = client.post(f"/rides/{ride['id']}/requests/{req['id']}/reject")
    assert reject_by_passenger.status_code == 403


def test_accept_unknown_request_returns_404(client):
    register_user(client, "hostmissing", "hostmissing@example.com")
    login_user(client, "hostmissing@example.com")
    response = client.post("/rides/1/requests/999/accept")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Trips
# ---------------------------------------------------------------------------


def test_trips_include_hosted_and_requested_rides(client):
    register_user(client, "hosttrip", "hosttrip@example.com")
    register_user(client, "passengertrip", "passengertrip@example.com")

    login_user(client, "hosttrip@example.com")
    ride = create_ride(client, hours_from_now=10)

    client.cookies.clear()
    login_user(client, "passengertrip@example.com")
    other_ride_owner_trips = client.get("/trips/")
    assert other_ride_owner_trips.json() == []

    join = client.post(f"/rides/{ride['id']}/join").json()
    trips = client.get("/trips/").json()
    assert len(trips) == 1
    assert trips[0]["role"] == "passenger"
    assert trips[0]["request_status"] == "pending"

    client.cookies.clear()
    login_user(client, "hosttrip@example.com")
    client.post(f"/rides/{ride['id']}/requests/{join['id']}/accept")
    host_trips = client.get("/trips/").json()
    assert len(host_trips) == 1
    assert host_trips[0]["role"] == "host"
    assert host_trips[0]["request_status"] is None

    client.cookies.clear()
    login_user(client, "passengertrip@example.com")
    passenger_trips = client.get("/trips/").json()
    assert passenger_trips[0]["request_status"] == "accepted"
    assert passenger_trips[0]["pickup_location"] == ride["pickup_location"]


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


def test_non_member_cannot_read_or_send_conversation_messages(client):
    register_user(client, "hostconvo", "hostconvo@example.com")
    register_user(client, "outsiderconvo", "outsiderconvo@example.com")

    login_user(client, "hostconvo@example.com")
    create_ride(client)

    conversations = client.get("/conversations/").json()
    conversation_id = conversations[0]["id"]

    client.cookies.clear()
    login_user(client, "outsiderconvo@example.com")
    read_response = client.get(f"/conversations/{conversation_id}")
    assert read_response.status_code == 403

    send_response = client.post(f"/conversations/{conversation_id}/messages", json={"content": "hi"})
    assert send_response.status_code == 403


def test_unknown_conversation_returns_404(client):
    register_user(client, "convouser", "convouser@example.com")
    login_user(client, "convouser@example.com")
    response = client.get("/conversations/999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


def test_mark_read_rejects_other_users_notification(client):
    register_user(client, "notifyowner", "notifyowner@example.com")
    register_user(client, "notifyintruder", "notifyintruder@example.com")

    login_user(client, "notifyowner@example.com")
    create_ride(client)

    client.cookies.clear()
    login_user(client, "notifyintruder@example.com")
    join_target = client.get("/rides/").json()[0]["id"]
    client.post(f"/rides/{join_target}/join")

    client.cookies.clear()
    login_user(client, "notifyowner@example.com")
    my_notifications = client.get("/notifications/").json()
    assert len(my_notifications) >= 1
    notification_id = my_notifications[0]["id"]

    client.cookies.clear()
    login_user(client, "notifyintruder@example.com")
    response = client.post(f"/notifications/{notification_id}/read")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ratings
# ---------------------------------------------------------------------------


def test_rating_requires_participation_in_the_ride(client):
    register_user(client, "hostrating", "hostrating@example.com")
    register_user(client, "randomrater", "randomrater@example.com")

    login_user(client, "hostrating@example.com")
    ride = create_ride(client)

    client.cookies.clear()
    login_user(client, "randomrater@example.com")
    response = client.post(
        f"/rides/{ride['id']}/ratings",
        json={"to_user_id": 1, "rating_score": 5},
    )
    assert response.status_code == 403


def test_rating_target_must_be_host_or_accepted_passenger(client):
    register_user(client, "hostrating2", "hostrating2@example.com")
    register_user(client, "randomtarget", "randomtarget@example.com")

    login_user(client, "hostrating2@example.com")
    ride = create_ride(client)

    outsider = register_user(client, "randomtarget2", "randomtarget2@example.com")

    response = client.post(
        f"/rides/{ride['id']}/ratings",
        json={"to_user_id": outsider["id"], "rating_score": 4},
    )
    assert response.status_code == 400
    assert "must be the host" in response.json()["detail"]


def test_rating_unknown_ride_or_user_returns_404(client):
    register_user(client, "raterunknown", "raterunknown@example.com")
    login_user(client, "raterunknown@example.com")

    unknown_ride = client.post("/rides/999/ratings", json={"to_user_id": 1, "rating_score": 3})
    assert unknown_ride.status_code == 404

    ride = create_ride(client)
    unknown_user = client.post(
        f"/rides/{ride['id']}/ratings", json={"to_user_id": 999, "rating_score": 3}
    )
    assert unknown_user.status_code == 404


# ---------------------------------------------------------------------------
# Payments (Stripe mocked out — no network calls, no real API key needed)
# ---------------------------------------------------------------------------


class _FakeCheckoutSession:
    def __init__(self, session_id="cs_test_123"):
        self.id = session_id
        self.url = f"https://checkout.stripe.com/{session_id}"


def _mock_stripe_checkout(monkeypatch, session_id="cs_test_123"):
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: _FakeCheckoutSession(session_id))
    monkeypatch.setattr("app.application.services.payment_service.stripe_configured", lambda: True)


def _accept_ride_request(client, host_email, passenger_email):
    login_user(client, host_email)
    ride = create_ride(client)

    client.cookies.clear()
    login_user(client, passenger_email)
    req = client.post(f"/rides/{ride['id']}/join").json()

    client.cookies.clear()
    login_user(client, host_email)
    client.post(f"/rides/{ride['id']}/requests/{req['id']}/accept")
    return ride, req


def test_checkout_confirmation_pages(client):
    assert client.get("/payments/checkout/success").status_code == 200
    assert client.get("/payments/checkout/cancel").status_code == 200


def test_checkout_requires_stripe_configuration(client):
    register_user(client, "hostpaycfg", "hostpaycfg@example.com")
    register_user(client, "passengerpaycfg", "passengerpaycfg@example.com")
    ride, req = _accept_ride_request(client, "hostpaycfg@example.com", "passengerpaycfg@example.com")

    client.cookies.clear()
    login_user(client, "passengerpaycfg@example.com")
    response = client.post("/payments/checkout", json={"ride_request_id": req["id"]})
    assert response.status_code == 503


def test_checkout_full_flow(client, monkeypatch):
    _mock_stripe_checkout(monkeypatch)
    register_user(client, "hostpay", "hostpay@example.com")
    register_user(client, "passengerpay", "passengerpay@example.com")
    ride, req = _accept_ride_request(client, "hostpay@example.com", "passengerpay@example.com")

    client.cookies.clear()
    login_user(client, "passengerpay@example.com")

    checkout_response = client.post("/payments/checkout", json={"ride_request_id": req["id"]})
    assert checkout_response.status_code == 200, checkout_response.text
    body = checkout_response.json()
    assert body["checkout_url"] == "https://checkout.stripe.com/cs_test_123"
    assert body["amount_cents"] == int(ride["price_per_person"] * 100)

    status_response = client.get(f"/payments/ride-requests/{req['id']}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "pending"

    # Only the payer or payee may view the payment.
    client.cookies.clear()
    register_user(client, "paymentsnooper", "paymentsnooper@example.com")
    login_user(client, "paymentsnooper@example.com")
    forbidden = client.get(f"/payments/ride-requests/{req['id']}")
    assert forbidden.status_code == 403


def test_checkout_rejects_non_payer_and_unaccepted_request(client, monkeypatch):
    _mock_stripe_checkout(monkeypatch)
    register_user(client, "hostpay2", "hostpay2@example.com")
    register_user(client, "passengerpay2", "passengerpay2@example.com")
    register_user(client, "intruderpay", "intruderpay@example.com")

    login_user(client, "hostpay2@example.com")
    ride = create_ride(client)

    client.cookies.clear()
    login_user(client, "passengerpay2@example.com")
    req = client.post(f"/rides/{ride['id']}/join").json()

    # Not accepted yet.
    not_accepted = client.post("/payments/checkout", json={"ride_request_id": req["id"]})
    assert not_accepted.status_code == 400

    client.cookies.clear()
    login_user(client, "hostpay2@example.com")
    client.post(f"/rides/{ride['id']}/requests/{req['id']}/accept")

    client.cookies.clear()
    login_user(client, "intruderpay@example.com")
    wrong_payer = client.post("/payments/checkout", json={"ride_request_id": req["id"]})
    assert wrong_payer.status_code == 403

    unknown_request = client.post("/payments/checkout", json={"ride_request_id": 999})
    assert unknown_request.status_code == 404


def test_cannot_pay_twice_for_same_request(client, monkeypatch):
    _mock_stripe_checkout(monkeypatch)
    register_user(client, "hostpay3", "hostpay3@example.com")
    register_user(client, "passengerpay3", "passengerpay3@example.com")
    ride, req = _accept_ride_request(client, "hostpay3@example.com", "passengerpay3@example.com")

    client.cookies.clear()
    login_user(client, "passengerpay3@example.com")
    client.post("/payments/checkout", json={"ride_request_id": req["id"]})

    # Simulate Stripe confirming the payment via webhook.
    webhook_response = client.post(
        "/webhooks/stripe",
        json={
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_123", "payment_status": "paid"}},
        },
    )
    assert webhook_response.status_code == 200

    status_response = client.get(f"/payments/ride-requests/{req['id']}")
    assert status_response.json()["status"] == "succeeded"

    second_attempt = client.post("/payments/checkout", json={"ride_request_id": req["id"]})
    assert second_attempt.status_code == 400
    assert "already been paid" in second_attempt.json()["detail"]


def test_payment_status_unknown_request_returns_404(client):
    register_user(client, "paystatususer", "paystatususer@example.com")
    login_user(client, "paystatususer@example.com")
    response = client.get("/payments/ride-requests/999")
    assert response.status_code == 404


def test_webhook_expired_checkout_marks_payment_failed(client, monkeypatch):
    _mock_stripe_checkout(monkeypatch, session_id="cs_failed_1")
    register_user(client, "hostpayfail", "hostpayfail@example.com")
    register_user(client, "passengerpayfail", "passengerpayfail@example.com")
    ride, req = _accept_ride_request(client, "hostpayfail@example.com", "passengerpayfail@example.com")

    client.cookies.clear()
    login_user(client, "passengerpayfail@example.com")
    client.post("/payments/checkout", json={"ride_request_id": req["id"]})

    client.post(
        "/webhooks/stripe",
        json={"type": "checkout.session.expired", "data": {"object": {"id": "cs_failed_1"}}},
    )
    status_response = client.get(f"/payments/ride-requests/{req['id']}")
    assert status_response.json()["status"] == "failed"


def test_webhook_ignores_events_for_unknown_sessions(client):
    # Should not raise even though nothing matches.
    response = client.post(
        "/webhooks/stripe",
        json={
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_does_not_exist", "payment_status": "paid"}},
        },
    )
    assert response.status_code == 200


def test_webhook_rejects_bad_signature_when_secret_configured(client, monkeypatch):
    monkeypatch.setattr("app.presentation.api.v1.webhooks.STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    response = client.post(
        "/webhooks/stripe",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_x"}}},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Driver verification (Stripe Identity mocked out)
# ---------------------------------------------------------------------------


class _FakeVerificationSession:
    def __init__(self, session_id="vs_test_123", url="https://verify.stripe.com/test"):
        self.id = session_id
        self.url = url


def _mock_stripe_identity(monkeypatch, session_id="vs_test_123"):
    monkeypatch.setattr(
        stripe.identity.VerificationSession, "create", lambda **kwargs: _FakeVerificationSession(session_id)
    )
    monkeypatch.setattr("app.application.services.driver_verification_service.stripe_configured", lambda: True)


def test_driver_verification_status_defaults_to_unverified(client):
    register_user(client, "freshdriver", "freshdriver@example.com")
    login_user(client, "freshdriver@example.com")
    response = client.get("/driver-verification/status")
    assert response.status_code == 200
    assert response.json()["status"] == "unverified"


def test_driver_verification_requires_stripe_configuration(client):
    register_user(client, "driverunconfigured", "driverunconfigured@example.com")
    login_user(client, "driverunconfigured@example.com")
    response = client.post("/driver-verification/start", json={"vehicle_make": "Honda"})
    assert response.status_code == 503


def test_driver_verification_start_and_webhook_marks_verified(client, monkeypatch):
    _mock_stripe_identity(monkeypatch)
    register_user(client, "driververify", "driververify@example.com")
    login_user(client, "driververify@example.com")

    start_response = client.post(
        "/driver-verification/start",
        json={
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_color": "Blue",
            "vehicle_plate": "ABC123",
        },
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "pending"
    assert start_response.json()["verification_url"] == "https://verify.stripe.com/test"

    pending_status = client.get("/driver-verification/status")
    assert pending_status.json()["status"] == "pending"
    assert pending_status.json()["vehicle_model"] == "Corolla"

    webhook_response = client.post(
        "/webhooks/stripe",
        json={"type": "identity.verification_session.verified", "data": {"object": {"id": "vs_test_123"}}},
    )
    assert webhook_response.status_code == 200

    verified_status = client.get("/driver-verification/status")
    assert verified_status.json()["status"] == "verified"

    # Starting again once verified is a no-op that reports the existing status.
    restart_response = client.post("/driver-verification/start", json={})
    assert restart_response.json()["status"] == "verified"


def test_driver_verification_rejected_via_webhook(client, monkeypatch):
    _mock_stripe_identity(monkeypatch, session_id="vs_reject_1")
    register_user(client, "driverreject", "driverreject@example.com")
    login_user(client, "driverreject@example.com")
    client.post("/driver-verification/start", json={})

    client.post(
        "/webhooks/stripe",
        json={
            "type": "identity.verification_session.requires_input",
            "data": {"object": {"id": "vs_reject_1"}},
        },
    )
    status_response = client.get("/driver-verification/status")
    assert status_response.json()["status"] == "rejected"


# ---------------------------------------------------------------------------
# Database wiring
# ---------------------------------------------------------------------------


def test_get_db_dependency_yields_and_closes_session():
    generator = database_module.get_db()
    session = next(generator)
    assert session is not None
    with pytest.raises(StopIteration):
        next(generator)
