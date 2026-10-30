from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.controllers import consultation_controller
from app.db import Session
from app.middleware.auth_middleware import Authed, CurrentUser
from app.middleware.rbac_middleware import require_checked_visits_access
from app.schemas.consultation_schema import CheckedVisitsQuery

router = APIRouter(prefix="/visits", tags=["Visits"], dependencies=[Authed, Depends(require_checked_visits_access)])


# Patients a doctor has checked: shared with reception and accounts.
@router.get("/checked")
async def list_checked(q: Annotated[CheckedVisitsQuery, Query()], user: CurrentUser, s: Session):
    return await consultation_controller.list_checked(s, user, q)
