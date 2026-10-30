from fastapi import APIRouter

from . import (
    admin_routes,
    analytics_routes,
    appointment_routes,
    attendance_routes,
    auth_routes,
    department_routes,
    doctor_routes,
    duty_routes,
    leave_routes,
    patient_routes,
    payment_routes,
    prescription_routes,
    user_routes,
    visit_routes,
)

router = APIRouter()

router.include_router(auth_routes.router)
router.include_router(user_routes.router)
router.include_router(admin_routes.router)
router.include_router(department_routes.router)
router.include_router(duty_routes.router)
router.include_router(attendance_routes.router)
router.include_router(leave_routes.router)
router.include_router(patient_routes.router)
router.include_router(appointment_routes.router)
router.include_router(doctor_routes.router)
router.include_router(prescription_routes.router)
router.include_router(visit_routes.router)
router.include_router(analytics_routes.router)
router.include_router(payment_routes.router)
