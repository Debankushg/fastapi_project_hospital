from sqlalchemy.ext.asyncio import AsyncSession

from app.config.permissions_config import AREA_ROLE
from app.models import User
from app.models.enums import ADMIN_AREAS
from app.repositories import admin_assignment_repository, duty_schedule_repository, user_repository
from app.services import permission_service
from app.services.duty_service import to_duty_view
from app.utils.mapper_util import to_public_user


async def list_staff(s: AsyncSession, actor: User) -> list[User]:
    """Staff the actor manages (used by attendance and leave pickers)."""
    roles = await permission_service.manageable_staff_roles(s, actor)
    return await user_repository.list_users(s, roles) if roles else []


async def overview(s: AsyncSession, actor: User) -> list[dict]:
    """Departments (work areas) of the actor with their members and duty times.
    Admin: only assigned areas. Super admin: every area.

    Admins appear only inside their own profession's department (their `base_role`), tagged e.g.
    "Doctor, Admin" - never under the other departments they administer."""
    if actor.role == "super_admin":
        areas = [(area, None) for area in ADMIN_AREAS]
    else:
        areas = [(a.area, a.notes) for a in await admin_assignment_repository.list_by_admin(s, actor.id)]
    if not areas:
        return []

    roles = [AREA_ROLE[area] for area, _ in areas]
    people = await user_repository.list_users(s, [*roles, "admin"])
    duties = await duty_schedule_repository.list_by_user_ids(s, [m.id for m in people if m.role != "patient"])
    duty_by_user = {d.user_id: to_duty_view(d) for d in duties}

    result = []
    for area, notes in areas:
        role = AREA_ROLE[area]
        members = [m for m in people if m.role == role or (m.role == "admin" and m.base_role == role)]
        result.append(
            {
                "area": area,
                "role": role,
                "notes": notes,
                "members": [{**to_public_user(m), "duty": duty_by_user.get(m.id)} for m in members],
            }
        )
    return result


async def admins_without_profession(s: AsyncSession, actor: User) -> list[dict]:
    """Super admin only: admins with no profession set. They cannot be placed in a department until the
    super admin chooses what they work as, so the UI points them out."""
    if actor.role != "super_admin":
        return []
    return [
        {"id": a.id, "fullName": a.full_name, "email": a.email}
        for a in await user_repository.list_users(s, ["admin"])
        if not a.base_role
    ]
