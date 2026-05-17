"""JWT helpers — create and decode access tokens.

Tokens are signed with HS256 using the JWT_SECRET from global Settings.
They carry only two claims: issue time (iat) and expiry (exp). No user
identity is embedded — the token itself is proof of access for this MVP.

Usage:
    from app.auth.jwt import create_token, decode_token

    token = create_token()
    payload = decode_token(token)   # raises JWTError if invalid/expired
"""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def create_token() -> str:
    """Create a signed JWT that expires in 24 hours.

    Returns:
        Encoded JWT string ready to send to the client.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "iat": now,
        "exp": now + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT.

    Args:
        token: Encoded JWT string from the Authorization header.

    Returns:
        The decoded payload dict (contains ``iat`` and ``exp``).

    Raises:
        JWTError: If the token is invalid, expired, or the signature
            does not match. Callers should map this to a 401 response.
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    # python-jose validates exp automatically when present but does not
    # require it. We enforce it manually — a token without exp would be
    # permanently valid, which is a security hole.
    if "exp" not in payload or "iat" not in payload:
        raise JWTError("Token is missing required claims: exp and iat")
    return payload
