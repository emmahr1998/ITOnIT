from app.repositories.base import BaseRepository
from app.repositories.category import CategoryRepository
from app.repositories.comment import CommentRepository
from app.repositories.history import HistoryRepository
from app.repositories.role import RoleRepository
from app.repositories.ticket import TicketRepository
from app.repositories.user import UserRepository

__all__ = [
    "BaseRepository",
    "CategoryRepository",
    "CommentRepository",
    "HistoryRepository",
    "RoleRepository",
    "TicketRepository",
    "UserRepository",
]
