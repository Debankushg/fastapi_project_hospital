from typing import Literal

from app.models import enums as e

Role = Literal[tuple(e.ROLES)]  # type: ignore[valid-type]
Specialty = Literal[tuple(e.SPECIALTIES)]  # type: ignore[valid-type]
AdminArea = Literal[tuple(e.ADMIN_AREAS)]  # type: ignore[valid-type]
AttendanceStatus = Literal[tuple(e.ATTENDANCE_STATUSES)]  # type: ignore[valid-type]
LeaveType = Literal[tuple(e.LEAVE_TYPES)]  # type: ignore[valid-type]
LeaveStatus = Literal[tuple(e.LEAVE_STATUSES)]  # type: ignore[valid-type]
AppointmentStatus = Literal[tuple(e.APPOINTMENT_STATUSES)]  # type: ignore[valid-type]
PaymentStatus = Literal[tuple(e.PAYMENT_STATUSES)]  # type: ignore[valid-type]

# mfa_pending : password OK, must submit TOTP/recovery code
# mfa_setup   : password OK, staff account that must enrol MFA before anything else
# full        : fully authenticated
TokenStage = Literal["mfa_pending", "mfa_setup", "full"]
