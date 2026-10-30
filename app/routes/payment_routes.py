from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request

from app.controllers import payment_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import require_payments
from app.schemas.payment_schema import ReceivablesQuery, StartCheckoutIn, SyncPaymentIn

router = APIRouter(prefix="/payments", tags=["Payments"])
accounts_only = [Authed, Depends(require_payments)]


@router.get("/receivables", dependencies=accounts_only)
async def receivables(q: Annotated[ReceivablesQuery, Query()], s: Session):
    return await payment_controller.receivables(s, q)


@router.get("/summary", dependencies=accounts_only)
async def summary(s: Session):
    return await payment_controller.summary(s)


@router.post("/checkout", dependencies=accounts_only)
async def checkout(body: StartCheckoutIn, user: CurrentUser, s: Session):
    return await payment_controller.checkout(s, user, body)


@router.post("/sync", dependencies=accounts_only)
async def sync(body: SyncPaymentIn, s: Session):
    return await payment_controller.sync(s, body)


# Stripe calls this, not a signed-in user: no bearer token, the signature is verified instead.
@router.post("/webhook", summary="Stripe webhook")
async def webhook(request: Request, s: Session, stripe_signature: Annotated[str | None, Header()] = None):
    return await payment_controller.webhook(s, await request.body(), stripe_signature)
