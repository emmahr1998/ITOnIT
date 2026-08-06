from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Reusable CRUD operations shared by every model-specific repository.

    Deliberately has no commit(): the request-scoped session is a unit of
    work, and deciding when to commit belongs to the service layer that
    orchestrates one or more repository calls, not to the repository itself.
    """

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        self.db = db
        self.model = model

    def get_by_id(self, id_: int) -> ModelType | None:
        return self.db.get(self.model, id_)

    def get_all(self) -> list[ModelType]:
        return list(self.db.scalars(select(self.model)).all())

    def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        self.flush()
        self.refresh(obj)
        return obj

    def update(self, obj: ModelType) -> ModelType:
        self.flush()
        self.refresh(obj)
        return obj

    def delete(self, obj: ModelType) -> None:
        self.db.delete(obj)
        self.flush()

    def flush(self) -> None:
        self.db.flush()

    def refresh(self, obj: ModelType) -> None:
        self.db.refresh(obj)


class CompanyScopedRepository(BaseRepository[ModelType], Generic[ModelType]):
    """A BaseRepository whose reads are always confined to one company.

    Every tenant-owned repository (Ticket, Department, Category, Location,
    Priority, Comment, Attachment, History) extends this instead of
    BaseRepository directly, and is always constructed with the requesting
    user's own company_id (see app.dependencies.auth.get_current_company_id)
    - never a client-supplied value. get_by_id/get_all are overridden here
    so the isolation guarantee holds even for a caller that forgets it
    exists; every custom query method a subclass adds (get_by_title,
    get_with_filters, list_for_ticket, ...) must add its own
    `self.model.company_id == self.company_id` predicate too, since this
    base class has no way to see into those bespoke select() statements.

    Returning None/an empty result for a row that exists in another company
    - rather than raising a distinct "wrong company" error - is deliberate:
    the caller's existing "not found" handling (a 404, or a domain
    NotFoundError mapped to one) already does the right thing, and a
    cross-company id is genuinely indistinguishable from one that was never
    a real row at all - the same generic response.

    UserRepository is the one exception: it is NOT built on this class,
    because auth needs to resolve "who is this JWT for" before any company
    is known at all - see UserRepository's own docstring.
    """

    def __init__(self, db: Session, model: type[ModelType], company_id: int) -> None:
        super().__init__(db, model)
        self.company_id = company_id

    def get_by_id(self, id_: int) -> ModelType | None:
        return self.db.scalar(
            select(self.model).where(
                self.model.id == id_, self.model.company_id == self.company_id
            )
        )

    def get_all(self) -> list[ModelType]:
        return list(
            self.db.scalars(
                select(self.model).where(self.model.company_id == self.company_id)
            ).all()
        )
