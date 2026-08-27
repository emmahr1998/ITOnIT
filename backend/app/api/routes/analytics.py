from fastapi import APIRouter, Depends, HTTPException, status

from app.core.time import InvalidCompanyTimezoneError
from app.dependencies import get_analytics_service, require_roles
from app.models.user import User
from app.schemas.analytics import InventoryAnalyticsResponse, TicketAnalyticsResponse
from app.schemas.response import DataResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Every role that can view tickets at all can view analytics over the
# tickets they're allowed to see - System Administrator (platform-level,
# not company-scoped) is out of scope, matching every other company-scoped
# endpoint in this codebase.
_TICKET_VIEW_ROLES = ("Employee", "Technician", "Company Administrator")

# Employee has no inventory access anywhere in this codebase (see
# inventory_items.py's own _VIEW_ROLES) - inventory analytics is no
# exception. System Administrator remains out of scope, same as above.
_INVENTORY_VIEW_ROLES = ("Technician", "Company Administrator")


@router.get("/tickets", response_model=DataResponse[TicketAnalyticsResponse])
def get_ticket_analytics(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: User = Depends(require_roles(*_TICKET_VIEW_ROLES)),
) -> DataResponse[TicketAnalyticsResponse]:
    """Role scoping (Company Administrator: company-wide, Technician:
    assigned-only, Employee: created-by-only) is entirely
    AnalyticsService's decision, via the same TicketService.resolve_ownership_scope
    every other ticket-scoped read uses - this route does not recreate
    that logic, and never accepts company_id from the client (company_id
    comes from get_current_company_id via get_analytics_service, derived
    from the authenticated user's own row).
    """
    try:
        analytics = analytics_service.get_ticket_analytics(current_user)
    except InvalidCompanyTimezoneError as exc:
        # A genuine data-integrity problem on the company record, not
        # something the caller can fix by resubmitting - reported as a
        # clear 500 without echoing the invalid stored value or any
        # internal detail back to the client.
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "This company's timezone setting is invalid. Contact support.",
        ) from exc
    return DataResponse(
        data=TicketAnalyticsResponse.from_domain(analytics),
        msg="Ticket analytics fetched successfully",
    )


@router.get("/inventory", response_model=DataResponse[InventoryAnalyticsResponse])
def get_inventory_analytics(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: User = Depends(require_roles(*_INVENTORY_VIEW_ROLES)),
) -> DataResponse[InventoryAnalyticsResponse]:
    """Which fields come back (the full company-wide picture vs. only
    reserved_for_my_tickets_count) is entirely
    AnalyticsService.get_inventory_analytics's decision, based on
    current_user.role - this route does not decide or recreate that
    logic, and never accepts company_id from the client (see
    get_ticket_analytics's docstring for the identical rationale).
    Employee is refused before reaching this function at all
    (require_roles), matching Employee having no inventory access
    anywhere else in this codebase.
    """
    analytics = analytics_service.get_inventory_analytics(current_user)
    return DataResponse(
        data=InventoryAnalyticsResponse.from_domain(analytics),
        msg="Inventory analytics fetched successfully",
    )
