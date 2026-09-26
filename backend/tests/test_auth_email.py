"""Tests for email verification and password reset (OTP-based)."""

from unittest.mock import patch

import models
from auth_security import create_access_token, hash_password, verify_password
from services.email_tokens import create_otp

# db_session and client fixtures come from conftest.py (Postgres).


def _auth_headers(user: models.User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@patch("routers.auth.send_verification_email", return_value=True)
def test_register_sets_unverified_and_sends_email(mock_send, client, db_session):
    response = client.post(
        "/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email_verified"] is False
    mock_send.assert_called_once()
    user = db_session.query(models.User).filter(models.User.email == "new@example.com").first()
    assert user is not None
    assert user.email_verified is False


@patch("routers.auth.send_password_reset_email", return_value=True)
def test_forgot_password_sends_for_password_user(mock_send, client, db_session):
    user = models.User(
        email="reset@example.com",
        password=hash_password("oldpassword1"),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/forgot-password",
        json={"email": user.email},
    )
    assert response.status_code == 200
    mock_send.assert_called_once()


def test_forgot_password_generic_for_unknown_email(client):
    response = client.post(
        "/auth/forgot-password",
        json={"email": "missing@example.com"},
    )
    assert response.status_code == 200
    assert "account exists" in response.json()["message"].lower()


def test_reset_password_updates_hash(client, db_session):
    user = models.User(
        email="reset2@example.com",
        password=hash_password("oldpassword1"),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    code = create_otp(db_session, user.id, models.AuthTokenPurpose.PASSWORD_RESET)

    response = client.post(
        "/auth/reset-password",
        json={"email": user.email, "code": code, "password": "newpassword99"},
    )
    assert response.status_code == 200
    db_session.refresh(user)
    assert verify_password("newpassword99", user.password)


def test_reset_password_rejects_wrong_code(client, db_session):
    user = models.User(
        email="reset3@example.com",
        password=hash_password("oldpassword1"),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    create_otp(db_session, user.id, models.AuthTokenPurpose.PASSWORD_RESET)

    response = client.post(
        "/auth/reset-password",
        json={"email": user.email, "code": "000000", "password": "newpassword99"},
    )
    assert response.status_code == 400
    db_session.refresh(user)
    assert verify_password("oldpassword1", user.password)


def test_reset_password_locks_out_after_max_attempts(client, db_session):
    user = models.User(
        email="reset4@example.com",
        password=hash_password("oldpassword1"),
        email_verified=True,
    )
    db_session.add(user)
    db_session.commit()
    code = create_otp(db_session, user.id, models.AuthTokenPurpose.PASSWORD_RESET)

    for _ in range(5):
        response = client.post(
            "/auth/reset-password",
            json={"email": user.email, "code": "111111", "password": "newpassword99"},
        )
        assert response.status_code == 400

    # Even the correct code no longer works once the code is locked out.
    response = client.post(
        "/auth/reset-password",
        json={"email": user.email, "code": code, "password": "newpassword99"},
    )
    assert response.status_code == 400
    db_session.refresh(user)
    assert verify_password("oldpassword1", user.password)


def test_verify_email_marks_user_verified(client, db_session):
    user = models.User(
        email="verify@example.com",
        password=hash_password("password123"),
        email_verified=False,
    )
    db_session.add(user)
    db_session.commit()
    code = create_otp(db_session, user.id, models.AuthTokenPurpose.EMAIL_VERIFY)

    response = client.post(
        "/auth/verify-email",
        json={"code": code},
        headers=_auth_headers(user),
    )
    assert response.status_code == 200
    db_session.refresh(user)
    assert user.email_verified is True
    assert user.email_verified_at is not None


def test_verify_email_requires_auth(client, db_session):
    user = models.User(
        email="verify2@example.com",
        password=hash_password("password123"),
        email_verified=False,
    )
    db_session.add(user)
    db_session.commit()
    code = create_otp(db_session, user.id, models.AuthTokenPurpose.EMAIL_VERIFY)

    response = client.post("/auth/verify-email", json={"code": code})
    assert response.status_code == 401


def test_otp_codes_are_scoped_per_user(client, db_session):
    """Two users must not be able to verify each other's OTP even if the
    generated codes happen to collide (only 1,000,000 possibilities)."""
    user_a = models.User(
        email="usera@example.com",
        password=hash_password("password123"),
        email_verified=False,
    )
    user_b = models.User(
        email="userb@example.com",
        password=hash_password("password123"),
        email_verified=False,
    )
    db_session.add_all([user_a, user_b])
    db_session.commit()

    code_a = create_otp(db_session, user_a.id, models.AuthTokenPurpose.EMAIL_VERIFY)
    create_otp(db_session, user_b.id, models.AuthTokenPurpose.EMAIL_VERIFY)

    # user_b attempting user_a's code must fail even though it's a
    # syntactically valid 6-digit code that exists in the table.
    response = client.post(
        "/auth/verify-email",
        json={"code": code_a},
        headers=_auth_headers(user_b),
    )
    assert response.status_code == 400
    db_session.refresh(user_b)
    assert user_b.email_verified is False
