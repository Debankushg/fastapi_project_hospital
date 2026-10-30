from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Payment
from app.utils.date_util import utc_now


def create(s: AsyncSession, **values) -> Payment:
    payment = Payment(**values)
    s.add(payment)
    return payment


async def find_by_session_id(s: AsyncSession, session_id: str) -> Payment | None:
    return await s.scalar(
        select(Payment).where(Payment.stripe_session_id == session_id).execution_options(populate_existing=True)
    )


async def list_by_appointment_ids(s: AsyncSession, ids: list[str]) -> list[Payment]:
    if not ids:
        return []
    q = select(Payment).where(Payment.appointment_id.in_(ids)).order_by(Payment.created_at.desc())
    return list((await s.scalars(q)).all())


async def mark_paid(s: AsyncSession, session_id: str, payment_intent_id: str | None) -> None:
    """Idempotent: a payment that is already paid is left untouched."""
    await s.execute(
        update(Payment)
        .where(Payment.stripe_session_id == session_id, Payment.status != "paid")
        .values(status="paid", paid_at=utc_now(), stripe_payment_intent_id=payment_intent_id)
    )


async def mark_expired(s: AsyncSession, session_id: str) -> None:
    await s.execute(
        update(Payment).where(Payment.stripe_session_id == session_id, Payment.status == "pending").values(status="expired")
    )


async def summary(s: AsyncSession) -> dict:
    """Money collected vs still owed on checked visits."""
    r = (
        await s.execute(
            text(
                """
                select
                  coalesce((select sum(amount) from payments where status = 'paid'), 0)::text as collected,
                  (select count(*)::int from payments where status = 'paid') as paid_count,
                  coalesce((select sum(coalesce(a.checked_fee, d.consultation_fee)) from appointments a
                            left join doctor_profiles d on d.user_id = a.doctor_id
                            where a.status = 'checked' and coalesce(a.checked_fee, d.consultation_fee) > 0
                              and not exists (select 1 from payments p where p.appointment_id = a.id and p.status = 'paid')), 0)::text as outstanding,
                  (select count(*)::int from appointments a
                    left join doctor_profiles d on d.user_id = a.doctor_id
                    where a.status = 'checked' and coalesce(a.checked_fee, d.consultation_fee) > 0
                      and not exists (select 1 from payments p where p.appointment_id = a.id and p.status = 'paid')) as unpaid_count
                """
            )
        )
    ).one()
    return {"collected": r.collected, "paidCount": r.paid_count, "outstanding": r.outstanding, "unpaidCount": r.unpaid_count}
