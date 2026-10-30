from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import doctor_profile_repository, prescription_repository, user_repository
from app.schemas.user_schema import CreateUserIn
from app.services import permission_service
from app.utils.file_storage_util import delete_prescription_files
from app.utils.http_error_util import HttpError
from app.utils.mapper_util import to_public_user
from app.utils.password_util import hash_password


async def create_user(s: AsyncSession, actor: User, data: CreateUserIn) -> dict:
    """Super admin: any role. Admin: only roles within assigned areas."""
    if not await permission_service.can_manage_role(s, actor, data.role):
        raise HttpError(403, f"You are not assigned to manage {data.role} accounts")
    password_hash = await hash_password(data.password)

    user = await user_repository.create(
        s,
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        password_hash=password_hash,
        role=data.role,
        created_by=actor.id,
    )
    if data.role == "doctor":
        doctor_profile_repository.create(
            s,
            user_id=user.id,
            specialty=data.specialty,
            license_no=data.license_no,
            consultation_fee=None if data.consultation_fee is None else f"{data.consultation_fee:.2f}",
        )
    await s.commit()
    await s.refresh(user)
    return to_public_user(user)


async def list_users(s: AsyncSession, actor: User, role: str | None) -> list[dict]:
    allowed = await permission_service.manageable_roles(s, actor)
    if allowed is None:
        roles = [role] if role else None
    else:
        if not allowed:
            return []
        if role and role not in allowed:
            raise HttpError(403, "Role outside your assigned areas")
        roles = [role] if role else allowed
    return [to_public_user(u) for u in await user_repository.list_users(s, roles)]


async def set_active(s: AsyncSession, actor: User, target_id: str, is_active: bool) -> dict:
    target = await user_repository.find_by_id(s, target_id)
    if not target:
        raise HttpError(404, "User not found")
    if target.id == actor.id:
        raise HttpError(400, "You cannot change your own status")
    if not await permission_service.can_manage_role(s, actor, target.role):
        raise HttpError(403, "You cannot manage this user")
    user_repository.update(target, is_active=is_active)
    await s.commit()
    return to_public_user(target)


async def delete_user(s: AsyncSession, actor: User, target_id: str) -> None:
    """Super admin only (enforced by the route). Permanently deletes the account together with its
    profile, MFA data, assignments, duty, attendance and leave records."""
    target = await user_repository.find_by_id(s, target_id)
    if not target:
        raise HttpError(404, "User not found")
    if target.id == actor.id:
        raise HttpError(400, "You cannot delete your own account")
    if target.role == "super_admin":
        raise HttpError(403, "A super admin account cannot be deleted")
    files = await prescription_repository.stored_names_for_patient(s, target.id) if target.role == "patient" else []
    await user_repository.delete(s, target)
    await s.commit()
    await delete_prescription_files(files)


async def list_doctors(s: AsyncSession, specialty: str | None) -> list[dict]:
    return await doctor_profile_repository.list_active(s, specialty)
