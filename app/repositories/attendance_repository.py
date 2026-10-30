from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttendanceRecord
from app.utils.date_util import utc_now

_KEY = [AttendanceRecord.user_id, AttendanceRecord.date]


async def upsert(s: AsyncSession, **values) -> AttendanceRecord:
    """Creates the record for (user, date) or overwrites it if one already exists."""
    update_cols = {k: values.get(k) for k in ("status", "notes", "marked_by")}
    stmt = insert(AttendanceRecord).values(**values)
    stmt = stmt.on_conflict_do_update(index_elements=_KEY, set_={**update_cols, "updated_at": utc_now()})
    return (await s.execute(stmt.returning(AttendanceRecord).execution_options(populate_existing=True))).scalar_one()


async def mark_dates(s: AsyncSession, user_id: str, dates: list[date], status: str, marked_by: str) -> None:
    """Marks the same status on many dates at once (used when leave is approved)."""
    if not dates:
        return
    stmt = insert(AttendanceRecord).values(
        [{"user_id": user_id, "date": d, "status": status, "marked_by": marked_by} for d in dates]
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=_KEY,
        set_={"status": stmt.excluded.status, "marked_by": stmt.excluded.marked_by, "updated_at": utc_now()},
    )
    await s.execute(stmt)


async def list_by_date(s: AsyncSession, day: date, user_ids: list[str]) -> list[AttendanceRecord]:
    if not user_ids:
        return []
    q = select(AttendanceRecord).where(AttendanceRecord.date == day, AttendanceRecord.user_id.in_(user_ids))
    return list((await s.scalars(q)).all())


async def list_by_user(s: AsyncSession, user_id: str, start: date, end: date) -> list[AttendanceRecord]:
    q = (
        select(AttendanceRecord)
        .where(AttendanceRecord.user_id == user_id, AttendanceRecord.date.between(start, end))
        .order_by(AttendanceRecord.date.desc())
    )
    return list((await s.scalars(q)).all())
