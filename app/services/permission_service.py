from sqlalchemy.ext.asyncio import AsyncSession

from app.config.permissions_config import ROLE_AREA
from app.models import User
from app.repositories import admin_assignment_repository, user_repository
from app.utils.http_error_util import HttpError


async def manageable_roles(s: AsyncSession, actor: User) -> list[str] | None:
    """Roles the actor may manage. `None` means unrestricted (super admin).
    Admins get only the roles covered by the work areas assigned to them."""
    if actor.role == "super_admin":
        return None
    if actor.role != "admin":
        return []
    areas = {a.area for a in await admin_assignment_repository.list_by_admin(s, actor.id)}
    return [role for role, area in ROLE_AREA.items() if area in areas]


async def can_manage_role(s: AsyncSession, actor: User, target: str) -> bool:
    if actor.role == "super_admin":
        return True
    if actor.role != "admin":
        return False
    area = ROLE_AREA.get(target)
    if not area:  # admins can never manage admin / super_admin
        return False
    return await admin_assignment_repository.has_area(s, actor.id, area)


async def manageable_staff_roles(s: AsyncSession, actor: User) -> list[str]:
    """Staff roles (everyone except patients) the actor may manage. Super admin also covers admins."""
    if actor.role == "super_admin":
        return ["admin", "doctor", "receptionist", "pathologist", "accounts"]
    return [r for r in (await manageable_roles(s, actor) or []) if r != "patient"]


async def assert_can_manage_staff(s: AsyncSession, actor: User, user_id: str) -> User:
    """Loads the target and throws unless the actor may manage this staff member's duty/attendance/leave."""
    target = await user_repository.find_by_id(s, user_id)
    if not target:
        raise HttpError(404, "User not found")
    if target.role in ("patient", "super_admin"):
        raise HttpError(400, "This user is not a staff member")
    if not await can_manage_role(s, actor, target.role):
        raise HttpError(403, "This staff member is outside your assigned areas")
    return target


async def can_use_reception(s: AsyncSession, actor: User) -> bool:
    """Reception work (patient list, booking, assigning doctors): receptionists, the super admin, and admins
    who work as a receptionist (`base_role`) or are assigned Reception management."""
    if actor.role in ("receptionist", "super_admin"):
        return True
    if actor.role != "admin":
        return False
    if actor.base_role == "receptionist":
        return True
    return await admin_assignment_repository.has_area(s, actor.id, "reception_management")


async def can_delete_patients(s: AsyncSession, actor: User) -> bool:
    """Deleting patients: the super admin and the admin of the reception department only."""
    if actor.role == "super_admin":
        return True
    return actor.role == "admin" and await admin_assignment_repository.has_area(s, actor.id, "reception_management")


def is_doctor(actor: User) -> bool:
    """Seeing patients as a doctor: doctors and admins who work as a doctor."""
    return actor.role == "doctor" or (actor.role == "admin" and actor.base_role == "doctor")


async def can_use_accounts(s: AsyncSession, actor: User) -> bool:
    """Accounts work: accounts staff, admins who work as accounts / are assigned Accounts management, super admin."""
    if actor.role in ("accounts", "super_admin"):
        return True
    if actor.role != "admin":
        return False
    if actor.base_role == "accounts":
        return True
    return await admin_assignment_repository.has_area(s, actor.id, "accounts_management")


async def can_take_payments(s: AsyncSession, actor: User) -> bool:
    """Taking payments (Stripe): accounts staff, the super admin, and admins assigned the Accounts department.
    Narrower than can_use_accounts: an admin who merely works as accounts (`base_role`) is not enough."""
    if actor.role in ("accounts", "super_admin"):
        return True
    return actor.role == "admin" and await admin_assignment_repository.has_area(s, actor.id, "accounts_management")


async def can_view_checked_visits(s: AsyncSession, actor: User) -> bool:
    """The list of patients a doctor has checked is shared with reception and accounts."""
    return await can_use_reception(s, actor) or await can_use_accounts(s, actor)


async def capabilities_of(s: AsyncSession, actor: User) -> dict:
    """What the UI may offer this user (computed here so the rules live in one place)."""
    reception = await can_use_reception(s, actor)
    accounts = await can_use_accounts(s, actor)
    return {
        "reception": reception,
        "editPatients": reception,
        "deletePatients": await can_delete_patients(s, actor),
        "doctor": is_doctor(actor),
        "accounts": accounts,
        "payments": await can_take_payments(s, actor),
        "viewChecked": reception or accounts,
    }
