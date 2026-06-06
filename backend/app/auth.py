"""Shared-password authentication for the CPE Video API.

When ``AUTH_PASSWORD`` is unset the whole API is open (handy for local dev).
When it is set, clients log in with the password via ``POST /api/login`` and
receive a stable bearer token (an HMAC of the password). Every protected
route then requires ``Authorization: Bearer <token>``.
"""

import hmac
from hashlib import sha256

from fastapi import APIRouter, HTTPException, Request, status

from app.schemas import LoginRequest, LoginResponse
from app.settings import Settings

_TOKEN_SALT = b"cpe-video-auth-v1"


def expected_token(password: str) -> str:
    return hmac.new(_TOKEN_SALT, password.encode("utf-8"), sha256).hexdigest()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def require_auth(request: Request) -> None:
    """FastAPI dependency that guards protected routes."""
    password = _settings(request).resolved_auth_password()
    if not password:
        return  # auth disabled

    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登入",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not hmac.compare_digest(token, expected_token(password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登入憑證無效",
            headers={"WWW-Authenticate": "Bearer"},
        )


router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/auth/status")
async def auth_status(request: Request) -> dict[str, bool]:
    return {"authRequired": bool(_settings(request).resolved_auth_password())}


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request) -> LoginResponse:
    password = _settings(request).resolved_auth_password()
    if not password:
        # Auth disabled — accept any login, return an empty token.
        return LoginResponse(token="")
    if not hmac.compare_digest(payload.password.encode("utf-8"), password.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="密碼錯誤")
    return LoginResponse(token=expected_token(password))
