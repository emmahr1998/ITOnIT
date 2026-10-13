from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.location import Location
from app.repositories.location import LocationRepository
from app.schemas.location import LocationCreate, LocationUpdate


class LocationNotFoundError(Exception):
    """Raised when a location id does not exist."""


class LocationTitleConflictError(Exception):
    """Raised when a location title already exists (case-insensitive)."""


class LocationService:
    """Owns location business rules: title uniqueness.

    Also owns the transaction boundary for writes - repositories only
    flush (see BaseRepository), so commit()/rollback() happen here. Same
    shape as DepartmentService/PriorityService; there is no delete method
    because locations are deactivated (is_active=False) instead of
    deleted, so a ticket already referencing one keeps a valid reference.

    company_id always comes from the authenticated caller (see
    app.dependencies.auth.get_current_company_id), never from client input.
    """

    def __init__(
        self,
        db: Session,
        company_id: int,
        location_repository: LocationRepository | None = None,
    ) -> None:
        self._db = db
        self._company_id = company_id
        self._location_repository = (
            location_repository
            if location_repository is not None
            else LocationRepository(db, company_id)
        )

    def list_locations(self) -> list[Location]:
        return self._location_repository.get_all()

    def get_location(self, location_id: int) -> Location:
        location = self._location_repository.get_by_id(location_id)
        if location is None:
            raise LocationNotFoundError
        return location

    def create_location(self, payload: LocationCreate) -> Location:
        if self._location_repository.get_by_title(payload.title) is not None:
            raise LocationTitleConflictError

        location = Location(company_id=self._company_id, title=payload.title, is_active=True)
        try:
            self._location_repository.create(location)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise LocationTitleConflictError from exc
        return location

    def update_location(self, location_id: int, payload: LocationUpdate) -> Location:
        location = self.get_location(location_id)

        if payload.title is not None:
            duplicate = self._location_repository.get_by_title(payload.title)
            if duplicate is not None and duplicate.id != location_id:
                raise LocationTitleConflictError
            location.title = payload.title

        if payload.is_active is not None:
            location.is_active = payload.is_active

        try:
            self._location_repository.update(location)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise LocationTitleConflictError from exc
        return location
