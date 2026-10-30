from collections.abc import Awaitable, Callable
from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import Session
from app.models import User
from app.repositories import user_repository
from app.typings.domain_types import TokenStage
from app.utils.http_error_util import HttpError
from app.utils.jwt_util import verify_token

# auto_error=False: we answer with our own 401 body; the scheme is declared so Swagger UI shows "Authorize".
_bearer = HTTPBearer(auto_error=False)


def authenticate(*stages: TokenStage) -> Callable[..., Awaitable[User]]:
    """Verifies the bearer token and only accepts the listed stages (default: full)."""
    allowed = stages or ("full",)

    async def dependency(
        request: Request,
        s: Session,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    ) -> User:
        if not credentials:
            raise HttpError(401, "Missing bearer token")
        try:
            user_id, stage = verify_token(credentials.credentials)
        except (jwt.PyJWTError, KeyError):
            raise HttpError(401, "Invalid or expired token") from None
        if stage not in allowed:
            raise HttpError(403, "MFA enrolment required" if stage == "mfa_setup" else "Insufficient authentication stage")

        user = await user_repository.find_by_id(s, user_id)
        if not user or not user.is_active:
            raise HttpError(401, "Account unavailable")
        request.state.stage = stage
        return user

    return dependency


_full = authenticate()
# Route parameters:  `user: CurrentUser`
CurrentUser = Annotated[User, Depends(_full)]
SetupOrFullUser = Annotated[User, Depends(authenticate("mfa_setup", "full"))]
MfaPendingUser = Annotated[User, Depends(authenticate("mfa_pending"))]
# Router-level `dependencies=[Authed]`: same callable as CurrentUser, so the check runs once per request.
Authed = Depends(_full)
