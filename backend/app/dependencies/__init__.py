from app.dependencies.auth import (
    get_auth_service,
    get_current_active_user,
    get_current_user,
    get_user_repository,
    require_roles,
)
from app.dependencies.category import get_category_repository, get_category_service
from app.dependencies.comment import get_comment_repository, get_comment_service
from app.dependencies.database import get_db
from app.dependencies.history import get_history_repository, get_history_service
from app.dependencies.ticket import (
    get_ticket_repository,
    get_ticket_service,
    get_viewable_ticket,
)

__all__ = [
    "get_db",
    "get_auth_service",
    "get_current_active_user",
    "get_current_user",
    "get_user_repository",
    "require_roles",
    "get_category_repository",
    "get_category_service",
    "get_comment_repository",
    "get_comment_service",
    "get_history_repository",
    "get_history_service",
    "get_ticket_repository",
    "get_ticket_service",
    "get_viewable_ticket",
]
