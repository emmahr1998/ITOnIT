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
