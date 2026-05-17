"""FastAPI auth dependency.

Import ``require_auth`` and pass it to ``Depends()`` on any route that
should be protected. Routes without this dependency remain public.

Usage:
    from fastapi import Depends
    from app.auth.dependencies import require_auth

    @router.post("/chat")
    async def chat(request: ChatRequest, _=Depends(require_auth)):
        ...
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.jwt import decode_token

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Validate the Bearer token on the incoming request.

    Args:
        credentials: Extracted from the ``Authorization: Bearer <token>``
            header by FastAPI's HTTPBearer scheme. None if the header
            is absent (auto_error=False prevents an automatic 403).

    Raises:
        HTTPException 401: If the header is missing, the token is
            malformed, expired, or signed with a wrong secret.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
