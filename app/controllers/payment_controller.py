from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.schemas.payment_schema import ReceivablesQuery, StartCheckoutIn, SyncPaymentIn
from app.services import payment_service
from app.utils.response_util import ok


async def receivables(s: AsyncSession, q: ReceivablesQuery):
    return ok(await payment_service.receivables(s, q))


async def summary(s: AsyncSession):
    return ok(await payment_service.summary(s))


async def checkout(s: AsyncSession, actor: User, body: StartCheckoutIn):
    return ok(await payment_service.start_checkout(s, actor, body.appointment_id), 201)


async def sync(s: AsyncSession, body: SyncPaymentIn):
    return ok(await payment_service.sync(s, body.session_id))


async def webhook(s: AsyncSession, raw_body: bytes, signature: str | None):
    """The signature is computed over the raw bytes, so the body is passed on unparsed."""
    await payment_service.handle_webhook(s, raw_body, signature)
    return ok({"received": True})
