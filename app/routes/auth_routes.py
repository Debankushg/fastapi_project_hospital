from fastapi import APIRouter

from app.controllers import auth_controller, mfa_controller
from app.db import Session
from app.middleware.auth_middleware import CurrentUser, MfaPendingUser, SetupOrFullUser
from app.middleware.rate_limit_middleware import auth_rate_limiter
from app.schemas.auth_schema import LoginIn, MfaCodeIn, MfaDisableIn, MfaLoginIn, MfaRevealIn, RegisterIn

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", dependencies=[auth_rate_limiter], summary="Public self-registration: always creates a patient")
async def register(body: RegisterIn, s: Session):
    return await auth_controller.register(s, body)


@router.post("/login", dependencies=[auth_rate_limiter])
async def login(body: LoginIn, s: Session):
    return await auth_controller.login(s, body)


@router.get("/me")
async def me(user: CurrentUser, s: Session):
    return await auth_controller.me(s, user)


@router.post("/mfa/verify-login", dependencies=[auth_rate_limiter], summary="Second login step")
async def verify_mfa_login(body: MfaLoginIn, user: MfaPendingUser, s: Session):
    return await auth_controller.verify_mfa_login(s, user, body)


# Setup/enable accept a mfa_setup token (forced enrolment) or a full token (voluntary, e.g. patients).
@router.post("/mfa/setup")
async def mfa_setup(user: SetupOrFullUser, s: Session):
    return await mfa_controller.setup(s, user)


@router.post("/mfa/enable", dependencies=[auth_rate_limiter])
async def mfa_enable(body: MfaCodeIn, user: SetupOrFullUser, s: Session):
    return await mfa_controller.enable(s, user, body)


@router.post("/mfa/secret", dependencies=[auth_rate_limiter])
async def mfa_reveal_secret(body: MfaRevealIn, user: CurrentUser, s: Session):
    return await mfa_controller.reveal_secret(s, user, body)


@router.post("/mfa/disable", dependencies=[auth_rate_limiter], status_code=204)
async def mfa_disable(body: MfaDisableIn, user: CurrentUser, s: Session):
    return await mfa_controller.disable(s, user, body)
