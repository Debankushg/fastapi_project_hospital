# Which admin work area governs each manageable role. Admins/super admins are never listed.
ROLE_AREA: dict[str, str] = {
    "doctor": "doctor_management",
    "receptionist": "reception_management",
    "pathologist": "pathology_management",
    "accounts": "accounts_management",
    "patient": "patient_management",
}

# Roles that must have MFA enrolled before they can use the system.
MFA_MANDATORY_ROLES = ["super_admin", "admin", "doctor", "receptionist", "pathologist", "accounts"]

# Reverse of ROLE_AREA: the role whose members belong to each work area.
AREA_ROLE: dict[str, str] = {area: role for role, area in ROLE_AREA.items()}
