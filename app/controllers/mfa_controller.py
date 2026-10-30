from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.auth_schema import MfaCodeIn, MfaDisableIn, MfaRevealIn
from app.services import mfa_service
from app.utils.response_util import ok


async def setup(s: AsyncSession, user: User):
    return ok(await mfa_service.begin_setup(s, user))


async def enable(s: AsyncSession, user: User, body: MfaCodeIn):
    return ok(await mfa_service.enable(s, user, body.code))


async def reveal_secret(s: AsyncSession, user: User, body: MfaRevealIn):
    return ok(await mfa_service.reveal_secret(s, user, body.password, body.code))


async def disable(s: AsyncSession, user: User, body: MfaDisableIn):
    await mfa_service.disable(s, user, body.password, body.code)
    return Response(status_code=204)
