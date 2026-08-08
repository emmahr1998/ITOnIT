from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    """Company lookups needed for authentication.

    Deliberately NOT built on CompanyScopedRepository: a company is the
    tenant boundary itself, not tenant-owned data - same reasoning as
    RoleRepository staying unscoped.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db, Company)

    def get_by_code(self, company_code: str) -> Company | None:
        """Case-insensitive lookup, since a company code is typed by hand."""
        return self.db.scalar(
            select(Company).where(
                func.lower(Company.company_code) == company_code.strip().lower()
            )
        )
