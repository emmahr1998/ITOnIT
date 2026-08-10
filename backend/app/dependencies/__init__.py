from app.dependencies.attachment import get_attachment_repository, get_attachment_service
from app.dependencies.auth import (
    get_auth_service,
    get_current_active_user,
    get_current_company_id,
    get_current_user,
    get_user_repository,
    require_roles,
)
from app.dependencies.category import get_category_repository, get_category_service
from app.dependencies.comment import get_comment_repository, get_comment_service
from app.dependencies.company import get_company_repository, get_company_service
from app.dependencies.database import get_db
from app.dependencies.department import get_department_repository, get_department_service
from app.dependencies.history import get_history_repository, get_history_service
from app.dependencies.inventory_category import (
    get_inventory_category_repository,
    get_inventory_category_service,
)
from app.dependencies.inventory_item import (
    get_inventory_item_repository,
    get_inventory_item_service,
)
from app.dependencies.location import get_location_repository, get_location_service
from app.dependencies.priority import get_priority_repository, get_priority_service
from app.dependencies.ticket import (
    get_ticket_repository,
    get_ticket_service,
    get_viewable_ticket,
)
from app.dependencies.user import get_user_service

__all__ = [
    "get_db",
    "get_auth_service",
    "get_current_active_user",
    "get_current_company_id",
    "get_current_user",
    "get_user_repository",
    "get_user_service",
    "require_roles",
    "get_category_repository",
    "get_category_service",
    "get_comment_repository",
    "get_comment_service",
    "get_company_repository",
    "get_company_service",
    "get_department_repository",
    "get_department_service",
    "get_history_repository",
    "get_history_service",
    "get_inventory_category_repository",
    "get_inventory_category_service",
    "get_inventory_item_repository",
    "get_inventory_item_service",
    "get_location_repository",
    "get_location_service",
    "get_priority_repository",
    "get_priority_service",
    "get_ticket_repository",
    "get_ticket_service",
    "get_viewable_ticket",
    "get_attachment_repository",
    "get_attachment_service",
]
