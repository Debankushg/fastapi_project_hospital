from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.auth_schema import LoginIn, MfaLoginIn, RegisterIn
from app.services import auth_service
from app.utils.response_util import ok


async def register(s: AsyncSession, body: RegisterIn):
    return ok({"user": await auth_service.register_patient(s, body)}, 201)


async def login(s: AsyncSession, body: LoginIn):
    return ok(await auth_service.login(s, body.email, body.password))


async def verify_mfa_login(s: AsyncSession, user: User, body: MfaLoginIn):
    return ok(await auth_service.verify_mfa_login(s, user, body))


async def me(s: AsyncSession, user: User):
    return ok({"user": await auth_service.to_session_user(s, user)})
