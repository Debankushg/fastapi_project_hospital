from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def _rows(s: AsyncSession, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r._mapping) for r in (await s.execute(text(sql), params)).all()]


def _unit(unit: str) -> str:
    """`unit` is whitelisted by the schema (day|month), so it is safe to inline as a SQL literal."""
    if unit not in ("day", "month"):
        raise ValueError(unit)
    return unit


async def patient_series(s: AsyncSession, start: date, end: date, unit: str) -> list[dict]:
    """Appointments per bucket by status, plus new patient registrations. Empty buckets are included."""
    u = _unit(unit)
    return await _rows(
        s,
        f"""
        with buckets as (
          select generate_series(date_trunc('{u}', cast(:start as date)), date_trunc('{u}', cast(:end as date)), interval '1 {u}')::date as bucket
        ),
        appts as (
          select date_trunc('{u}', appointment_date)::date as bucket,
            count(*) filter (where status = 'requested')::int as requested,
            count(*) filter (where status = 'approved')::int as approved,
            count(*) filter (where status = 'checked')::int as checked,
            count(*) filter (where status in ('rejected', 'cancelled'))::int as cancelled
          from appointments
          where appointment_date between cast(:start as date) and cast(:end as date)
          group by 1
        ),
        regs as (
          select date_trunc('{u}', (created_at at time zone 'UTC'))::date as bucket, count(*)::int as n
          from users
          where role = 'patient'
            and (created_at at time zone 'UTC')::date between cast(:start as date) and cast(:end as date)
          group by 1
        )
        select b.bucket::text as bucket,
          coalesce(a.requested, 0) as requested, coalesce(a.approved, 0) as approved,
          coalesce(a.checked, 0) as checked, coalesce(a.cancelled, 0) as cancelled,
          coalesce(r.n, 0) as "newPatients"
        from buckets b
        left join appts a on a.bucket = b.bucket
        left join regs r on r.bucket = b.bucket
        order by b.bucket""",
        start=start,
        end=end,
    )


async def total_patients(s: AsyncSession) -> int:
    return (await _rows(s, "select count(*)::int as n from users where role = 'patient'"))[0]["n"]


async def revenue_series(s: AsyncSession, start: date, end: date, unit: str) -> list[dict]:
    """Revenue per bucket (visit date): `collected` = fees of checked visits with a paid Stripe payment,
    `pending` = fees of checked visits not paid yet."""
    u = _unit(unit)
    return await _rows(
        s,
        f"""
        with buckets as (
          select generate_series(date_trunc('{u}', cast(:start as date)), date_trunc('{u}', cast(:end as date)), interval '1 {u}')::date as bucket
        ),
        v as (
          select date_trunc('{u}', a.appointment_date)::date as bucket,
            sum(f.fee) filter (where f.paid) as collected,
            sum(f.fee) filter (where not f.paid) as pending,
            count(*)::int as visits
          from appointments a
          left join doctor_profiles dp on dp.user_id = a.doctor_id
          cross join lateral (
            select coalesce(a.checked_fee, dp.consultation_fee, 0) as fee,
                   exists (select 1 from payments p where p.appointment_id = a.id and p.status = 'paid') as paid
          ) f
          where a.status = 'checked' and a.appointment_date between cast(:start as date) and cast(:end as date)
          group by 1
        )
        select b.bucket::text as bucket,
          coalesce(v.collected, 0)::text as collected,
          coalesce(v.pending, 0)::text as pending,
          coalesce(v.visits, 0) as visits
        from buckets b left join v on v.bucket = b.bucket
        order by b.bucket""",
        start=start,
        end=end,
    )


async def revenue_by_specialty(s: AsyncSession, start: date, end: date) -> list[dict]:
    return await _rows(
        s,
        """
        select a.specialty::text as specialty,
          sum(coalesce(a.checked_fee, dp.consultation_fee, 0))::text as revenue,
          count(*)::int as visits
        from appointments a
        left join doctor_profiles dp on dp.user_id = a.doctor_id
        where a.status = 'checked' and a.appointment_date between cast(:start as date) and cast(:end as date)
        group by a.specialty
        order by sum(coalesce(a.checked_fee, dp.consultation_fee, 0)) desc""",
        start=start,
        end=end,
    )


async def doctor_workload(s: AsyncSession, start: date, end: date) -> list[dict]:
    """Every active doctor with how many of their patients are checked / still to be seen in the window."""
    return await _rows(
        s,
        """
        select u.id::text as "doctorId", u.full_name as "doctorName", dp.specialty::text as specialty,
          count(a.id) filter (where a.status = 'checked')::int as checked,
          count(a.id) filter (where a.status = 'approved')::int as unchecked
        from doctor_profiles dp
        join users u on u.id = dp.user_id and u.is_active
        left join appointments a on a.doctor_id = u.id
          and a.status in ('approved', 'checked')
          and a.appointment_date between cast(:start as date) and cast(:end as date)
        group by u.id, u.full_name, dp.specialty
        order by (count(a.id)) desc, u.full_name""",
        start=start,
        end=end,
    )
