from app.repositories.attachment import AttachmentRepository
from app.repositories.base import BaseRepository
from app.repositories.category import CategoryRepository
from app.repositories.comment import CommentRepository
from app.repositories.company import CompanyRepository
from app.repositories.department import DepartmentRepository
from app.repositories.history import HistoryRepository
from app.repositories.location import LocationRepository
from app.repositories.priority import PriorityRepository
from app.repositories.role import RoleRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository

__all__ = [
    "AttachmentRepository",
    "BaseRepository",
    "CategoryRepository",
    "CommentRepository",
    "CompanyRepository",
    "DepartmentRepository",
    "HistoryRepository",
    "LocationRepository",
    "PriorityRepository",
    "RoleRepository",
    "TicketRepository",
    "UserRepository",
]
