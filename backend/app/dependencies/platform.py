from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.services.platform_service import PlatformService


def get_platform_service(db: Session = Depends(get_db)) -> PlatformService:
    """Deliberately has no company_id dependency at all - unlike every
    tenant-scoped get_x_service factory in this package, PlatformService is
    never scoped to a caller's own company (a System Administrator has
    none). Do not add a get_current_company_id parameter here."""
    return PlatformService(db)
