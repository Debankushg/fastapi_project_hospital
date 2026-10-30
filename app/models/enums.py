from sqlalchemy import Enum

ROLES = ["super_admin", "admin", "doctor", "receptionist", "pathologist", "accounts", "patient"]
SPECIALTIES = ["opd", "gynecologist", "cardiologist", "ent", "dermatologist", "pediatrician"]
# Work areas a super admin can hand to an admin.
ADMIN_AREAS = [
    "doctor_management",
    "reception_management",
    "pathology_management",
    "accounts_management",
    "patient_management",
]
ATTENDANCE_STATUSES = ["present", "absent", "late", "half_day", "on_leave"]
LEAVE_TYPES = ["sick", "casual", "annual", "unpaid", "other"]
LEAVE_STATUSES = ["pending", "approved", "rejected"]
APPOINTMENT_STATUSES = ["requested", "approved", "checked", "rejected", "cancelled"]
PAYMENT_STATUSES = ["pending", "paid", "expired"]

# Enum type names match the Drizzle schema, so both backends can share one database.
role_enum = Enum(*ROLES, name="role")
specialty_enum = Enum(*SPECIALTIES, name="specialty")
admin_area_enum = Enum(*ADMIN_AREAS, name="admin_area")
attendance_status_enum = Enum(*ATTENDANCE_STATUSES, name="attendance_status")
leave_type_enum = Enum(*LEAVE_TYPES, name="leave_type")
leave_status_enum = Enum(*LEAVE_STATUSES, name="leave_status")
appointment_status_enum = Enum(*APPOINTMENT_STATUSES, name="appointment_status")
payment_status_enum = Enum(*PAYMENT_STATUSES, name="payment_status")
