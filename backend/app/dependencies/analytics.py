from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_company_id
from app.dependencies.database import get_db
from app.services.analytics_service import AnalyticsService


def get_analytics_service(
    db: Session = Depends(get_db), company_id: int = Depends(get_current_company_id)
) -> AnalyticsService:
    return AnalyticsService(db, company_id)
