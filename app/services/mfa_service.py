import pyotp
import segno
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.config.constants import TOTP_WINDOW
from app.models import User
from app.repositories import mfa_recovery_code_repository, user_repository
from app.services import account_lock_service
from app.utils.crypto_util import decrypt, encrypt, generate_recovery_codes, sha256
from app.utils.http_error_util import HttpError
from app.utils.jwt_util import sign_token
from app.utils.password_util import verify_password


def verify_totp(user: User, code: str) -> bool:
    return bool(user.mfa_secret_enc) and pyotp.TOTP(decrypt(user.mfa_secret_enc)).verify(code, valid_window=TOTP_WINDOW)


async def verify_recovery_code(s: AsyncSession, user: User, recovery_code: str) -> bool:
    consumed = await mfa_recovery_code_repository.consume(s, user.id, sha256(recovery_code.strip().lower()))
    await s.commit()
    return consumed


def _setup_payload(user: User, secret: str) -> dict:
    otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=settings.MFA_ISSUER)
    return {
        "secret": secret,
        "otpauthUrl": otpauth_url,
        "qrCodeDataUrl": segno.make(otpauth_url, error="m").png_data_uri(scale=6, border=2),
    }


async def begin_setup(s: AsyncSession, user: User) -> dict:
    """Generates a fresh secret (not active until confirmed via `enable`)."""
    if user.mfa_enabled:
        raise HttpError(409, "MFA is already enabled")
    secret = pyotp.random_base32()
    user_repository.update(user, mfa_secret_enc=encrypt(secret))
    await s.commit()
    return _setup_payload(user, secret)


async def reveal_secret(s: AsyncSession, user: User, password: str, code: str) -> dict:
    """Shows the setup key of an account that already has MFA. Needs the password AND a current code, so
    only someone who can already sign in can see it. Wrong answers count toward the account lockout."""
    account_lock_service.assert_not_locked(user)
    if not user.mfa_enabled or not user.mfa_secret_enc:
        raise HttpError(400, "MFA is not enabled")

    if not (await verify_password(password, user.password_hash) and verify_totp(user, code)):
        await account_lock_service.record_failure(s, user)
        raise HttpError(401, "Incorrect password or code")
    await account_lock_service.reset(s, user)
    return _setup_payload(user, decrypt(user.mfa_secret_enc))


async def enable(s: AsyncSession, user: User, code: str) -> dict:
    if user.mfa_enabled:
        raise HttpError(409, "MFA is already enabled")
    if not user.mfa_secret_enc:
        raise HttpError(400, "Start MFA setup first")
    if not verify_totp(user, code):
        raise HttpError(401, "Invalid MFA code")

    recovery_codes = generate_recovery_codes()
    user_repository.update(user, mfa_enabled=True)
    await mfa_recovery_code_repository.replace_for_user(s, user.id, [sha256(c) for c in recovery_codes])
    await s.commit()
    return {"token": sign_token(user.id, "full"), "recoveryCodes": recovery_codes}


async def disable(s: AsyncSession, user: User, password: str, code: str) -> None:
    if user.role != "patient":
        raise HttpError(403, "MFA is mandatory for staff accounts")
    if not user.mfa_enabled:
        raise HttpError(400, "MFA is not enabled")
    if not await verify_password(password, user.password_hash):
        raise HttpError(401, "Invalid credentials")
    if not verify_totp(user, code):
        raise HttpError(401, "Invalid MFA code")

    user_repository.update(user, mfa_enabled=False, mfa_secret_enc=None)
    await mfa_recovery_code_repository.delete_all_for_user(s, user.id)
    await s.commit()
