"""Auth router — POST /auth/login.

The only unauthenticated route that produces a token. All other routes
(except /health and /) require the returned token in the Authorization header.
"""

import secrets

import structlog
from fastapi import APIRouter, HTTPException, status

from app.auth.jwt import create_token
from app.config import get_settings
from app.models.schemas import LoginRequest, TokenResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Verify the app password and return a JWT access token.

    Uses ``secrets.compare_digest`` for the password comparison to prevent
    timing attacks — a constant-time comparison ensures an attacker cannot
    measure which characters of the password are correct.

    Args:
        request: Body containing the ``password`` field.

    Returns:
        A ``TokenResponse`` with a signed JWT valid for 24 hours.

    Raises:
        HTTPException 401: If the password is incorrect.
    """
    settings = get_settings()

    # Timing-safe comparison — do not replace with ==
    password_correct = secrets.compare_digest(
        request.password.encode("utf-8"),
        settings.APP_PASSWORD.encode("utf-8"),
    )

    if not password_correct:
        logger.warning("login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password.",
        )

    token = create_token()
    logger.info("login_success")
    return TokenResponse(access_token=token)
