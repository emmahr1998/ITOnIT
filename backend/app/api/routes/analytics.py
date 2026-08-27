from fastapi import APIRouter, Depends, HTTPException, status

from app.core.time import InvalidCompanyTimezoneError
from app.dependencies import get_analytics_service, require_roles
from app.models.user import User
from app.schemas.analytics import TicketAnalyticsResponse
from app.schemas.response import DataResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Every role that can view tickets at all can view analytics over the
# tickets they're allowed to see - System Administrator (platform-level,
# not company-scoped) is out of scope, matching every other company-scoped
# endpoint in this codebase.
_VIEW_ROLES = ("Employee", "Technician", "Company Administrator")


@router.get("/tickets", response_model=DataResponse[TicketAnalyticsResponse])
def get_ticket_analytics(
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    current_user: User = Depends(require_roles(*_VIEW_ROLES)),
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
