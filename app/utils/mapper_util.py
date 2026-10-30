"""Row → API dict helpers (camelCase keys, like the Node API)."""

from typing import Any

from sqlalchemy import inspect

from app.models import Base, PatientProfile, User


def camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(p.capitalize() for p in rest)


def row(obj: Base) -> dict[str, Any]:
    """Every column of a model instance, camelCased."""
    return {camel(a.key): getattr(obj, a.key) for a in inspect(obj).mapper.column_attrs}


def camelize(d: dict[str, Any]) -> dict[str, Any]:
    return {camel(k): v for k, v in d.items()}


def to_public_user(u: User) -> dict[str, Any]:
    """User fields that are safe to return from the API."""
    return {
        "id": u.id,
        "email": u.email,
        "fullName": u.full_name,
        "phone": u.phone,
        "role": u.role,
        "baseRole": u.base_role,
        "isActive": u.is_active,
        "mfaEnabled": u.mfa_enabled,
        "createdAt": u.created_at,
    }


def to_patient_view(user: User, profile: PatientProfile | None) -> dict[str, Any]:
    """Patient account + profile details as returned to receptionists."""
    return {
        **to_public_user(user),
        "dateOfBirth": profile.date_of_birth if profile else None,
        "gender": profile.gender if profile else None,
        "bloodGroup": profile.blood_group if profile else None,
        "address": profile.address if profile else None,
    }
