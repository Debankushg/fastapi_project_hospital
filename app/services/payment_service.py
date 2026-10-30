import asyncio
from typing import Any

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Payment, User
from app.repositories import appointment_repository, doctor_profile_repository, payment_repository, user_repository
from app.schemas.payment_schema import ReceivablesQuery
from app.utils.http_error_util import HttpError
from app.utils.pagination_util import offset_of, to_page
from app.utils.stripe_util import get_stripe, to_minor_units


async def _apply_session(s: AsyncSession, session: Any) -> Payment | None:
    """Brings a stored payment in line with what Stripe says about its Checkout Session."""
    if session.payment_status == "paid":
        intent = session.payment_intent
        intent_id = intent if isinstance(intent, str) or intent is None else intent.id
        await payment_repository.mark_paid(s, session.id, intent_id)
    elif session.status == "expired":
        await payment_repository.mark_expired(s, session.id)
    await s.commit()
    return await payment_repository.find_by_session_id(s, session.id)


def _to_public_payment(p: Payment) -> dict:
    return {
        "id": p.id,
        "status": p.status,
        "amount": p.amount,
        "currency": p.currency,
        "sessionId": p.stripe_session_id,
        "paidAt": p.paid_at,
    }


async def receivables(s: AsyncSession, q: ReceivablesQuery) -> dict:
    """Checked visits with their payment state (unpaid first by default)."""
    rows, total = await appointment_repository.list_appointments(
        s,
        status="checked",
        search=q.search,
        paid=None if q.status == "all" else q.status == "paid",
        sort="checked_desc",
        limit=q.page_size,
        offset=offset_of(q.page, q.page_size),
    )
    all_payments = await payment_repository.list_by_appointment_ids(s, [r["id"] for r in rows])
    items = []
    for r in rows:
        mine = [p for p in all_payments if p.appointment_id == r["id"]]
        shown = next((p for p in mine if p.status == "paid"), None) or next((p for p in mine if p.status == "pending"), None)
        items.append(
            {
                **r,
                "currency": settings.STRIPE_CURRENCY,
                "paymentStatus": shown.status if shown else "unpaid",
                "payment": _to_public_payment(shown) if shown else None,
            }
        )
    return to_page(items, total, q.page, q.page_size)


async def summary(s: AsyncSession) -> dict:
    return {**await payment_repository.summary(s), "currency": settings.STRIPE_CURRENCY}


async def start_checkout(s: AsyncSession, actor: User, appointment_id: str) -> dict:
    """Starts (or resumes) a Stripe-hosted Checkout page for a checked visit."""
    client = get_stripe()
    appt = await appointment_repository.find_by_id(s, appointment_id)
    if not appt or appt.status != "checked":
        raise HttpError(404, "Checked visit not found")
    # Visits checked before fees were snapshotted fall back to the doctor's current fee.
    profile = (
        await doctor_profile_repository.find_by_user(s, appt.doctor_id)
        if appt.checked_fee is None and appt.doctor_id
        else None
    )
    fee = float(appt.checked_fee if appt.checked_fee is not None else (profile.consultation_fee if profile else 0) or 0)
    if not fee > 0:
        raise HttpError(400, "This visit has no consultation fee to collect")

    existing = await payment_repository.list_by_appointment_ids(s, [appt.id])
    if any(p.status == "paid" for p in existing):
        raise HttpError(409, "This visit is already paid")

    # Reuse a Checkout page that is still open instead of creating duplicates.
    for p in (x for x in existing if x.status == "pending"):
        session = await asyncio.to_thread(client.v1.checkout.sessions.retrieve, p.stripe_session_id)
        if session.status == "open" and session.url:
            return {"payment": _to_public_payment(p), "url": session.url}
        updated = await _apply_session(s, session)
        if updated and updated.status == "paid":
            raise HttpError(409, "This visit is already paid")

    patient = await user_repository.find_by_id(s, appt.patient_id)
    session = await asyncio.to_thread(
        client.v1.checkout.sessions.create,
        {
            "mode": "payment",
            "client_reference_id": appt.id,
            **({"customer_email": patient.email} if patient else {}),
            "metadata": {"appointmentId": appt.id},
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": settings.STRIPE_CURRENCY,
                        "unit_amount": to_minor_units(fee),
                        "product_data": {
                            "name": f"Consultation – {appt.specialty.upper()}",
                            "description": f"Visit on {appt.appointment_date.isoformat()}",
                        },
                    },
                }
            ],
            "success_url": f"{settings.FRONTEND_URL}/payments?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.FRONTEND_URL}/payments?checkout=cancelled",
        },
    )
    if not session.url:
        raise HttpError(502, "Stripe did not return a payment page")

    payment = payment_repository.create(
        s,
        appointment_id=appt.id,
        patient_id=appt.patient_id,
        amount=f"{fee:.2f}",
        currency=settings.STRIPE_CURRENCY,
        stripe_session_id=session.id,
        created_by=actor.id,
    )
    await s.commit()
    await s.refresh(payment)
    return {"payment": _to_public_payment(payment), "url": session.url}


async def sync(s: AsyncSession, session_id: str) -> dict:
    """Asks Stripe for the current state of a session (used after redirect and for the Refresh button)."""
    stored = await payment_repository.find_by_session_id(s, session_id)
    if not stored:
        raise HttpError(404, "Payment not found")
    session = await asyncio.to_thread(get_stripe().v1.checkout.sessions.retrieve, session_id)
    payment = await _apply_session(s, session)
    return {"payment": _to_public_payment(payment or stored)}


async def handle_webhook(s: AsyncSession, raw_body: bytes, signature: str | None) -> None:
    """Stripe webhook: verifies the signature, then applies Checkout events."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HttpError(503, "Stripe webhook is not configured")
    if not signature:
        raise HttpError(400, "Missing Stripe signature")
    get_stripe()  # 503 when Stripe itself is not configured
    try:
        event = stripe.Webhook.construct_event(raw_body, signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:  # noqa: BLE001 - bad payload or signature
        raise HttpError(400, "Invalid Stripe signature") from None
    if event["type"] in (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.expired",
    ):
        await _apply_session(s, event["data"]["object"])
