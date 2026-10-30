from sqlalchemy.ext.asyncio import AsyncSession

from app.config.permissions_config import MFA_MANDATORY_ROLES
from app.models import User
from app.repositories import patient_profile_repository, user_repository
from app.schemas.auth_schema import MfaLoginIn, RegisterIn
from app.services import account_lock_service, mfa_service, permission_service
from app.utils.http_error_util import HttpError
from app.utils.jwt_util import sign_token
from app.utils.mapper_util import to_public_user
from app.utils.password_util import DUMMY_HASH, hash_password, verify_password


async def to_session_user(s: AsyncSession, user: User) -> dict:
    """Public user plus what the UI may offer them (reception access, patient deletion…)."""
    return {**to_public_user(user), "capabilities": await permission_service.capabilities_of(s, user)}


async def register_patient(s: AsyncSession, data: RegisterIn) -> dict:
    user = await user_repository.create(
        s,
        email=data.email,
        full_name=data.full_name,
        phone=data.phone,
        password_hash=await hash_password(data.password),
        role="patient",
    )
    patient_profile_repository.create(
        s,
        user_id=user.id,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        blood_group=data.blood_group,
        address=data.address,
    )
    await s.commit()
    await s.refresh(user)
    return to_public_user(user)


async def login(s: AsyncSession, email: str, password: str) -> dict:
    """Step 1: password check. The returned status tells the client what to do next."""
    user = await user_repository.find_by_email(s, email)
    if not user:
        await verify_password(password, DUMMY_HASH)
        raise HttpError(401, "Invalid credentials")
    account_lock_service.assert_not_locked(user)
    if not await verify_password(password, user.password_hash):
        await account_lock_service.record_failure(s, user)
        raise HttpError(401, "Invalid credentials")
    if not user.is_active:
        raise HttpError(403, "Account is deactivated")

    if user.mfa_enabled:
        return {"status": "mfa_required", "mfaToken": sign_token(user.id, "mfa_pending")}
    if user.role in MFA_MANDATORY_ROLES:
        return {"status": "mfa_setup_required", "setupToken": sign_token(user.id, "mfa_setup")}
    await account_lock_service.reset(s, user)
    return {"status": "authenticated", "token": sign_token(user.id, "full"), "user": await to_session_user(s, user)}


async def verify_mfa_login(s: AsyncSession, user: User, data: MfaLoginIn) -> dict:
    """Step 2: TOTP code or one-time recovery code."""
    account_lock_service.assert_not_locked(user)
    if not user.mfa_enabled:
        raise HttpError(400, "MFA is not enabled")

    if data.code:
        ok = mfa_service.verify_totp(user, data.code)
    elif data.recovery_code:
        ok = await mfa_service.verify_recovery_code(s, user, data.recovery_code)
    else:
        ok = False

    if not ok:
        await account_lock_service.record_failure(s, user)
        raise HttpError(401, "Invalid MFA code")
    await account_lock_service.reset(s, user)
    return {"token": sign_token(user.id, "full"), "user": await to_session_user(s, user)}
