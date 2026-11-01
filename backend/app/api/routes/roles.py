from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.roles import COMPANY_ADMINISTRATOR_ROLE, COMPANY_ROLE_NAMES
from app.dependencies import get_current_company_id, require_roles
from app.dependencies.database import get_db
from app.models.user import User
from app.repositories.role import RoleRepository
from app.schemas.response import DataResponse
from app.schemas.role import RoleResponse

router = APIRouter(prefix="/roles", tags=["Roles"])


def get_role_repository(db: Session = Depends(get_db)) -> RoleRepository:
    return RoleRepository(db)


@router.get("", response_model=DataResponse[list[RoleResponse]])
def list_assignable_roles(
    role_repository: RoleRepository = Depends(get_role_repository),
    _current_user: User = Depends(require_roles(COMPANY_ADMINISTRATOR_ROLE)),
    _company_id: int = Depends(get_current_company_id),
) -> DataResponse[list[RoleResponse]]:
    """The roles a Company Administrator may assign (Employee, Technician,
    Company Administrator), with their real ids. System Administrator is
    never listed - UserService rejects it on POST/PATCH /users as well."""
    roles = role_repository.get_by_names(COMPANY_ROLE_NAMES)
    return DataResponse(
        data=[RoleResponse.model_validate(r) for r in roles],
        msg=f"Fetched {len(roles)} roles",
    )
