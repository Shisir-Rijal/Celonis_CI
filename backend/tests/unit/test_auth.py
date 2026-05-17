"""Unit tests for JWT helpers and auth dependency.

All tests run against a fixed test secret — no .env needed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth.dependencies import require_auth
from app.auth.jwt import ALGORITHM, TOKEN_EXPIRE_HOURS, create_token, decode_token
from app.config import Settings

TEST_SECRET = "a" * 32  # exactly 32 chars, satisfies length validator
TEST_PASSWORD = "test-password-123"

TEST_SETTINGS = Settings(
    OPENAI_API_KEY="test",
    APP_PASSWORD=TEST_PASSWORD,
    JWT_SECRET=TEST_SECRET,
)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

class TestCreateToken:
    def test_returns_string(self) -> None:
        """create_token() returns a non-empty string."""
        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            token = create_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contains_exp_and_iat(self) -> None:
        """Created token carries exp and iat claims."""
        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            token = create_token()
        payload = jwt.decode(token, TEST_SECRET, algorithms=[ALGORITHM])
        assert "exp" in payload
        assert "iat" in payload

    def test_token_expires_in_24h(self) -> None:
        """Token expiry is approximately 24 hours from now."""
        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            token = create_token()
        payload = jwt.decode(token, TEST_SECRET, algorithms=[ALGORITHM])
        now = datetime.now(timezone.utc).timestamp()
        expected_exp = now + TOKEN_EXPIRE_HOURS * 3600
        assert abs(payload["exp"] - expected_exp) < 5  # within 5 seconds


class TestDecodeToken:
    def test_valid_token_round_trip(self) -> None:
        """Token created with create_token() is decodable with decode_token()."""
        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            token = create_token()
            payload = decode_token(token)
        assert "exp" in payload

    def test_expired_token_raises(self) -> None:
        """decode_token() raises JWTError for an expired token."""
        from jose import JWTError

        expired_payload = {
            "iat": datetime.now(timezone.utc) - timedelta(hours=48),
            "exp": datetime.now(timezone.utc) - timedelta(hours=24),
        }
        expired_token = jwt.encode(expired_payload, TEST_SECRET, algorithm=ALGORITHM)

        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            with pytest.raises(JWTError):
                decode_token(expired_token)

    def test_wrong_signature_raises(self) -> None:
        """decode_token() raises JWTError for a token signed with a different secret."""
        from jose import JWTError

        other_secret = "b" * 32
        payload = {
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
        }
        bad_token = jwt.encode(payload, other_secret, algorithm=ALGORITHM)

        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            with pytest.raises(JWTError):
                decode_token(bad_token)

    def test_garbage_string_raises(self) -> None:
        """decode_token() raises JWTError for a completely invalid string."""
        from jose import JWTError

        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            with pytest.raises(JWTError):
                decode_token("not.a.token")


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_missing_header_raises_401(self) -> None:
        """require_auth() raises 401 when no Authorization header is present."""
        with patch("app.auth.dependencies.decode_token"):
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(credentials=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_passes(self) -> None:
        """require_auth() does not raise for a valid token."""
        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            token = create_token()

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.dependencies.decode_token") as mock_decode:
            mock_decode.return_value = {"exp": 9999999999}
            await require_auth(credentials=credentials)  # must not raise

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self) -> None:
        """require_auth() raises 401 when decode_token() raises JWTError."""
        from jose import JWTError

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="invalid.token.here"
        )

        with patch("app.auth.dependencies.decode_token", side_effect=JWTError("bad")):
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(credentials=credentials)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Timing-safe password comparison
# ---------------------------------------------------------------------------

class TestTimingSafeCompare:
    def test_compare_digest_used_in_login(self) -> None:
        """Login handler uses secrets.compare_digest, not == operator."""
        import inspect
        import app.api.auth as auth_module

        source = inspect.getsource(auth_module)
        assert "compare_digest" in source, (
            "Login route must use secrets.compare_digest for timing-safe comparison"
        )


# ---------------------------------------------------------------------------
# Codex findings — regression tests for the two fixes
# ---------------------------------------------------------------------------

class TestCodexFindings:
    def test_token_without_exp_is_rejected(self) -> None:
        """decode_token() rejects a token missing the exp claim (Fix: required claims).

        A token signed with the correct secret but without exp would be
        permanently valid without this check.
        """
        from jose import JWTError

        no_exp_token = jwt.encode(
            {"iat": datetime.now(timezone.utc)},  # no exp
            TEST_SECRET,
            algorithm=ALGORITHM,
        )
        with patch("app.auth.jwt.get_settings", return_value=TEST_SETTINGS):
            with pytest.raises(JWTError):
                decode_token(no_exp_token)

    def test_app_password_too_short_raises_on_startup(self) -> None:
        """Settings rejects APP_PASSWORD shorter than 12 characters (Fix: min length).

        A short password is brute-forceable since the login endpoint has no
        rate limiting at this stage.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="APP_PASSWORD"):
            Settings(
                _env_file=None,
                OPENAI_API_KEY="test",
                APP_PASSWORD="short",  # only 5 chars
                JWT_SECRET=TEST_SECRET,
            )

    def test_jwt_secret_too_short_raises_on_startup(self) -> None:
        """Settings rejects JWT_SECRET shorter than 32 characters."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="JWT_SECRET"):
            Settings(
                _env_file=None,
                OPENAI_API_KEY="test",
                APP_PASSWORD="valid-password-123",
                JWT_SECRET="tooshort",
            )
