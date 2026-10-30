from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import admin_assignment_repository, user_repository
from app.schemas.admin_schema import BASE_ROLES, CreateAdminIn, UpdateAdminWorkIn
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import to_public_user
from app.utils.password_util import hash_password


def _to_assignment_view(a) -> dict:
    return {"area": a.area, "notes": a.notes, "createdAt": a.created_at}


def _items(data) -> list[dict]:
    return [{"area": a.area, "notes": a.notes} for a in data.assignments]


async def _require_admin(s: AsyncSession, user_id: str) -> User:
    target = await user_repository.find_by_id(s, user_id)
    if not target or target.role != "admin":
        raise HttpError(404, "Admin not found")
    return target


async def list_admins(s: AsyncSession) -> list[dict]:
    admins = await user_repository.list_users(s, ["admin"])
    assignments = await admin_assignment_repository.list_all(s)
    return [
        {**to_public_user(a), "assignments": [_to_assignment_view(x) for x in assignments if x.admin_id == a.id]}
        for a in admins
    ]


async def create_admin(s: AsyncSession, actor: User, data: CreateAdminIn) -> dict:
    """Create a brand-new admin account and assign their work in one step."""
    password_hash = await hash_password(data.password)
    user = await user_repository.create(
        s,
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        password_hash=password_hash,
        role="admin",
        base_role=data.base_role,
        created_by=actor.id,
    )
    items = _items(data)
    reassigned = await admin_assignment_repository.replace_for_admin(s, user.id, actor.id, items)
    await s.commit()
    await s.refresh(user)
    return {"user": to_public_user(user), "assignments": items, "reassigned": reassigned}


async def promote(s: AsyncSession, actor: User, user_id: str, data: UpdateAdminWorkIn) -> dict:
    """Promote an existing user to admin and assign their work.
    A doctor/receptionist/pathologist/accounts user keeps that as their department role ("Doctor, Admin")."""
    target = await user_repository.find_by_id(s, user_id)
    if not target:
        raise HttpError(404, "User not found")
    if target.role == "super_admin":
        raise HttpError(400, "Cannot change a super admin")
    if target.role == "patient":
        raise HttpError(400, "Patients cannot be promoted to admin; create the admin as staff instead")

    previous_staff_role = target.role if target.role in BASE_ROLES else None
    base_role = data.base_role or previous_staff_role or target.base_role
    if not base_role:
        raise HttpError(
            400,
            "Choose the profession this admin works as (doctor, receptionist, pathologist or accounts)",
            {"baseRole": ["Required for users who are not already doctors, receptionists, pathologists or accounts staff"]},
        )

    user_repository.update(target, role="admin", base_role=base_role)
    items = _items(data)
    reassigned = await admin_assignment_repository.replace_for_admin(s, target.id, actor.id, items)
    await s.commit()
    return {"user": to_public_user(target), "assignments": items, "reassigned": reassigned}


async def replace_assignments(s: AsyncSession, actor: User, user_id: str, data: UpdateAdminWorkIn) -> dict:
    target = await _require_admin(s, user_id)
    items = _items(data)
    reassigned = await admin_assignment_repository.replace_for_admin(s, target.id, actor.id, items)
    if data.base_role is not None:
        user_repository.update(target, base_role=data.base_role)
    await s.commit()
    return {"assignments": items, "reassigned": reassigned}


async def get_assignments(s: AsyncSession, user_id: str) -> list[dict]:
    return [_to_assignment_view(a) for a in await admin_assignment_repository.list_by_admin(s, user_id)]


async def demote(s: AsyncSession, user_id: str, role: str) -> dict:
    """Revoke admin rights: the user falls back to the given role and loses all assignments."""
    target = await _require_admin(s, user_id)
    await admin_assignment_repository.delete_by_admin(s, target.id)
    user_repository.update(target, role=role, base_role=None)
    await s.commit()
    return to_public_user(target)
