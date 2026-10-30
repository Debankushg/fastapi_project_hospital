from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DutySchedule
from app.utils.date_util import utc_now


async def find_by_user(s: AsyncSession, user_id: str) -> DutySchedule | None:
    return await s.get(DutySchedule, user_id)


async def list_by_user_ids(s: AsyncSession, user_ids: list[str]) -> list[DutySchedule]:
    if not user_ids:
        return []
    return list((await s.scalars(select(DutySchedule).where(DutySchedule.user_id.in_(user_ids)))).all())


async def upsert(s: AsyncSession, user_id: str, **values) -> DutySchedule:
    stmt = insert(DutySchedule).values(user_id=user_id, **values)
    stmt = stmt.on_conflict_do_update(index_elements=[DutySchedule.user_id], set_={**values, "updated_at": utc_now()})
    return (await s.execute(stmt.returning(DutySchedule).execution_options(populate_existing=True))).scalar_one()
