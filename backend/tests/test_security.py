"""Tests for security module."""
import pytest
from datetime import datetime, timedelta, timezone
from jose import JWTError
from backend.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    decode_token,
    generate_api_key,
    sanitize_input,
    validate_device_id,
    validate_filename,
)


class TestPasswordHashing:
    def test_hash_verification(self):
        password = "SecurePass123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = hash_password("CorrectPass")
        assert not verify_password("WrongPass", hashed)

    def test_same_password_different_hashes(self):
        pwd = "SamePassword"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        assert h1 != h2  # bcrypt salts

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed)


class TestJWTTokens:
    def test_create_access_token(self):
        token = create_access_token(subject="user123", role="user")
        assert token
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT structure

    def test_create_refresh_token(self):
        token = create_refresh_token(subject="user123")
        assert token
        assert isinstance(token, str)

    def test_verify_valid_token(self):
        token = create_access_token(subject="user123", role="user")
        payload = verify_token(token)
        assert payload is not None
        assert payload.sub == "user123"
        assert payload.role == "user"

    def test_verify_expired_token(self):
        token = create_access_token(
            subject="user123",
            role="user",
            expires_delta=timedelta(seconds=-1),  # expired
        )
        payload = verify_token(token)
        assert payload is None

    def test_decode_token_structure(self):
        token = create_access_token(subject="user123", role="admin", scopes=["read", "write"])
        payload = decode_token(token)
        assert payload["sub"] == "user123"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_invalid_token(self):
        assert verify_token("invalid.token.here") is None


class TestAPIKeyGeneration:
    def test_generate_api_key(self):
        raw, hashed = generate_api_key()
        assert raw.startswith("jv_")
        assert len(raw) > 20
        assert hashed != raw

    def test_key_uniqueness(self):
        keys = {generate_api_key()[0] for _ in range(10)}
        assert len(keys) == 10  # All unique


class TestInputValidation:
    def test_sanitize_control_chars(self):
        assert sanitize_input("hello\x00world") == "helloworld"

    def test_sanitize_max_length(self):
        result = sanitize_input("a" * 5000, max_length=10)
        assert len(result) == 10

    def test_valid_device_id(self):
        assert validate_device_id("android-abc123-def456")
        assert validate_device_id("a1b2c3d4e5f6g7h8")

    def test_invalid_device_id(self):
        assert not validate_device_id("")
        assert not validate_device_id("short")
        assert not validate_device_id("../traversal")

    def test_valid_filename(self):
        assert validate_filename("test.wav")
        assert validate_filename("my-file_v2.mp3")

    def test_invalid_filename(self):
        assert not validate_filename("")
        assert not validate_filename(".env")
        assert not validate_filename("../etc/passwd")
        assert not validate_filename("file; rm -rf /")
