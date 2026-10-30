from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session
from app.middleware.auth_middleware import CurrentUser
from app.models import User
from app.services import permission_service
from app.utils.http_error_util import HttpError

_FORBIDDEN = "You do not have permission to perform this action"


def require_role(*roles: str):
    """Allows the request only if the authenticated user has one of the given roles."""

    async def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HttpError(403, _FORBIDDEN)
        return user

    return dependency


def _require(check: Callable[[AsyncSession, User], Awaitable[bool]]):
    async def dependency(user: CurrentUser, s: Session) -> User:
        if not await check(s, user):
            raise HttpError(403, _FORBIDDEN)
        return user

    return dependency


async def _patient_or_reception(s: AsyncSession, u: User) -> bool:
    return u.role == "patient" or await permission_service.can_use_reception(s, u)


async def _doctor(_: AsyncSession, u: User) -> bool:
    return permission_service.is_doctor(u)


async def _doctor_insights(_: AsyncSession, u: User) -> bool:
    return permission_service.is_doctor(u) or u.role == "super_admin"


# Reception access: receptionists, reception-role admins, Reception-management admins and the super admin.
require_reception = _require(permission_service.can_use_reception)
# Patients (for themselves) or reception staff.
require_patient_or_reception = _require(_patient_or_reception)
# Only the super admin and the admin of the reception department.
require_reception_admin = _require(permission_service.can_delete_patients)
# Doctors and admins who work as a doctor.
require_doctor = _require(_doctor)
# Reception or accounts: may see the list of checked patients.
require_checked_visits_access = _require(permission_service.can_view_checked_visits)
# Doctor workload chart: doctors (and admins working as a doctor) and the super admin.
require_doctor_insights = _require(_doctor_insights)
# Taking payments: accounts staff, Accounts-department admins and the super admin.
require_payments = _require(permission_service.can_take_payments)

# Ready-made router/route dependencies
RequireSuperAdmin = Depends(require_role("super_admin"))
RequireAdmin = Depends(require_role("super_admin", "admin"))
