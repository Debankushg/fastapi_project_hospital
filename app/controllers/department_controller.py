from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import department_service
from app.utils.mapper_util import to_public_user
from app.utils.response_util import ok


async def overview(s: AsyncSession, actor: User):
    return ok(
        {
            "departments": await department_service.overview(s, actor),
            "unplacedAdmins": await department_service.admins_without_profession(s, actor),
        }
    )


async def staff(s: AsyncSession, actor: User):
    return ok({"staff": [to_public_user(m) for m in await department_service.list_staff(s, actor)]})
