"""
Unit tests for app.core.security.

Covers token creation (with/without custom expiry) and password hashing round-trip.
No external services needed — pure crypto operations only.
"""
from __future__ import annotations

from datetime import timedelta, datetime, timezone

import pytest
from jose import jwt

from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.config import settings


class TestPasswordHashing:

    def test_hash_and_verify_roundtrip(self):
        """get_password_hash + verify_password must accept the original password."""
        plain = "securePass1!"
        hashed = get_password_hash(plain)
        assert hashed != plain
        assert verify_password(plain, hashed) is True

    def test_wrong_password_fails_verify(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_is_not_deterministic(self):
        """bcrypt uses a random salt — same plaintext must produce different hashes."""
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2

    def test_hash_is_long_enough_to_be_bcrypt(self):
        """bcrypt hashes are always 60 characters."""
        hashed = get_password_hash("any_password")
        assert len(hashed) == 60


class TestCreateAccessToken:

    def test_token_contains_correct_subject(self):
        """'sub' claim must match the subject passed in."""
        subject = "user-uuid-abc123"
        token = create_access_token(subject=subject)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == subject

    def test_token_uses_default_expiry_when_no_delta_given(self):
        """Without expires_delta the token should expire in ~ACCESS_TOKEN_EXPIRE_MINUTES."""
        token = create_access_token(subject="u1")
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = (exp - datetime.now(timezone.utc)).total_seconds()
        expected = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        # Allow ±30 s tolerance for test execution time
        assert expected - 30 < delta < expected + 30

    def test_token_uses_custom_expiry_delta(self):
        """Explicit expires_delta must override the default."""
        token = create_access_token(subject="u1", expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = (exp - datetime.now(timezone.utc)).total_seconds()
        # Should be ~5 minutes (300 s) ± 30 s tolerance
        assert 270 < delta < 330

    def test_token_is_valid_jwt_string(self):
        """Token must be a non-empty string with the standard three-part structure."""
        token = create_access_token(subject="u1")
        assert isinstance(token, str)
        assert token.count(".") == 2  # header.payload.signature

    def test_token_signed_with_correct_algorithm(self):
        """Decoding with the wrong algorithm must fail."""
        token = create_access_token(subject="u1")
        with pytest.raises(Exception):
            jwt.decode(token, settings.SECRET_KEY, algorithms=["RS256"])
